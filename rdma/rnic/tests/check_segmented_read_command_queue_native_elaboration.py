#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete actual READ graph with bounded owner-checked metadata lookahead.

All original READ profile/width/domain/module-count/clock/drain checks plus
all prior route/mux/HLS/source gates remain. Compile-only, NOT native runtime.
"""
import check_segmented_read_profile_native_elaboration as checked
import segmented_read_command_queue_native_sources as source


if __name__=='__main__':
    checked.source=source
    checked.__doc__=__doc__
    checked.main()
