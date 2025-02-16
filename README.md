# govee-h5075-thermo-hygrometer

Shell script and python lib for Govee H5075 thermometer / hygrometer for Linux, Raspberry Pis and Windows.

## Preconditions
Install the python module [bleak](https://bleak.readthedocs.io/en/latest/)

```
$ pip install bleak
```

or globally for all users (maybe also required on Raspberry Pi OS)
```
sudo apt install python3-bleak
```

## Help
```
$ ./govee-h5075.py --help
usage: govee-h5075.py [-h] [-a ADDRESS] [-s] [-m] [--status] [-i] [--set-humidity-alarm "<on|off> <lower> <upper>"] [--set-temperature-alarm "<on|off> <lower> <upper>"]
                      [--set-humidity-offset <offset>] [--set-temperature-offset <offset>] [-d] [--start <hhh:mm>] [--end <hhh:mm>] [-j] [-l {DEBUG,INFO,WARN,ERROR}]

Shell script in order to request Govee H5075 temperature humidity sensor

options:
  -h, --help            show this help message and exit
  -a ADDRESS, --address ADDRESS
                        MAC address or alias
  -s, --scan            scan for devices for 20 seconds
  -m, --measure         capture measurements/advertisements from nearby devices
  --status              request current temperature, humidity and battery level for given MAC address or alias
  -i, --info            request device information and configuration for given MAC address or alias
  --set-humidity-alarm "<on|off> <lower> <upper>"
                        set temperature alarm. Range is from 0.0 to 100.0 in steps of 0.1, e.g. "on 30.0 75.0"
  --set-temperature-alarm "<on|off> <lower> <upper>"
                        set temperature alarm. Range is from -20.0 to 60.0 in steps of 0.1, e.g. "on 15.0 26.0"
  --set-humidity-offset <offset>
                        set offset for humidity to calibrate. Range is from -20.0 to 20.0 in steps of 0.1, e.g. -5.0
  --set-temperature-offset <offset>
                        set offset for temperature to calibrate. Range is from -3.0 to 3.0 in steps of 0.1, e.g. -1.0
  -d, --data            request recorded data for given MAC address or alias
  --start <hhh:mm>      request recorded data from start time expression, e.g. 480:00 (here max. value 20 days)
  --end <hhh:mm>        request recorded data to end time expression, e.g. 480:00 (here max. value 20 days)
  -j, --json            print in JSON format
  -l {DEBUG,INFO,WARN,ERROR}, --log {DEBUG,INFO,WARN,ERROR}
                        print logging information
```

## Scan for nearby devices and grab measurement

Scan for devices for 20 seconds
```
$ ./govee-h5075.py -s
MAC-Address/Alias     Device name   Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure  Battery
A4:C1:38:68:41:23     GVH5075_4123  21.9°C       14.5°C     71.4°F       58.1°F     63.0%          12.2 g/m³      16.5 mbar       96%
A4:C1:38:5A:20:A1     GVH5075_20A1  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar       95%
 28 bluetooth devices seen
```

or even without any parameters:
```
$ ./govee-h5075.py
MAC-Address/Alias     Device name   Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure  Battery
A4:C1:38:5A:20:A1     GVH5075_20A1  22.0°C       13.9°C     71.6°F       57.0°F     60.4%          11.7 g/m³      15.9 mbar       95%
A4:C1:38:68:41:23     GVH5075_4123  21.9°C       14.5°C     71.4°F       58.1°F     63.0%          12.2 g/m³      16.5 mbar       96%
``` 

## Put ```.known_govees```-file to your home directory
To use friendly device names and request devices by name, place a ```.known_govees``` file in your home directory.

This file is crucial for accurate calibration when receiving advertisement data during measurement and scanning. Calibration data is not sourced from device configuration in these instances. Calibration data is only applied when querying measurement or historical data. 

Example:
```
A4:C1:38:68:41:23 Bedroom 0.0 0.0
A4:C1:38:5A:20:A1 Livingroom 0.0 0.0
```

The meaning of columns is as follows:
1. MAC address
2. Alias
3. Offset / calibration for humidity
4. Offset / calibration for temperature

Afterwards you'll see the alias if you scan or grab measurements instead of the MAC-address.

## Continuously grab measurements from nearby devices
```
$ ./govee-h5075.py -m
Timestamp             MAC-Address/Alias     Device name   Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure  Battery
2023-09-19 13:42:37   Bedroom               GVH5075_4123  22.0°C       14.6°C     71.6°F       58.3°F     63.1%          12.3 g/m³      16.7 mbar       96%
2023-09-19 13:42:39   Bedroom               GVH5075_4123  21.9°C       14.5°C     71.4°F       58.1°F     63.1%          12.2 g/m³      16.6 mbar       96%
2023-09-19 13:42:41   Bedroom               GVH5075_4123  22.0°C       14.6°C     71.6°F       58.3°F     63.1%          12.3 g/m³      16.7 mbar       96%
2023-09-19 13:42:42   Livingroom            GVH5075_20A1  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar       95%
```

End this by pressing CRTL+C.

## Request device information

```
$ ./govee-h5075.py -a Bedr -i
Devicename:           GVH5075_4123
Address:              A4:C1:38:68:41:23
Manufacturer:         GV
Model:                H5075
Hardware-Rev.:        1.03.02
Firmware-Rev.:        1.04.06
Battery level:        15 %
Humidity alarm:       active, lower threshold: 40.0 %, upper threshold: 60.0 %
Temperature alarm:    active, lower threshold: 16.0 °C, upper threshold: 24.0 °C

Timestamp:            2025-01-05 09:02
Temperature:          19.9 °C / 67.8 °F
Rel. humidity:        46.6 %
Dew point:            8.1 °C / 46.6 °F
Abs. humidity:        8.0 g/m³
Steam pressure:       10.8 mbar
```

Note: The alias has been used. It works also if you just enter the first letters of the alias.

If you want to have the result in JSON-format you can call it like this:
```
$ ./govee-h5075.py -a Bedr -j
{
  "name": "GVH5075_4123",
  "address": "A4:C1:38:68:41:23",
  "manufacturer": "GV",
  "model": "H5075",
  "hardware": "1.03.02",
  "firmware": "1.04.06",
  "battery": 15,
  "humidityAlarm": {
    "active": true,
    "lower": 40.0,
    "upper": 60.0
  },
  "temperatureAlarm": {
    "active": true,
    "lower": 16.0,
    "upper": 24.0
  },
  "humidityOffset": 0.0,
  "temperatureOffset": 0.0,
  "currentMeasurement": {
    "timestamp": "2025-01-05 09:03",
    "temperatureC": 19.9,
    "temperatureF": 67.9,
    "temperatureOffset": 0,
    "relHumidity": 46.6,
    "humidityOffset": 0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  }
}
```

Note: If you want to get device information you can also leave out the '-i' switch. 

## Request historical data
In this example recorded data of the last 10 minutes is requested.
```
$ govee-h5075.py -a Badr --data --start 0:10
2025-01-05 08:55  19.8°C       8.1°C     67.6°F       46.6°F     46.7%          8.0 g/m³      10.8 mbar
2025-01-05 08:56  19.8°C       8.1°C     67.6°F       46.6°F     46.7%          8.0 g/m³      10.8 mbar
2025-01-05 08:57  19.8°C       8.1°C     67.6°F       46.6°F     46.7%          8.0 g/m³      10.8 mbar
2025-01-05 08:58  19.8°C       8.1°C     67.6°F       46.6°F     46.7%          8.0 g/m³      10.8 mbar
2025-01-05 08:59  19.8°C       8.0°C     67.6°F       46.4°F     46.6%          8.0 g/m³      10.7 mbar
2025-01-05 09:00  19.8°C       8.0°C     67.6°F       46.4°F     46.6%          8.0 g/m³      10.7 mbar
2025-01-05 09:01  19.9°C       8.1°C     67.8°F       46.6°F     46.6%          8.0 g/m³      10.8 mbar
2025-01-05 09:02  19.9°C       8.1°C     67.8°F       46.6°F     46.5%          8.0 g/m³      10.8 mbar
2025-01-05 09:03  19.9°C       8.1°C     67.8°F       46.6°F     46.5%          8.0 g/m³      10.8 mbar
2025-01-05 09:04  19.9°C       8.1°C     67.8°F       46.6°F     46.5%          8.0 g/m³      10.8 mbar
2025-01-05 09:05  19.9°C       8.1°C     67.8°F       46.6°F     46.5%          8.0 g/m³      10.8 mbar
```

or in JSON-format:
```json
$ govee-h5075.py -a Bedroom -d --start 0:20 --end 0:10 -j
[
  {
    "timestamp": "2025-01-05 08:56",
    "temperatureC": 19.8,
    "temperatureF": 67.6,
    "temperatureOffset": 0.0,
    "relHumidity": 46.7,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 08:57",
    "temperatureC": 19.8,
    "temperatureF": 67.6,
    "temperatureOffset": 0.0,
    "relHumidity": 46.7,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 08:58",
    "temperatureC": 19.8,
    "temperatureF": 67.6,
    "temperatureOffset": 0.0,
    "relHumidity": 46.7,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 08:59",
    "temperatureC": 19.8,
    "temperatureF": 67.6,
    "temperatureOffset": 0.0,
    "relHumidity": 46.7,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 09:00",
    "temperatureC": 19.8,
    "temperatureF": 67.6,
    "temperatureOffset": 0.0,
    "relHumidity": 46.6,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.0,
    "dewPointF": 46.4,
    "steamPressure": 10.7
  },
  {
    "timestamp": "2025-01-05 09:01",
    "temperatureC": 19.8,
    "temperatureF": 67.6,
    "temperatureOffset": 0.0,
    "relHumidity": 46.6,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.0,
    "dewPointF": 46.4,
    "steamPressure": 10.7
  },
  {
    "timestamp": "2025-01-05 09:02",
    "temperatureC": 19.9,
    "temperatureF": 67.8,
    "temperatureOffset": 0.0,
    "relHumidity": 46.6,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 09:03",
    "temperatureC": 19.9,
    "temperatureF": 67.8,
    "temperatureOffset": 0.0,
    "relHumidity": 46.5,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 09:04",
    "temperatureC": 19.9,
    "temperatureF": 67.8,
    "temperatureOffset": 0.0,
    "relHumidity": 46.5,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 09:05",
    "temperatureC": 19.9,
    "temperatureF": 67.8,
    "temperatureOffset": 0.0,
    "relHumidity": 46.5,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  },
  {
    "timestamp": "2025-01-05 09:06",
    "temperatureC": 19.9,
    "temperatureF": 67.8,
    "temperatureOffset": 0.0,
    "relHumidity": 46.5,
    "humidityOffset": 0.0,
    "absHumidity": 8.0,
    "dewPointC": 8.1,
    "dewPointF": 46.6,
    "steamPressure": 10.8
  }
]
```

## Configure device
To configure alarms and offset values type the following:
```
$ ./govee-h5075.py -a Schl --set-humidity-alarm "on 40.0 60.0" --set-temperature-alarm "on 16.0 25.0" --set-humidity-offset 0.0
 --set-temperature-offset 0.0
```

## Logging
If you want to get information about what's going over the air enable logging like this:
```
$ ./govee-h5075.py -a Bedroom --log DEBUG
INFO    A4:C1:38:68:41:23: Request to connect
INFO    A4:C1:38:68:41:23: Successfully connected
DEBUG   A4:C1:38:68:41:23: Start listening for notifications for device data on UUID 494e5445-4c4c-495f-524f-434b535f2011
DEBUG   A4:C1:38:68:41:23: Start listening for notifications for commands on UUID 494e5445-4c4c-495f-524f-434b535f2012
DEBUG   A4:C1:38:68:41:23: Start listening for notifications for data on UUID 494e5445-4c4c-495f-524f-434b535f2013
INFO    A4:C1:38:68:41:23: request device name
DEBUG   A4:C1:38:68:41:23: >>> read_gatt_char(00002a00-0000-1000-8000-00805f9b34fb)
DEBUG   A4:C1:38:68:41:23: <<< response data(47 56 48 35 30 37 35 5f 34 31 32 33)
INFO    A4:C1:38:68:41:23: received device name: GVH5075_4123
INFO    A4:C1:38:68:41:23: request configuration for humidity alarm
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2011, aa 03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 a9)
DEBUG   A4:C1:38:68:41:23: <<< received notification with device data(aa 03 01 a0 0f 70 17 00 00 00 00 00 00 00 00 00 00 00 00 60)
INFO    A4:C1:38:68:41:23: received configuration for humidity alarm: active, lower threshold: 40.0 %, upper threshold: 60.0 %
INFO    A4:C1:38:68:41:23: request configuration for temperature alarm
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2011, aa 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ae)
DEBUG   A4:C1:38:68:41:23: <<< received notification with device data(aa 04 01 40 06 c4 09 00 00 00 00 00 00 00 00 00 00 00 00 24)
INFO    A4:C1:38:68:41:23: received configuration for temperature alarm: active, lower threshold: 16.0 °C, upper threshold: 25.0 °C
INFO    A4:C1:38:68:41:23: request configuration for humidity offset
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2011, aa 06 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ac)
DEBUG   A4:C1:38:68:41:23: <<< received notification with device data(aa 06 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ac)
INFO    A4:C1:38:68:41:23: received configuration for humidity offset: 0.0 %
INFO    A4:C1:38:68:41:23: request configuration for temperature offset
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2011, aa 07 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ad)
DEBUG   A4:C1:38:68:41:23: <<< received notification with device data(aa 07 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ad)
INFO    A4:C1:38:68:41:23: received configuration for temperature offset: 0.0 °C
INFO    A4:C1:38:68:41:23: request hardware version
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2011, aa 0d 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 a7)
DEBUG   A4:C1:38:68:41:23: <<< received notification with device data(aa 0d 31 2e 30 33 2e 30 32 00 00 00 00 00 00 00 00 00 00 97)
INFO    A4:C1:38:68:41:23: received hardware version: 1.03.02
INFO    A4:C1:38:68:41:23: request firmware version
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2011, aa 0e 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 a4)
DEBUG   A4:C1:38:68:41:23: <<< received notification with device data(aa 0e 31 2e 30 34 2e 30 36 00 00 00 00 00 00 00 00 00 00 97)
INFO    A4:C1:38:68:41:23: received firmware version: 1.04.06
INFO    A4:C1:38:68:41:23: request current measurement and battery
DEBUG   A4:C1:38:68:41:23: >>> write_gatt_char(494e5445-4c4c-495f-524f-434b535f2012, aa 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ab)
DEBUG   A4:C1:38:68:41:23: <<< received notification after command (aa 01 07 df 12 16 0f 00 00 00 00 00 00 00 00 00 00 00 00 78)
INFO    A4:C1:38:68:41:23: received current measurement and battery level:
Timestamp:            2025-01-05 09:17
Temperature:          20.1 °C / 68.3 °F
Rel. humidity:        46.3 %
Dew point:            8.2 °C / 46.8 °F
Abs. humidity:        8.1 g/m³
Steam pressure:       10.9 mbar
Battery level:        15 %
Devicename:           GVH5075_4123
Address:              A4:C1:38:68:41:23
Manufacturer:         GV
Model:                H5075
Hardware-Rev.:        1.03.02
Firmware-Rev.:        1.04.06
Battery level:        15 %
Humidity alarm:       active, lower threshold: 40.0 %, upper threshold: 60.0 %
Temperature alarm:    active, lower threshold: 16.0 °C, upper threshold: 25.0 °C

Timestamp:            2025-01-05 09:17
Temperature:          20.1 °C / 68.3 °F
Rel. humidity:        46.3 %
Dew point:            8.2 °C / 46.8 °F
Abs. humidity:        8.1 g/m³
Steam pressure:       10.9 mbar
INFO    A4:C1:38:68:41:23: Request to disconnect
INFO    A4:C1:38:68:41:23: Successfully disconnected
```

## Usage in your python code
### Grab measurements from nearby devices
```python
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
```

### Request recorded data 
```python
async def recorded_data(address: str, start: int, end: int):

    try:
        device = GoveeThermometerHygrometer(address)
        await device.connect()
        measurements = await device.requestRecordedData(start=start, end=end)
        print("Timestamp         Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure", flush=True)
        for m in measurements:
            timestamp = m.timestamp.strftime("%Y-%m-%d %H:%M")
            print(f"{timestamp}  {m.temperatureC:.1f}°C       {m.dewPointC:.1f}°C     {m.temperatureF:.1f}°F       {m.dewPointF:.1f}°F     {m.relHumidity:.1f}%          {m.absHumidity:.1f} g/m³      {m.steamPressure:.1f} mbar", flush=True)
    finally:
        await device.disconnect()
```