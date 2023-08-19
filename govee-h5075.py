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

    def __str__(self) -> str:

        return "\n".join([
            "Timestamp:      %s" % self.timestamp.strftime("%Y-%m-%d %H:%M"),
            f"Temperature:    {self.temperatureC:.1f} °C",
            f"Dew point:      {self.dewPointC:.1f} °C",
            "",
            f"Temperature:    {self.temperatureF:.1f} °F",
            f"Dew point:      {self.dewPointF:.1f} °F",
            "",
            f"Rel. humidity:  {self.relHumidity:.1f} %",
            f"Abs. humidity:  {self.absHumidity:.1f} g/m³",
            f"Steam pressure: {self.steamPressure:.1f} mbar"
        ])

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


class DeviceInfo():

    def __init__(self, macAddress: str, name: str, manufacturer: str, model: str, hardware: str, firmware: str) -> None:

        self.macAddress: str = macAddress
        self.name: str = name
        self.manufacturer: str = manufacturer
        self.model: str = model
        self.hardware: str = hardware
        self.firmware: str = firmware

    def __str__(self) -> str:

        return "\n".join([
            f"MAC-Address:    {self.macAddress}",
            f"Devicename:     {self.name}",
            f"Manufacturer:   {self.manufacturer}",
            f"Model:          {self.model}",
            f"Hardware-Rev.:  {self.hardware}",
            f"Firmware-Rev.:  {self.firmware}"
        ])

    def to_dict(self) -> dict:

        return {
            "mac": self.macAddress,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hardware": self.hardware,
            "firmware": self.firmware
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


class GoveeThermometerHygrometer():

    MAC_PREFIX = "A4:C1:38:"
    _COMMANDS = {
        "NAME": {
            "UUID": "00002a00-0000-1000-8000-00805f9b34fb",
        },
        "FIRMWARE": {
            "UUID": "494e5445-4c4c-495f-524f-434b535f2011",
            "SEQUENCE": [0xaa, 0x0e] + [0] * 17 + [0xa4]
        },
        "HARDWARE": {
            "UUID": "494e5445-4c4c-495f-524f-434b535f2011",
            "SEQUENCE": [0xaa, 0x0d] + [0] * 17 + [0xa7]
        },
        "DATA_CONTROL": {
            "UUID": "494e5445-4c4c-495f-524f-434b535f2012",
            "SEQUENCE": [0x33, 0x01]
        },
        "DATA": {
            "UUID": "494e5445-4c4c-495f-524f-434b535f2013"
        }
    }

    def __init__(self, mac: str) -> None:

        self._client = BleakClient(mac)
        self._mac = mac
        self._measurement = None
        self._deviceInfo = None
        self._buffer = dict()
        self._data_control: DataControl = None

    async def connect(self) -> None:

        async def notification_handler_device(c, bytes: bytearray) -> None:

            if bytes[0] == 0xaa and bytes[1] == 0x0e:
                self._buffer["FIRMWARE"] = bytes[2:9].decode()

            elif bytes[0] == 0xaa and bytes[1] == 0x0d:
                self._buffer["HARDWARE"] = bytes[2:9].decode()

        async def notification_handler_data(c, bytes: bytearray) -> None:

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
                temperatureC, relHumidity = GoveeThermometerHygrometer.decodeMeasurement(
                    bytes=_ba)
                self._data_control.measurements.append(Measurement(
                    timestamp=timestamp, temperatureC=temperatureC, relHumidity=relHumidity))

            self._data_control.count()

        async def notification_handler_data_control(c, bytes: bytearray) -> None:

            if bytes[0] == 0x33 and bytes[1] == 0x01 and self._data_control:
                self._data_control.status = DataControl.DATA_CONTROL_STARTED

            elif bytes[0] == 0xee and bytes[1] == 0x01 and self._data_control:
                self._data_control.received_msg = struct.unpack(">H", bytes[2:4])[
                    0]
                if self._data_control.received_msg == self._data_control.counted_msg:
                    self._data_control.status = DataControl.DATA_CONTROL_COMPLETE
                else:
                    self._data_control.status = DataControl.DATA_CONTROL_INCOMPLETE

        await self._client.connect()

        if self._client.is_connected:
            await self._client.start_notify(self._COMMANDS["FIRMWARE"]["UUID"], callback=notification_handler_device)
            await self._client.start_notify(self._COMMANDS["DATA_CONTROL"]["UUID"], callback=notification_handler_data_control)
            await self._client.start_notify(self._COMMANDS["DATA"]["UUID"], callback=notification_handler_data)
            await asyncio.sleep(.2)

    async def disconnect(self) -> None:

        if self._client.is_connected:
            await self._client.disconnect()

    async def _sendCommand(self, command: dict, params: 'list[int]' = []) -> None:

        _bytearray = bytearray(command["SEQUENCE"])
        if params:
            _bytearray.extend(params)
        if len(_bytearray) < 20:
            _bytearray.extend([0] * (19 - len(_bytearray)))
            _checksum = 0
            for _b in _bytearray:
                _checksum ^= _b

            _bytearray.append(_checksum)

        await self._client.write_gatt_char(command["UUID"], _bytearray, response=True)

    async def requestRecordedData(self, start: int, end: int) -> 'list[Measurement]':

        if not self._client.is_connected:
            self.connect()

        self._data_control = DataControl(
            expected_msg=math.ceil((start - end + 1) / 6))
        await self._sendCommand(command=self._COMMANDS["DATA_CONTROL"], params=[start >> 8, start & 0xff, end >> 8, end & 0xff])

        i = 0
        while i < 600 and (self._data_control.status not in [DataControl.DATA_CONTROL_COMPLETE, DataControl.DATA_CONTROL_INCOMPLETE]):
            await asyncio.sleep(.1)
            i += 1

        measurements = self._data_control.measurements
        self._data_control = None
        return measurements

    async def requestDeviceInfo(self) -> DeviceInfo:

        self._buffer["HARDWARE"] = None
        self._buffer["FIRMWARE"] = None

        if not self._client.is_connected:
            self.connect()

        await self._sendCommand(self._COMMANDS["HARDWARE"])
        await self._sendCommand(self._COMMANDS["FIRMWARE"])

        i = 0
        while i < 10 and (not self._buffer["HARDWARE"] or not self._buffer["FIRMWARE"]):
            await asyncio.sleep(.1)
            i += 1

        _name = await self._client.read_gatt_char(self._COMMANDS["NAME"]["UUID"])
        if not _name or not self._buffer["HARDWARE"] or not self._buffer["FIRMWARE"]:
            return None

        _name = _name.decode()

        return DeviceInfo(macAddress=self._mac, name=_name, manufacturer=_name[:2], model=_name[2:7], hardware=self._buffer["HARDWARE"], firmware=self._buffer["FIRMWARE"])

    @staticmethod
    def decodeMeasurement(bytes) -> 'tuple[float,float]':

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
                        temperatureC, relHumidity = GoveeThermometerHygrometer.decodeMeasurement(
                            advertising_data.manufacturer_data[0xec88][0:4])
                        battery = advertising_data.manufacturer_data[0xec88][4]
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

    parser = argparse.ArgumentParser(prog='govee-h5075.py', description=
        'Shell script in order to request Govee H5075 temperature humidity sensor')
    parser.add_argument(
        '-s', '--scan', help='scan for devices for 20 seconds', action='store_true')
    parser.add_argument('-m', '--measure',
                        help='capture measurements/advertisements from nearby devices', action='store_true')
    parser.add_argument(
        '-i', '--info', help='request device information for given mac or alias', type=str)
    parser.add_argument(
        '-d', '--data', help='request recorded data for given mac or alias', type=str)
    parser.add_argument(
        '--start', help='request recorded data from start time expression, e.g. 480:00 (here max. value 20 days)', type=str, default=None)
    parser.add_argument(
        '--end', help='request recorded data to end time expression, e.g. 480:00 (here max. value 20 days)', type=str, default=None)
    parser.add_argument(
        '-j', '--json', help='print in JSON format', action='store_true')

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


async def device_info(label: str, _json: bool = False) -> None:

    try:
        mac = alias.resolve(label=label)
        device = GoveeThermometerHygrometer(mac)
        await device.connect()
        deviceInfo = await device.requestDeviceInfo()
        if _json:
            print(json.dumps(deviceInfo.to_dict(), indent=2))
        else:
            print(str(deviceInfo))

    except Exception as e:
        print(e, file=sys.stderr)

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
                print(f"{timestamp}  {m.temperatureC:.1f}°C       {m.dewPointC:.1f}°C     {m.temperatureF:.1f}°F       {m.dewPointF:.1f}°F     {m.relHumidity:.1f}%          {m.absHumidity:.1f} g/m³      {m.steamPressure:.1f} mbar", flush=True)

    except Exception as e:
        print(e, file=sys.stderr)

    finally:
        await device.disconnect()

if __name__ == '__main__':

    alias = Alias()
    try:

        if len(sys.argv) == 1:
            scan()

        else:
            args = arg_parse(sys.argv[1:])
            if args.scan:
                scan()

            elif args.measure:
                measure()
            elif args.info:
                asyncio.run(device_info(label=args.info, _json=args.json))
            elif args.data:
                asyncio.run(recorded_data(label=args.data, start=args.start, end=args.end, _json=args.json))

    except KeyboardInterrupt:
        pass
