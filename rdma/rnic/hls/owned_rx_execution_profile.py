#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in actual FNS RX IBH/EXH FSMs with immutable packet/native ownership.

This is source/offline integration, NOT authenticated native admission, the
ONE shared/native transport selection, DMA/CQ, a drain/unpin certificate, or
physical qualification. Original licensed/frozen inputs are never edited.
"""
import importlib.util
import re
from pathlib import Path

spec=importlib.util.spec_from_file_location('wire_tx',Path(__file__).with_name('owned_wire_tx_profile.py'))
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
ROOT=source.ROOT;CPP=source.CPP;HPP=source.HPP;once=source.once

TYPES=r'''
// Must come from the real retained native WR/MR admission, not wire bytes,
// a userspace permission bit, or a late current-head lookup. Acceptance here
// retains these EXACT values; the caller must already hold all real refs.
// No output below is CQ publication or permission to release those refs.
struct as02RxExecutionOwner {
    ap_uint<1024> packet=0;ap_uint<588> native=0;
};
inline bool as02_rx_same_owner(as02RxExecutionOwner a,as02RxExecutionOwner b) {
    return a.packet==b.packet && a.native==b.native;
}
template<typename T> struct as02RxOwned {
    T normal;as02RxExecutionOwner owner;
    as02RxOwned() {}
    as02RxOwned(T n,as02RxExecutionOwner o):normal(n),owner(o) {}
};
template<typename T> inline as02RxOwned<T> as02_rx_tag(T n,as02RxExecutionOwner o) {
    return as02RxOwned<T>(n,o);
}
// SAME588-bit layout as rocev2_wqe_hls_sq/shared transport/lifetime. Keep
// every bit, including zero keys/PD/tag/wr_id/flags/offset and error provenance.
inline ap_uint<24> as02_rx_qpn(as02RxExecutionOwner o) {return o.native(395,372);}
inline ap_uint<64> as02_rx_va(as02RxExecutionOwner o) {return o.native(243,180);}
inline ap_uint<32> as02_rx_length(as02RxExecutionOwner o) {return o.native(307,276);}
inline ap_uint<24> as02_rx_delta(as02RxExecutionOwner o) {return o.packet(391,368);}
inline ap_uint<64> as02_rx_address(as02RxExecutionOwner o) {
    return as02_rx_va(o)+ap_uint<64>(as02_rx_delta(o))*PMTU;
}
inline ap_uint<8> as02_rx_syndrome(as02RxExecutionOwner o) {return o.packet(419,412);}
inline bool as02_rx_control(as02RxExecutionOwner o) {
    return o.packet[420] && as02_rx_syndrome(o)(7,5)!=0;
}
inline bool as02_rx_execution_valid(as02RxExecutionOwner o) {
    ap_uint<448> b=o.packet(447,0);ap_uint<248> lease=b(247,0);
    ap_uint<320> d=o.packet(1015,696);ap_uint<588> n=o.native;
    ap_uint<24> qpn=as02_rx_qpn(o),psn=b(295,272);ap_uint<8> op=b(303,296);
    ap_uint<64> epoch=n(459,396),sequence=n(523,460);
    ap_uint<16> native_op=n(339,324);ap_uint<32> length=as02_rx_length(o);
    BaseTransportHeader<64> h;h.setRawHeader(o.packet(543,448));
    ExHeader<64> ex;ex.setRawHeader(o.packet(671,544));AckExHeader<64> a=ex.getAckHeader();
    bool has=op!=RC_RDMA_READ_RESP_MIDDLE;
    ap_uint<65> va_end=ap_uint<65>(as02_rx_va(o))+length;
    ap_uint<65> off_end=ap_uint<65>(n(179,116))+length;
    ap_uint<65> remote_end=ap_uint<65>(n(115,52))+length;
    const ap_uint<65> limit=ap_uint<65>(1)<<64;
    // Widen before modular subtraction. The intermediate never becomes a
    // negative vendor ap_int on the host model when the24-bit PSN wraps.
    ap_uint<25> psn_distance=ap_uint<25>(psn)+(ap_uint<25>(1)<<24);
    psn_distance=psn_distance-ap_uint<25>(lease(119,96));
    if(n(19,2)!=0 || !n[1] || !n[0] || n(355,340)==0 || n(323,309)!=0 ||
        (native_op!=1 && native_op!=2) || qpn>=MAX_QPS || epoch==0 || sequence==0 ||
        va_end>limit || off_end>limit || remote_end>limit) return false;
    if(o.packet(1023,1016)!=0 || o.packet[695] || !b[422] || b(447,423)!=0 ||
        b(399,392)!=0 || b(411,400)==0 || b(411,400)>META_TABLE_SIZE ||
        lease(15,0)>=META_TABLE_SIZE || lease(79,16)==0 || lease(95,80)!=qpn ||
        lease(183,120)!=epoch || lease(247,184)!=sequence ||
        b(271,248)!=qpn || b(367,304)!=epoch ||
        ap_uint<24>(psn_distance)!=as02_rx_delta(o)) return false;
    if(d(319,290)!=0 || d[105] || !d[104] || d(273,106)!=0 ||
        d(23,0)!=qpn || d(87,24)!=epoch || d(103,88)<(has?16:12) ||
        ap_uint<17>(d(103,88))+12>65535 || op<RC_RDMA_READ_RESP_FIRST || op>RC_ACK ||
        b[420]!=has || h.getOpCode()!=op || h.getDstQP()!=qpn || h.getPsn()!=psn ||
        h.getPartitionKey()!=d(289,274) || (o.packet(463,456)&15)!=0 ||
        (o.packet(487,480)&63)!=0 || (o.packet(519,512)&127)!=0 ||
        o.packet(693,672)!=1) return false;
    if(has) {
        if(a.getSyndrome()!=as02_rx_syndrome(o) || bool(o.packet[694])!=a.isNAK())return false;
    } else if(o.packet(671,544)!=0 || as02_rx_syndrome(o)!=0 || o.packet[694])return false;
    // All7 nonpositive syndrome classes are retained for a dedicated control
    // consumer, never interpreted as successful ACK/READ data or timer-clear.
    if(op!=RC_ACK && native_op!=2)return false;
    if(as02_rx_control(o))return true;
    ap_uint<2> pad=o.packet(461,460);
    if(op==RC_ACK)return native_op==1 && d(103,88)==16 && pad==0 && as02_rx_delta(o)==0;
    if(native_op!=2 || length==0)return false;
    ap_uint<33> span=(ap_uint<33>(length)+PMTU-1)/PMTU;
    ap_uint<33> delta=as02_rx_delta(o),offset=delta*PMTU;
    if(span==0 || span>=8388608 || delta>=span || offset>=length)return false;
    bool first=delta==0,last=delta==span-1;
    unsigned expected_op=first?(last?RC_RDMA_READ_RESP_ONLY:RC_RDMA_READ_RESP_FIRST):
        (last?RC_RDMA_READ_RESP_LAST:RC_RDMA_READ_RESP_MIDDLE);
    ap_uint<32> bytes=length-offset;if(bytes>PMTU)bytes=PMTU;
    // Avoid passing a negative ap_int temporary into the vendor constructor.
    // 4-(bytes mod4) is nonnegative; its low2bits are exactly (-bytes) mod4.
    ap_uint<3> complement=ap_uint<3>(4)-ap_uint<3>(bytes(1,0));
    ap_uint<2> expected_pad=last?ap_uint<2>(complement):ap_uint<2>(0);
    return op==expected_op && pad==expected_pad &&
        ap_uint<33>(d(103,88))==ap_uint<33>(has?16:12)+bytes+expected_pad;
}
inline bool as02_rx_ibh_matches(ibhMeta m,as02RxExecutionOwner o) {
    BaseTransportHeader<64> b;b.setRawHeader(o.packet(543,448));
    return m.op_code==b.getOpCode() && m.partition_key==b.getPartitionKey() &&
        m.dest_qp==b.getDstQP() && m.psn==b.getPsn() && m.validPSN;
}
// Keep full64-bit VA BEFORE the original memCmd constructor's48-bit
// address/28-bit length/10-bit QP routing packing. Never reconstruct native
// DMA authority from that lossy transport word or from current QP state.
struct as02RxMemoryEffect {
    // length is the original RAW transport byte count (including padding),
    // NOT native DMA authority. Checked unpad must consume pad_bytes and the
    // real native executor must use payload_length with the retained MR/PTE.
    ap_uint<64> address=0;ap_uint<32> length=0;ap_uint<24> qpn=0;
    ap_uint<32> payload_length=0;ap_uint<2> pad_bytes=0;
    ap_uint<1> ctl=0,host=0;as02RxExecutionOwner owner;
};
inline as02RxMemoryEffect as02_rx_memory_effect(ap_uint<64> address,ap_uint<32> length,
    ap_uint<1> ctl,ap_uint<1> host,ap_uint<24> qpn,as02RxExecutionOwner owner) {
    as02RxMemoryEffect e;e.address=address;e.length=length;e.ctl=ctl;e.host=host;e.qpn=qpn;e.owner=owner;
    e.pad_bytes=owner.packet(461,460);
    e.payload_length=length>=e.pad_bytes?ap_uint<32>(length-e.pad_bytes):ap_uint<32>(0);
    return e;
}
inline bool as02_rx_memory_valid(as02RxMemoryEffect e) {
    as02RxExecutionOwner o=e.owner;ap_uint<8> op=o.packet(303,296);
    bool last=op==RC_RDMA_READ_RESP_ONLY || op==RC_RDMA_READ_RESP_LAST;
    ap_uint<32> bytes=as02_rx_length(o)-ap_uint<33>(as02_rx_delta(o))*PMTU;
    if(bytes>PMTU)bytes=PMTU;
    ap_uint<2> pad=o.packet(461,460);
    return as02_rx_execution_valid(o) && !as02_rx_control(o) && op!=RC_ACK &&
        e.qpn==as02_rx_qpn(o) && e.host==PKG_HOST && e.address==as02_rx_address(o) &&
        e.length==ap_uint<33>(bytes)+pad && e.payload_length==bytes && e.pad_bytes==pad && bool(e.ctl)==last;
}
// Native MSN progress counts payload, not wire padding. The original raw
// READ ONLY/FIRST/MIDDLE updates otherwise store an out-of-range padded VA.
// This is state progression only, NOT memory visibility/CQ/MR release.
inline as02RxOwned<rxMsnReq> as02_rx_msn_effect(rxMsnReq normal,as02RxExecutionOwner owner) {
    ap_uint<8> op=owner.packet(303,296);
    if(normal.write && op>=RC_RDMA_READ_RESP_FIRST && op<=RC_RDMA_READ_RESP_ONLY) {
        ap_uint<32> bytes=as02_rx_length(owner)-ap_uint<33>(as02_rx_delta(owner))*PMTU;
        if(bytes>PMTU)bytes=PMTU;
        normal.vaddr=as02_rx_address(owner)+bytes;normal.dma_length=bytes;
    }
    return as02_rx_tag(normal,owner);
}
// One exact raw-frame token paired with ONE already retained native context.
// Does not obtain actual ib_umem/PD/QP references or authenticate its caller.
void as02_rx_execution_admit(stream<ap_uint<1024>>& frames,stream<ap_uint<588>>& natives,
    stream<as02RxOwned<ibhMeta>>& ibhs,stream<as02RxOwned<exhMeta>>& exhs,ap_uint<32>& fault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<32> error=0;static as02RxExecutionOwner owner;
    fault=error;if(error)return;
    if(!frames.empty() && !natives.empty() && !ibhs.full() && !exhs.full()) {
        owner.packet=frames.read();owner.native=natives.read();
        if(!as02_rx_execution_valid(owner)) {error=60;return;}
        BaseTransportHeader<64> b;b.setRawHeader(owner.packet(543,448));
        ibhMeta m(b.getOpCode(),b.getPartitionKey(),b.getDstQP(),b.getPsn(),true);
        exhMeta e(bool(owner.packet[694]),ap_uint<22>(owner.packet(693,672)));
        ibhs.write(as02_rx_tag(m,owner));exhs.write(as02_rx_tag(e,owner));
    }
}
'''

def tag_writes(text,names):
    """Wrap each exact actual effect expression, retaining its original value."""
    for name in names:
        pattern=re.compile(r'\b'+name+r'\.write\(')
        positions=list(pattern.finditer(text))
        if not positions:raise ValueError('missing actual RX effect: '+name)
        for match in reversed(positions):
            start=match.end();end=start;depth=1
            while depth and end<len(text):
                if text[end]=='(':depth+=1
                elif text[end]==')':depth-=1
                end+=1
            if depth:raise ValueError('unclosed RX output expression')
            original=text[start:end-1]
            if name=='memoryWriteCmd':
                if not original.startswith('memCmd(') or not original.endswith(')'):
                    raise ValueError('original full-address memory constructor changed')
                args=original[len('memCmd('):-1]
                replacement='{ as02RxMemoryEffect effect=as02_rx_memory_effect('+args+',owner);\n'
                replacement+=' if(!as02_rx_memory_valid(effect)) {error=67;return;}\n memoryWriteCmd.write(effect); }'
                if text[end:end+1]!=';':raise ValueError('memory expression semicolon changed')
                text=text[:match.start()]+replacement+text[end+1:]
            else:
                tag='as02_rx_msn_effect'if name=='rxExh2msnTable_upd_req'else'as02_rx_tag'
                text=text[:start]+tag+'('+original+',owner)'+text[end-1:]
    return text

def owned_streams(text,names):
    for name in names:
        text,count=re.subn(r'stream<\s*'+name+r'\s*>\s*&',r'stream<as02RxOwned<'+name+r'>>&',text)
        if not count:raise ValueError('missing actual RX typed stream: '+name)
    return text

def derive_ibh(cpp):
    s=source.function(cpp,'rx_ibh_fsm')
    s=once(s,'void rx_ibh_fsm(','void as02_owned_rx_ibh_fsm(')
    s=once(s,'ap_uint<32>&\t\tregInvalidPsnDropCount\n)',
        'ap_uint<32>&\t\tregInvalidPsnDropCount,\n stream<as02RxOwned<ap_uint<8>>>& controls,ap_uint<32>& fault\n)')
    s=owned_streams(s,['ibhMeta','exhMeta','rxStateRsp','rxStateReq','ackEvent','bool','fwdPolicy','ackMeta','rxTimerUpdate','retransUpdate','psnPkg'])
    s=once(s,'#pragma HLS pipeline II=1',
        '#pragma HLS pipeline II=1\n static ap_uint<32> error=0;static as02RxExecutionOwner owner;\n fault=error;if(error)return;')
    s=once(s,'metaIn.read(meta);',
        'as02RxOwned<ibhMeta> im=metaIn.read();owner=im.owner;meta=im.normal;')
    s=once(s,'exhMetaFifo.read(emeta);',r'''as02RxOwned<exhMeta> em=exhMetaFifo.read();emeta=em.normal;
            if(!as02_rx_execution_valid(owner) || !as02_rx_same_owner(owner,em.owner) ||
                !as02_rx_ibh_matches(meta,owner) || emeta.numPkg!=owner.packet(693,672) ||
                emeta.isNak!=bool(owner.packet[694])) {error=61;return;}
            if(as02_rx_control(owner)) {controls.write(as02_rx_tag(as02_rx_syndrome(owner),owner));return;}''')
    s=once(s,'stateTable_rsp.read(qpState);',r'''as02RxOwned<rxStateRsp> rsp=stateTable_rsp.read();
            if(!as02_rx_same_owner(owner,rsp.owner)) {error=62;return;}
            qpState=rsp.normal;''')
    s=once(s,'if (isResponse && meta.op_code != RC_RDMA_READ_RESP_MIDDLE)',
        'if (isResponse && !emeta.isNak && meta.op_code != RC_RDMA_READ_RESP_MIDDLE)')
    return tag_writes(s,['stateTable_upd_req','metaOut','ibhEventFifo','ibhDropFifo','ibhDropMetaFifo',
        'm_axis_rx_ack_meta','rxClearTimer_req','rx2retrans_upd','m_axis_dbg'])

def derive_exh(cpp):
    s=source.function(cpp,'rx_exh_fsm')
    s=once(s,'void rx_exh_fsm(','void as02_owned_rx_exh_fsm(')
    s=once(s,'stream<ap_uint<16> >& udpLengthFifo,','/* UDP length is reconstructed from the SAME validated frame, not an independent FIFO. */')
    s=once(s,'stream<ExHeader<WIDTH> >& headerInput,','/* EXH comes from the SAME validated full-token owner. */')
    s=once(s,'stream<pkgShift>& rx_pkgShiftTypeFifo\n)',
        'stream<pkgShift>& rx_pkgShiftTypeFifo,ap_uint<32>& fault\n)')
    s=once(s,'stream<memCmd>& memoryWriteCmd','stream<as02RxMemoryEffect>& memoryWriteCmd')
    s=owned_streams(s,['ibhMeta','dmaState','retransmission','retransRdInit','readRequest','rxMsnReq','ackEvent','pkgSplit','pkgShift'])
    s=once(s,'#pragma HLS pipeline II=1',
        '#pragma HLS pipeline II=1\n static ap_uint<32> error=0;static as02RxExecutionOwner owner;\n fault=error;if(error)return;')
    s=once(s,'if (!metaIn.empty() && !headerInput.empty())','if (!metaIn.empty())')
    s=once(s,'metaIn.read(meta);',r'''as02RxOwned<ibhMeta> im=metaIn.read();owner=im.owner;meta=im.normal;
            if(!as02_rx_execution_valid(owner) || !as02_rx_ibh_matches(meta,owner) ||
                as02_rx_control(owner)) {error=63;return;}''')
    s=once(s,'headerInput.read(exHeader);',r'''exHeader.setRawHeader(owner.packet(671,544));
            udpLength=ap_uint<17>(owner.packet(799,784))+12;''')
    s=once(s,'!msnTable2rxExh_rsp.empty() && !udpLengthFifo.empty() && (!consumeReadInit || !retrans2rx_init.empty())',
        '!msnTable2rxExh_rsp.empty() && (!consumeReadInit || !retrans2rx_init.empty())')
    s=once(s,'msnTable2rxExh_rsp.read(dmaMeta);',r'''as02RxOwned<dmaState> dm=msnTable2rxExh_rsp.read();
            if(!as02_rx_same_owner(owner,dm.owner)) {error=64;return;}
            dmaMeta=dm.normal;
            if((meta.op_code==RC_RDMA_READ_RESP_MIDDLE || meta.op_code==RC_RDMA_READ_RESP_LAST) &&
                (dmaMeta.vaddr!=as02_rx_address(owner) || (meta.op_code==RC_RDMA_READ_RESP_LAST && dmaMeta.lst!=1))) {
                error=65;return;
            }''')
    s=once(s,'udpLengthFifo.read(udpLength);','/* SAME-token UDP length was captured before the MSN request. */')
    s=once(s,'retrans2rx_init.read(readReqInit);',r'''as02RxOwned<retransRdInit> ri=retrans2rx_init.read();
                if(!as02_rx_same_owner(owner,ri.owner) || ri.normal.laddr!=as02_rx_va(owner) || ri.normal.lst!=1) {
                    error=66;return;
                }
                readReqInit=ri.normal;''')
    last='memoryWriteCmd.write(memCmd(dmaMeta.vaddr, payLoadLength, dmaMeta.lst, PKG_HOST, meta.dest_qp));'
    s=once(s,last,last+r'''
                // Close the real MSN packet transaction for LAST as well.
                // The owned service validates the exact pending packet before
                // changing state. This is NOT WR/MR/CQ retirement.
                rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp,dmaMeta.msn,
                    dmaMeta.vaddr+payLoadLength,payLoadLength,dmaMeta.lst));''')
    return tag_writes(s,['memoryWriteCmd','readRequestFifo','rxExh2msnTable_upd_req','rx_exhEventMetaFifo',
        'rx_pkgSplitTypeFifo','rx_pkgShiftTypeFifo','rx2retrans_req'])

def derive(cpp):
    license=cpp[:cpp.index('#include')]
    return license+'''#pragma once
#include "ib_transport_protocol.hpp"
#include "state_table.hpp"
#include "msn_table.hpp"
#include "transport_timer.hpp"
#include "retransmitter/retransmitter.hpp"
'''+TYPES+'\n'+derive_ibh(cpp)+'\n'+derive_exh(cpp)+'\n'
