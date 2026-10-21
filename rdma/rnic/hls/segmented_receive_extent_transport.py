#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same receive graph/checks with a remaining-span payload extent circuit.

Expected contiguous KEEP proves the actual byte count without a64-term
population-count feedback chain. Exact EOF and up to3 actual zero pad bytes
are still required. Preserve clocks/II/owners/ports/all other consumers.
This separate frozen candidate never mutates/restarts the live source004.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_receive_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP;NAME=base.NAME
PARENT=ROOT/'rdma/rnic/build/native-segmented-receive-transport-004'

EXTENT=r'''
template<int WIDTH> bool as02_read_payload_extent(pkgShift shift,net_axis<WIDTH> word,ap_uint<32>& copied) {
#pragma HLS inline
    bool receive=shift.receive_owned;
    if(!shift.request_length_checked && !receive)return true;
    ap_uint<32> expected=receive ? ap_uint<32>((shift.receive.owner.length+3)&ap_uint<32>(0xfffffffc)):shift.request_bytes;
    if(receive && (!as02_recv_packet_valid(shift.receive) || shift.request_owned))return false;
    if((!receive && !shift.request_owned) || copied>=expected)return false;
    ap_uint<32> left=expected-copied;
    ap_uint<7> count=left>=WIDTH/8 ? ap_uint<7>(WIDTH/8):ap_uint<7>(left);
    ap_uint<WIDTH/8+1> mask=(ap_uint<WIDTH/8+1>(1)<<count)-1;
    if(word.keep!=mask || bool(word.last)!=(left<=WIDTH/8))return false;
    if(receive && word.last) {
        ap_uint<2> padding=-shift.receive.owner.length;
        if(padding!=0) {
            if(count<padding)return false;
            ap_uint<WIDTH> tail=word.data>>((count-padding)*8);
            ap_uint<32> pad_mask=(ap_uint<32>(1)<<(padding*8))-1;
            if((ap_uint<32>(tail(31,0))&pad_mask)!=0)return false;
        }
    }
    copied+=count;return true;
}
'''


def derive():
    out=base.derive()
    def replace(t):
        if t.count('bool as02_read_payload_extent(')!=1:raise ValueError('one exact original helper required')
        # change() selects only the function, leaving the template line and
        # every call/pipeline/consumer intact.
        return EXTENT[EXTENT.index('bool as02_read_payload_extent('):].strip()
    out[CPP]=base.change(out[CPP],'bool as02_read_payload_extent(',replace)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=NAME or not info.get('segmented_SEND_Immediate_receive'):raise ValueError('exact full source004 required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h:raise ValueError('parent changed:'+n)
    old=base.derive();new=derive()
    if [n for n in new if new[n]!=old[n]]!=[CPP]:raise ValueError('only actual payload helper may change')
    shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in new.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in new.items()},
        remaining_span_extent_checker=True,actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,only_payload_extent_helper_changed=True,old_live_source_unchanged=True)))


if __name__=='__main__':main()
