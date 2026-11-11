// board.h - pin map for the original GeekMagic SmallTV (ESP-12F / ESP8266).
// 1.54" 240x240 ST7789 IPS on hardware SPI. Taken from giovi321/smalltv-mod's
// src/board_esp8266.h, confirmed working on this unit.
#pragma once

#define TFT_DC      0   // data/command (boot-strap pin)
#define TFT_RST     2   // reset        (boot-strap pin)
#define TFT_CS     15   // chip select  (boot-strap pin)
#define TFT_BL      5   // backlight PWM, active-low
// HW SPI is fixed on the ESP8266: SCLK = GPIO14, MOSI = GPIO13.

#define TFT_W     240
#define TFT_H     240
// The ST7789 has 240x320 of RAM; rotations 2/3 need an 80-row offset.
#define TFT_ROW_OFFSET2 80

#define BL_INVERTED true
