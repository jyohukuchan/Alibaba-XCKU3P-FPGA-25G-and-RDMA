// SPDX-License-Identifier: BSD-2-Clause-Views
// Adapter for the missing generated header in upstream standalone RoCEv2.
// This is a synthesis probe, not an adopted or validated hardware endpoint.
#pragma once
#include "fns_config.hpp"
#define RETRANS_EN
// 250MHz transport clock, also used by C simulation (no shortened timers).
#define AS02_TIMER_CLOCK_PS 4000
// Preserve all eight entries, but infer resettable registers and real RAW
// dependencies instead of the upstream false-dependency pipelined BRAM.
#define AS02_TIMER_REGISTER_TABLE 1
#ifndef AS02_SMALL_FIFO_SRL
#define AS02_SMALL_FIFO_SRL 1
#endif
