// clock_face.h - the clock screen: big seven-segment HH:MM, a seconds bar,
// the date (or today's AI usage), and a one-line network status footer.
#pragma once
#include <time.h>
#include "usage.h"

// Forget what is on screen so the next clockFaceDraw() repaints everything.
void clockFaceInvalidate();
// Cheap to call often: only redraws the parts that changed. With usage data
// that shows activity today, the date line becomes a Claude / Copilot table.
void clockFaceDraw(const struct tm& t, const char* footer, const Usage* usage);
