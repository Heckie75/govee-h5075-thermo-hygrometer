## Get version (firmware)
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


## Get hardware version
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
