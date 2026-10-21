#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same full receive graph with a balanced KEEP-prefix/actual-pad checker.

Preserve the original consumer acceptance and copied-byte side effects,
including short nonterminal beats and split padding. A six-level priority
encoder replaces64-term population-count feedback. No clock/II/owner/port
or other consumer changes; live source004 and discarded005 stay immutable.
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
    static_assert(WIDTH==512,"original512-bit extent cohort required");
    bool receive=shift.receive_owned;
    if(!shift.request_length_checked && !receive)return true;
    ap_uint<32> expected=receive ? ap_uint<32>((shift.receive.owner.length+3)&ap_uint<32>(0xfffffffc)):shift.request_bytes;
    if(receive && (!as02_recv_packet_valid(shift.receive) || shift.request_owned))return false;
    // Highest-set-bit plus exact prefix equality is the actual valid byte
    // count, including SHORT contiguous nonterminal beats. No guessed EOF.
    ap_uint<64> k=word.keep;ap_uint<6> top=0;
    top[5]=k(63,32)!=0;ap_uint<32> k32=top[5] ? ap_uint<32>(k(63,32)):ap_uint<32>(k(31,0));
    top[4]=k32(31,16)!=0;ap_uint<16> k16=top[4] ? ap_uint<16>(k32(31,16)):ap_uint<16>(k32(15,0));
    top[3]=k16(15,8)!=0;ap_uint<8> k8=top[3] ? ap_uint<8>(k16(15,8)):ap_uint<8>(k16(7,0));
    top[2]=k8(7,4)!=0;ap_uint<4> k4=top[2] ? ap_uint<4>(k8(7,4)):ap_uint<4>(k8(3,0));
    top[1]=k4(3,2)!=0;ap_uint<2> k2=top[1] ? ap_uint<2>(k4(3,2)):ap_uint<2>(k4(1,0));
    top[0]=k2[1];ap_uint<7> count=k!=0 ? ap_uint<7>(ap_uint<7>(top)+1):ap_uint<7>(0);
    ap_uint<65> mask=(ap_uint<65>(1)<<count)-1;
    ap_uint<33> next=ap_uint<33>(copied)+count;
    if((!receive && !shift.request_owned) || !count || word.keep!=mask || next>expected ||
       bool(word.last)!=(next==expected))return false;
    // Padding can itself be split across short beats. Check every actual
    // padding byte, not merely bytes in the final beat; ignore invalid lanes.
    if(receive && next>shift.receive.owner.length) {
        ap_uint<33> padding_start=copied>=shift.receive.owner.length ? ap_uint<33>(copied):ap_uint<33>(shift.receive.owner.length);
        ap_uint<3> padding=next-padding_start;
        ap_uint<512> tail=word.data>>((count-padding)*8);
        ap_uint<32> pad_mask=(ap_uint<32>(1)<<(padding*8))-1;
        if((ap_uint<32>(tail(31,0))&pad_mask)!=0)return false;
    }
    copied=next;return true;
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
        balanced_prefix_extent_checker=True,actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,only_payload_extent_helper_changed=True,old_live_source_unchanged=True)))


if __name__=='__main__':main()
