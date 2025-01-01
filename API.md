# Request device information and configuration
```
uuid: 494e5445-4c4c-495f-524f-434b535f2011
handle: 0x11
```

## Request alarm for humidity (command aa03)
```
[A4:C1:38:5A:20:A1][LE]> char-write-req 0x11 aa030000000000000000000000000000000000a9
Notification handle = 0x0011 value: aa 03 01 b8 0b 4c 1d 00 00 00 00 00 00 00 00 00 00 00 00 4a
                                          |  |     + upper limit, here 0x1d4c -> 7500 -> 7500 / 100 = 75.00%
                                          |  + lower limit, here 0x0bb8 -> 3000 -> 3000 / 100 = 30.00%
                                          + flag for on (0x01) and off (0x00)
Characteristic value was written successfully
```

## Request alarm for temperature (command aa04)
```
[A4:C1:38:5A:20:A1][LE]> char-write-req 0x11 aa040000000000000000000000000000000000ae
Notification handle = 0x0011 value: aa 04 01 dc 05 fc 08 00 00 00 00 00 00 00 00 00 00 00 00 82
                                          |  |     + upper limit, here 0x08fc -> 2300 -> 2300 / 100 = 23.0°C
                                          |  + lower limit, here 0x05dc -> 1500 -> 1500 / 100 = 15.0°C
                                          + flag for on (0x01) and off (0x00)
Characteristic value was written successfully
```

## Request current calibration for humidity (command aa06)
```
[A4:C1:38:68:41:23][LE]> char-write-req 0x11 aa060000000000000000000000000000000000ac
Notification handle = 0x0011 value: aa 06 f6 ff 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 a5
                                          +---+ 0xfff6 (=65386) => 0xfff6 - 2^16 = -10 (-0.1%)
Characteristic value was written successfully
```

Range is from -20.0% to 20% in steps of 0.1%
* min: 0xf830 (=63536) => 0xf830 - 2^16 = -2000 (-20.00%)
* zero: 0x0000 => 0.0%
* max: 0x012c => 300 (3.00°C)

## Request current calibration for temperature (command aa07)
```
[A4:C1:38:68:41:23][LE]> char-write-req 0x11 aa070000000000000000000000000000000000ad
Notification handle = 0x0011 value: aa 07 0a 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 a7
                                          +---+ 0x000a (=10) => 10 (0.1°C)
Characteristic value was written successfully
```

Range is from -3.0°C to 3.0°C in steps of 0.1°C
* min: 0xfed4 (=65236) => 0xfed4 - 2^16 = -300 (-3.0°C)
* zero: 0x0000 => 0.0°C
* max: 0x012c => 300 (3.00°C)

## Request battery level (command aa08)
```
[A4:C1:38:5A:20:A1][LE]> char-write-req 0x11 aa080000000000000000000000000000000000a2
Notification handle = 0x0011 value: aa 08 25 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 87
                                          + 0x25 -> 37%
Characteristic value was written successfully
```

## Request MAC address (command aa0c)
```
[A4:C1:38:5A:20:A1][LE]> char-write-req 0x11 aa0c0000000000000000000000000000000000a6
Notification handle = 0x0011 value: aa 0c a1 20 5a 38 c1 a4 e8 10 00 00 00 00 00 00 00 00 00 d8
                                          |               | +---+ unknown
                                          +---------------+ MAC address in reverse order, here: A4:C1:38:5A:20:A1

Notification handle = 0x0011 value: aa 0c 23 41 68 38 c1 a4 b8 5f 00 00 00 00 00 00 00 00 00 16

Notification handle = 0x0011 value: aa 0c dd 1d 3b 38 c1 a4 e0 40 00 00 00 00 00 00 00 00 00 a0

Characteristic value was written successfully
```

## Get hardware version (command aa0d)
```
[A4:C1:38:68:41:23][LE]> char-write-req 0x11 aa0d0000000000000000000000000000000000a7
Notification handle = 0x0011 value: aa 0d 31 2e 30 33 2e 30 32 00 00 00 00 00 00 00 00 00 00 97
                                          ^------------------^ Ascii of version here: 1.03.02
Characteristic value was written successfully
```

Example code:
```python
>>> chr(0x31)+chr(0x2e)+chr(0x30)+chr(0x33)+chr(0x2e)+chr(0x30)+chr(0x32)
'1.03.02'
```

## Get version (firmware) (command aa0e)
```
[A4:C1:38:68:41:23][LE]> char-write-req 0x11 aa0e0000000000000000000000000000000000a4
Notification handle = 0x0011 value:          aa 0e 31 2e 30 34 2e 30 36 00 00 00 00 00 00 00 00 00 00 97
                                                   ^------------------^ Ascii of version here: 1.04.06
Characteristic value was written successfully
```

Example code:
```python
>>> chr(0x31)+chr(0x2e)+chr(0x30)+chr(0x34)+chr(0x2e)+chr(0x30)+chr(0x36)
'1.04.06'
```

# Calibration
```
uuid: 494e5445-4c4c-495f-524f-434b535f2012
handle: 0x15
```

## Calibrate temperature
Range is from -3.0°C to 3.0°C in steps of 0.1°C

```
3307d4fe0000000000000000000000000000001e
    +--+ 0xfed4 (=65236) => 0xfed4 - 2^16 = -300 (-3.00°C)

3307000000000000000000000000000000000034
    +--+ 0.0°C
	
33072c010000000000000000000000000000001e
    +---+ 0x012c => 300 (3.00°C)
```

## Calibrate humidity
Range is from -20.0% to 20% in steps of 0.1%

```
330630f8000000000000000000000000000000fd
    +--+ 0xf830 (=63536) => 0xf830 - 2^16 = -2000 (-20.00%)

3306000000000000000000000000000000000035
    +--+ 0.00%
```

# Measurements
Data control:
```
uuid: 494e5445-4c4c-495f-524f-434b535f2012
handle 0x15
```

Data transmission (notification for historical data):
```
uuid: 494e5445-4c4c-495f-524f-434b535f2013
handle: 0x19
```

## request current measurement
```
[A4:C1:38:5A:20:A1][LE]> char-write-req 0x15 aa010000000000000000000000000000000000ab
Notification handle = 0x0015 value: aa 01 08 65 12 5d 25 00 00 00 00 00 00 00 00 00 00 00 00 ac
                                          |     |     + current battery level, here 0x25 -> 37%
                                          |     + current humidity, here 0x125d -> 4701 / 100 = 47.01%
                                          + current temperature, here 0x0865 -> 2149 / 100 = 21.49°C
Characteristic value was written successfully
```

## request historical data 
Max 20 days (or 28,800 seconds, 0x7080)

```
[A4:C1:38:68:41:23][LE]> char-write-req 0x15 3301001500020000000000000000000000000035
                                             |   |   |   |                         + Byte 20: checksum XORed all bytes from 1 to byte 19 
                                             |   |   |   + Byte 7 - 19: static zeros
                                             |   |   + Byte 5 - 6 (2 bytes): minutes back in the past when to end
                                             |   + Byte 3 - 4 (2 bytes): minutes back in the past when to start
                                             ^ Byte 1 - 2: Command 0x3301

Notification handle = 0x0015 value: 33 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 32
                                    |                                                        + Byte 20: checksum XORed all bytes from 1 to byte 19 
                                    ^ Byte 1 - 2: notification on handle 0x15 that request was successful and data transfer will start
Characteristic value was written successfully

Notification handle = 0x0019 value: 00 15 03 71 e7 03 75 cf 03 71 e7 03 75 cf 03 71 e6 03 75 ce
                                    |     + Byte 3 - 5, 6 - 8, 9 - 11, 12 - 14, 15 - 17, 18 - 20 (6 records each 3 bytes): encoded temperature and humidity (see 'decode temperature and humitity') 
                                    + Byte 1 - 2: minute back of first record, here now - 21m


Notification handle = 0x0019 value: 00 0f 03 75 cf 03 75 cf 03 75 ce 03 75 cf 03 75 ce 03 75 cf
Notification handle = 0x0019 value: 00 09 03 75 cf 03 75 cf 03 75 d1 03 75 d0 03 75 d0 03 75 cf
Notification handle = 0x0019 value: 00 03 03 75 cf 03 75 cf 03 75 ce ff ff ff ff ff ff ff ff ff

Notification handle = 0x0015 value: ee 01 00 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 eb
                                    |     |                                                  + Byte 20: checksum XORed all bytes from 1 to byte 19 
                                    |     + Byte 3 - 4: Number of messages (notifications) sent
                                    + Byte 1 - 2: notification on handle 0x15 that data transfer has finished
```

get all available data (max 20 days)
```
[A4:C1:38:68:41:23][LE]> char-write-req 0x15 33017080000100000000000000000000000000c3
```


## decode temperature and humitity

Example:
1. Three octets are: 03 71 e7
2. Convert to decimal: 0x0371e7, v = 225767
3. Get rel. humidity in %: h = v % 1000 / 10, h = 76.7%
4. get temperature in °C (positiv value): t = int(v / 1000) / 10, v = 22.5°C
5. get temperature in °C (negative value): see example code

Example code:
```python
    def decodeMeasurement(bytes) -> 'tuple[float,float]':

        # Note that integer requires 4 bytes (fill with 00), e.g. 0x0371e7 --> 0x000371e7
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
```


# Measure in realtime
```
> bluetoothctl
[bluetooth]# scan le
...
[CHG] Device A4:C1:38:5A:20:A1 ManufacturerData Key: 0xec88
[CHG] Device A4:C1:38:5A:20:A1 ManufacturerData Value:
  00 03 7d a9 64 00
  |           + Byte 5: Battery level, here 100%
  ^ Byte 1 - 4: encoded temperature and humidity (see 'decode temperature and humidity')
...
```
