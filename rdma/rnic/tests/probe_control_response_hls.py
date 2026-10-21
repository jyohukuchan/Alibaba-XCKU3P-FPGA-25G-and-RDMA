#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual typed control ACK/MSN consumers plus every87 old HLS mode.

Native authenticated480-bit owner is modeled. Header512 receipt is NOT
payload/PSN-update/MR/DMA/RQ/MAC/CQ or physical execution qualification.
"""
import ast
import json
from pathlib import Path
import tempfile
import probe_segmented_write_owned_hls as parent

ROOT=parent.ROOT;once=parent.once
MODES=['control-headers','control-priority','control-rnr-bad',*['control-bad'+str(i)for i in range(15)]]


def control_harness():
    t=parent.write_owned_harness()
    t=once(t,'hls::stream<as02WriteDone> write_done;',
        'hls::stream<as02WriteDone> write_done;hls::stream<as02ControlDone> control_done;')
    t=once(t,'exh_words,recv_ack,write_ack,zero_tx)',
        'exh_words,recv_ack,write_ack,control_done,zero_tx)')
    # Legacy test endpoints leave the NEW input empty, but execute the REAL
    # new merger; no replacement payload/header/completion producer is used.
    helper=r'''
template<int I> void as02_native_rnr_merger(hls::stream<ackEvent>& exh,hls::stream<ackEvent>& ibh,
 hls::stream<as02RnrEvent>& rnr,hls::stream<ackEvent>& out,ap_uint<1>& rf) {
 static hls::stream<as02ControlOwner> unused_control;ap_uint<1> cf=0;
 as02_native_control_merger<I>(exh,ibh,rnr,unused_control,out,rf,cf);assert(!cf);
}
'''
    return once(t,'template<int I> struct Harness {',helper+'\ntemplate<int I> struct Harness {')


def verify_control(output):
    lines=[s.split()for s in output.splitlines()if s.startswith('CONTROL_WIRE ')]
    if len(lines)!=5:raise ValueError('all five actual control ACK/NAK headers required')
    context=0
    for width,value in [(4,14),(48,0x8af3fbb97531),(48,0xb8830367c5d0),(32,0xc0a81f02),(32,0xc0a81f01),
        (24,196),(64,0xfedcba9889abcdef),(64,0x9123456700000001),(16,17),(24,2)]:context=(context<<width)|value
    result=[]
    for serial,(row,syndrome)in enumerate(zip(lines,[0x1f,0x60,0x61,0x62,0x63]),1):
        received=0xfffffe if syndrome==0x1f else 5 if syndrome==0x60 else 0;response=0xffffff if syndrome==0x1f else 0
        if len(row)!=8 or list(map(int,row[1:6]))!=[syndrome,received,response,serial,1]:raise ValueError('actual independent syndrome/PSN/MSN/serial')
        token=(syndrome<<468)|(received<<444)|(response<<420)|((0xa123456700000000+serial)<<356)|context
        ack=bytearray(16);ack[0]=17;ack[1]=0x40;ack[2:4]=b'\xff\xff';ack[5:8]=(196).to_bytes(3,'big')
        ack[9:12]=response.to_bytes(3,'big');ack[12]=syndrome;ack[13:16]=(1).to_bytes(3,'big')
        if int(row[6],16)!=token or bytes.fromhex(row[7])!=ack:raise ValueError('full480 owner and every actual ACK/MSN byte required')
        result.append(dict(syndrome=syndrome,received_PSN=received,response_PSN=response,serial=serial,MSN=1,owner480=f'{token:0120x}',ACK_hex=ack.hex()))
    return result


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'from probe_segmented_write_owned_hls import write_owned_harness,write_owned_prior,verify_packet_receipts',
        'from probe_segmented_write_owned_hls import write_owned_prior,verify_packet_receipts\n'
        'from probe_control_response_hls import control_harness,verify_control')
    for old,new in [("info.get('HLS_top')!='rocev2_native_segmented_write_owned_top'","info.get('HLS_top')!='rocev2_native_control_response_top'"),
        ("prefix='segmented-write-owned-hls-'","prefix='control-response-hls-'"),
        ("prefix='as02-segmented-write-owned-hls-'","prefix='as02-control-response-hls-'"),
        ('write_text(write_owned_harness())','write_text(control_harness())'),
        ("shutil.copy2(hls/'test_segmented_write_owned.cpp',run/'test.cpp')",
         "(run/'control_prior.cpp').write_text(once((hls/'test_segmented_write_owned.cpp').read_text(),'int main(int argc,char **argv) {','int preceding_write_owned_main(int argc,char **argv) {'))\n"
         "    shutil.copy2(hls/'test_control_response.cpp',run/'test.cpp')"),
        ("['segmented_write_owned','segmented_write_receive'","['control_response','segmented_write_owned','segmented_write_receive'"),
        ("Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',",
         "Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_control_response_hls.py',ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',"),
        ("*['write-owned-bad'+str(i)for i in range(21)]]:",f"*['write-owned-bad'+str(i)for i in range(21)],*{MODES!r}]:"),
        ("            elif mode=='write-owned-hold':",'''            elif mode=='control-headers':
                item['independent_control_oracles']=verify_control(r.stdout);markers=['CONTROL_RESPONSE_HLS']
            elif mode=='control-priority':markers=['CONTROL_PRIORITY']
            elif mode=='control-rnr-bad':markers=['CONTROL_RNR_NEGATIVE']
            elif mode.startswith('control-bad'):
                if 'CONTROL_NEGATIVE '+mode[11:]not in r.stdout:raise ValueError('actual invalid control owner missing')
                markers=[]
            elif mode=='write-owned-hold':'''),
        ("if len(report['tests'])!=87:raise ValueError('all65 prior exact modes and22 actual typed-WRITE cases required')",
         "if len(report['tests'])!=105:raise ValueError('all87 original modes and18 actual control modes required')"),
        ('typed424_remote_write_owner=True,actual456_write_packet_receipt=True,',
         'typed424_remote_write_owner=True,actual456_write_packet_receipt=True,typed480_control_owner=True,actual512_control_header_receipt=True,all87_prior_modes_retained=True,')]:t=once(t,old,new)
    t=once(t,"    (run/'zero_rq_endpoint.hpp').write_text(once(t,'        h.tick();','        h.tick(true,payload,tables);'))",'''    t=once(t,'hls::stream<as02RnrEvent> rnr;',
        'hls::stream<as02RnrEvent> rnr;hls::stream<as02ControlOwner> control_owners;ap_uint<1> control_fault=0;')
    t=once(t,'as02_native_rnr_merger<I>(h.rx_ack_events,other_ack,rnr,h.ack_events,rnr_fault);',
        'as02_native_control_merger<I>(h.rx_ack_events,other_ack,rnr,control_owners,h.ack_events,rnr_fault,control_fault);')
    (run/'zero_rq_endpoint.hpp').write_text(once(t,'        h.tick();','        h.tick(true,payload,tables);'))''')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='control-response-hls-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
