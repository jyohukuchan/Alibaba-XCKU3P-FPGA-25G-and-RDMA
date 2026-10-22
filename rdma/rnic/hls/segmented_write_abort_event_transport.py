#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Decouple real retransmission-table initialization from scalar fault barriers.

Same 2000-entry one-entry-per-invocation reset sweep, RAM, insertion/readback,
owner checks and sticky failure. Only the metadata fault transport becomes a
single sticky event and real collector; ordinary calls emit no status token.
This is an unqualified separate source cohort, not a timing/native/drain proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_write_abort_scheduled_transport as parent

ROOT=parent.ROOT;NAME=parent.NAME;once=parent.once
PARENT=ROOT/'rdma/rnic/build/native-write-abort-scheduled-transport-001'
META='hls/ib_transport_protocol/retransmitter/retransmitter.hpp'

COLLECTOR=r'''
// Sticky status, not a per-invocation rendezvous with unrelated parser work.
template<int INSTID=0>
void as02_retrans_meta_fault_collect(stream<ap_uint<1>>& events,ap_uint<1>& regFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static bool fault=false;
#pragma HLS reset variable=fault
    // The actual producer emits exactly one token on its first real error.
    // Any token is conservatively a fault; no event can authorize completion.
    if(!events.empty()){events.read();fault=true;}
    regFault=fault;
}
'''


def derive():
    out=parent.derive();t=out[META];a=t.index('void retrans_meta_table(')
    begin=t.rfind('template ',0,a);end=t.index('\n}',a)+2
    original=t[begin:end];engine=once(original,'void retrans_meta_table(',
        'void as02_retrans_meta_table_event(')
    engine=once(engine,'stream<as02ReqInsert>& request_inserted,ap_uint<1>& regRequestMetaFault)',
        'stream<as02ReqInsert>& request_inserted,stream<ap_uint<1>>& meta_fault_events)')
    engine=once(engine,'static bool request_fault=false;regRequestMetaFault=request_fault;if(request_fault)return;',
        'static bool request_fault=false;\n#pragma HLS reset variable=request_fault\n    if(request_fault)return;')
    error='request_fault=true;regRequestMetaFault=1;return;'
    if engine.count(error)!=2:raise ValueError('both actual invalid-index/readback fault sites required')
    engine=engine.replace(error,'request_fault=true;meta_fault_events.write(1);return;')
    # Legacy component API calls the SAME actual engine and sticky collector.
    # There is no duplicate RAM, echoed insertion proof or C++-only algorithm.
    signature=original[:original.index('{')+1]
    compat=signature+r'''
    static stream<ap_uint<1>> meta_fault_events("meta_fault_events");
#pragma HLS STREAM depth=2 variable=meta_fault_events
    as02_retrans_meta_table_event<INSTID>(meta_upd_req,meta_rsp,request_inserted,meta_fault_events);
    as02_retrans_meta_fault_collect<INSTID>(meta_fault_events,regRequestMetaFault);
}'''
    t=t[:begin]+engine+'\n'+COLLECTOR+'\n'+compat+t[end:]
    old='retrans_meta_table<INSTID>( rt_metaReqFifo,\n\t\t\t\t\t\trt_metaRspFifo,request_inserted,mf);'
    new=r'''// Real native path: the table never rendezvous on every successful
    // invocation with the slower parser's scalar fault-report collector.
    static stream<ap_uint<1>> meta_fault_events("meta_fault_events");
    #pragma HLS STREAM depth=2 variable=meta_fault_events
    as02_retrans_meta_table_event<INSTID>(rt_metaReqFifo,rt_metaRspFifo,request_inserted,meta_fault_events);
    as02_retrans_meta_fault_collect<INSTID>(meta_fault_events,mf);'''
    out[META]=once(t,old,new)
    return out


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve all prior cohorts')
    info=json.loads((PARENT/'source.json').read_text());original=parent.derive();files=derive()
    before={str(q.relative_to(ROOT)):digest(q)for q in PARENT.rglob('*')if q.is_file()}
    for n,h in info['derived_sources'].items():
        if digest(PARENT/'fns'/n)!=h or hashlib.sha256(original[n].encode()).hexdigest()!=h:
            raise ValueError('actual scheduled parent changed:'+n)
    if {n for n in files if files[n]!=original[n]}!={META}:
        raise ValueError('only metadata status transport may change')
    shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    for n,h in before.items():
        if digest(ROOT/n)!=h:raise ValueError('parent changed:'+n)
    r=dict(info,scope=__doc__,parent_source=str(PARENT),event_parent_tree_sha256=before,
        generator_sha256=digest(__file__),derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        same_actual_metadata_RAM_and_reset_sweep=True,ordinary_invocations_emit_no_fault_token=True,
        actual_sticky_fault_event_and_collector=True,legacy_API_uses_same_engine=True,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
