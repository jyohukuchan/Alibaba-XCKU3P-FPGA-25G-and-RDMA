#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual separate32767/127 register/CQ profile including whole Immediate.

Keep every prior controller/CQ case, add eight whole large Immediate owners.
Only newly supported Immediate rejection inputs move to1MiB+1. Upstream
controller/ticket/commit/retire endpoints modeled; kernel profile NOT matched.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_read_profile_rtl as base

ROOT=base.ROOT;once=base.source.once


def runner_source():
    t=Path(base.__file__).read_text()
    t=once(t,'import derive_segmented_read_profile as source','import derive_segmented_immediate as source')
    t=once(t,'after=16383 if disabled is None else 16383^','after=32767 if disabled is None else 32767^')
    t=once(t,"'host_value!=63)$fatal(1,\"message feature ABI\")'","'host_value!=127)$fatal(1,\"message feature ABI\")'")
    t=once(t,"    return source.once(t,' if(pub_published!=8 || pub_acked!=8)',body+' if(pub_published!=12 || pub_acked!=12)')",
        "    for seq,(op,length)in enumerate([(op,n)for op in [5,6]for n in [4097,8193,65537,1048576]],13):\n"
        "        body+=f'publish({old.cq.owner(op,pd=17,sequence=seq,tag=seq,length=length,immediate=0x89abcdef)},0,{seq},0);\\n'\n"
        "    return source.once(t,' if(pub_published!=8 || pub_acked!=8)',body+' if(pub_published!=20 || pub_acked!=20)')")
    t=once(t,'if generated[q]!=parent[q]','if q not in parent or generated[q]!=parent[q]')
    t=once(t,"if changed!={'rocev2_wqe_admission.v','rocev2_wqe_hls_sq.v','rocev2_control_regs.v','rocev2_cq_mmio.v'}:",
        "if changed!={n+'.v'for n in ['rocev2_wqe_lifetime','rocev2_wqe_mac_tx','rocev2_wqe_tx_lifetime','rocev2_wqe_response_guard','rocev2_wqe_replay','rocev2_shared_hls_transport','rocev2_integrity_transport','rocev2_wqe_admission','rocev2_wqe_hls_sq','rocev2_cq_mmio','rocev2_control_regs','rocev2_segmented_executor_mux','rocev2_segmented_source_executor','rocev2_segmented_tx_padding']}:")
    for a,b in [("prefix='segmented-read-profile-rtl-'","prefix='segmented-immediate-profile-rtl-'"),
        ('RNC_features=16383,CQC_features=63','RNC_features=32767,CQC_features=127'),
        ('length=1048577 if op in [1,2,3]else 8193','length=1048577 if op in [1,2,3,5,6]else 8193'),
        ('CQ_old8_and_READ4','CQ_old12_and_Immediate8'),("item['published_and_acked']=12","item['published_and_acked']=20")]:t=once(t,a,b)if t.count(a)==1 else t.replace(a,b)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-immediate-profile-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
