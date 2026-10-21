#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze the exact29-case native runner with matched pre-padded LAST RTL.

All prior tests, oracles, original clocks/tails/drains and1200s/30s bounds
remain. This is not hardware/Linux/timing qualification or default selection.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_wire_native_full as parent

ROOT=parent.ROOT;once=parent.once


def runner_source():
    t=parent.runner_source()
    t=once(t,'import segmented_wire_native_sources as source','import segmented_padding_native_sources as source')
    t=once(t,"'atomic_CQ_retirement_fanout','per_packet_lifetime_and_cache_advance_wired']",
        "'atomic_CQ_retirement_fanout','per_packet_lifetime_and_cache_advance_wired','segmented_pre_padded_TX_selected']")
    t=once(t,"prefix='segmented-wire-native-full-'","prefix='segmented-padding-native-full-'")
    t=once(t,"prefix='as02-segmented-wire-obj-'","prefix='as02-segmented-padding-obj-'")
    t=once(t,"prefix='as02-segmented-wire-artifacts-'","prefix='as02-segmented-padding-artifacts-'")
    t=once(t,'large_native_wire_CQ=False,planned_cases=29',
        'segmented_pre_padded_TX_selected=True,large_native_wire_CQ=False,planned_cases=29')
    ast.parse(t);return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-padding-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
