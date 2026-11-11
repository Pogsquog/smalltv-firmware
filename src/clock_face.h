// clock_face.h - the clock screen: big seven-segment HH:MM, a seconds bar,
// the date, and a one-line network status footer.
#pragma once
#include <time.h>

// Forget what is on screen so the next clockFaceDraw() repaints everything.
void clockFaceInvalidate();
// Cheap to call often: only redraws the parts that changed.
void clockFaceDraw(const struct tm& t, const char* footer);
