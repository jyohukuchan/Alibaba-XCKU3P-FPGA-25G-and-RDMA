#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual segmented SEND/Immediate RX plus all21 earlier full HLS modes.

Strict independent packet-data, ACK-MSN and whole-receipt oracles. Runtime
limits stay30s per mode. Packets/posted owners/connections/memory endpoints
are models, not native MR/PTE/DMA visibility/MAC/CQ/Linux/physical proof.
"""
import ast
import json
from pathlib import Path
import tempfile
import probe_segmented_immediate_hls as base

ROOT=base.ROOT;once=base.once


def verify_receive(output,op):
    lengths=[4097,8192,8193,12289,65537,1048576];expected=[];messages=[];psn=0xfffffe
    for seq,total in enumerate(lengths,1):
        initial=psn
        for offset in range(0,total,4096):
            count=min(4096,total-offset);last=offset+count==total
            data=bytes((((offset+b)*91)^0x69)&255 for b in range(count))+bytes((-count)&3)
            ack=bytes([17,0x40,0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x00'+psn.to_bytes(3,'big')+b'\x00'+int(seq if last else seq-1).to_bytes(3,'big')
            expected.extend([f'SEGMENTED_RECEIVE_DATA {op} {total} {offset} {data.hex()}',
                f'SEGMENTED_RECEIVE_ACK {op} {total} {offset} {ack.hex()}'])
            final=psn;psn=(psn+1)&0xffffff
        imm=0 if seq==1 else 0xffffffff if seq==2 else 0x89abcdef+seq-1
        expected.append(f'SEGMENTED_RECEIVE_MESSAGE {op} {total} {initial} {final} {seq} {imm if op==5 else 0} 1048576')
        messages.append(dict(actual_bytes=total,posted_capacity=1048576,first_PSN=initial,last_PSN=final,MSN=seq))
    rows=[s for s in output.splitlines()if s.startswith(('SEGMENTED_RECEIVE_DATA ','SEGMENTED_RECEIVE_ACK ','SEGMENTED_RECEIVE_MESSAGE '))]
    if rows!=expected:raise ValueError('independent complete payload/padding/ACK/PSN/MSN/whole-byte-count oracle mismatch')
    return dict(packets=(len(rows)-6)//2,whole_messages=messages,all_bytes_and_zero_padding=True,
        ACK_MSN_advances_only_at_message_end=True,posted_capacity_not_substituted_for_actual_bytes=True)


def runner_source():
    t=base.runner_source()
    t=once(t,'from probe_segmented_immediate_hls import verify_immediate',
        'from probe_segmented_immediate_hls import verify_immediate\nfrom probe_segmented_receive_hls import verify_receive')
    t=once(t,"info.get('HLS_top')!='rocev2_native_segmented_immediate_top'", "info.get('HLS_top')!='rocev2_native_segmented_receive_top'")
    t=once(t,"prefix='segmented-immediate-hls-'","prefix='segmented-receive-hls-'")
    t=once(t,"prefix='as02-segmented-immediate-hls-'","prefix='as02-segmented-receive-hls-'")
    t=once(t,"shutil.copy2(hls/'test_segmented_immediate.cpp',run/'test.cpp')",
        "(run/'immediate_prior.cpp').write_text(once((hls/'test_segmented_immediate.cpp').read_text(),'int main(int argc,char **argv) {','int preceding_immediate_main(int argc,char **argv) {'))\n"
        "    shutil.copy2(hls/'test_segmented_receive.cpp',run/'test.cpp')")
    t=once(t,"['segmented_immediate','segmented_read'","['segmented_receive','segmented_immediate','segmented_read'")
    t=once(t,"Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_segmented_immediate_hls.py'",
        "Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_segmented_receive_hls.py',ROOT/'rdma/rnic/tests/probe_segmented_immediate_hls.py'")
    t=once(t,"*['imm-bad'+str(i)for i in range(8)]]:",
        "*['imm-bad'+str(i)for i in range(8)],'rx-send','rx-imm',*['rx-bad'+str(i)for i in range(21)]]:")
    t=once(t,"            elif mode in ['imm-send','imm-write']:",
        "            elif mode in ['rx-send','rx-imm']:\n"
        "                item['independent_receive_oracles']=verify_receive(r.stdout,3 if mode=='rx-send'else 5);markers=['SEGMENTED_RECEIVE_HLS']\n"
        "            elif mode.startswith('rx-bad'):\n"
        "                if 'SEGMENTED_RECEIVE_NEGATIVE '+mode[6:]not in r.stdout:raise ValueError('actual new RX negative missing')\n"
        "                markers=[]\n"
        "            elif mode in ['imm-send','imm-write']:")
    t=once(t,'receive_buffer_max_bytes=4096,prior_Immediate_rejection_policy_change=',
        'receive_buffer_max_bytes=1048576,segmented_SEND_Immediate_RX=True,segmented_WRITE_Immediate_RX=False,all21_prior_modes_retained=True,prior_Immediate_rejection_policy_change=')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-receive-hls-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
