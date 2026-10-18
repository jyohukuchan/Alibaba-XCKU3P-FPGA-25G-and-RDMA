#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Run the original full READ app probe unchanged with the compiled backend.

Same bench, clocks, finite controller, real generated HLS, all wire bytes,
BAR readback and sentinels. Verilator is a two-state additional check only.
Use a fresh report/log; preserve the original Icarus timeout/failure evidence.
"""
import probe_rw_read as original
import rw_sim_verilator as compiled


if __name__=='__main__':
    original.rw_sim=compiled
    original.main()
