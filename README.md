# govee-h5075-thermo-hygrometer

Shell script and python lib for Govee H5075 thermometer / hygrometer for Linux, Raspberry Pis and Windows.

## Preconditions
Install the python module [bleak](https://bleak.readthedocs.io/en/latest/)

```
$ pip install bleak
```

## Help
```
$ ./govee-h5075.py --help
usage: govee-h5075.py [-h] [-s] [-m] [-i INFO] [-d DATA] [--start START] [--end END] [-j]

Shell script in order to request Govee H5075 temperature humidity sensor

options:
  -h, --help            show this help message and exit
  -s, --scan            scan for devices for 20 seconds
  -m, --measure         capture measurements/advertisements from nearby devices
  -i INFO, --info INFO  request device information for given mac or alias
  -d DATA, --data DATA  request recorded data for given mac or alias
  --start START         request recorded data from start time expression, e.g. 480:00 (here max. value 20 days)
  --end END             request recorded data to end time expression, e.g. 480:00 (here max. value 20 days)
  -j, --json            print in JSON format
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
In order to get friendly names and request device by name you can put a ```.known_govees```-file in your home directory like this:
```
A4:C1:38:68:41:23 Bedroom
A4:C1:38:5A:20:A1 Livingroom
```

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
$ ./govee-h5075.py -i Bedr
MAC-Address:    A4:C1:38:5A:20:A1
Devicename:     GVH5075_20A1
Manufacturer:   GV
Model:          H5075
Hardware-Rev.:  1.03.02
Firmware-Rev.:  1.04.06
```

Note: The alias has been used. It works also if you just enter the first letters of the alias.

If you want to have the result in JSON-format you can call it like this:
```
$ ./govee-h5075.py -i Bedr -j
{
  "mac": "A4:C1:38:5A:20:A1",
  "name": "GVH5075_20A1",
  "manufacturer": "GV",
  "model": "H5075",
  "hardware": "1.03.02",
  "firmware": "1.04.06"
}
```

## Request historical data
In this example recorded data of the last 10 minutes is requested.
```
$ govee-h5075.py -d Badr --start 0:10
Timestamp         Temperature  Dew point  Temperature  Dew point  Rel. humidity  Abs. humidity  Steam pressure
2023-09-19 13:39  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:40  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:41  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:42  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:43  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:44  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:45  22.0°C       13.9°C     71.6°F       57.0°F     60.3%          11.7 g/m³      15.9 mbar
2023-09-19 13:46  22.0°C       13.9°C     71.6°F       57.0°F     60.2%          11.7 g/m³      15.9 mbar
2023-09-19 13:47  22.0°C       13.9°C     71.6°F       57.0°F     60.2%          11.7 g/m³      15.9 mbar
2023-09-19 13:48  22.0°C       13.9°C     71.6°F       57.0°F     60.2%          11.7 g/m³      15.9 mbar
2023-09-19 13:49  22.0°C       13.9°C     71.6°F       57.0°F     60.2%          11.7 g/m³      15.9 mbar
```

or in JSON-format:
```json
$ govee-h5075.py -d Bedroom --start 0:20 --end 0:10 -j
[
  {
    "timestamp": "2023-09-19 13:31",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.4,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:32",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.4,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:33",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.4,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:34",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.4,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:35",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.4,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:36",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.4,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:37",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.3,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:38",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.3,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:39",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.3,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:40",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.3,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  },
  {
    "timestamp": "2023-09-19 13:41",
    "temperatureC": 22.0,
    "temperatureF": 71.6,
    "relHumidity": 60.3,
    "absHumidity": 11.7,
    "dewPointC": 13.9,
    "dewPointF": 57.0,
    "steamPressure": 15.9
  }
]
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