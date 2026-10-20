#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in actual FNS TX producers carrying immutable per-WR context.

No shared/native/board selection, RX lookup, producer fence, MAC-SFD or CQ
completion is implied. Original licensed inputs are never modified.
"""
import importlib.util
from pathlib import Path
import re

spec=importlib.util.spec_from_file_location('owned_timer',Path(__file__).with_name('owned_timer_profile.py'))
owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
ROOT=owned.ROOT;BASE=owned.BASE;META=owned.META;once=owned.once
CPP=BASE/'fns/hls/ib_transport_protocol/ib_transport_protocol.cpp'
HPP=CPP.with_suffix('.hpp')

CONTEXT=r'''
// This is a trusted internal context, NEVER obtained from wire packet bytes
// or a late "current QP owner" lookup. Native admission binding is still open.
struct as02WireContext {
    ap_uint<16> qpn=0;ap_uint<64> epoch=0,sequence=0;
    ap_uint<248> lease=0;bool valid=false,retry=false;
};
inline bool as02_wire_valid(as02WireContext c,ap_uint<24> qpn) {
    return c.valid && qpn<MAX_QPS && c.qpn==qpn && c.epoch!=0 && c.sequence!=0;
}
inline bool as02_wire_same(as02WireContext a,as02WireContext b) {
    return a.valid==b.valid && a.retry==b.retry && a.qpn==b.qpn &&
        a.epoch==b.epoch && a.sequence==b.sequence && a.lease==b.lease;
}
template<typename T> inline T as02_wire_tag(T normal,as02WireContext owner) {
    normal.owner=owner;return normal;
}
'''

ADMIT=r'''
// Pair EXACTLY ONE existing248-bit SQ record with its trusted192-bit context.
// This boundary must be wired to the real admitted/native owner, not userspace
// descriptor/wire data. It does not authenticate that external source itself.
template<int ID=0>
void as02_owned_wire_admit(stream<ap_uint<248>>& sq,stream<ap_uint<192>>& contexts,
    stream<as02WireTxMeta>& out,ap_uint<32>& fault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<32> error=0;fault=error;if(error)return;
    if(!sq.empty() && !contexts.empty() && !out.full()) {
        ap_uint<248> r=sq.read();ap_uint<192> c=contexts.read();as02WireTxMeta m;
        ap_uint<32> op=r(31,0);m.qpn=r(41,32);m.host=r[42];m.lst=r[43];m.offs=r(47,44);
        m.params=r(239,48);m.rkey_valid=r[240];
        m.owner.qpn=c(15,0);m.owner.epoch=c(79,16);m.owner.sequence=c(143,80);m.owner.valid=true;
        if(r(247,241)!=0 || c(191,144)!=0 || op>RC_ACK ||
            !as02_wire_valid(m.owner,m.qpn)) {error=1;return;}
        m.op_code=static_cast<ibOpCode>(op.to_uint());out.write(m);
    }
}
'''

HEADER_WORD=r'''
// Same packetHeader::consumeWord contract, using constant word cases instead
// of a full16-bit add -> multiply -> subtract -> compare chain. The COMPLETE
// original16-bit index is compared; out-of-range values do not wrap or change
// output/index. Partial last words preserve the original unused output lanes.
// ready/header contents are untouched, as in the original consumer.
template<int WIDTH,int BITS>
ap_uint<8> as02_owned_wire_consume_word(packetHeader<WIDTH,BITS>& h,ap_uint<WIDTH>& word) {
#pragma HLS inline
    static_assert(WIDTH>0 && WIDTH%8==0 && BITS>0 && BITS%8==0,"whole-byte headers/words required");
    static_assert((BITS+WIDTH-1)/WIDTH<65536,"original16-bit index capacity");
    const uint16_t index=h.idx;ap_uint<8> remaining=0;
    for(unsigned i=0;i<(BITS+WIDTH-1)/WIDTH;i++) {
#pragma HLS unroll
        // Capture before updating h.idx: never consume multiple words at once.
        if(index==i) {
            if((i+1)*WIDTH<=BITS) {
                word=h.header((i+1)*WIDTH-1,i*WIDTH);
                remaining=(BITS-(i+1)*WIDTH)/8;
            } else {
                word(BITS-i*WIDTH-1,0)=h.header(BITS-1,i*WIDTH);
                remaining=0;
            }
            h.idx=i+1;
        }
    }
    return remaining;
}
'''


def source_block(source,anchor):
    # Upstream local_req_handler contains a commented-out switch opening brace.
    # Braces in comments/quoted debug text are not C++ scope delimiters.
    masked=re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        lambda m:re.sub(r'[^\n]',' ',m.group()),source)
    start=masked.index(anchor);left=masked.index('{',start);depth=1;end=left+1
    while depth and end<len(masked):
        if masked[end]=='{':depth+=1
        elif masked[end]=='}':depth-=1
        end+=1
    if depth:raise ValueError('unclosed real C++ function/struct: '+anchor)
    return start,left,end


def struct(source,name,new_name):
    start,_,end=source_block(source,'struct '+name+'\n')
    text=source[start:end+1]
    text=re.sub(r'\b'+name+r'\b',new_name,text)
    at=text.index('{')
    return text[:at+1]+'\n    as02WireContext owner;'+text[at+1:]


def function(source,name):
    start,_,end=source_block(source,'void '+name+'(')
    template=source.rfind('template <',0,start)
    # merge_retrans_request is the one non-template original producer.
    if name!='merge_retrans_request':start=template
    return source[start:end]


def guarded(text,signature):
    text=once(text,signature,signature.rsplit(')',1)[0]+',ap_uint<32>& fault)')
    # Insert after the two original pragmas, not into comments/other functions.
    anchor='#pragma HLS pipeline II=1'
    return once(text,anchor,anchor+'\n    static ap_uint<32> error=0;fault=error;if(error)return;')


def derive(cpp,hpp,meta):
    license=cpp[:cpp.index('#include')]
    types=CONTEXT+'\n'+ '\n'.join(struct(src,name,new) for src,name,new in [
        (hpp,'txMeta','as02WireTxMeta'),(hpp,'event','as02WireEvent'),
        (hpp,'ibhMeta','as02WireIBHMeta'),(meta,'retransMeta','as02WireRetransMeta'),
        (meta,'retransAddrLen','as02WireAddrLen')])
    def fn(name):
        f=function(cpp,name)
        for old,new in [('txMeta','as02WireTxMeta'),('event','as02WireEvent'),('ibhMeta','as02WireIBHMeta'),
            ('retransMeta','as02WireRetransMeta'),('retransAddrLen','as02WireAddrLen')]:
            f=re.sub(r'\b'+old+r'\b',new,f)
        return once(f,'void '+name+'(','void as02_owned_wire_'+name+'(')
    local=fn('local_req_handler')
    local=guarded(local,'ap_uint<32>& regRetransCount)')
    local=once(local,'stream<retransEvent>& retransEventFifo','stream<as02OwnedEvent>& retransEventFifo')
    local=once(local,'retransEventFifo.read(rev);',r'''
        as02OwnedEvent owned_event=retransEventFifo.read();rev=owned_event.normal;
        as02WireContext retry_owner;retry_owner.qpn=owned_event.lease(95,80);
        retry_owner.epoch=owned_event.lease(183,120);retry_owner.sequence=owned_event.lease(247,184);
        retry_owner.lease=owned_event.lease;retry_owner.retry=true;retry_owner.valid=true;
        if(owned_event.marker || !as02_wire_valid(retry_owner,rev.qpn) ||
            owned_event.lease(79,16)==0 || owned_event.lease(15,0)>=META_TABLE_SIZE || !rev.validPsn) {
            error=2;return; // fence markers require a future real producer closure
        }
''')
    local=once(local,'ev.rkey = rev.rkey;','ev.owner=retry_owner;\n\t\tev.rkey = rev.rkey;')
    local=once(local,'s_axis_sq_meta.read(meta);',r'''
        s_axis_sq_meta.read(meta);
        bool supported=meta.op_code==RC_RDMA_READ_REQUEST || meta.op_code==RC_RDMA_WRITE_ONLY ||
            meta.op_code==RC_RDMA_WRITE_FIRST || meta.op_code==RC_RDMA_WRITE_MIDDLE || meta.op_code==RC_RDMA_WRITE_LAST ||
            meta.op_code==RC_SEND_ONLY || meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST;
        if(!supported || !as02_wire_valid(meta.owner,meta.qpn) || meta.owner.retry || meta.owner.lease!=0 ||
            (meta.op_code==RC_RDMA_READ_REQUEST && meta.params(159,128)==0)) {error=3;return;}
''')
    # Both actual READ and WRITE/SEND branches must copy the immutable owner.
    anchor='ev = as02WireEvent(meta.op_code, meta.qpn, raddr, length);'
    if local.count(anchor)!=2:raise ValueError('READ and WRITE producer branches changed')
    local=local.replace(anchor,anchor+'\n            ev.owner=meta.owner;')
    addr='as02WireAddrLen(laddr, raddr, length, lst, offs, meta.params(191,160), meta.rkey_valid, meta.host)'
    local=once(local,addr,'as02_wire_tag('+addr+',meta.owner)')

    merger=fn('meta_merger')
    for call in ['as02WireIBHMeta(ev.op_code, key, ev.qpn, ev.psn, ev.validPsn)',
                 'as02WireIBHMeta(ev.op_code, key, ev.qpn, numPkg)']:
        # Response and retry paths can have the same constructor spelling.
        if call not in merger:raise ValueError('meta merger owner anchor changed')
        merger=merger.replace(call,'as02_wire_tag('+call+',ev.owner)')

    ibh=fn('generate_ibh')
    ibh=guarded(ibh,'stream<BaseTransportHeader<WIDTH> >& tx_ibhHeaderFifo\n)')
    ibh=once(ibh,'// Else: Set the PSN, request an ACK and update the PSN in the state table.',r'''
                if(!as02_wire_valid(meta.owner,meta.dest_qp) || meta.owner.retry || meta.owner.lease!=0) {error=4;return;}
                // Else: Set the PSN, request an ACK and update the PSN in the state table.''')
    insert='as02WireRetransMeta(meta.dest_qp, qpState.req_next_psn, meta.op_code)'
    ibh=once(ibh,insert,'as02_wire_tag('+insert+',meta.owner)')

    exh=fn('generate_exh')
    exh=guarded(exh,'stream<net_axis<WIDTH> >& output\n)')
    exh=once(exh,'stream<ap_uint<24> >&\ttxSetTimer_req','stream<as02WireContext>&\ttxSetTimer_req')
    # Preserve the actual original generate_exh timer condition and position.
    # Its old omission of SEND is NOT claimed fixed by this context change.
    exh=once(exh,'txSetTimer_req.write(meta.qpn);\n\t\t\t}',r'''
                if(!as02_wire_valid(meta.owner,meta.qpn)) {error=5;return;}
                txSetTimer_req.write(meta.owner);
            }''')
    if exh.count('rdmaHeader.consumeWord(sendWord.data)')!=2 or exh.count('ackHeader.consumeWord(sendWord.data)')!=2:
        raise ValueError('actual RETH/AETH word consumer sites changed')
    exh=exh.replace('rdmaHeader.consumeWord(sendWord.data)',
        'as02_owned_wire_consume_word<WIDTH,RETH_SIZE>(rdmaHeader,sendWord.data)')
    exh=exh.replace('ackHeader.consumeWord(sendWord.data)',
        'as02_owned_wire_consume_word<WIDTH,AETH_SIZE>(ackHeader,sendWord.data)')

    merge=fn('merge_retrans_request')
    merge=once(merge,'stream<retransEntry>&\t\ttx2retrans_insertRequest',
        'stream<as02OwnedInsert>&\t\ttx2retrans_insertRequest')
    merge=guarded(merge,'stream<as02OwnedInsert>&\t\ttx2retrans_insertRequest\n)')
    merge=once(merge,'tx2retrans_insertRequest.write(retransEntry(meta, addrlen));',r'''
        if(!as02_wire_valid(meta.owner,meta.qpn) || !as02_wire_same(meta.owner,addrlen.owner) ||
            meta.owner.retry || meta.owner.lease!=0) {error=6;return;}
        as02OwnedInsert out;
        out.normal=retransEntry(meta.qpn,meta.psn,meta.opCode,addrlen.localAddr,addrlen.remoteAddr,
            addrlen.length,addrlen.lst,addrlen.offs,addrlen.rkey,addrlen.rkey_valid,addrlen.host);
        out.epoch=meta.owner.epoch;out.sequence=meta.owner.sequence;out.bad=false;out.marker=false;
        tx2retrans_insertRequest.write(out);''')
    return license+'''#pragma once
#include "ib_transport_protocol.hpp"
#include "state_table.hpp"
#include "msn_table.hpp"
#include "retransmitter/owned_retrans_fence.hpp"
'''+types+'\n'+ADMIT+'\n'+HEADER_WORD+'\n'+'\n\n'.join([local,merger,ibh,exh,merge])+'\n'
