#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual segmented Immediate consumers and all prior READ/WRITE/SEND modes.

Freeze an exact checked extension of the existing READ runner. Only the two
newly supported Immediate policy-rejection cases move to1MiB+1; all other
old assertions, independent wire/READ oracles, clocks and30s limits remain.
Packet/source/connection boundaries are models, not native/physical proof.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import probe_segmented_read_hls as base

ROOT=base.ROOT;once=base.once;digest=base.digest


def verify_immediate(output,op):
    records=[];fresh={};replays=0;psn=0xfffffe;expected_keys=[]
    lengths=[4097,8192,8193,12289,65537,1048576]
    for total in lengths:
        for offset in range(0,total,4096):expected_keys.append((op,total,offset,psn));psn=(psn+1)&0xffffff
    for line in output.splitlines():
        if not line.startswith('IMMEDIATE_SEGMENT_WIRE '):continue
        _,actual_op,total,offset,psn,replay,imm,wire=line.split()
        actual_op,total,offset,psn,replay,imm=map(int,[actual_op,total,offset,psn,replay,imm])
        if actual_op!=op or total not in lengths:raise ValueError('unexpected new operation or extent')
        index=lengths.index(total);expected_imm=0 if index==0 else 0xffffffff if index==1 else 0x89abcdef+index
        if imm!=expected_imm:raise ValueError('retained Immediate field not the independent posted value')
        count=min(4096,total-offset);first=offset==0;last=offset+count==total
        opcode=(0 if first else 3 if last else 1)if op==5 else(6 if first else 9 if last else 7)
        pad=(-count)&3
        expected=bytes([opcode,0x40|(pad<<4),0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
        if op==6 and first:expected+=struct.pack('!QII',0xe23456789abcdef0,0x81234567,total)
        if last:expected+=expected_imm.to_bytes(4,'big')
        expected+=bytes((((offset+i)*53)^0x97)&255 for i in range(count))+bytes(pad)
        actual=bytes.fromhex(wire)
        if actual!=expected:raise ValueError('independent Immediate LAST/RETH/full-payload/PSN/padding oracle')
        key=(op,total,offset,psn)
        if replay:
            if fresh.get(key)!=actual:raise ValueError('stored first/middle/LAST replay differs from actual fresh packet')
            replays+=1
        else:
            if key in fresh:raise ValueError('duplicate fresh packet')
            fresh[key]=actual
        records.append(dict(opcode=opcode,WR_opcode=op,total_bytes=total,offset=offset,PSN=psn,
            replay=bool(replay),wire_bytes=len(actual),Immediate_on_LAST=last))
    if list(fresh)!=expected_keys or replays!=13:raise ValueError('all6 complete messages/packets/13 stored replays required')
    return records


def runner_source():
    t=Path(base.__file__).read_text()
    t=once(t,"import probe_segmented_request_hls as old",'import probe_segmented_request_hls as old\nfrom probe_segmented_immediate_hls import verify_immediate')
    t=once(t,"info.get('HLS_top')!='rocev2_native_segmented_read_top'or info.get('large_READ_max_bytes')!=1048576",
        "info.get('HLS_top')!='rocev2_native_segmented_immediate_top'or info.get('large_READ_max_bytes')!=1048576 or info.get('Immediate_max_bytes')!=1048576")
    t=once(t,"prefix='segmented-read-hls-'","prefix='segmented-immediate-hls-'")
    t=once(t,"prefix='as02-segmented-read-hls-'","prefix='as02-segmented-immediate-hls-'")
    t=once(t,"if n=='segmented_request':t=once(t,'segmented_policy_negative<1604>(2,4097);','segmented_policy_negative<1604>(2,1048577);')",
        "if n=='segmented_request':\n"
        "            for old_case,new_case in [('1604>(2,4097)','1604>(2,1048577)'),('1605>(5,4097)','1605>(5,1048577)'),('1606>(6,4097)','1606>(6,1048577)')]:\n"
        "                t=once(t,old_case,new_case)")
    t=once(t,"shutil.copy2(hls/'test_segmented_read.cpp',run/'test.cpp')",
        "(run/'read_prior.cpp').write_text(once((hls/'test_segmented_read.cpp').read_text(),'int main(int argc,char **argv) {','int preceding_read_main(int argc,char **argv) {'))\n"
        "    shutil.copy2(hls/'test_segmented_immediate.cpp',run/'test.cpp')")
    t=once(t,"['segmented_read','segmented_request','zero_service'","['segmented_immediate','segmented_read','segmented_request','zero_service'")
    t=once(t,"Path(__file__).resolve(),Path(old.__file__).resolve()",
        "Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_segmented_immediate_hls.py',ROOT/'rdma/rnic/tests/probe_segmented_read_hls.py',Path(old.__file__).resolve()")
    t=once(t,"for mode in ['prior','read',*['bad'+str(i)for i in range(9)]]:",
        "for mode in ['prior','read',*['bad'+str(i)for i in range(9)],'imm-send','imm-write',*['imm-bad'+str(i)for i in range(8)]]:")
    t=once(t,"            else:\n                if 'SEGMENTED_READ_NEGATIVE '",
        "            elif mode in ['imm-send','imm-write']:\n"
        "                item['independent_immediate_wire_oracles']=verify_immediate(r.stdout,5 if mode=='imm-send'else 6);markers=['SEGMENTED_IMMEDIATE_HLS']\n"
        "            elif mode.startswith('imm-bad'):\n"
        "                if 'SEGMENTED_IMMEDIATE_NEGATIVE '+mode[-1]not in r.stdout:raise ValueError('new negative assertion missing')\n"
        "                markers=[]\n"
        "            else:\n                if 'SEGMENTED_READ_NEGATIVE '")
    t=once(t,"report.update(pass_test=True,source_unchanged=True)",
        "report.update(pass_test=True,source_unchanged=True,all11_prior_modes_retained=True,large_Immediate_max_bytes=1048576,receive_buffer_max_bytes=4096,prior_Immediate_rejection_policy_change='only newly supported4097 to independently oversized1048577; assertions retained')")
    return t


def main():
    # The checked generated runner is a frozen build input, not a replacement
    # test result. Its own real process output supplies every recorded check.
    run=Path(tempfile.mkdtemp(prefix='segmented-immediate-hls-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    namespace=dict(__file__=str(frozen),__name__='__main__')
    exec(compile(frozen.read_text(),str(frozen),'exec'),namespace)


if __name__=='__main__':main()
