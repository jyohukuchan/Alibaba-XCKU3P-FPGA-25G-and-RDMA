#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked whole-native compile extension for the matched LAST padding path.

Keep all parent module/domain/clock/drain/geometry checks; require precisely
one actual new padding instance. No runtime/native-Linux/hardware signoff.
"""
import ast
from pathlib import Path
import check_segmented_wire_native_elaboration as parent
import segmented_padding_native_sources as source


def runner_source():
    t=Path(parent.__file__).read_text();once=source.candidate.once
    t=once(t,'import segmented_wire_native_sources as source','import segmented_padding_native_sources as source')
    t=once(t,"prefix='segmented-wire-native-elaboration-'","prefix='segmented-padding-native-elaboration-'")
    t=once(t,"prefix='as02-segmented-wire-elaboration-'","prefix='as02-segmented-padding-elaboration-'")
    t=once(t,'large_native_wire_CQ_runtime=False,default_graph_changed=False)',
        'large_native_wire_CQ_runtime=False,default_graph_changed=False,segmented_pre_padded_TX_selected=True)')
    t=once(t,"        model=(ram/'native.vvp').read_text();wanted=baseline['module_counts']",
        "        model=(ram/'native.vvp').read_text();wanted=baseline['module_counts']\n"
        "        if model.count('\\\"rocev2_segmented_tx_padding\\\"')!=1 or \\\n"
        "           'rocev2_segmented_tx_padding tx_padding ('not in(run/'rocev2_integrity_transport.v').read_text():\n"
        "            raise ValueError('one actual private segmented-HLS padding selection required')")
    ast.parse(t)
    return t


def main():
    t=runner_source()
    # The wrapper and exact parent generator are both in normal helper hashes.
    exec(compile(t,str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
