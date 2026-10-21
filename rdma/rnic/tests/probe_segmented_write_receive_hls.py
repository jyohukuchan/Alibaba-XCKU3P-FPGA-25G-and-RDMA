#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual segmented WRITE/Immediate HLS plus ALL44 earlier full-core modes.

Independent complete data/ACK/MSN/PSN/count oracles, original30s per mode.
Peer/posted-RQ/memory are models, not native MR/PTE/DMA/MAC/CQ/physical proof.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_receive_hls as parent
import probe_segmented_read_hls as read

ROOT=parent.ROOT;once=parent.once


def write_receive_harness():
    t=read.harness()
    t=once(t,'hls::stream<as02RecvOwner> recv_owners;',
        'hls::stream<as02RecvOwner> recv_owners;hls::stream<as02WriteNotify> write_notify;')
    return once(t,'atomic_commit,recv_owners,recv_fault,', 'atomic_commit,recv_owners,write_notify,recv_fault,')


def verify_write_receive(output,immediate):
    expected=[];psn=0xfffffe;messages=[];lengths=[4097,8192,8193,12289,65537,1048576]
    for seq,total in enumerate(lengths,1):
        first=psn;value=0 if seq==1 else 0xffffffff if seq==2 else 0x89abcdef+seq-1
        capacity=0 if seq in [1,4]else 1 if seq==2 else 17 if seq==3 else 8194 if seq==5 else 1048576
        for offset in range(0,total,4096):
            count=min(4096,total-offset);last=offset+count==total
            data=bytes((((offset+i)*113)^((offset+i)>>8)^0xb7)&255 for i in range(count))+bytes((-count)&3)
            ack=bytes([17,0x40,0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x00'+psn.to_bytes(3,'big')+b'\x00'+int(seq if last else seq-1).to_bytes(3,'big')
            expected.extend([f'WRITE_RECEIVE_DATA {int(immediate)} {total} {offset} {data.hex()}',
                f'WRITE_RECEIVE_ACK {int(immediate)} {total} {offset} {ack.hex()}'])
            final=psn;psn=(psn+1)&0xffffff
        if immediate:expected.append(f'WRITE_RECEIVE_MESSAGE {total} {first} {final} {seq} {value} {capacity}')
        messages.append(dict(bytes=total,first_PSN=first,last_PSN=final,MSN=seq,RQ_capacity=capacity if immediate else None))
    rows=[s for s in output.splitlines()if s.startswith(('WRITE_RECEIVE_DATA ','WRITE_RECEIVE_ACK ','WRITE_RECEIVE_MESSAGE '))]
    if rows!=expected:raise ValueError('independent actual WRITE payload/padding/ACK/PSN/MSN/late-RQ/count oracle mismatch')
    return dict(packets=284,messages=messages,all_bytes_and_zero_padding=True,ACK_MSN_only_LAST=True,
        actual_whole_bytes_not_late_RQ_capacity=True,remote_RETH_not_RQ_buffer=True)


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'from probe_segmented_receive_hls import verify_receive',
        'from probe_segmented_receive_hls import verify_receive\nfrom probe_segmented_write_receive_hls import write_receive_harness,verify_write_receive')
    t=once(t,"info.get('HLS_top')!='rocev2_native_segmented_receive_top'","info.get('HLS_top')!='rocev2_native_segmented_write_receive_top'")
    t=once(t,"prefix='segmented-receive-hls-'","prefix='segmented-write-receive-hls-'")
    t=once(t,"prefix='as02-segmented-receive-hls-'","prefix='as02-segmented-write-receive-hls-'")
    t=once(t,"write_text(harness())","write_text(write_receive_harness())")
    t=once(t,"shutil.copy2(hls/'test_segmented_receive.cpp',run/'test.cpp')",
        "rx=(hls/'test_segmented_receive.cpp').read_text()\n"
        "    rx=once(rx,'int main(int argc,char **argv) {','int preceding_receive_main(int argc,char **argv) {')\n"
        "    rx=once(rx,'as02_recv_message_join<I>(this->received,packets,messages,message_fault);',\n"
        "        'as02_recv_write_message_join<I>(this->received,packets,messages,this->h.write_notify,message_fault);')\n"
        "    (run/'receive_prior.cpp').write_text(rx)\n"
        "    shutil.copy2(hls/'test_segmented_write_receive.cpp',run/'test.cpp')")
    t=once(t,"['segmented_receive','segmented_immediate'","['segmented_write_receive','segmented_receive','segmented_immediate'")
    t=once(t,"ROOT/'rdma/rnic/tests/probe_segmented_receive_hls.py',",
        "ROOT/'rdma/rnic/tests/probe_segmented_write_receive_hls.py',ROOT/'rdma/rnic/tests/probe_segmented_receive_hls.py',")
    t=once(t,"*['rx-bad'+str(i)for i in range(21)]]:",
        "*['rx-bad'+str(i)for i in range(21)],'write-rx','write-rx-imm',*['write-rx-bad'+str(i)for i in range(19)]]:")
    t=once(t,"            elif mode in ['rx-send','rx-imm']:",
        "            elif mode in ['write-rx','write-rx-imm']:\n"
        "                item['independent_write_receive_oracles']=verify_write_receive(r.stdout,mode=='write-rx-imm');markers=['WRITE_RECEIVE_HLS']\n"
        "            elif mode.startswith('write-rx-bad'):\n"
        "                if 'WRITE_RECEIVE_NEGATIVE '+mode[12:]not in r.stdout:raise ValueError('actual new WRITE receive negative missing')\n"
        "                markers=[]\n"
        "            elif mode in ['rx-send','rx-imm']:")
    t=once(t,'segmented_WRITE_Immediate_RX=False,all21_prior_modes_retained=True,',
        'segmented_WRITE_Immediate_RX=True,all44_prior_modes_retained=True,all21_prior_modes_retained=True,')
    t=once(t,'        if any(digest(ROOT/n)!=h for n,h in before.items()):',
        "        if len(report['tests'])!=65:raise ValueError('all44 old plus2 new actual WRITE modes and19 negatives required')\n"
        '        if any(digest(ROOT/n)!=h for n,h in before.items()):')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-receive-hls-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
