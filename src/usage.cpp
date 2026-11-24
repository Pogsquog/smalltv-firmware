#include "usage.h"
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <build_secrets.h>

#ifdef USAGE_URL

static const uint32_t POLL_MS = 60UL * 1000, FIRST_POLL_MS = 3000, STALE_MS = 30UL * 60 * 1000;
static Usage    s_usage;
static bool     s_have = false;
static uint32_t s_lastOk = 0, s_lastTry = 0;
static bool     s_tried = false;

// "v1 <day> <claude today> <claude month> <req today> <req month> <cr today> <cr month> <age>"
static bool parse(char* line, Usage& u) {
  char* save = nullptr;
  char* tok = strtok_r(line, " \r\n", &save);
  if (!tok || strcmp(tok, "v1") != 0) return false;
  tok = strtok_r(nullptr, " \r\n", &save);
  if (!tok || strlen(tok) != 10) return false;
  memcpy(u.day, tok, 11);
  float* const out[] = {&u.claudeToday, &u.claudeMonth, &u.reqToday, &u.reqMonth,
                        &u.creditsToday, &u.creditsMonth};
  for (float* f : out) {
    tok = strtok_r(nullptr, " \r\n", &save);
    if (!tok) return false;
    char* end;
    *f = strtod(tok, &end);
    if (end == tok) return false;
  }
  return true;
}

static void fetch() {
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(2000);   // blocks the clock while waiting, so keep it short
  if (!http.begin(client, USAGE_URL)) return;
  if (http.GET() == HTTP_CODE_OK) {
    String body = http.getString();
    char line[160];
    strlcpy(line, body.c_str(), sizeof(line));
    Usage u;
    if (parse(line, u)) {
      u.seq = s_usage.seq + 1;
      s_usage = u;
      s_have = true;
      s_lastOk = millis();
    }
  }
  http.end();
}

void usageLoop() {
  if (WiFi.status() != WL_CONNECTED) return;
  const uint32_t wait = s_tried ? POLL_MS : FIRST_POLL_MS;
  if (millis() - s_lastTry < wait) return;
  s_lastTry = millis();
  s_tried = true;
  fetch();
}

const Usage* usageGet() {
  if (!s_have || millis() - s_lastOk > STALE_MS) return nullptr;
  return &s_usage;
}

#else   // no USAGE_URL: feature off

void usageLoop() {}
const Usage* usageGet() { return nullptr; }

#endif
