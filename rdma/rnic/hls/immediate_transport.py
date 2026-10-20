#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Immediate request AND receive execution in the same complete duplex core.

Candidate profile only: native guard/CQ ports and kernel/provider integration
remain pending. Incoming RETH is NOT DMA authorization. Retain the independent
posted RQ context; attach actual wire immediate only to the execution proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import immediate_request_transport as base

parent=base.parent;once=parent.once;CPP=base.CPP;HPP=base.HPP

EXECUTE=r'''
        case RC_SEND_ONLY_WITH_IMD:
        case RC_RDMA_WRITE_ONLY_WIT_IMD: {
            if(s_axis_recv_owner.empty())break;
            as02RecvOwner o=s_axis_recv_owner.read();
            bool write=meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD;
            ap_uint<32> wire_length=(o.length+3)&ap_uint<32>(0xfffffffc);
            ap_uint<6> header_bytes=write ? 20:4;
            auto reth=exHeader.getRdmaHeader();
            if(!as02_recv_owner_valid(o,write) || o.context(395,372)!=meta.dest_qp ||
                o.psn!=meta.psn || ap_uint<32>(udpLength)!=24+header_bytes+wire_length ||
                (write && (reth.getLength()!=o.length ||
                 ap_uint<65>(reth.getVirtualAddress())+o.length>(ap_uint<65>(1)<<64)))) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            as02RecvProof p;p.owner=o;p.msn=dmaMeta.msn+1;
            p.immediate=exHeader.getImmediate(write);p.flags=write ? 3:1;
            // WRITE data uses the independently authorized RETH target, NOT
            // the posted receive buffer. Native full-key/MR guards must still
            // validate the original full VA/key before this raw command.
            memCmd c=write ? memCmd(reth.getVirtualAddress(),wire_length,PKG_F,PKG_HOST,meta.dest_qp):
                memCmd(0,wire_length,PKG_F,PKG_INT,meta.dest_qp);
            memoryWriteCmd.write(as02_duplex_command(c,false));
            rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp,p.msn));
            ackEvent a(meta.dest_qp,meta.psn,false);a.receive_owned=true;a.receive=p;
            rx_exhEventMetaFifo.write(a);rx_pkgSplitTypeFifo.write(pkgSplit(meta.op_code));
            pkgShift s(SHIFT_NONE,meta.dest_qp);s.receive_owned=true;s.receive=p;
            rx_pkgShiftTypeFifo.write(s);pe_fsmState=META;break;
        }
'''

STRIP=r'''
    case IMMEDIATE:
        if(!input.empty() && !rx_exhNoShiftFifo.full()) {
            auto w=input.read();ap_uint<7> bytes=0;
            for(unsigned b=0;b<64;b++)bytes+=w.keep[b];
            ap_uint<7> fresh=bytes-imm_skip;
            ap_uint<512> body=w.data>>(imm_skip*8);
            body&=(ap_uint<512>(1)<<(fresh*8))-1;
            ap_uint<1024> joined=ap_uint<1024>(imm_carry)|(ap_uint<1024>(body)<<(imm_count*8));
            ap_uint<8> total=ap_uint<8>(imm_count)+fresh;imm_skip=0;
            net_axis<WIDTH> o;o.data=joined(511,0);
            if(total>=64) {
                o.keep=~ap_uint<64>(0);o.last=w.last && total==64;rx_exhNoShiftFifo.write(o);
                imm_carry=joined(1023,512);imm_count=total-64;
                if(w.last)rep_state=imm_count ? IMM_FLUSH:META;
            } else if(w.last) {
                o.keep=(ap_uint<64>(1)<<total)-1;o.last=1;rx_exhNoShiftFifo.write(o);rep_state=META;
            } else {imm_carry=joined(511,0);imm_count=total;}
        }
        break;
    case IMM_FLUSH:
        if(!rx_exhNoShiftFifo.full()) {
            net_axis<WIDTH> o;o.data=imm_carry;o.keep=(ap_uint<64>(1)<<imm_count)-1;o.last=1;
            rx_exhNoShiftFifo.write(o);rep_state=META;
        }
        break;
'''

def derive():
    out=base.derive()
    out[HPP]=once(out[HPP],'class ExHeader: public packetHeader<W, RETH_SIZE>',
        'class ExHeader: public packetHeader<W, 160>')
    # Only ExHeader, not the actual RETH wire geometry, becomes160 bits.
    start=out[HPP].index('class ExHeader:');end=out[HPP].index('\nstruct ImmDt',start)
    part=once(out[HPP][start:end],'using packetHeader<W, RETH_SIZE>::header;',
        'using packetHeader<W, 160>::header;')
    part=once(part,'\tExHeader() {}',r'''
    ExHeader() {}
    ap_uint<32> getImmediate(bool write) {
        ap_uint<32> raw=write ? ap_uint<32>(header(159,128)):ap_uint<32>(header(31,0));
        return reverse(raw);
    }''')
    out[HPP]=out[HPP][:start]+part+out[HPP][end:]
    out[HPP]=once(out[HPP],'struct as02RecvProof {as02RecvOwner owner;ap_uint<24> msn=0;};',
        'struct as02RecvProof {as02RecvOwner owner;ap_uint<24> msn=0;ap_uint<32> immediate=0;ap_uint<8> flags=0;};')
    out[HPP]=once(out[HPP],'inline bool as02_recv_owner_valid(as02RecvOwner o)',
        'inline bool as02_recv_owner_valid(as02RecvOwner o,bool write=false)')
    out[HPP]=once(out[HPP],'n(115,20)==0 && n(307,276)!=0',
        'n(619,588)==0 && n(115,20)==0 && n(307,276)!=0')
    out[HPP]=once(out[HPP],'o.length!=0 && o.length<=n(307,276);',
        'o.length!=0 && o.length<=4096 && (write || o.length<=n(307,276));')
    out[HPP]=once(out[HPP],'a.owner.reserved==b.owner.reserved && a.msn==b.msn;',
        'a.owner.reserved==b.owner.reserved && a.msn==b.msn && a.immediate==b.immediate && a.flags==b.flags;')
    join='hls/ib_transport_protocol/as02_recv_retire.hpp'
    out[join]=once(out[join],'if(!as02_recv_owner_valid(saved.owner))',
        'if((saved.flags!=0 && saved.flags!=1 && saved.flags!=3) || (saved.flags==0 && saved.immediate!=0) || !as02_recv_owner_valid(saved.owner,saved.flags==3))')
    def parse(t):
        t=once(t,'{META, ACK_HEADER, RETH_HEADER, NO_HEADER}',
            '{META, ACK_HEADER, RETH_HEADER, NO_HEADER, IMMEDIATE_HEADER}')
        t=once(t,'if (checkIfAethHeader(opCode))',
            'if(opCode==RC_SEND_ONLY_WITH_IMD || opCode==RC_RDMA_WRITE_ONLY_WIT_IMD)state=IMMEDIATE_HEADER;\n'
            '\t\t\telse if (checkIfAethHeader(opCode))')
        return once(t,'\t}//switch',r'''
    case IMMEDIATE_HEADER:
        static_assert(WIDTH==512,"matched original512-bit lanes required");
        if(!input.empty()) {
            auto w=input.read();output.write(w);
            if(!metaWritten) {
                ExHeader<WIDTH> e;e.setRawHeader(w.data(159,0));
                exhMetaFifo.write(exhMeta(false));metaOut.write(e);metaWritten=true;
            }
            if(w.last)state=META;
        }
        break;
    }//switch''')
    out[CPP]=parent.change(out[CPP],'void rx_process_exh(',parse)
    out[CPP]=parent.change(out[CPP],'void rx_exh_fsm(',lambda t:once(t,'        case RC_SEND_ONLY:',EXECUTE+'\n        case RC_SEND_ONLY:'))
    def payload(t):
        t=once(t,'{META, PKG}', '{META, PKG, IMMEDIATE, IMM_FLUSH}')
        t=once(t,'static pkgSplit meta;', 'static pkgSplit meta;\n'
            '    static ap_uint<512> imm_carry=0;static ap_uint<7> imm_count=0,imm_skip=0;')
        t=once(t,'\t\t\trep_state = PKG;',r'''
            if(meta.op_code==RC_SEND_ONLY_WITH_IMD || meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD) {
                imm_carry=0;imm_count=0;imm_skip=meta.op_code==RC_SEND_ONLY_WITH_IMD ? 4:20;
                rep_state=IMMEDIATE;
            } else rep_state=PKG;''')
        return once(t,'\t} //switch',STRIP+'\n\t} //switch')
    out[CPP]=parent.change(out[CPP],'void rx_exh_payload(',payload)
    utils='hls/ib_transport_protocol/ib_utils.cpp'
    out[utils]=parent.change((parent.qp.BASE/'fns'/utils).read_text(),'bool checkIfWrite(',lambda t:once(t,
        'code == RC_RDMA_WRITE_ONLY)', 'code == RC_RDMA_WRITE_ONLY || code == RC_RDMA_WRITE_ONLY_WIT_IMD)'))
    out[base.TOP]=out[base.TOP].replace('rocev2_native_immediate_request_top','rocev2_native_immediate_top')
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    original=parent.qp.BASE;before={str(x.relative_to(original)):parent.qp.digest(x)for x in original.rglob('*')if x.is_file()}
    files=derive();shutil.copytree(original/'fns',a.output/'fns');shutil.copytree(original/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if before!={n:parent.qp.digest(original/n)for n in before}:raise ValueError('original changed')
    info=dict(scope=__doc__,source_base=str(original),source_sha256=before,generator_sha256=parent.qp.digest(__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},original_unchanged=True,
        external_replay=True,native_rnr=True,receive_retirement=True,request_retirement=True,
        duplex_memory_provenance=True,request_immediate=True,receive_immediate=True,native_integration=False,
        HLS_top='rocev2_native_immediate_top',request_context_bits=620,receive_owner_bits=680,
        receive_done_bits=752,source_only=True,hardware_verified=False,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=info['HLS_top'],original_unchanged=True)))

if __name__=='__main__':main()
