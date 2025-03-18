#!/usr/bin/python3
#Modified to add support for Govee H5179 and H5074 thermometers
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

    def __init__(self, timestamp: datetime, temperatureC: float, relHumidity: float, humidityOffset: float = 0, temperatureOffset: float = 0) -> None:

        self.timestamp: datetime = timestamp
        self.humidityOffset: float = humidityOffset
        self.temperatureOffset: float = temperatureOffset
        self.temperatureC: float = temperatureC + temperatureOffset
        self.relHumidity: float = relHumidity + humidityOffset

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

        self.temperatureF: float = Measurement.to_fahrenheit(self.temperatureC)
        self.dewPointF: float = Measurement.to_fahrenheit(self.dewPointC)

    @staticmethod
    def to_fahrenheit(temperatureC: float) -> float:
        return temperatureC * 9.0/5.0 + 32

    @staticmethod
    def unpack_h5179_date(byte_data: bytearray):
        #Date is received as minutes since 1/1/1970
        mins_since_1970 = struct.unpack("<I", byte_data[0:4])
        h5179_date = datetime(year=1970,month=1,day=1) + timedelta(minutes=mins_since_1970[0])
        return h5179_date

    @staticmethod
    def twos_complement(n: int, w: int = 16) -> int:
            """Two's complement integer conversion."""
            #Courtesy of ThrilleratPlay on Github
            # Adapted from: https://stackoverflow.com/a/33716541.
            if n & (1 << (w - 1)):
                n = n - (1 << w)
            return n
    @staticmethod
    def unpack_H5179_history_record(bytes: bytearray, timestamp: datetime = None, little_endian=True, humidityOffset: float = 0, temperatureOffset: float = 0) -> 'Measurement':
            
        # Decode data from Govee 5179
        # Original courtesy of ThrilleratPlay on Github
        #https://github.com/Home-Is-Where-You-Hang-Your-Hack/sensor.goveetemp_bt_hci/blob/master/custom_components/govee_ble_hci/govee_advertisement.py#L97
        temp, hum = struct.unpack_from("<HH", bytes)
        # Negative temperature stored an two's complement
        temperature = float(Measurement.twos_complement(temp) / 100.0)
        relHumidity = float(hum / 100.0)
        #model = "Govee H5179"
                    
        return Measurement(timestamp=timestamp, temperatureC=temperature, relHumidity=relHumidity, humidityOffset=humidityOffset, temperatureOffset=temperatureOffset)
    
    @staticmethod
    def from_bytes(bytes: bytearray, timestamp: datetime = None, little_endian=False, humidityOffset: float = 0, temperatureOffset: float = 0) -> 'Measurement':

        if not timestamp:
            timestamp = datetime.now()

        if len(bytes) == 4:
            temperatureC, relHumidity = struct.unpack(
                "<hh", bytes) if little_endian else struct.unpack(">hh", bytes)
            temperatureC /= 100
            relHumidity /= 100

        elif len(bytes) == 3:
            raw = struct.unpack(">I", bytearray([0]) + bytes)[0]
            if raw & 0x800000:
                is_negative = True
                raw = raw ^ 0x800000
            else:
                is_negative = False

            temperatureC = int(raw / 1000) / 10.0

            if is_negative:
                temperatureC = 0 - temperatureC

            relHumidity = (raw % 1000) / 10.0

        else:
            return None

        return Measurement(timestamp=timestamp, temperatureC=temperatureC, relHumidity=relHumidity, humidityOffset=humidityOffset, temperatureOffset=temperatureOffset)

    def __str__(self) -> str:

        s: 'list[str]' = list()

        s.append(f"Timestamp:            "
                 f"{self.timestamp.strftime('%Y-%m-%d %H:%M')}")
        s.append(f"Temperature:          "
                 f"{self.temperatureC:.1f} °C / {self.temperatureF:.1f} °F")
        if self.temperatureOffset:
            s.append(f"Temperature offset:   "
                     f"{self.temperatureOffset:.1f} °C / {Measurement.to_fahrenheit(self.temperatureOffset):.1f} °F")
        s.append(f"Rel. humidity:        {self.relHumidity:.1f} %")

        if self.humidityOffset:
            s.append(f"Rel. humidity offset: {self.humidityOffset:.1f} %")

        s.append(f"Dew point:            "
                 f"{self.dewPointC:.1f} °C / {self.dewPointF:.1f} °F")
        s.append(f"Abs. humidity:        {self.absHumidity:.1f} g/m³")
        s.append(f"Steam pressure:       {self.steamPressure:.1f} mbar")

        return "\n".join(s)

    def to_dict(self) -> dict:

        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M"),
            "temperatureC": round(self.temperatureC, 1),
            "temperatureF": round(self.temperatureF, 1),
            "temperatureOffset": round(self.temperatureOffset, 1),
            "relHumidity": round(self.relHumidity, 1),
            "humidityOffset": round(self.humidityOffset, 1),
            "absHumidity": round(self.absHumidity, 1),
            "dewPointC": round(self.dewPointC, 1),
            "dewPointF": round(self.dewPointF, 1),
            "steamPressure": round(self.steamPressure, 1)
        }


class Alarm():

    def __init__(self, active: bool, lower: float, upper: float, unit: str = ""):
        self.active: bool = active
        self.lower: float = lower
        self.upper: float = upper
        self.unit: str = unit

    @staticmethod
    def from_bytes(bytes: bytearray, unit: str = None) -> 'Alarm':

        active, lower, upper = struct.unpack("<?hh", bytes)
        return Alarm(active=active, lower=lower/100.0, upper=upper/100.0, unit=unit)

    def to_bytes(self) -> bytearray:

        return struct.pack("<?hh", self.active, int(self.lower * 100), int(self.upper * 100))

    def __str__(self):

        return "%s, lower threshold: %.1f%s, upper threshold: %.1f%s" % ("active" if self.active else "inactive", self.lower, self.unit, self.upper, self.unit)

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
        self.device_category: str = ""
        
        self.set_device_category("")
        
    def set_device_category(self,device_type):
        self.device_category = self.get_device_category(device_type)        
        return
    
    @staticmethod
    def get_device_category(device_type):
        
        if device_type == "H5179":
            device_category = "H5179"
        elif device_type in ["H5075","H5074"]:
            device_category = "H507*"
        else:
            device_category = "H507*"
        
        return device_category
            
 
    def count(self) -> None:

        self.counted_msg += 1


class MacAndSerial():

    def __init__(self, mac: str, serial: int):

        self.mac: str = mac
        self.serial: int = serial

    @staticmethod
    def from_bytes(bytes: bytearray) -> 'MacAndSerial':

        mac = list()
        for i in range(6):
            m = "0%s" % hex(bytes[5-i]).upper().replace("0X", "")
            mac.append(m[-2:])

        return MacAndSerial(mac=MacAndSerial.decode_mac(bytes=bytes), serial=struct.unpack("<h", bytes[6:8])[0])

    @staticmethod
    def decode_mac(bytes: bytearray) -> str:

        mac = list()
        for i in range(6):
            m = "0%s" % hex(bytes[5-i]).upper().replace("0X", "")
            mac.append(m[-2:])

        return ":".join(mac)

    def __str__(self):

        return f"{self.mac}, {self.serial}"

    def to_dict(self) -> dict:

        return {
            "mac": self.mac,
            "serial": self.serial
        }


class GoveeThermometerHygrometer(BleakClient):

    MAC_PREFIX = ["A4:C1:38:","1C:9F:24:"]

    UUID_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
    UUID_DEVICE = "494e5445-4c4c-495f-524f-434b535f2011"
    UUID_COMMAND = "494e5445-4c4c-495f-524f-434b535f2012"
    UUID_DATA = "494e5445-4c4c-495f-524f-434b535f2013"

    REQUEST_CURRENT_MEASUREMENT = bytearray([0xaa, 0x01])
    REQUEST_CURRENT_MEASUREMENT2 = bytearray([0xaa, 0x0a])

    REQUEST_ALARM_HUMIDTY = bytearray([0xaa, 0x03])
    REQUEST_ALARM_TEMPERATURE = bytearray([0xaa, 0x04])
    REQUEST_OFFSET_HUMIDTY = bytearray([0xaa, 0x06])
    REQUEST_OFFSET_TEMPERATURE = bytearray([0xaa, 0x07])
    REQUEST_BATTERY_LEVEL = bytearray([0xaa, 0x08])
    REQUEST_MAC_AND_SERIAL = bytearray([0xaa, 0x0c])
    REQUEST_HARDWARE = bytearray([0xaa, 0x0d])
    REQUEST_FIRMWARE = bytearray([0xaa, 0x0e])
    REQUEST_MAC_ADDRESS = bytearray([0xaa, 0x0f])
    
    SEND_RECORDS_H5179_TX_REQUEST = bytearray([0x00, 0x00])
    SEND_RECORDS_TX_REQUEST = bytearray([0x33, 0x01])
    SEND_ALARM_HUMIDTY = bytearray([0x33, 0x03])
    SEND_ALARM_TEMPERATURE = bytearray([0x33, 0x04])
    SEND_OFFSET_HUMIDTY = bytearray([0x33, 0x06])
    SEND_OFFSET_TEMPERATURE = bytearray([0x33, 0x07])

    RECORDS_TX_COMPLETED = bytearray([0xee, 0x01])

    def __init__(self, address) -> None:

        super().__init__(address, timeout=30.0)

        self.name: str = None
        self.manufacturer: str = None
        self.model: str = None
        self.hardware: str = None
        self.firmware: str = None
        self.macAndSerial: MacAndSerial = None
        self.mac: str = None
        self.batteryLevel: int = None

        self.humidityAlarm: Alarm = None
        self.temperatureAlarm: Alarm = None
        self.humidityOffset: float = 0
        self.temperatureOffset: float = 0
        self.measurement: Measurement = None
        

        self._data_control: DataControl = None

    async def connect(self) -> None:

        async def notification_handler_device(device: BLEDevice, bytes: bytearray) -> None:

            LOGGER.debug(f"{self.address}: <<< received notification with device data("
                         f"{MyLogger.hexstr(bytes)})")

            if bytes[0:2] == GoveeThermometerHygrometer.REQUEST_ALARM_HUMIDTY:
                self.humidityAlarm = Alarm.from_bytes(bytes[2:7], unit=" %")
                LOGGER.info(f'{self.address}: received configuration for humidity alarm: '
                            f'{str(self.humidityAlarm)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_ALARM_TEMPERATURE:
                self.temperatureAlarm = Alarm.from_bytes(
                    bytes[2:7], unit=" °C")
                LOGGER.info(f'{self.address}: received configuration for temperature alarm: '
                            f'{str(self.temperatureAlarm)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_OFFSET_HUMIDTY:

                self.humidityOffset = struct.unpack(
                    "<h", bytes[2:4])[0] / 100.0
                LOGGER.info(f'{self.address}: received configuration for humidity offset: '
                            f'{self.humidityOffset:.1f} %')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_OFFSET_TEMPERATURE:
                self.temperatureOffset = struct.unpack(
                    "<h", bytes[2:4])[0] / 100.0
                LOGGER.info(f'{self.address}: received configuration for temperature offset: '
                            f'{self.temperatureOffset:.1f} °C')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_BATTERY_LEVEL:
                self.batteryLevel = bytes[2]
                LOGGER.info(f'{self.address}: received battery level: '
                            f'{self.batteryLevel} %')

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT2:

                self.measurement = Measurement.from_bytes(
                    bytes=bytes[2:6], little_endian=True, humidityOffset=self.humidityOffset or 0, temperatureOffset=self.temperatureOffset or 0)
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

            elif bytes[0:2] == GoveeThermometerHygrometer.REQUEST_MAC_ADDRESS:
                self.mac = MacAndSerial.decode_mac(bytes[2:8])
                LOGGER.info(f'{self.address}: received mac address: '
                            f'{str(self.mac)}')

            elif bytes[0:2] == GoveeThermometerHygrometer.SEND_ALARM_HUMIDTY:

                LOGGER.info(
                    f'{self.address}: configuration for humidity alarm successful')

            elif bytes[0:2] == GoveeThermometerHygrometer.SEND_ALARM_TEMPERATURE:

                LOGGER.info(
                    f'{self.address}: configuration for temperature alarm successful')

            elif bytes[0:2] == GoveeThermometerHygrometer.SEND_OFFSET_HUMIDTY:

                LOGGER.info(
                    f'{self.address}: configuration for humidity offset successful')

            elif bytes[0:2] == GoveeThermometerHygrometer.SEND_OFFSET_TEMPERATURE:

                LOGGER.info(
                    f'{self.address}: configuration for temperature offset successful')

        async def notification_handler_data(device: BLEDevice, bytes: bytearray) -> None:

            LOGGER.debug(f"{self.address}: <<< received notification with measurement data ("
                         f"{MyLogger.hexstr(bytes)})")

            if not self._data_control:
                return

            if self._data_control.device_category == "H5179": 
                #Get the date of this set of measurements
                record_time = Measurement.unpack_h5179_date(bytes)
                for i in range(4):
                    #maximum 4 measurements in each message
                    spos = 4 + (i*4)
                    epos = spos + 4
                    if bytes[spos] != 0xff:
                        measurement = Measurement.unpack_H5179_history_record(bytes[spos:epos],timestamp=record_time, humidityOffset=self.humidityOffset, temperatureOffset=self.temperatureOffset)
                        LOGGER.debug(f"{self.address}: Time: {record_time} temperature={measurement.temperatureC} °C, humidity={measurement.relHumidity} %")
                        #Save this measurement
                        self._data_control.measurements.append(measurement)

                    #Change time for next measurement
                    record_time = record_time - timedelta(minutes=1)
                    
            else: # default to H507* 
                for i in range(6):
                    minutes_back = struct.unpack(">H", bytes[0:2])[0]
                    if bytes[2 + 3 * i] == 0xff:
                        continue
    
                    timestamp = self._data_control.timestamp - \
                        timedelta(minutes=minutes_back - i)
                    _ba = bytearray(bytes[2 + 3 * i:5 + 3 * i])
                    measurement = Measurement.from_bytes(
                        bytes=_ba, timestamp=timestamp, humidityOffset=self.humidityOffset, temperatureOffset=self.temperatureOffset)
                    LOGGER.debug(f"{self.address}: Decoded measurement data("
                         f"{MyLogger.hexstr(_ba)}) is temperature={measurement.temperatureC} °C, humidity={measurement.relHumidity} %")
                    self._data_control.measurements.append(measurement)

            self._data_control.count()

        async def notification_handler_command(device: BLEDevice, bytes: bytearray) -> None:

            LOGGER.debug(f"{self.address}: <<< received notification after command ("
                         f"{MyLogger.hexstr(bytes)})")

            if bytes[0:2] == GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT:

                self.measurement = Measurement.from_bytes(
                    bytes=bytes[2:6], little_endian=False, humidityOffset=self.humidityOffset or 0, temperatureOffset=self.temperatureOffset or 0)
                self.batteryLevel = bytes[6]
                LOGGER.info(f'{self.address}: received current measurement and battery level:\n'
                            f'{str(self.measurement)}\nBattery level:        {self.batteryLevel} %')

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

    async def write_H5179_hist_gatt_char_command(self, uuid: str, command: bytearray, start: int = None, end: int = None) -> None:
    
        # H5179 command is the command + start time and end time in minutes since 1/1/1970 00:00
        _bytearray = bytearray(command)
        if start and end:
            _bytearray = _bytearray  + start.to_bytes(4,byteorder="little")
            _bytearray = _bytearray  + end.to_bytes(4,byteorder="little")
        else:
            ba_len = 10 
            if len(_bytearray) < ba_len:
                _bytearray.extend([0] * (ba_len - 1 - len(_bytearray)))
                _checksum = 0
                for _b in _bytearray:
                    _checksum ^= _b
                
                _bytearray.append(_checksum)      
                
        LOGGER.debug("%s: >>> write_gatt_char(%s, %s)" %
                     (self.address, uuid, MyLogger.hexstr(_bytearray)))
    
        await self.write_gatt_char(uuid, _bytearray, response=True)
        
        return    


    async def write_gatt_char_command(self, uuid: str, command: bytearray, params: bytearray = None) -> None:

        if not uuid or not command:
            return None
        
        _bytearray = bytearray(command)
        if params:
            _bytearray.extend(params)
        
        ba_len = 20 
        if len(_bytearray) < ba_len:
            _bytearray.extend([0] * (ba_len - 1 - len(_bytearray)))
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

    async def requestRecordedData(self, start: int, end: int,  device_type: str = "H5075") -> 'list[Measurement]':

        device_category = DataControl.get_device_category(device_type)

        if device_category == "H5179":
            records_per_msg = 4
            LOGGER.info(f"{self.address}: request recorded measurements from "
                    f"{start} to {end} minutes since 1/1/1970 00:00")
        else:
            records_per_msg = 6
            LOGGER.info(f"{self.address}: request recorded measurements from "
                    f"{start} to {end} minutes in the past")
        
        self._data_control = DataControl(
            expected_msg=math.ceil((start - end + 1) / records_per_msg))
        #Now set the device category
        self._data_control.set_device_category(device_type)
        
        # Special case for 5179
        if device_category == "H5179":
            #H5179
            await self.write_H5179_hist_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_COMMAND, command=GoveeThermometerHygrometer.SEND_RECORDS_H5179_TX_REQUEST, start = start, end = end)
        else:
            #Default to H507*
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
        if "H5075" in self.name:
            self.manufacturer = name[0:2]
            self.model = name[2:7]
        elif "H5074" in self.name or "H5179" in self.name:
            self.manufacturer = name[0:5]
            self.model = name[6:11]
        else:
            self.manufacturer = "Unknown"
            self.model = "Unknown"
            
        return self.name

    async def requestHumidityAlarm(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for humidity alarm")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_ALARM_HUMIDTY)

    async def requestTemperatureAlarm(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for temperature alarm")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_ALARM_TEMPERATURE)

    async def requestHumidityOffset(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for humidity offset")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_OFFSET_HUMIDTY)

    async def requestTemperatureOffset(self) -> None:

        LOGGER.info(
            f"{self.address}: request configuration for temperature offset")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_OFFSET_TEMPERATURE)

    async def requestBatteryLevel(self) -> None:

        LOGGER.info(
            f"{self.address}: request battery level")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_BATTERY_LEVEL)

    async def requestMacAddress(self) -> None:

        LOGGER.info(
            f"{self.address}: request MAC address")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_MAC_ADDRESS)

    async def requestMacAndSerial(self) -> None:

        LOGGER.info(
            f"{self.address}: request MAC address and serial no.")

        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_MAC_AND_SERIAL)

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

    async def requestMeasurementAndBattery(self, device_type: str = "H5075") -> None:

        LOGGER.info(
            f"{self.address}: request current measurement and battery")
        if device_type == "H5179":
            #This doesn't work, it just returns 01
            await self.write_H5179_hist_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT2)
        else:    
            await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_COMMAND, command=GoveeThermometerHygrometer.REQUEST_CURRENT_MEASUREMENT)

    async def setHumidityAlarm(self, alarm: Alarm) -> None:

        LOGGER.info(
            f"{self.address}: set humidity alarm: {str(alarm)}")

        if alarm.active == None or alarm.lower < 0.0 or alarm.lower > 99.9 or alarm.upper < 0.1 or alarm.upper > 100:
            LOGGER.error("Values for humidity alarm are invalid.")
            return None

        bytes = alarm.to_bytes()
        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.SEND_ALARM_HUMIDTY, params=bytes)

    async def setTemperatureAlarm(self, alarm: Alarm) -> None:

        LOGGER.info(
            f"{self.address}: set temperature alarm: {str(alarm)}")

        if alarm.active == None or alarm.lower < -20.0 or alarm.lower > 59.9 or alarm.upper < -19.9 or alarm.upper > 60.0:
            LOGGER.error("Values for temperature alarm are invalid.")
            return None

        bytes = alarm.to_bytes()
        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.SEND_ALARM_TEMPERATURE, params=bytes)

    async def setHumidityOffset(self, offset: float) -> None:

        LOGGER.info(
            f"{self.address}: set humidity offset: {offset:.1f} %")

        if offset == None or offset < -20.0 or offset > 20.0:
            LOGGER.error(
                "Value for humidity offset is invalid. Must be between -20.0 and 20.0")
            return None

        bytes = struct.pack("<h", int(offset * 100))
        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.SEND_OFFSET_HUMIDTY, params=bytes)

    async def setTemperatureOffset(self, offset: float) -> None:

        LOGGER.info(
            f"{self.address}: set temperature offset: {offset:.1f} °C")

        if offset == None or offset < -3.0 or offset > 3.0:
            LOGGER.error(
                "Value for temperature offset is invalid. Must be between -3.0 and 3.0")
            return None

        bytes = struct.pack("<h", int(offset * 100))
        await self.write_gatt_char_command(uuid=GoveeThermometerHygrometer.UUID_DEVICE, command=GoveeThermometerHygrometer.SEND_OFFSET_TEMPERATURE, params=bytes)

    @staticmethod
    async def scan(consumer, duration: int = 20, unique: bool = True, mac_filter: str = None, progress=None):

        found_devices = list()
        
        def decode_5074(bytes) -> 'tuple[float,float]':
            # Decode data from Govee 5074
            temperatureC, relHumidity = struct.unpack("<hh", bytes[1:5]) 
            temperatureC /= 100
            relHumidity /= 100
            battery = bytes[5]

            return round(temperatureC,1), round(relHumidity,1), battery
            
        def decode_5179(mfg_data):
            # Decode advertising data from Govee 5179
            #Courtesy of ThrilleratPlay on Github
            #https://github.com/Home-Is-Where-You-Hang-Your-Hack/sensor.goveetemp_bt_hci/blob/master/custom_components/govee_ble_hci/govee_advertisement.py#L97
            temp, hum, batt = struct.unpack_from("<HHB", mfg_data, 4)
            # Negative temperature stored an two's complement
            temperature = float(Measurement.twos_complement(temp) / 100.0)
            humidity = float(hum / 100.0)
            battery = int(batt)
                        
            return temperature, humidity, battery

        def callback(device: BLEDevice, advertising_data: AdvertisementData):

            if unique is False or device.address not in found_devices:
                #Only record as found if advertisement has measurement data
                if 0xec88 in advertising_data.manufacturer_data \
                    or 0x8801 in advertising_data.manufacturer_data:
                    found_devices.append(device.address)
                    LOGGER.debug(f"Found {device.address} ({device.name})")
                if device.name and device.address.upper()[0:9] in GoveeThermometerHygrometer.MAC_PREFIX:
                    #print (advertising_data)
                    if 0xec88 in advertising_data.manufacturer_data:
                        LOGGER.debug(
                            f"{device.address} ({device.name}): Received advertisement data({MyLogger.hexstr(advertising_data.manufacturer_data[0xec88])})")

                        if device.address in alias.aliases:
                            humidityOffset = alias.aliases[device.address][1] if alias.aliases[device.address][1] else 0.0
                            temperatureOffset = alias.aliases[device.address][2] if alias.aliases[device.address][2] else 0.0
                        else:
                            humidityOffset = 0.0
                            temperatureOffset = 0.0
                        
                        #H5075 and H5074 have different format
                        if "H5074" in device.name:
                            temperatureC, relHumidity, battery = decode_5074(advertising_data.manufacturer_data[0xec88])
                            measurement = Measurement(datetime.now(), temperatureC, relHumidity, 0, 0)
                        else:
                            measurement = Measurement.from_bytes(
                                bytes=advertising_data.manufacturer_data[0xec88][1:4], humidityOffset=humidityOffset, temperatureOffset=temperatureOffset)
                            battery = advertising_data.manufacturer_data[0xec88][4]

                        LOGGER.debug(f"{device.address}: Decoded measurement data("
                                     f"{MyLogger.hexstr(advertising_data.manufacturer_data[0xec88][0:4])}) is temperature={measurement.temperatureC}°C, humidity={measurement.relHumidity}%")
                        LOGGER.debug(f"{device.address}: Decoded battery data("
                                     f"{hex(advertising_data.manufacturer_data[0xec88][4])}) is {battery}%")

                        consumer(device.address, device.name,
                                 battery, measurement)
                    elif 0x8801 in advertising_data.manufacturer_data:
                    #Govee 5179
                        LOGGER.debug(
                            f"{device.address} ({device.name}): Received advertisement data({MyLogger.hexstr(advertising_data.manufacturer_data[0x8801])})")

                        temperatureC, relHumidity, battery = decode_5179(advertising_data.manufacturer_data[0x8801])
                        measurement = Measurement(datetime.now(), temperatureC, relHumidity, 0, 0)
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

        s: 'list[str]' = list()

        if self.name:
            s.append(f"Devicename:           {self.name}")

        s.append(f"Address:              {self.address}")

        if self.manufacturer:
            s.append(f"Manufacturer:         {self.manufacturer}")

        if self.model:
            s.append(f"Model:                {self.model}")

        if self.hardware:
            s.append(f"Hardware-Rev.:        {self.hardware}")

        if self.firmware:
            s.append(f"Firmware-Rev.:        {self.firmware}")

        if self.batteryLevel:
            s.append(f"Battery level:        {self.batteryLevel} %")

        if self.humidityAlarm:
            s.append(f"Humidity alarm:       {str(self.humidityAlarm)}")

        if self.temperatureAlarm:
            s.append(f"Temperature alarm:    {str(self.temperatureAlarm)}")

        if self.humidityOffset:
            s.append(f"Humidity offset:      {self.humidityOffset:.1f} %")

        if self.temperatureOffset:
            s.append(f"Temperature offset:   {self.temperatureOffset:.1f} °C")

        if self.measurement:
            s.append(f"\n{str(self.measurement)}")

        return "\n".join(s)

    def to_dict(self) -> dict:

        return {
            "name": self.name.strip() if self.name else None,
            "address": self.address,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hardware": self.hardware,
            "firmware": self.firmware,
            "battery": self.batteryLevel,
            "humidityAlarm": self.humidityAlarm.to_dict() if self.humidityAlarm else None,
            "temperatureAlarm": self.temperatureAlarm.to_dict() if self.temperatureAlarm else None,
            "humidityOffset": self.humidityOffset,
            "temperatureOffset": self.temperatureOffset,
            "currentMeasurement": self.measurement.to_dict() if self.measurement else None
        }


class Alias():

    _KNOWN_DEVICES_FILE = ".known_govees"

    def __init__(self) -> None:

        self.aliases: 'dict[str,tuple[str, float, float]]' = dict()
        try:
            filename = os.path.join(os.environ['USERPROFILE'] if os.name == "nt" else os.environ['HOME']
                                    if "HOME" in os.environ else "~", Alias._KNOWN_DEVICES_FILE)

            if os.path.isfile(filename):
                with open(filename, "r") as ins:
                    for line in ins:
                        _m = re.match(
                            r"([0-9A-Fa-f:]+) +([^ ]+)( (-?\d+\.\d) (-?\d+\.\d))?$", line)
                        if _m and _m.groups()[0].upper()[0:9] in GoveeThermometerHygrometer.MAC_PREFIX:

                            alias = _m.groups()[1].strip()
                            humidityOffset = float(_m.groups()[3]) if _m.groups()[
                                3] else 0.0
                            temperatureOffset = float(
                                _m.groups()[4]) if _m.groups()[4] else 0.0

                            self.aliases[_m.groups()[0]] = (
                                alias, humidityOffset, temperatureOffset)

        except:
            pass

    def resolve(self, label: str) -> str:

        if label.upper()[0:9] in GoveeThermometerHygrometer.MAC_PREFIX:
            return label
        else:
            macs = [
                a for a in self.aliases if self.aliases[a][0].startswith(label)]
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
        '--set-humidity-alarm', metavar="\"<on|off> <lower> <upper>\"", help='set temperature alarm. Range is from 0.0 to 100.0 in steps of 0.1, e.g. \"on 30.0 75.0\"', type=str)
    parser.add_argument(
        '--set-temperature-alarm', metavar="\"<on|off> <lower> <upper>\"", help='set temperature alarm. Range is from -20.0 to 60.0 in steps of 0.1, e.g. \"on 15.0 26.0\"', type=str)
    parser.add_argument(
        '--set-humidity-offset', metavar="<offset>", help='set offset for humidity to calibrate. Range is from -20.0 to 20.0 in steps of 0.1, e.g. -5.0', type=float)
    parser.add_argument(
        '--set-temperature-offset', metavar="<offset>", help='set offset for temperature to calibrate. Range is from -3.0 to 3.0 in steps of 0.1, e.g. -1.0', type=float)
    parser.add_argument(
        '-d', '--data', help='request recorded data for given MAC address or alias', action='store_true')
    parser.add_argument(
        '--start', metavar="<hhh:mm>", help='request recorded data from start time expression, e.g. 480:00 (here max. value 20 days)', type=str, default=None)
    parser.add_argument(
        '--end', metavar="<hhh:mm>", help='request recorded data to end time expression, e.g. 480:00 (here max. value 20 days)', type=str, default=None)
    parser.add_argument(
        '-j', '--json', help='print in JSON format', action='store_true')
    parser.add_argument(
        '-l', '--log', help='print logging information', choices=MyLogger.NAMES)

    return parser.parse_args(args)


def scan():

    def stdout_consumer(address: str, name: str, battery: int, measurement: Measurement) -> None:

        label = (alias.aliases[address][0]
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
        label = (alias.aliases[address][0]
                 if address in alias.aliases else address) + " " * 21

        print(
            f"{timestamp}   {label[:21]} {name}  {measurement.temperatureC:.1f}°C       {measurement.dewPointC:.1f}°C     {measurement.temperatureF:.1f}°F       {measurement.dewPointF:.1f}°F     {measurement.relHumidity:.1f}%          {measurement.absHumidity:.1f} g/m³      {measurement.steamPressure:.1f} mbar       {battery}%", flush=True)

    print("Timestamp             MAC-Address/Alias     Device name   Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure  Battery", flush=True)
    asyncio.run(GoveeThermometerHygrometer.scan(
        unique=False, duration=0, consumer=stdout_consumer))


async def status(label: str, _json: bool = False) -> None:

    mac = alias.resolve(label=label)
    if not mac:
        LOGGER.error(f"Unable to resolve alias or mac "
                     f"{label}. Pls. check ~/.known_govees")
        return

    try:
        device = GoveeThermometerHygrometer(mac)
        await device.connect()
        await device.requestHumidityOffset()
        await device.requestTemperatureOffset()
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
        await device.requestHumidityOffset()
        await device.requestTemperatureOffset()
        await device.requestHardwareVersion()
        await device.requestFirmwareVersion()
        await device.requestBatteryLevel()
        device_type = device.model
        if device_type == "H5179":
            await device.requestMeasurement()
        else:
            await device.requestMeasurementAndBattery(device_type)

        await asyncio.sleep(.5)
        if _json:
            print(json.dumps(device.to_dict(), indent=2))
        else:
            print(str(device))

    except Exception as e:
        LOGGER.error(f"{mac}: {str(e)}")

    finally:
        await device.disconnect()


async def configure_device(label: str, humidityAlarm: str = None, temperatureAlarm: str = None, humidityOffset: str = None, temperatureOffset: str = None) -> None:

    def parseAlarm(arg: str) -> 'tuple[bool, float, float]':

        if not arg:
            return None, None, None

        m = re.match(
            r"^(on|off) (-?\d{1,2}\.\d) (-?\d{1,3}\.\d)$", arg.lower())
        if not m:
            return None, None, None

        return "on" == m.groups()[0], float(m.groups()[1]), float(m.groups()[2])

    has_errors = False
    if humidityAlarm:
        humidityAlarmActive, humidityAlarmLower, humidityAlarmUpper = parseAlarm(
            arg=humidityAlarm)
        if humidityAlarmActive == None or humidityAlarmLower < 0 or humidityAlarmLower > 99.9 or humidityAlarmUpper < 0.1 or humidityAlarmUpper > 100:
            LOGGER.error("Parameters for humidity alarm are incorrect.")
            has_errors = True

    if temperatureAlarm:
        temperatureAlarmActive, temperatureAlarmLower, temperatureAlarmUpper = parseAlarm(
            arg=temperatureAlarm)
        if temperatureAlarmActive == None or temperatureAlarmLower < -20.0 or temperatureAlarmLower > 59.9 or temperatureAlarmUpper < -19.9 or temperatureAlarmUpper > 60:
            LOGGER.error("Parameters for temperature alarm are incorrect.")
            has_errors = True

    if humidityOffset:
        if humidityOffset < -20.0 or humidityOffset > 20.0:
            LOGGER.error("Parameter for humidity offset is incorrect.")
            return

    if temperatureOffset:
        if temperatureOffset < -3.0 or temperatureOffset > 3.0:
            LOGGER.error("Parameter for temperature offset is incorrect.")
            has_errors = True

    if has_errors:
        return

    try:
        mac = alias.resolve(label=label)
        device = GoveeThermometerHygrometer(mac)
        await device.connect()

        if humidityAlarm != None:
            await device.setHumidityAlarm(alarm=Alarm(active=humidityAlarmActive, lower=humidityAlarmLower, upper=humidityAlarmUpper, unit=" %"))

        if temperatureAlarm != None:
            await device.setTemperatureAlarm(alarm=Alarm(active=temperatureAlarmActive, lower=temperatureAlarmLower, upper=temperatureAlarmUpper, unit=" °C"))

        if humidityOffset != None:
            await device.setHumidityOffset(offset=humidityOffset)

        if temperatureOffset != None:
            await device.setTemperatureOffset(offset=temperatureOffset)

        await asyncio.sleep(.5)

    except Exception as e:
        LOGGER.error(f"{mac}: {str(type(e))} {str(e)}")

    finally:
        await device.disconnect()


async def recorded_data(label: str, start: str, end: str, _json: bool = False):

    def parseTimeStr(s: str) -> int:

        a = s.split(":")
        return (int(a[0]) * 60 + int(a[1])) if len(a) == 2 else int(a[0])

    def get_1970_offset(minutes_before_now):
        #Convert time to minutes since 1/1/1970 00:00
        t_delta  = datetime.now() - datetime(year=1970,month=1,day=1)
        offset = int(t_delta.total_seconds()/60) - minutes_before_now
        return offset

    try:
        mac = alias.resolve(label=label)
        device = GoveeThermometerHygrometer(mac)
        await device.connect()
        #Get device name - this loads self.model with the device type
        await device.requestDeviceName()
        device_type = device.model
        if device_type == "H5179":
            start = get_1970_offset(parseTimeStr(start)) if start else get_1970_offset(60)
            end = get_1970_offset(parseTimeStr(end)) if end else get_1970_offset(0)
            #ensure start time is older than end time
            starttime = start if start < end else end
            endtime = end if end > start else start
        else:
            start = min(parseTimeStr(start) if start else 60, 28800)
            end = min(parseTimeStr(end) if end else 0, 28800)
            #ensure start time is older than end time
            starttime = start if start > end else end
            endtime = end if end < start else start
        LOGGER.debug(f"Device type: {device_type}, start: {str(start)}, end: {str(end)}")
        await device.requestHumidityOffset()
        await device.requestTemperatureOffset()
        measurements = await device.requestRecordedData(start=starttime, end=endtime, device_type =device_type)
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

            elif not args.address and (args.status or args.info or args.data or args.set_humidity_alarm or args.set_temperature_alarm or args.set_humidity_offset or args.set_temperature_offset):

                print("This operation requires to pass MAC address or alias",
                      file=sys.stderr, flush=True)

            elif args.set_humidity_alarm or args.set_temperature_alarm or args.set_humidity_offset or args.set_temperature_offset:
                asyncio.run(configure_device(label=args.address, humidityAlarm=args.set_humidity_alarm, temperatureAlarm=args.set_temperature_alarm,
                            humidityOffset=args.set_humidity_offset, temperatureOffset=args.set_temperature_offset))

            elif args.status:
                asyncio.run(status(label=args.address, _json=args.json))

            elif args.data:
                asyncio.run(recorded_data(label=args.address,
                            start=args.start, end=args.end, _json=args.json))

            else:
                asyncio.run(device_info(label=args.address, _json=args.json))

    except KeyboardInterrupt:
        pass

    exit(0)
