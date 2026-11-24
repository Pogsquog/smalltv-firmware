// usage.h - polls the AI usage hub (usage/hub.py) for today's and this
// month's Claude and Copilot totals. Enabled when USAGE_URL is set at build time.
#pragma once
#include <stdint.h>

struct Usage {
  char     day[11];          // hub's "today", YYYY-MM-DD
  float    claudeToday, claudeMonth;     // USD
  float    reqToday, reqMonth;           // Copilot premium requests
  float    creditsToday, creditsMonth;   // Copilot AI credits
  uint32_t seq;              // bumps on every successful fetch
};

// Call every loop iteration; fetches once a minute.
void usageLoop();
// Latest data, or nullptr if never fetched or older than 30 minutes.
const Usage* usageGet();
