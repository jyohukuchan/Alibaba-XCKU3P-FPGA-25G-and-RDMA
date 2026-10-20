#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Immediate requester producer/retirement in the SAME complete duplex core.

Append32 immutable immediate bits to the620-bit native request context. Full
remote key/VA and all lower588 fields stay independent/exact. New op5 is
SEND_WITH_IMM; op6 is WRITE_WITH_IMM. This REQUEST stage is not RX-immediate,
kernel/native integration, generated RTL or a physical completion claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import duplex_transport as base

parent=base.parent
ROOT=base.ROOT
CPP=base.CPP;HPP=base.HPP
RETRANS='hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
TOP='hls/rocev2/rocev2.cpp'
once=parent.once

OWNER=r'''inline bool as02_req_owner_valid(ap_uint<620> n) {
    ap_uint<16> op=n(339,324);ap_uint<32> len=n(307,276);
    ap_uint<65> limit=ap_uint<65>(1)<<64;
    bool send=op==3 || op==5,imm=op==5 || op==6;
    return as02_req_token_valid(as02_req_token(n)) && n(355,340)!=0 && n(323,309)==0 &&
        n(19,0)==3 && (op==1 || op==2 || op==3 || op==5 || op==6) && len!=0 && len<=4096 &&
        (!send || n(115,20)==0) && (imm || n(619,588)==0) &&
        ap_uint<65>(n(243,180))+len<=limit && ap_uint<65>(n(179,116))+len<=limit &&
        ap_uint<65>(n(115,52))+len<=limit;
}'''
OPCODE=r'''inline ap_uint<8> as02_req_opcode(ap_uint<620> n) {
    ap_uint<16> op=n(339,324);
    return op==1 ? ap_uint<8>(RC_RDMA_WRITE_ONLY):op==2 ? ap_uint<8>(RC_RDMA_READ_REQUEST):
        op==5 ? ap_uint<8>(RC_SEND_ONLY_WITH_IMD):op==6 ? ap_uint<8>(RC_RDMA_WRITE_ONLY_WIT_IMD):
        ap_uint<8>(RC_SEND_ONLY);
}'''
APPENDER=r'''void append_payload(
    stream<txPacketInfo>& info_in,stream<net_axis<WIDTH>>& headers,
    stream<net_axis<WIDTH>>& aeth,stream<net_axis<WIDTH>>& reth,
    stream<net_axis<WIDTH>>& raw,stream<net_axis<WIDTH>>& output) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static_assert(WIDTH==512,"matched immediate profile uses original512-bit memory lanes");
    enum Phase {INFO,HEADER,PAYLOAD,FLUSH};static Phase phase=INFO;
    static txPacketInfo info;static ap_uint<WIDTH> carry=0;
    static ap_uint<7> count=0;static ap_uint<WIDTH> tail=0;static ap_uint<7> tail_count=0;
    if(phase==INFO && !info_in.empty()) {
        info=info_in.read();carry=0;count=0;
        phase=info.hasHeader ? HEADER:PAYLOAD;
    } else if(phase==HEADER && !headers.empty() && !output.full()) {
        auto h=headers.read();count=info.header_bytes;
        carry=h.data&((ap_uint<WIDTH>(1)<<(count*8))-1);
        if(!info.hasPayload) {
            net_axis<WIDTH> o;o.data=h.data;o.keep=(ap_uint<64>(1)<<count)-1;o.last=1;
            output.write(o);phase=INFO;
        } else phase=PAYLOAD;
    } else if(phase==PAYLOAD && !output.full()) {
        bool available=info.hasHeader ? (info.isAETH ? !aeth.empty():!reth.empty()):!raw.empty();
        if(available) {
            net_axis<WIDTH> w=info.hasHeader ? (info.isAETH ? aeth.read():reth.read()):raw.read();
            ap_uint<7> bytes=0;
            for(unsigned b=0;b<64;b++)bytes+=w.keep[b];
            ap_uint<1024> joined=ap_uint<1024>(carry)|(ap_uint<1024>(w.data)<<(count*8));
            ap_uint<8> total=ap_uint<8>(count)+bytes;
            net_axis<WIDTH> o;o.data=joined(511,0);
            if(total>=64) {
                o.keep=~ap_uint<64>(0);o.last=w.last && total==64;output.write(o);
                carry=joined(1023,512);count=total-64;
                if(w.last){tail=carry;tail_count=count;phase=count ? FLUSH:INFO;}
            } else if(w.last) {
                o.keep=(ap_uint<64>(1)<<total)-1;o.last=1;output.write(o);phase=INFO;
            } else {carry=joined(511,0);count=total;}
        }
    } else if(phase==FLUSH && !output.full()) {
        net_axis<WIDTH> o;o.data=tail;o.keep=(ap_uint<64>(1)<<tail_count)-1;o.last=1;
        output.write(o);phase=INFO;
    }
}'''

def compare_ops(t,field):
    for old,new in [('RC_RDMA_WRITE_ONLY','RC_RDMA_WRITE_ONLY_WIT_IMD'),('RC_SEND_ONLY','RC_SEND_ONLY_WITH_IMD')]:
        pattern=re.escape(field)+r'\s*==\s*'+old+r'\b'
        t=re.sub(pattern,lambda m:'('+m[0]+' || '+field+' == '+new+')',t)
    return t

def derive():
    out={n:t.replace('ap_uint<588>','ap_uint<620>')for n,t in base.derive().items()}
    out[HPP]=parent.change(out[HPP],'inline bool as02_req_owner_valid(',lambda _:OWNER)
    out[HPP]=parent.change(out[HPP],'inline ap_uint<8> as02_req_opcode(',lambda _:OPCODE)
    for name in ['txMeta','event','retransEvent']:
        out[HPP]=once(out[HPP],'struct '+name+'\n{','struct '+name+'\n{\n    ap_uint<32> immediate=0;')
    # txMeta field order must keep the original lower241-bit fields exact;
    # move its appended immediate AFTER rkey_valid, not ahead of opcode.
    out[HPP]=once(out[HPP],'struct txMeta\n{\n    ap_uint<32> immediate=0;', 'struct txMeta\n{')
    out[HPP]=once(out[HPP],'\tap_uint<1> rkey_valid;','\tap_uint<1> rkey_valid;\n    ap_uint<32> immediate=0;')
    out[HPP]=once(out[HPP],'struct txPacketInfo\n{','struct txPacketInfo\n{\n    ap_uint<6> header_bytes=0;')
    out[HPP]=once(out[HPP],'struct as02ReqInsert {','struct as02ReqInsert {ap_uint<32> immediate=0;')
    join='hls/ib_transport_protocol/as02_request_retire.hpp'
    out[join]=once(out[join],'r.rkey!=owner(51,20) || !r.rkey_valid',
        'r.rkey!=owner(51,20) || r.immediate!=owner(619,588) || !r.rkey_valid')
    def app(t):
        t=compare_ops(t,'meta.op_code')
        t=once(t,'meta.params(191,160)!=n(51,20))','meta.params(191,160)!=n(51,20) || meta.immediate!=n(619,588))')
        t=once(t,'ev.rkey_valid = rev.rkey_valid;','ev.rkey_valid = rev.rkey_valid;ev.immediate=rev.immediate;')
        if t.count('ev.rkey_valid = meta.rkey_valid;')!=2:raise ValueError('unreviewed app event producers')
        t=t.replace('ev.rkey_valid = meta.rkey_valid;','ev.rkey_valid = meta.rkey_valid;ev.immediate=meta.immediate;')
        return once(t,'r.request_owned=true;r.request_token=token;tx2retrans_insertAddrLen.write(r);',
            'r.immediate=meta.immediate;r.request_owned=true;r.request_token=token;tx2retrans_insertAddrLen.write(r);')
    out[CPP]=parent.change(out[CPP],'void local_req_handler(',app)
    def memory(t):
        anchor='\t\tlocalReadRequests.read(cmd);'
        return once(t,anchor,anchor+r'''
        if(cmd.op_code==RC_SEND_ONLY_WITH_IMD || cmd.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD) {
            if(cmd.sync)out.write(as02_duplex_command(memCmd(cmd.addr,cmd.len,PKG_F,SYNC,cmd.host,cmd.offs,cmd.qpn),true));
            else out.write(as02_duplex_command(memCmd(cmd.addr,cmd.len,PKG_F,cmd.host,cmd.qpn),true));
            pkgInfoFifo.write(pkgInfo(cmd.op_code==RC_SEND_ONLY_WITH_IMD ? AETH:RETH,(cmd.len+WIDTH/8-1)/(WIDTH/8)));return;
        }''')
    out[CPP]=parent.change(out[CPP],'void mem_cmd_merger(',memory)
    def exh(t):
        t=compare_ops(t,'meta.op_code')
        t=once(t,'\t\t\tswitch(meta.op_code)',r'''
            info.header_bytes=(meta.op_code==RC_RDMA_WRITE_ONLY || meta.op_code==RC_RDMA_WRITE_FIRST ||
                meta.op_code==RC_RDMA_READ_REQUEST) ? 16:
                (meta.op_code==RC_ACK || meta.op_code==RC_RDMA_READ_RESP_ONLY ||
                 meta.op_code==RC_RDMA_READ_RESP_FIRST || meta.op_code==RC_RDMA_READ_RESP_LAST) ? 4:0;
            switch(meta.op_code)''')
        return once(t,'\t\t\t// WRITE_ONLY / FIRST:',r'''
            case RC_SEND_ONLY_WITH_IMD:
            case RC_RDMA_WRITE_ONLY_WIT_IMD: {
                bool write=meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD;
                sendWord.data=0;
                ap_uint<32> imm=0;
                imm(7,0)=meta.immediate(31,24);imm(15,8)=meta.immediate(23,16);
                imm(23,16)=meta.immediate(15,8);imm(31,24)=meta.immediate(7,0);
                if(write) {
                    rdmaHeader.setVirtualAddress(meta.addr);rdmaHeader.setLength(meta.length);
                    rdmaHeader.setRemoteKey(meta.rkey_valid ? meta.rkey:msnMeta.r_key);
                    rdmaHeader.consumeWord(sendWord.data);sendWord.data(159,128)=imm;
                } else sendWord.data(31,0)=imm;
                info.header_bytes=write ? 20:4;info.isAETH=!write;
                info.hasHeader=true;info.hasPayload=meta.length!=0;
                sendWord.keep=(ap_uint<WIDTH/8>(1)<<info.header_bytes)-1;sendWord.last=1;
                output.write(sendWord);packetInfoFifo.write(info);
                lengthFifo.write(ap_uint<16>(12+info.header_bytes+meta.length+4));
                ge_state=META;break;
            }
            // WRITE_ONLY / FIRST:''')
    out[CPP]=parent.change(out[CPP],'void generate_exh(',exh)
    out[CPP]=parent.change(out[CPP],'void append_payload(',lambda _:APPENDER)
    # New appender consumes actual unshifted memory lanes, handling0/4/16/20
    # header bytes in one real producer. Keep original physical data width.
    for call in [
        'lshiftWordByOctet<WIDTH,12,INSTID>(((AETH_SIZE%WIDTH)/8), tx_split2aethShift, tx_aethShift2payFifo);',
        'lshiftWordByOctet<WIDTH,13,INSTID>(((RETH_SIZE%WIDTH)/8), tx_rethMerge2rethShift, tx_rethShift2payFifo);']:
        out[CPP]=once(out[CPP],call,'/* integrated by typed immediate append_payload */')
    out[CPP]=once(out[CPP],'append_payload<WIDTH, INSTID>(tx_packetInfoFifo, tx_exh2payFifo, tx_aethShift2payFifo, tx_rethShift2payFifo, tx_rawPayFifo, tx_exh2shiftFifo);',
        'append_payload<WIDTH, INSTID>(tx_packetInfoFifo, tx_exh2payFifo, tx_split2aethShift, tx_rethMerge2rethShift, tx_rawPayFifo, tx_exh2shiftFifo);')
    r=out[RETRANS]
    for name in ['retransAddrLen','retransEntry','retransMetaEntry']:
        r=once(r,'struct '+name+'\n{','struct '+name+'\n{\n    ap_uint<32> immediate=0;')
    r=once(r,':request_owned(meta.request_owned),request_token(meta.request_token),rkey(addrlen.rkey)',
        ':immediate(addrlen.immediate),request_owned(meta.request_owned),request_token(meta.request_token),rkey(addrlen.rkey)')
    r=once(r,':request_owned(e.request_owned),request_token(e.request_token),rkey(e.rkey)',
        ':immediate(e.immediate),request_owned(e.request_owned),request_token(e.request_token),rkey(e.rkey)')
    r=once(r,'p.rkey=receipt_entry.rkey;p.rkey_valid=',
        'p.immediate=receipt_entry.immediate;p.rkey=receipt_entry.rkey;p.rkey_valid=')
    r=parent.change(r,'void process_retransmissions(',lambda t:compare_ops(t,'meta.opCode'))
    # Constructor keeps compatibility with old call sites; actual replay
    # copies its retained immediate independently of the full remote key.
    out[HPP]=once(out[HPP],'ap_uint<1> host = PKG_INT)\n\t\t:rkey(rkey), rkey_valid(rkey_valid), host(host), op_code(op)',
        'ap_uint<1> host = PKG_INT,ap_uint<32> immediate=0)\n\t\t:immediate(immediate),rkey(rkey), rkey_valid(rkey_valid), host(host), op_code(op)')
    if r.count('meta.rkey, meta.rkey_valid, meta.host));')!=2:raise ValueError('unreviewed replay constructors')
    r=r.replace('meta.rkey, meta.rkey_valid, meta.host));','meta.rkey, meta.rkey_valid, meta.host, meta.immediate));')
    out[RETRANS]=r
    out[TOP]=out[TOP].replace('rocev2_native_duplex_top','rocev2_native_immediate_request_top')
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve prior source')
    origin=parent.qp.BASE;before={str(x.relative_to(origin)):parent.qp.digest(x)for x in origin.rglob('*')if x.is_file()}
    files=derive();shutil.copytree(origin/'fns',a.output/'fns');shutil.copytree(origin/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if before!={n:parent.qp.digest(origin/n)for n in before}:raise ValueError('original changed')
    info=dict(scope=__doc__,source_base=str(origin),source_sha256=before,
        generator_sha256=parent.qp.digest(__file__),derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        original_unchanged=True,external_replay=True,native_rnr=True,receive_retirement=True,request_retirement=True,
        duplex_memory_provenance=True,request_immediate=True,receive_immediate=False,native_integration=False,
        HLS_top='rocev2_native_immediate_request_top',request_context_bits=620,SQ_payload_bits=280,
        metadata_entries=2000,MAX_QPS=8,source_only=True,hardware_verified=False,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=info['HLS_top'],original_unchanged=True)))

if __name__=='__main__':main()
