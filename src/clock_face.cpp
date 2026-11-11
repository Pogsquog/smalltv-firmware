#include "clock_face.h"
#include "display.h"
#include "board.h"

// ---- layout ---------------------------------------------------------------
static const int DIGIT_W = 46, DIGIT_H = 92, SEG_T = 10;
static const int DIGIT_Y = 56;
static const int DIGIT_X[4] = {8, 60, 134, 186};
static const int COLON_X = 120;                 // centre
static const int BAR_Y = DIGIT_Y + DIGIT_H + 12, BAR_H = 4, BAR_X = 8, BAR_W = TFT_W - 16;
static const int DAY_Y = 20, DATE_Y = 184, FOOTER_Y = 228;

static const uint16_t C_DIGIT = C_WHITE;
static const uint16_t C_ACCENT = C_CYAN;

// ---- seven-segment digits ---------------------------------------------------
//  aaa
// f   b
//  ggg
// e   c
//  ddd
static const uint8_t kSegments[10] = {
  //  gfedcba
  0b0111111, 0b0000110, 0b1011011, 0b1001111, 0b1100110,
  0b1101101, 0b1111101, 0b0000111, 0b1111111, 0b1101111,
};

// Every segment is painted, lit or black, so a change never clears the digit
// first (no flicker). Segments don't overlap, so the order doesn't matter.
static void drawDigit(int x, int y, int d) {
  const uint8_t m = (d >= 0 && d <= 9) ? kSegments[d] : 0;
  const int t = SEG_T, w = DIGIT_W, h = DIGIT_H, half = h / 2;
  const int g = 2;          // gap between segments
  const int r = t / 2 - 1;  // corner radius
  const int hLen = w - 2 * t;             // horizontal: between the verticals, so no overlap
  const int vLen = half - t / 2 - 2 * g;  // vertical segment length
  auto c = [m](uint8_t bit) { return (m & bit) ? C_DIGIT : C_BLACK; };
  gfx->fillRoundRect(x + t, y, hLen, t, r, c(0x01));                 // a
  gfx->fillRoundRect(x + w - t, y + t / 2 + g, t, vLen, r, c(0x02));     // b
  gfx->fillRoundRect(x + w - t, y + half + g, t, vLen, r, c(0x04));      // c
  gfx->fillRoundRect(x + t, y + h - t, hLen, t, r, c(0x08));         // d
  gfx->fillRoundRect(x, y + half + g, t, vLen, r, c(0x10));              // e
  gfx->fillRoundRect(x, y + t / 2 + g, t, vLen, r, c(0x20));             // f
  gfx->fillRoundRect(x + t, y + half - t / 2, hLen, t, r, c(0x40));  // g
}

static void drawColon(bool on) {
  const uint16_t c = on ? C_ACCENT : C_BLACK;
  const int s = SEG_T;
  gfx->fillRoundRect(COLON_X - s / 2, DIGIT_Y + DIGIT_H / 3 - s / 2, s, s, 2, c);
  gfx->fillRoundRect(COLON_X - s / 2, DIGIT_Y + 2 * DIGIT_H / 3 - s / 2, s, s, 2, c);
}

// ---- state: what is currently on screen ------------------------------------
static int  s_digits[4];
static int  s_colon;
static int  s_barPx;
static int  s_yday;
static char s_footer[48];

void clockFaceInvalidate() {
  for (int& d : s_digits) d = -2;
  s_colon = -1;
  s_barPx = -1;
  s_yday = -1;
  s_footer[0] = '\x01';  // never equal to a real footer
  s_footer[1] = 0;
  gfx->fillScreen(C_BLACK);
}

static const char* const kDays[] = {"SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY",
                                    "THURSDAY", "FRIDAY", "SATURDAY"};
static const char* const kMonths[] = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"};

void clockFaceDraw(const struct tm& t, const char* footer) {
  // Digits: redraw only the ones that changed.
  const int now[4] = {t.tm_hour / 10, t.tm_hour % 10, t.tm_min / 10, t.tm_min % 10};
  for (int i = 0; i < 4; i++) {
    if (now[i] != s_digits[i]) {
      s_digits[i] = now[i];
      drawDigit(DIGIT_X[i], DIGIT_Y, now[i]);
    }
  }

  // Colon blinks with the seconds.
  const int colon = (t.tm_sec % 2 == 0);
  if (colon != s_colon) {
    s_colon = colon;
    drawColon(colon);
  }

  // Seconds bar fills across the minute; only the changed slice is painted.
  const int px = BAR_W * t.tm_sec / 59;
  if (px != s_barPx) {
    if (px < s_barPx || s_barPx < 0) {
      gfx->fillRect(BAR_X, BAR_Y, BAR_W, BAR_H, C_DKGRAY);
      s_barPx = 0;
    }
    gfx->fillRect(BAR_X + s_barPx, BAR_Y, px - s_barPx, BAR_H, C_ACCENT);
    s_barPx = px;
  }

  // Day name and date, once a day.
  if (t.tm_yday != s_yday) {
    s_yday = t.tm_yday;
    gfx->fillRect(0, DAY_Y, TFT_W, 24, C_BLACK);
    drawCentered(kDays[t.tm_wday % 7], DAY_Y, 3, C_ACCENT);
    char date[24];
    snprintf(date, sizeof(date), "%d %s %d", t.tm_mday, kMonths[t.tm_mon % 12], 1900 + t.tm_year);
    gfx->fillRect(0, DATE_Y, TFT_W, 24, C_BLACK);
    drawCentered(date, DATE_Y, 3, C_WHITE);
  }

  // Footer (IP / WiFi state), when it changes.
  if (strncmp(footer, s_footer, sizeof(s_footer)) != 0) {
    strlcpy(s_footer, footer, sizeof(s_footer));
    // Text is drawn with a background, so only the margins need clearing.
    const int w = textWidth(footer, 1), x = (TFT_W - w) / 2;
    gfx->fillRect(0, FOOTER_Y, x, 8, C_BLACK);
    gfx->fillRect(x + w, FOOTER_Y, TFT_W - x - w, 8, C_BLACK);
    drawCentered(footer, FOOTER_Y, 1, C_GRAY);
  }
}
