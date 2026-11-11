# smalltv-firmware

Custom firmware for the GeekMagic SmallTV, the little desk cube with a 1.54"
240×240 screen and an ESP8266 inside. It replaces the stock firmware with a
deliberately small base that is easy to build on.

> Based on **[giovi321/smalltv-mod](https://github.com/giovi321/smalltv-mod)** by
> giovi321, a much fuller firmware for the same family of devices (stock ticker,
> Claude usage meter, plane radar, Home Assistant screens, themes and more). This
> project started as a stripped-down copy of it; see [Credits](#credits).
> Not affiliated with GeekMagic.

What it does today:

- **Clock**: big seven-segment HH:MM with a blinking colon, a seconds bar, the
  day and date, and the IP address and WiFi signal in the footer. Time comes from
  NTP. The timezone defaults to UK time and can be changed at build time.
- **WiFi setup**: no credentials in the code. The device tries the network it
  last joined, then an optional network set at build time, then opens a
  `SmallTV-Setup` hotspot with a captive portal where you pick your network.
- **Updates over WiFi**: upload a new firmware image from the browser at
  `http://smalltv/update`, or straight from PlatformIO with
  `pio run -t upload`.

More features will be added on top of this.

## Hardware

Only the original **GeekMagic SmallTV** is supported: an ESP-12F (ESP8266) with
4 MB flash and an ST7789 IPS panel on hardware SPI.

| Signal | GPIO |
|---|---|
| Display DC | 0 |
| Display RST | 2 |
| Display CS | 15 |
| SPI clock / data | 14 / 13 (fixed) |
| Backlight (PWM, active-low) | 5 |

Lookalikes such as the SmallTV-ultra, the SmallTV Pro, or the ESP32-C2 version use
different chips or flash layouts and aren't supported. smalltv-mod supports them.

## Building

You need [PlatformIO](https://platformio.org/) (`pip install platformio`).

```sh
cp secrets.env.example secrets.env   # optional, then edit
pio run                              # build .pio/build/smalltv/firmware.bin
```

`secrets.env` is gitignored, and every setting in it is optional:

| Key | What it does |
|---|---|
| `WIFI_SSID`, `WIFI_PASS` | Network to join when the stored credentials don't work, so a freshly flashed device can join without the setup hotspot |
| `OTA_PASS` | Password for `/update`, **Reboot** and **Forget WiFi** (user `admin`). Export it in your shell too, so the upload script can log in. Without it, anyone on your network can flash the device, and the build warns |
| `CLOCK_TZ` | [POSIX TZ string](https://github.com/nayarsystems/posix_tz_db/blob/master/zones.csv); defaults to `GMT0BST,M3.5.0/1,M10.5.0` (UK) |

`scripts/secrets.py` turns these into a generated header in the build folder,
so they never end up in the source tree.

## Flashing

### First install

- **From [smalltv-mod](https://github.com/giovi321/smalltv-mod):** upload
  `.pio/build/smalltv/firmware.bin` on the System tab's firmware upload. Both
  firmwares use the same flash layout, so moving between them over WiFi is safe.
- **From the stock GeekMagic firmware:** follow
  [smalltv-mod's flashing guide](https://github.com/giovi321/smalltv-mod#flashing)
  for your model. This image goes in the same way.
- **Over serial:** wire a USB-serial adapter to the UART pads, hold GPIO0 low at
  power-up, and run `pio run -e smalltv_serial -t upload`.

### Updates

```sh
pio run -t upload                              # http://smalltv/update
pio run -t upload --upload-port 192.168.1.50   # by IP
```

The upload runs `scripts/ota-upload.sh`, which POSTs the image with curl. On WSL
it uses Windows' `curl.exe`: WSL2 often can't resolve LAN hostnames, and uploads
over its NAT stall. You can also upload the `.bin` by hand at
`http://smalltv/update`.

An upload takes about 2 minutes, then the device reboots into the new image.

## Using it

- **First boot without WiFi:** the screen shows **WIFI SETUP**. Join the
  `SmallTV-Setup` network from a phone, pick your WiFi on the page that opens
  (or browse to `http://192.168.4.1`), and the device reboots onto your network.
  The hotspot closes after 5 minutes and the device tries the saved network
  again, so a router outage doesn't leave it stuck in setup.
- **Device page:** `http://smalltv/` (or `http://smalltv.local/`) shows the
  firmware version, time, uptime, network, signal, free memory and last reset
  reason, with **Reboot** and **Forget WiFi** buttons. Those buttons and
  firmware uploads ask for the `OTA_PASS` login, and requests sent from other
  websites are refused. **Forget WiFi** erases the
  saved network and reboots into the setup hotspot. If `WIFI_SSID` was compiled
  in, the device rejoins that network instead.
- **JSON status:** `http://smalltv/api/status`.

## Recovery

- WiFi credentials live in the ESP8266 SDK's own flash area, so flashing a new
  image keeps them.
- If an upload dies partway, the old firmware keeps running. Its web server can
  stay unresponsive until you unplug the device and plug it back in.
- An image that crashes before its web server starts can't be fixed over WiFi.
  Then the only way back is the serial header, so check each build boots before
  relying on it.

## Code layout

| File | What it does |
|---|---|
| `src/board.h` | pins and panel geometry |
| `src/display.*` | ST7789 setup (incl. the SPI mode 3 fix), backlight, text helpers, status screens |
| `src/clock_face.*` | the clock screen; redraws only what changed, so nothing flickers |
| `src/net.*` | WiFi, setup portal, mDNS, web server, OTA endpoint |
| `src/main.cpp` | boot sequence and main loop |
| `scripts/secrets.py` | generates `build_secrets.h` from `secrets.env` / the environment |
| `scripts/ota-upload.sh` | the `pio run -t upload` uploader |

Build notes:

- `PIO_FRAMEWORK_ARDUINO_LWIP2_HIGHER_BANDWIDTH` halves OTA upload time compared
  with the default low-memory network stack.
- The flash layout is `eagle.flash.4m1m.ld`: 1 MB LittleFS (unused for now),
  with the rest for the sketch and its OTA copy.

## Credits

This project is derived from
**[giovi321/smalltv-mod](https://github.com/giovi321/smalltv-mod)** by giovi321,
released under the [WTFPL](https://github.com/giovi321/smalltv-mod/blob/main/LICENSE).
Taken from it:

- the SmallTV pin map and panel geometry
- the ST7789 fix that forces SPI mode 3, without which the screen stays black
- the 4m1m flash layout, kept so the two firmwares can replace each other over WiFi
- the general approach of WiFi setup, a web portal and browser OTA on this hardware

If you want a full-featured SmallTV firmware rather than a starting point, use
smalltv-mod.

Libraries: [GFX Library for Arduino](https://github.com/moononournation/Arduino_GFX)
and [WiFiManager](https://github.com/tzapu/WiFiManager).

## License

[WTFPL](LICENSE), the same as smalltv-mod.
