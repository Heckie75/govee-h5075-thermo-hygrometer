#!/usr/bin/python3
import argparse
import asyncio
import json
import math
import os
import re
import struct
import sys
from datetime import datetime, timedelta

from bleak import AdvertisementData, BleakClient, BleakScanner, BLEDevice


class MyLogger():

    LEVELS = {
        "DEBUG": 0,
        "INFO": 1,
        "WARN": 2,
        "ERROR": 3
    }

    NAMES = ["DEBUG", "INFO", "WARN", "ERROR"]

    def __init__(self, level: int) -> None:

        self.level = level

    def error(self, s: str):

        self.log(MyLogger.LEVELS["ERROR"], s)

    def warning(self, s: str):

        self.log(MyLogger.LEVELS["WARN"], s)

    def info(self, s: str):

        self.log(MyLogger.LEVELS["INFO"], s)

    def debug(self, s: str):

        self.log(MyLogger.LEVELS["DEBUG"], s)

    def log(self, level: int, s: str):

        if level >= self.level:
            print(f"{MyLogger.NAMES[level]}\t{s}", file=sys.stderr, flush=True)

    @staticmethod
    def hexstr(ba: bytearray) -> str:

        return " ".join([("0" + hex(b).replace("0x", ""))[-2:] for b in ba])


LOGGER = MyLogger(level=MyLogger.LEVELS["WARN"])


class Measurement():

    def __init__(self, timestamp: datetime, temperatureC: float, relHumidity: float) -> None:

        self.timestamp: datetime = timestamp
        self.temperatureC: float = temperatureC
        self.relHumidity: float = relHumidity

        z1 = (7.45 * self.temperatureC) / (235 + self.temperatureC)
        es = 6.1 * math.exp(z1*2.3025851)
        e = es * self.relHumidity / 100.0
        z2 = e / 6.1

        # absolute humidity / g/m3
        self.absHumidity: float = round(
            (216.7 * e) / (273.15 + self.temperatureC) * 10) / 10.0

        z3 = 0.434292289 * math.log(z2)
        self.dewPointC: float = int((235 * z3) / (7.45 - z3) * 10) / 10.0
        self.steamPressure: float = int(e * 10) / 10.0

        self.temperatureF: float = self.temperatureC * 9.0/5.0 + 32
        self.dewPointF: float = self.dewPointC * 9.0/5.0 + 32

    @staticmethod
    def from_bytes(bytes: bytearray, timestamp: datetime = None, from_device=False) -> 'Measurement':

        if not timestamp:
            timestamp = datetime.now()

        if len(bytes) == 4 and not from_device:
            temperatureC, relHumidity = struct.unpack(">hh", bytes)
            temperatureC /= 100
            relHumidity /= 100

        elif len(bytes) == 4 and from_device:
            temperatureC, relHumidity = struct.unpack("<hh", bytes)
            temperatureC /= 100
            relHumidity /= 100

        elif len(bytes) == 3:

            raw = struct.unpack(">I", bytes)[0]
            if raw & 0x800000:
                is_negative = True
                raw = raw ^ 0x800000
            else:
                is_negative = False

            temperatureC = int(raw / 1000) / 10
            if is_negative:
                temperatureC = 0 - temperatureC

            relHumidity = (raw % 1000) / 10

        else:
            return None

        return Measurement(timestamp=timestamp, temperatureC=temperatureC, relHumidity=relHumidity)

    def __str__(self) -> str:

        return (
            f"Timestamp:          "
            f"{self.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
            f"Temperature:        "
            f"{self.temperatureC:.1f} °C / {self.temperatureF:.1f} °F\n"
            f"Dew point:          "
            f"{self.dewPointC:.1f} °C / {self.dewPointF:.1f} °F\n"
            f"Rel. humidity:      {self.relHumidity:.1f} %\n"
            f"Abs. humidity:      {self.absHumidity:.1f} g/m³\n"
            f"Steam pressure:     {self.steamPressure:.1f} mbar"
        )

    def to_dict(self) -> dict:

        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M"),
            "temperatureC": round(self.temperatureC, 1),
            "temperatureF": round(self.temperatureF, 1),
            "relHumidity": round(self.relHumidity, 1),
            "absHumidity": round(self.absHumidity, 1),
            "dewPointC": round(self.dewPointC, 1),
            "dewPointF": round(self.dewPointF, 1),
            "steamPressure": round(self.steamPressure, 1)
        }


class Alarm():

    def __init__(self, active: bool, lower: float, upper: float):
        self.active: bool = active
        self.lower: float = lower
        self.upper: float = upper

    @staticmethod
    def from_bytes(bytes: bytearray) -> 'Alarm':

        active, lower, upper = struct.unpack("<?hh", bytes)
        return Alarm(active=active, lower=lower/100, upper=upper/100)

    def to_bytes(self) -> bytearray:

        return None

    def __str__(self):

        return "%s, lower limit=%.1f, upper limit=%.1f" % ("active" if self.active else "inactive", self.lower, self.upper)

    def to_dict(self) -> dict:

        return {
            "active": self.active,
            "lower": self.lower,
            "upper": self.upper
        }


class DataControl():

    DATA_CONTROL_IDLE = 0
    DATA_CONTROL_WAIT = 1
    DATA_CONTROL_STARTED = 2
    DATA_CONTROL_COMPLETE = 3
    DATA_CONTROL_INCOMPLETE = -1

    def __init__(self, expected_msg: int) -> None:

        self.timestamp: datetime = datetime.now()
        self.status: int = DataControl.DATA_CONTROL_IDLE
        self.expected_msg: int = expected_msg
        self.counted_msg: int = 0
        self.received_msg: int = 0
        self.measurements: 'list[Measurement]' = list()

    def count(self) -> None:

        self.counted_msg += 1


class MacAndSerial():

    def __init__(self, mac: str, serial: int):

        self.mac: str = mac
        self.serial: int = serial

    @staticmethod
    def from_bytes(bytes: bytearray) -> 'MacAndSerial':

        return None

    def __str__(self):

        return f"MacAndSerial: {self.mac}, {self.serial}"

    def to_dict(self) -> dict:

        return {
            "mac": self.mac,
            "serial": self.serial
        }


class GoveeThermometerHygrometer(BleakClient):

    MAC_PREFIX = "A4:C1:38:"

    UUID_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
    UUID_DEVICE = "494e5445-4c4c-495f-524f-434b535f2011"
    UUID_COMMAND = "494e5445-4c4c-495f-524f-434b535f2012"
    UUID_DATA = "494e5445-4c4c-495f-524f-434b535f2013"

    REQUEST_CURRENT_MEASUREMENT = bytearray([0xaa, 0x01])
    REQUEST_CURRENT_MEASUREMENT2 = bytearray([0xaa, 0x0a])

    REQUEST_ALARM_HUMIDTY = bytearray([0xaa, 0x03])
    REQUEST_ALARM_TEMPERATURE = bytearray([0xaa, 0x04])
    REQUEST_CALIBRATION_HUMIDTY = bytearray([0xaa, 0x06])
    REQUEST_CALIBRATION_TEMPERATURE = bytearray([0xaa, 0x07])
    REQUEST_BATTERY_LEVEL = bytearray([0xaa, 0x08])
    REQUEST_MAC_AND_SERIAL = bytearray([0xaa, 0x0c])
    REQUEST_HARDWARE = bytearray([0xaa, 0x0d])
    REQUEST_FIRMWARE = bytearray([0xaa, 0x0e])

    SEND_RECORDS_TX_REQUEST = bytearray([0x33, 0x01])
    SEND_ALARM_HUMIDTY = bytearray([0x33, 0x03])
    SEND_ALARM_TEMPERATURE = bytearray([0x33, 0x04])
    SEND_CALIBRATION_HUMIDTY = bytearray([0x33, 0x06])
    SEND_CALIBRATION_TEMPERATURE = bytearray([0x33, 0x07])

    RECORDS_TX_COMPLETED = bytearray([0xee, 0x01])

    def __init__(self, address) -> None:

        super().__init__(address, timeout=30.0)

        self.name: str = None
        self.manufacturer: str = None
        self.model: str = None
        self.hardware: str = None
        self.firmware: str = None
        self.macAndSerial: MacAndSerial = None
        self.batteryLevel: int = None

        self.humidityAlarm: Alarm = None
        self.temperatureAlarm: Alarm = None
        self.humidityCalibration: float = 0
        self.temperatureCalibration: float = 0
        self.measurement: Measurement = None

        self._data_control: DataControl = None

    async def connect(self) -> None:

        async def notification_handler_device(device: BLEDevice, bytes: bytearray) -> None:

            LOGGER.debug(f"{self.address}: <<< received notification with device data("
                         f"{MyLogger.hexstr(bytes)})")

            if bytes[0:2] == GoveeThermometerHygrometer.REQUEST_ALARM_HUMIDTY:
                self.humidityAlarm = Alarm.from_bytes(bytes[2:7])
                LOGGER.info(f'{self.address}: received configuration for humidity alarm: '
                            f'{str(self.humidityAlarm)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_ALARM_TEMPERATURE:
                self.temperatureAlarm = Alarm.from_bytes(bytes[2:7])
                LOGGER.info(f'{self.address}: received configuration for temperature alarm: '
                            f'{str(self.temperatureAlarm)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_CALIBRATION_HUMIDTY:

                self.humidityCalibration = struct.unpack(
                    "<h", bytes[2:4])[0] / 100
                LOGGER.info(f'{self.address}: received configuration for humidity calibration: '
                            f'{self.humidityCalibration:.1f} %')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_CALIBRATION_TEMPERATURE:
                self.temperatureCalibration = struct.unpack(
                    "<h", bytes[2:4])[0] / 100
                LOGGER.info(f'{self.address}: received configuration for temperature calibration: '
                            f'{self.temperatureCalibration:.1f} °C')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_BATTERY_LEVEL:
                self.batteryLevel = bytes[2]
                LOGGER.info(f'{self.address}: received battery level: '
                            f'{self.batteryLevel} %')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT2:

                self.measurement = Measurement.from_bytes(
                    bytes=bytes[2:6], from_device=True)
                LOGGER.info(f'{self.address}: received current measurement:\n'
                            f'{str(self.measurement)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_MAC_AND_SERIAL:
                self.macAndSerial = MacAndSerial.from_bytes(bytes[2:10])
                LOGGER.info(f'{self.address}: received mac address and serial: '
                            f'{str(self.macAndSerial)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_HARDWARE:
                self.hardware = bytes[2:9].decode()
                LOGGER.info(f'{self.address}: received hardware version: '
                            f'{self.hardware}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_FIRMWARE:
                self.firmware = bytes[2:9].decode()
                LOGGER.info(f'{self.address}: received firmware version: '
                            f'{self.firmware}')

        async def notification_handler_data(device: BLEDevice, bytes: bytearray) -> None:

            LOGGER.debug(f"{self.address}: <<< received notification with measurement data ("
                         f"{MyLogger.hexstr(bytes)})")

            if not self._data_control:
                return

            for i in range(6):
                minutes_back = struct.unpack(">H", bytes[0:2])[0]
                if bytes[2 + 3 * i] == 0xff:
                    continue

                timestamp = self._data_control.timestamp - \
                    timedelta(minutes=minutes_back - i)
                _ba = bytearray([0])
                _ba.extend(bytes[2 + 3 * i:5 + 3 * i])
                temperatureC, relHumidity = GoveeThermometerHygrometer.decode_measurement(
                    bytes=_ba)
                LOGGER.debug(f"{self.address}: Decoded measurement data("
                             f"{MyLogger.hexstr(_ba)}) is temperature={temperatureC}°C, humidity={relHumidity}%")
                self._data_control.measurements.append(Measurement(
                    timestamp=timestamp, temperatureC=temperatureC, relHumidity=relHumidity))

            self._data_control.count()

        async def notification_handler_command(device: BLEDevice, bytes: bytearray) -> None:

            LOGGER.debug(f"{self.address}: <<< received notification after command ("
                         f"{MyLogger.hexstr(bytes)})")

            if bytes[0:2] == GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT:

                self.measurement = Measurement.from_bytes(bytes=bytes[2:6])
                self.batteryLevel = bytes[6]
                LOGGER.info(f'{self.address}: received current measurement and battery level:\n'
                            f'{str(self.measurement)}\nBattery level:      {self.batteryLevel} %')

            elif bytes[0:2] == GoveeThermometerHygrometer.SEND_RECORDS_TX_REQUEST and self._data_control:

                LOGGER.info(f"{self.address}: Data transmission starts")
                self._data_control.status = DataControl.DATA_CONTROL_STARTED

            elif bytes[0:2] == GoveeThermometerHygrometer.RECORDS_TX_COMPLETED and self._data_control:
                self._data_control.received_msg = struct.unpack(">H", bytes[2:4])[
                    0]
                if self._data_control.received_msg == self._data_control.counted_msg:
                    LOGGER.info(
                        f"{self.address}: Data transmission completed")
                    self._data_control.status = DataControl.DATA_CONTROL_COMPLETE
                else:
                    LOGGER.info(f"{self.address}: Data transmission aborted")
                    self._data_control.status = DataControl.DATA_CONTROL_INCOMPLETE

        LOGGER.info(f"{self.address}: Request to connect")
        await super().connect()

        if self.is_connected:
            LOGGER.info(f"{self.address}: Successfully connected")
            LOGGER.debug(f'{self.address}: Start listening for notifications for device data on UUID '
                         f'{self.UUID_DEVICE}')
            await self.start_notify(self.UUID_DEVICE, callback=notification_handler_device)
            LOGGER.debug(f'{self.address}: Start listening for notifications for commands on UUID '
                         f'{self.UUID_COMMAND}')
            await self.start_notify(self.UUID_COMMAND, callback=notification_handler_command)
            LOGGER.debug(f'{self.address}: Start listening for notifications for data on UUID '
                         f'{self.UUID_DATA}')
            await self.start_notify(self.UUID_DATA, callback=notification_handler_data)
            await asyncio.sleep(.2)
        else:
            LOGGER.error(f"{self.address}: Connecting has failed")

    async def disconnect(self) -> None:

        LOGGER.info(f"{self.address}: Request to disconnect")
        if self.is_connected:
            await super().disconnect()
            LOGGER.info(f"{self.address}: Successfully disconnected")

    async def write_gatt_char_command(self, uuid: str, command: bytearray, params: bytearray = None) -> None:

        if not uuid or not command:
            return None

        _bytearray = bytearray(command)
        if params:
            _bytearray.extend(params)

        if len(_bytearray) < 20:
            _bytearray.extend([0] * (19 - len(_bytearray)))
            _checksum = 0
            for _b in _bytearray:
                _checksum ^= _b

            _bytearray.append(_checksum)

        LOGGER.debug("%s: >>> write_gatt_char(%s, %s)" %
                     (self.address, uuid, MyLogger.hexstr(_bytearray)))

        await self.write_gatt_char(uuid, _bytearray, response=True)

    async def read_gatt_char_as_str(self, uuid: str) -> str:

        if not uuid:
            return None

        LOGGER.debug(f"{self.address}: >>> read_gatt_char("
                     f"{GoveeThermometerHygrometer.UUID_NAME})")
        bytes = await super().read_gatt_char(GoveeThermometerHygrometer.UUID_NAME)

        if not bytes:
            LOGGER.debug(f"{self.address}: <<< no response data received")
            return None
        else:
            LOGGER.debug(
                f"{self.address}: <<< response data({MyLogger.hexstr(bytes)})")
            return bytes.decode().replace("\u0000", "")

    async def requestRecordedData(self, start: int, end: int) -> 'list[Measurement]':

        LOGGER.info(f"{self.address}: request recorded measurements from "
                    f"{start} to {end} minutes in the past")

        self._data_control = DataControl(
            expected_msg=math.ceil((start - end + 1) / 6))
        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_COMMAND, command=GoveeThermometerHygrometer.SEND_RECORDS_TX_REQUEST, params=[start >> 8, start & 0xff, end >> 8, end & 0xff])

        i = 0
        while i < 600 and (self._data_control.status not in [DataControl.DATA_CONTROL_COMPLETE, DataControl.DATA_CONTROL_INCOMPLETE]):
            await asyncio.sleep(.1)
            i += 1

        measurements = self._data_control.measurements
        self._data_control = None
        return measurements

    async def requestDeviceName(self) -> str:

        LOGGER.info(f"{self.address}: request device name")

        name = await self.read_gatt_char_as_str(
            uuid=GoveeThermometerHygrometer.UUID_NAME)
        LOGGER.info(f"{self.address}: received device name: {name}")

        self.name = name or self.name
        self.manufacturer = name[0:2]
        self.model = name[2:7]
        return self.name

    async def requestHumidityAlarm(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for humidity alarm")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_ALARM_HUMIDTY)

    async def requestTemperatureAlarm(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for temperature alarm")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_ALARM_TEMPERATURE)

    async def requestHumidityCalibration(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for humidity calibration")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_CALIBRATION_HUMIDTY)

    async def requestTemperatureCalibration(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for temperature calibration")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_CALIBRATION_TEMPERATURE)

    async def requestBatteryLevel(self) -> None:

        LOGGER.info(
            f"{self.address}: request battery level")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_BATTERY_LEVEL)

    async def requestMacAndSerial(self) -> None:

        LOGGER.info(
            f"{self.address}: request MAC address and serial no.")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_BATTERY_LEVEL)

    async def requestHardwareVersion(self) -> None:

        LOGGER.info(
            f"{self.address}: request hardware version")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_HARDWARE)

    async def requestFirmwareVersion(self) -> None:

        LOGGER.info(
            f"{self.address}: request firmware version")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_FIRMWARE)

    async def requestMeasurement(self) -> None:

        LOGGER.info(
            f"{self.address}: request current measurement")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT2)

    @staticmethod
    def decode_measurement(bytes) -> 'tuple[float,float]':

        raw = struct.unpack(">I", bytes)[0]
        if raw & 0x800000:
            is_negative = True
            raw = raw ^ 0x800000
        else:
            is_negative = False

        temperatureC = int(raw / 1000) / 10
        if is_negative:
            temperatureC = 0 - temperatureC

        relHumidity = (raw % 1000) / 10

        return temperatureC, relHumidity

    @staticmethod
    async def scan(consumer, duration: int = 20, unique: bool = True, mac_filter: str = None, progress=None):

        found_devices = list()

        def callback(device: BLEDevice, advertising_data: AdvertisementData):

            if unique is False or device.address not in found_devices:
                found_devices.append(device.address)
                if device.name and device.address.upper().startswith(GoveeThermometerHygrometer.MAC_PREFIX):
                    if 0xec88 in advertising_data.manufacturer_data:
                        LOGGER.debug(
                            f"{device.address} ({device.name}): Received advertisement data({MyLogger.hexstr(advertising_data.manufacturer_data[0xec88])})")
                        temperatureC, relHumidity = GoveeThermometerHygrometer.decode_measurement(
                            advertising_data.manufacturer_data[0xec88][0:4])
                        LOGGER.debug(f"{device.address}: Decoded measurement data("
                                     f"{MyLogger.hexstr(advertising_data.manufacturer_data[0xec88][0:4])}) is temperature={temperatureC}°C, humidity={relHumidity}%")
                        battery = advertising_data.manufacturer_data[0xec88][4]
                        LOGGER.debug(f"{device.address}: Decoded battery data("
                                     f"{hex(advertising_data.manufacturer_data[0xec88][4])}) is {battery}%")
                        measurement = Measurement(timestamp=datetime.now(),
                                                  temperatureC=temperatureC, relHumidity=relHumidity)

                        consumer(device.address, device.name,
                                 battery, measurement)

                elif device.name and progress:
                    progress(len(found_devices))

        async with BleakScanner(callback) as scanner:
            if duration:
                await asyncio.sleep(duration)
            else:
                while True:
                    await asyncio.sleep(1)

    def __str__(self) -> str:

        return (
            f"Devicename:         {self.name}\n"
            f"Address:            {self.address}\n"
            f"MAC and serial:     {str(self.macAndSerial)}\n"
            f"Manufacturer:       {self.manufacturer}\n"
            f"Model:              {self.model}\n"
            f"Hardware-Rev.:      {self.hardware}\n"
            f"Firmware-Rev.:      {self.firmware}\n"
            f"Battery level:      {self.batteryLevel} %\n"
            f"Humidity alarm:     {str(self.humidityAlarm)}\n"
            f"Temperature alarm:  {str(self.temperatureAlarm)}\n"
            f"Humidity offset:    {self.humidityCalibration:.1f} %\n"
            f"Temperature offset: {self.temperatureCalibration:.1f} °C\n"
            f"\n{str(self.measurement)}"
        )

    def to_dict(self) -> dict:

        return {
            "name": self.name.strip() if self.name else None,
            "address": self.address,
            "macAndSerial": self.macAndSerial.to_dict() if self.macAndSerial else None,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hardware": self.hardware,
            "firmware": self.firmware,
            "battery": self.batteryLevel,
            "humidityAlarm": self.humidityAlarm.to_dict() if self.humidityAlarm else None,
            "temperatureAlarm": self.temperatureAlarm.to_dict() if self.temperatureAlarm else None,
            "humidityCalibration": self.humidityCalibration,
            "temperatureCalibration": self.temperatureCalibration,
            "currentMeasurement": self.measurement.to_dict() if self.measurement else None
        }


class Alias():

    _KNOWN_DEVICES_FILE = ".known_govees"

    def __init__(self) -> None:

        self.aliases: 'dict[str,str]' = dict()
        try:
            filename = os.path.join(os.environ['USERPROFILE'] if os.name == "nt" else os.environ['HOME']
                                    if "HOME" in os.environ else "~", Alias._KNOWN_DEVICES_FILE)

            if os.path.isfile(filename):
                with open(filename, "r") as ins:
                    for line in ins:
                        _m = re.match(
                            "([0-9A-Fa-f:]+) +(.*)$", line)
                        if _m and _m.groups()[0].upper().startswith(GoveeThermometerHygrometer.MAC_PREFIX):
                            self.aliases[_m.groups()[0]] = _m.groups()[1]

        except:
            pass

    def resolve(self, label: str) -> str:

        if label.upper().startswith(GoveeThermometerHygrometer.MAC_PREFIX):
            return label
        else:
            macs = [
                a for a in self.aliases if self.aliases[a].startswith(label)]
            return macs[0] if macs else None


def arg_parse(args: 'list[str]') -> dict:

    parser = argparse.ArgumentParser(
        prog='govee-h5075.py', description='Shell script in order to request Govee H5075 temperature humidity sensor')

    parser.add_argument('-a', '--address', help='MAC address or alias')
    parser.add_argument(
        '-s', '--scan', help='scan for devices for 20 seconds', action='store_true')
    parser.add_argument('-m', '--measure',
                        help='capture measurements/advertisements from nearby devices', action='store_true')
    parser.add_argument(
        '--status', help='request current temperature, humidity and battery level for given MAC address or alias', action='store_true')
    parser.add_argument(
        '-i', '--info', help='request device information and configuration for given MAC address or alias', action='store_true')
    parser.add_argument(
        '--set-humidity-alarm', help='request device information for given MAC address or alias', type=str)
    parser.add_argument(
        '--set-temperature-alarm', help='request device information for given MAC address or alias', type=str)
    parser.add_argument(
        '--set-humidity-calibration', help='request device information for given MAC address or alias', type=float)
    parser.add_argument(
        '--set-temperature-calibration', help='request device information for given MAC address or alias', type=float)
    parser.add_argument(
        '-d', '--data', help='request recorded data for given MAC address or alias', action='store_true')
    parser.add_argument(
        '--start', help='request recorded data from start time expression, e.g. 480:00 (here max. value 20 days)', type=str, default=None)
    parser.add_argument(
        '--end', help='request recorded data to end time expression, e.g. 480:00 (here max. value 20 days)', type=str, default=None)
    parser.add_argument(
        '-j', '--json', help='print in JSON format', action='store_true')
    parser.add_argument(
        '-l', '--log', help='print logging information', choices=MyLogger.NAMES)

    return parser.parse_args(args)


def scan():

    def stdout_consumer(address: str, name: str, battery: int, measurement: Measurement) -> None:

        label = (alias.aliases[address]
                 if address in alias.aliases else address) + " " * 21
        print(
            f"{label[:21]} {name}  {measurement.temperatureC:.1f}°C       {measurement.dewPointC:.1f}°C     {measurement.temperatureF:.1f}°F       {measurement.dewPointF:.1f}°F     {measurement.relHumidity:.1f}%          {measurement.absHumidity:.1f} g/m³      {measurement.steamPressure:.1f} mbar       {battery}%", flush=True)

    def progress(found: int) -> None:

        print(' %i bluetooth devices seen' % found, end='\r', file=sys.stderr)

    print("MAC-Address/Alias     Device name   Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure  Battery", flush=True)
    asyncio.run(GoveeThermometerHygrometer.scan(
        consumer=stdout_consumer, progress=progress))


def measure():

    def stdout_consumer(address: str, name: str, battery: int, measurement: Measurement) -> None:

        timestamp = measurement.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        label = (alias.aliases[address]
                 if address in alias.aliases else address) + " " * 21
        print(
            f"{timestamp}   {label[:21]} {name}  {measurement.temperatureC:.1f}°C       {measurement.dewPointC:.1f}°C     {measurement.temperatureF:.1f}°F       {measurement.dewPointF:.1f}°F     {measurement.relHumidity:.1f}%          {measurement.absHumidity:.1f} g/m³      {measurement.steamPressure:.1f} mbar       {battery}%", flush=True)

    print("Timestamp             MAC-Address/Alias     Device name   Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure  Battery", flush=True)
    asyncio.run(GoveeThermometerHygrometer.scan(
        unique=False, duration=0, consumer=stdout_consumer))


async def status(label: str, _json: bool = False) -> None:

    try:
        mac = alias.resolve(label=label)
        device = GoveeThermometerHygrometer(mac)
        await device.connect()
        await device.requestMeasurement()

        await asyncio.sleep(.3)
        if _json:
            print(json.dumps(device.measurement.to_dict(), indent=2))
        else:
            print(str(device.measurement))

    except Exception as e:
        LOGGER.error(f"{mac}: {str(e)}")

    finally:
        await device.disconnect()


async def device_info(label: str, _json: bool = False) -> None:

    try:
        mac = alias.resolve(label=label)
        device = GoveeThermometerHygrometer(mac)
        await device.connect()
        await device.requestDeviceName()
        await device.requestHumidityAlarm()
        await device.requestTemperatureAlarm()
        await device.requestHumidityCalibration()
        await device.requestTemperatureCalibration()
        await device.requestMacAndSerial()
        await device.requestHardwareVersion()
        await device.requestFirmwareVersion()
        await device.requestMeasurement()

        await asyncio.sleep(.5)
        if _json:
            print(json.dumps(device.to_dict(), indent=2))
        else:
            print(str(device))

    except Exception as e:
        LOGGER.error(f"{mac}: {str(e)}")

    finally:
        await device.disconnect()


async def recorded_data(label: str, start: str, end: str, _json: bool = False):

    def parseTimeStr(s: str) -> int:

        a = s.split(":")
        return (int(a[0]) * 60 + int(a[1])) if len(a) == 2 else int(a[0])

    try:
        mac = alias.resolve(label=label)
        device = GoveeThermometerHygrometer(mac)
        await device.connect()
        start = min(parseTimeStr(start) if start else 60, 28800)
        end = min(parseTimeStr(end) if end else 0, 28800)
        measurements = await device.requestRecordedData(start=start if start > end else end, end=end if end < start else start)
        if _json:
            print(json.dumps([m.to_dict()
                              for m in measurements], indent=2))
        else:
            print("Timestamp         Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure", flush=True)
            for m in measurements:
                timestamp = m.timestamp.strftime("%Y-%m-%d %H:%M")
                print(f"{timestamp}  {m.temperatureC:.1f}°C       {m.dewPointC:.1f}°C     {m.temperatureF:.1f}°F       "
                      f"{m.dewPointF:.1f}°F     {m.relHumidity:.1f}%          {m.absHumidity:.1f} g/m³      {m.steamPressure:.1f} mbar", flush=True)

    except Exception as e:
        LOGGER.error(f"An exception has occured: {str(e)}")

    finally:
        await device.disconnect()

if __name__ == '__main__':

    alias = Alias()
    try:

        if len(sys.argv) == 1:
            scan()

        else:
            args = arg_parse(sys.argv[1:])

            if args.log:
                LOGGER.level = MyLogger.NAMES.index(args.log)

            if args.scan:
                scan()

            elif args.measure:
                measure()

            elif not args.address and (args.status or args.info or args.data or args.set_humidity_alarm or args.set_temperature_alarm or args.set_humidity_calibration or args.set_temperature_calibration):

                print("This operation requires to pass MAC address or alias",
                      file=sys.stderr, flush=True)
                exit(1)

            if args.status:
                asyncio.run(status(label=args.address, _json=args.json))

            elif args.info:
                asyncio.run(device_info(label=args.address, _json=args.json))

            elif args.data:
                asyncio.run(recorded_data(label=args.address,
                            start=args.start, end=args.end, _json=args.json))

            else:
                if args.set_humidity_alarm:
                    pass  # TODO

                if args.set_temperature_alarm:
                    pass  # TODO

                if args.set_humidity_calibration:
                    pass  # TODO

                if args.set_temperature_calibration:
                    pass  # TODO

    except KeyboardInterrupt:
        pass

    exit(0)
