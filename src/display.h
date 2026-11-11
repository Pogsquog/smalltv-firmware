// display.h - panel bring-up, backlight, and simple text helpers.
#pragma once
#include <Arduino_GFX_Library.h>

// RGB565 colours
#define C_BLACK  0x0000
#define C_WHITE  0xFFFF
#define C_GRAY   0x8410
#define C_DKGRAY 0x2104
#define C_RED    0xF800
#define C_GREEN  0x07E0
#define C_YELLOW 0xFFE0
#define C_CYAN   0x07FF
#define C_ORANGE 0xFD20

extern Arduino_GFX* gfx;

void displayBegin(uint8_t brightnessPct);
void displaySetBrightness(uint8_t pct);

// Built-in 6x8 font, scaled by `size`.
int  textWidth(const char* s, uint8_t size);
void drawCentered(const char* s, int y, uint8_t size, uint16_t fg, uint16_t bg = C_BLACK);

// Full-screen status messages.
void showMessage(const char* title, const char* line1 = nullptr, const char* line2 = nullptr,
                 uint16_t titleColor = C_WHITE);
void showSetupPortal(const char* apName, const char* ip);
