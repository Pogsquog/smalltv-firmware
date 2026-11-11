// net.h - WiFi (stored credentials -> build-time fallback -> setup portal),
// mDNS, and the web server with the OTA endpoint.
#pragma once
#include <Arduino.h>

#define HOSTNAME   "smalltv"
#define SETUP_AP   "SmallTV-Setup"

// Blocks until connected, or reboots after the setup portal times out.
void netBegin();
// Call every loop iteration.
void netLoop();
bool netConnected();
// True once NTP has set the clock.
bool timeValid();
// Short status line for the clock footer, e.g. "192.168.1.50  -57dBm".
void netStatusLine(char* buf, size_t len);
