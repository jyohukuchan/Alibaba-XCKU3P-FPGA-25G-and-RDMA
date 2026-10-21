#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full8191/31 native elaboration with unchanged packet/owner/HLS paths.

Keep all prior native/MR/PTE/CQ/domain/clock/drain checks, plus exact large
identity reads' component evidence. Compile-only, no Linux/hardware runtime.
"""
import ast
from pathlib import Path
import check_segmented_padding_native_elaboration as parent
import segmented_profile_native_sources as source


def runner_source():
    t=parent.runner_source();once=source.candidate.once
    t=once(t,'import segmented_padding_native_sources as source','import segmented_profile_native_sources as source')
    t=once(t,"prefix='segmented-padding-native-elaboration-'","prefix='segmented-profile-native-elaboration-'")
    t=once(t,"prefix='as02-segmented-padding-elaboration-'","prefix='as02-segmented-profile-elaboration-'")
    t=once(t,'segmented_pre_padded_TX_selected=True)',
        'segmented_pre_padded_TX_selected=True,RNC_features=8191,CQC_features=31,software_profile=4)')
    marker="        text=root.read_text()"
    t=once(t,marker,"        if '| 4096;'not in(run/'rocev2_control_regs.v').read_text() or \\\n"
        "           '8:rd=31;'not in(run/'rocev2_cq_mmio.v').read_text():\n"
        "            raise ValueError('actual exact8191/31 profile leaves not selected')\n"+marker)
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
         dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
