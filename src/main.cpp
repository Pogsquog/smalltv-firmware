// SmallTV firmware: NTP clock, WiFi setup portal, web OTA.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <time.h>
#include <build_secrets.h>
#include "display.h"
#include "net.h"
#include "clock_face.h"

#ifndef CLOCK_TZ
#define CLOCK_TZ "GMT0BST,M3.5.0/1,M10.5.0"   // UK; see e.g. github.com/nayarsystems/posix_tz_db
#endif
#define BRIGHTNESS_PCT 90

static bool timeValid() { return time(nullptr) > 1609459200; }   // after 2021-01-01

void setup() {
  Serial.begin(115200);
  Serial.printf("\nSmallTV firmware %s\n", FW_VERSION);

  displayBegin(BRIGHTNESS_PCT);
  showMessage("SMALLTV", "v" FW_VERSION);

  netBegin();
  Serial.printf("IP %s\n", WiFi.localIP().toString().c_str());

  configTime(CLOCK_TZ, "pool.ntp.org", "time.google.com");
  showMessage("SYNCING TIME", WiFi.localIP().toString().c_str());
}

void loop() {
  netLoop();

  static bool     faceShown = false;
  static uint32_t lastDraw = 0;
  if (millis() - lastDraw < 100) return;   // 10 Hz is plenty to catch each second
  lastDraw = millis();

  if (!timeValid()) return;                // "SYNCING TIME" stays up until NTP answers
  if (!faceShown) {
    clockFaceInvalidate();
    faceShown = true;
  }
  time_t now = time(nullptr);
  struct tm t;
  localtime_r(&now, &t);
  char footer[48];
  netStatusLine(footer, sizeof(footer));
  clockFaceDraw(t, footer);
}
