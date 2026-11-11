#include "display.h"
#include "board.h"
#include <SPI.h>

// The SmallTV's ST7789 only latches SPI in mode 3, but Arduino_GFX forces
// mode 2 on the ESP8266, which leaves the screen black. Force mode 3.
class ST7789_SmallTV : public Arduino_ST7789 {
 public:
  using Arduino_ST7789::Arduino_ST7789;
  bool begin(int32_t speed = GFX_NOT_DEFINED) override {
    _override_datamode = SPI_MODE3;
    return Arduino_TFT::begin(speed);
  }
};

Arduino_GFX* gfx = nullptr;

void displaySetBrightness(uint8_t pct) {
  if (pct > 100) pct = 100;
  uint8_t steps = (uint8_t)((int)pct * 255 / 100);
  analogWrite(TFT_BL, BL_INVERTED ? 255 - steps : steps);
}

void displayBegin(uint8_t brightnessPct) {
  // Backlight first: a lit screen means the sketch got this far.
  pinMode(TFT_BL, OUTPUT);
  analogWriteRange(255);
  displaySetBrightness(brightnessPct);

  Arduino_DataBus* bus = new Arduino_HWSPI(TFT_DC, TFT_CS);
  gfx = new ST7789_SmallTV(bus, TFT_RST, 0 /*rotation*/, true /*IPS*/, TFT_W, TFT_H,
                           0, 0, 0, TFT_ROW_OFFSET2);
  gfx->begin();
  gfx->setTextWrap(false);
  gfx->fillScreen(C_BLACK);
}

int textWidth(const char* s, uint8_t size) { return (int)strlen(s) * 6 * size; }

void drawCentered(const char* s, int y, uint8_t size, uint16_t fg, uint16_t bg) {
  int x = (TFT_W - textWidth(s, size)) / 2;
  if (x < 0) x = 0;
  gfx->setTextSize(size);
  gfx->setTextColor(fg, bg);   // with a background colour: overdraws, no flicker
  gfx->setCursor(x, y);
  gfx->print(s);
}

// Largest size <= maxSize that fits the screen width with a small margin.
static uint8_t fitSize(const char* s, uint8_t maxSize) {
  for (uint8_t sz = maxSize; sz > 1; sz--)
    if (textWidth(s, sz) <= TFT_W - 8) return sz;
  return 1;
}

void showMessage(const char* title, const char* line1, const char* line2, uint16_t titleColor) {
  gfx->fillScreen(C_BLACK);
  drawCentered(title, 80, fitSize(title, 3), titleColor);
  if (line1) drawCentered(line1, 125, fitSize(line1, 2), C_GRAY);
  if (line2) drawCentered(line2, 155, fitSize(line2, 2), C_GRAY);
}

void showSetupPortal(const char* apName, const char* ip) {
  gfx->fillScreen(C_BLACK);
  drawCentered("WIFI SETUP", 20, 3, C_YELLOW);
  drawCentered("Join network:", 70, 2, C_GRAY);
  drawCentered(apName, 95, fitSize(apName, 3), C_WHITE);
  drawCentered("then open:", 145, 2, C_GRAY);
  char url[32];
  snprintf(url, sizeof(url), "http://%s", ip);
  drawCentered(url, 170, fitSize(url, 2), C_GREEN);
  drawCentered("(setup times out in 5 min)", 220, 1, C_GRAY);
}
