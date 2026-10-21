#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Typed control-only ACK/NAK on the SAME actual responder MSN/ACK pipeline.

Independent original implementation; behavioral reference: Linux v6.17 RXE
rxe_resp.c check_psn/duplicate_request/prepare_ack_packet and rxe_hdr.h AETH.
No Linux source is copied. Control responses NEVER prove payload/RQ/DMA/CQ
execution. Native authentication/error quarantine and MAC proof are separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import segmented_write_owned_transport as parent
import rnr_transport

ROOT=parent.ROOT;CPP=parent.CPP;HPP=parent.HPP;TOP=parent.TOP;once=parent.once;change=parent.change
PARENT=ROOT/'rdma/rnic/build/native-segmented-write-owned-transport-002'
NAME='rocev2_native_control_response_top'

TYPES=r'''
// Byte-aligned480-bit privileged identity, NOT remote-MR or RQ authority:
// {reserved4,syndrome8,receivedPSN24,responsePSN24,serial64,nativeContext356}.
// The SAME native context contains full QPN24/PD16/epoch64/QPcookie64 and
// peer route. A fresh nonwrapping serial disambiguates repeated rejects.
struct as02ControlOwner {ap_uint<480> token=0;};
struct as02ControlDone {as02ControlOwner owner;ap_uint<24> msn=0;ap_uint<8> error=0;};
inline bool as02_control_owner_valid(as02ControlOwner o) {
    auto t=o.token;ap_uint<8> syndrome=t(475,468);
    ap_uint<24> received=t(467,444),response=t(443,420);
    ap_uint<24> future=received-response,duplicate=ap_uint<24>(response+1)-received;
    bool sequence=syndrome==0x60 && future!=0 && !future[23];
    bool replay=syndrome==0x1f && duplicate!=0 && !duplicate[23];
    bool fatal=(syndrome==0x61 || syndrome==0x62 || syndrome==0x63) && received==response;
    return t(479,476)==0 && t(419,356)!=0 && t(167,104)!=0 &&
        t(103,40)!=0 && t(39,24)!=0 && t(23,0)<MAX_QPS && (sequence || replay || fatal);
}
'''

MERGER=r'''
template<int INSTID=0> void as02_native_control_merger(
    stream<ackEvent>& exh,stream<ackEvent>& ibh,stream<as02RnrEvent>& rnr,
    stream<as02ControlOwner>& control,stream<ackEvent>& output,
    ap_uint<1>& regRnrFault,ap_uint<1>& regControlFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static bool rnr_fault=false,control_fault=false;
    regRnrFault=rnr_fault;regControlFault=control_fault;
    if(rnr_fault || control_fault || output.full())return;
    // Preserve every old producer's priority and exact RNR-only validation.
    if(!exh.empty())output.write(exh.read());
    else if(!ibh.empty())output.write(ibh.read());
    else if(!rnr.empty()) {
        auto e=rnr.read();
        if(e.qpn>=MAX_QPS || e.syndrome!=0x20) {rnr_fault=true;regRnrFault=1;return;}
        ackEvent a(e.qpn,e.psn,false);a.syndrome=e.syndrome;a.syndrome_valid=true;output.write(a);
    } else if(!control.empty()) {
        auto o=control.read();
        if(!as02_control_owner_valid(o)) {control_fault=true;regControlFault=1;return;}
        ackEvent a(ap_uint<24>(o.token(23,0)),ap_uint<24>(o.token(443,420)),false);
        a.syndrome=o.token(475,468);a.syndrome_valid=true;
        a.control_owned=true;a.control_owner=o;output.write(a);
    }
}
'''


def derive():
    out=parent.derive()
    out[HPP]=once(out[HPP],'struct as02WriteOwner {',TYPES+'\nstruct as02WriteOwner {')
    for name in ['ackEvent','event']:
        out[HPP]=once(out[HPP],'struct '+name+'\n{',
            'struct '+name+'\n{\n    bool control_owned=false;as02ControlOwner control_owner;')
    out[HPP]=once(out[HPP],'write_owned(aev.write_owned),write_packet(aev.write_packet),',
        'control_owned(aev.control_owned),control_owner(aev.control_owner),write_owned(aev.write_owned),write_packet(aev.write_packet),')
    for name in [HPP,CPP,TOP]:
        text,n=re.subn(r'(ap_uint<1>& regWriteFault,)([ \t]*\\)?\n',
            lambda m:m[1]+(m[2]or'')+'\n    stream<as02ControlOwner>& s_axis_control_owner,'+(m[2]or'')+
            '\n    stream<as02ControlDone>& m_axis_control_done,'+(m[2]or'')+
            '\n    ap_uint<1>& regControlFault,'+(m[2]or'')+'\n',out[name])
        if not n:raise ValueError('every real control-response declaration required:'+name)
        if name==TOP:
            anchor='s_axis_write_owner,m_axis_write_done,regWriteFault,'
            if text.count(anchor)!=3:raise ValueError('all three actual inner/public-top forwarding calls required')
            text=text.replace(anchor,anchor+'s_axis_control_owner,m_axis_control_done,regControlFault,')
            anchor='#pragma HLS INTERFACE ap_none port=regWriteFault'
            if text.count(anchor)!=2:raise ValueError('both actual top interface sets required')
            text=text.replace(anchor,anchor+'\n#pragma HLS INTERFACE axis register port=s_axis_control_owner\n'
                '#pragma HLS aggregate variable=s_axis_control_owner compact=bit\n'
                '#pragma HLS INTERFACE axis register port=m_axis_control_done\n'
                '#pragma HLS aggregate variable=m_axis_control_done compact=bit\n'
                '#pragma HLS INTERFACE ap_none port=regControlFault')
            if text.count('void '+parent.NAME+'(')!=2:raise ValueError('both original top overloads required')
            text=text.replace('void '+parent.NAME+'(','void '+NAME+'(')
        out[name]=text
    out[CPP]=once(out[CPP],rnr_transport.MERGER,MERGER)
    out[CPP]=once(out[CPP],
        'as02_native_rnr_merger<INSTID>(rx_exhEventMetaFifo, rx_ibhEventFifo, s_axis_rnr_event, rx_ackEventFifo, regRnrFault);',
        'as02_native_control_merger<INSTID>(rx_exhEventMetaFifo, rx_ibhEventFifo, s_axis_rnr_event, s_axis_control_owner, rx_ackEventFifo, regRnrFault,regControlFault);')
    def exh(t):
        t=once(t,'stream<as02WriteProof>& write_ack_done,',
            'stream<as02WriteProof>& write_ack_done,stream<as02ControlDone>& control_done,')
        t=once(t,'PROCESS, RECV_DONE, WRITE_DONE, ZERO_DONE','PROCESS, RECV_DONE, WRITE_DONE, CONTROL_DONE, ZERO_DONE')
        t=once(t,'meta.receive_owned ? RECV_DONE : meta.write_owned ? WRITE_DONE : META;',
            'meta.control_owned ? CONTROL_DONE : meta.receive_owned ? RECV_DONE : meta.write_owned ? WRITE_DONE : META;')
        return once(t,'    case WRITE_DONE: {',r'''    case CONTROL_DONE: {
        // Same actual MSN read used to construct this ACK's AETH. This is
        // only header-consumer proof, NOT payload/PSN/DMA/MAC/CQ completion.
        as02ControlDone d;d.owner=meta.control_owner;d.msn=msnMeta.msn;
        control_done.write(d);ge_state=META;break;
    }
    case WRITE_DONE: {''')
    out[CPP]=change(out[CPP],'void generate_exh(',exh)
    out[CPP]=once(out[CPP],'tx_exh2payFifo,recv_ack_done,write_ack_done,zero_tx',
        'tx_exh2payFifo,recv_ack_done,write_ack_done,m_axis_control_done,zero_tx')
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source cohorts')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=parent.NAME:raise ValueError('exact actual typed-WRITE parent required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    original=parent.derive()
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h or hashlib.sha256(original[n].encode()).hexdigest()!=h:raise ValueError('qualified parent source changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,HLS_top=NAME,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        control_owner_bits=480,control_receipt_bits=512,control_response_is_payload_completion=False,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
