#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SAME state/MSN table consumers for owned RX execution, no hardware.

One real state RAM and one real MSN RAM per instance, not shadow lookup tables.
Native admission/read-init/pool/core drain/CQ/ONE-board selection still open.
"""
import importlib.util
from pathlib import Path
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
rx=module('owned_rx_execution',Path(__file__).with_name('owned_rx_execution_profile.py'))
state=module('state_fence',Path(__file__).with_name('state_table_fence_profile.py'))
ROOT=rx.ROOT;BASE=rx.source.BASE;STATE=state.STATE;MSN=STATE.with_name('msn_table.hpp');once=state.once

TYPES=r'''
struct as02RxStateMessage {as02StateReq normal;as02RxExecutionOwner owner;};
struct as02RxStateEntry {
    stateTableEntry normal;as02StateReq request;
    as02RxStateEntry() {}
    as02RxStateEntry(stateTableEntry n,as02StateReq r):normal(n),request(r) {}
};
// Normal RX requests use a retained full owner. Markers must eventually be
// injected by the REAL producer in this SAME queue; empty is not a marker.
template<int ID=0> void as02_owned_rx_state_encode(stream<as02RxOwned<rxStateReq>>& in,
    stream<as02RxStateMessage>& out,ap_uint<32>& fault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<32> error=0;static as02RxOwned<rxStateReq> held;
    fault=error;if(error)return;
    if(!in.empty() && !out.full()) {
        held=in.read();as02RxStateMessage m;m.owner=held.owner;
        if(!as02_rx_execution_valid(m.owner) || as02_rx_control(m.owner) ||
            held.normal.qpn!=as02_rx_qpn(m.owner) || !held.normal.isResponse) {error=70;return;}
        m.normal.qpn=held.normal.qpn;m.normal.write=held.normal.write;m.normal.response=true;
        m.normal.epoch=m.owner.native(459,396);m.normal.sequence=m.owner.native(523,460);
        if(held.normal.write) {m.normal.a=held.normal.epsn;m.normal.rc=held.normal.retryCounter;}
        out.write(m);
    }
}
struct as02MsnTxReq {
    ap_uint<24> qpn=0;ap_uint<64> epoch=0,sequence=0;
};
struct as02MsnTxRsp {
    txMsnRsp normal;as02MsnTxReq request;
    as02MsnTxRsp() {}
    as02MsnTxRsp(txMsnRsp n,as02MsnTxReq r):normal(n),request(r) {}
};
struct as02MsnInit {
    ap_uint<24> qpn=0;ap_uint<32> rkey=0;ap_uint<64> epoch=0,sequence=0;
};
// The OWNER IS IN THE REAL MSN ENTRY. Never tag stale data merely with the
// new requester. No parallel lease->WR lookup/shadow RAM is introduced.
struct as02MsnOwnedEntry {
    dmaState normal;as02RxExecutionOwner owner;
    bool read_active=false,pending=false;ap_uint<24> next_psn=0;
};
'''

def derive_state(original):
    # These are actual RAM actions, not replaceable behavioral callbacks.
    # Refuse changed/missing original effects before adding ownership ports.
    for action in [
        'state_table[rxRequest.qpn].req_old_unack = rxRequest.epsn;',
        'state_table[rxRequest.qpn].resp_epsn = rxRequest.epsn;',
        'state_table[txRequest.qpn].req_next_psn = txRequest.psn;',
        'state_table[ifRequest.qpn].req_old_valid = ifRequest.remote_psn;']:
        once(original,action,action)
    fenced=state.derive(original)
    s=rx.source.function(fenced,'as02_state_table_fence_consumer')
    s=once(s,'void as02_state_table_fence_consumer(','void as02_owned_rx_state_table(')
    s=once(s,'hls::stream<as02StateReq>& rxIbh2stateTable_upd_req','hls::stream<as02RxStateMessage>& rxIbh2stateTable_upd_req')
    s=once(s,'hls::stream<rxStateRsp>& stateTable2rxIbh_rsp','hls::stream<as02RxOwned<rxStateRsp>>& stateTable2rxIbh_rsp')
    for port in ['stateTable2txIbh_rsp','stateTable2qpi_rsp']:
        s=once(s,'hls::stream<stateTableEntry>& '+port,'hls::stream<as02RxStateEntry>& '+port)
    s=once(s,'hls::stream<as02StateReadback>& readbacks\n)',
        'hls::stream<as02StateReadback>& readbacks,ap_uint<32>& fault\n)')
    s=once(s,'static ap_uint<MAX_QPS> initialized=0;',r'''static ap_uint<MAX_QPS> initialized=0;
    static ap_uint<64> connection_epoch[MAX_QPS];
    static as02RxExecutionOwner pending_owner;
    static ap_uint<32> error=0;fault=error;if(error)return;''')
    s=once(s,'pending=rxIbh2stateTable_upd_req.read();pending_source=0;have_pending=true;',
        'as02RxStateMessage r=rxIbh2stateTable_upd_req.read();pending=r.normal;pending_owner=r.owner;pending_source=0;have_pending=true;')
    for stream,idx in [('txIbh2stateTable_upd_req',1),('qpi2stateTable_upd_req',2)]:
        s=once(s,'pending='+stream+'.read();pending_source='+str(idx)+';have_pending=true;',
            'pending='+stream+'.read();pending_owner=as02RxExecutionOwner();pending_source='+str(idx)+';have_pending=true;')
    # Keep all real ordered RX/TX/QPI marker/rendezvous/dispatch logic.
    s=once(s,'as02_state_marker(msg,0,token,seen,input_fault,failed_source,failed_qpn);',r'''
            if(pending_owner.packet!=0 || pending_owner.native!=0) {error=71;return;}
            as02_state_marker(msg,0,token,seen,input_fault,failed_source,failed_qpn);''')
    old='msg.bad || msg.qpn>=MAX_QPS || !initialized[msg.qpn]'
    common=old+' || msg.epoch==0 || msg.sequence==0 || connection_epoch[msg.qpn]!=msg.epoch'
    s=once(s,old+''') {
            input_fault=true;failed_source=0;''',common+r''' ||
            !as02_rx_execution_valid(pending_owner) || as02_rx_control(pending_owner) ||
            msg.qpn!=as02_rx_qpn(pending_owner) || !msg.response || msg.b!=0 || msg.state!=0 ||
            msg.epoch!=pending_owner.native(459,396) || msg.sequence!=pending_owner.native(523,460)) {
            error=72;input_fault=true;failed_source=0;''')
    s=once(s,old+''') {
            input_fault=true;failed_source=1;''',common+''') {
            error=73;input_fault=true;failed_source=1;''')
    s=once(s,'msg.bad || msg.qpn>=MAX_QPS || msg.state>5 || (!msg.write && !initialized[msg.qpn])',
        'msg.bad || msg.qpn>=MAX_QPS || msg.state>5 || msg.epoch==0 || msg.sequence==0 || (msg.write && initialized[msg.qpn]) || (!msg.write && (!initialized[msg.qpn] || connection_epoch[msg.qpn]!=msg.epoch))')
    s=once(s,'input_fault=true;failed_source=2;','error=74;input_fault=true;failed_source=2;')
    s=once(s,'if(msg.write)initialized[msg.qpn]=1;','if(msg.write) {connection_epoch[msg.qpn]=msg.epoch;initialized[msg.qpn]=1;}')
    # Full24-bit wrap without a negative vendor host-model intermediate.
    s=once(s,'entry.req_next_psn-1','ap_uint<24>(ap_uint<25>(entry.req_next_psn)+0xffffffU)')
    for port in ['stateTable2rxIbh_rsp']:
        s=rx.tag_writes(s,[port])
    # The RX tag belongs to the pending real request, not a late QP owner.
    s=s.replace(',owner)',',pending_owner)')
    for port in ['stateTable2txIbh_rsp','stateTable2qpi_rsp']:
        s=once(s,port+'.write(state_table[',port+'.write(as02RxStateEntry(state_table[')
        anchor=port+'.write(as02RxStateEntry(state_table['
        start=s.index(anchor);end=s.index(');',start)
        s=s[:end]+',msg)'+s[end:]
    return s

def derive_msn(original):
    at=original.index('template <int INSTID = 0>');start=original.index('void msn_table(',at)
    _,_,end=state.block(original[start:],'void msn_table(')
    s=original[at:start+end]
    s=once(s,'void msn_table(','void as02_owned_rx_msn_table(')
    for old,new in [('hls::stream<rxMsnReq>&','hls::stream<as02RxOwned<rxMsnReq>>&'),
        ('hls::stream<ap_uint<16> >&','hls::stream<as02MsnTxReq>&'),
        ('hls::stream<ifMsnReq>&','hls::stream<as02MsnInit>&'),
        ('hls::stream<dmaState>&','hls::stream<as02RxOwned<dmaState>>&'),
        ('hls::stream<txMsnRsp>&','hls::stream<as02MsnTxRsp>&')]:s=once(s,old,new)
    s=once(s,'hls::stream<as02MsnTxRsp>&\tmsnTable2txExh_rsp)',
        'hls::stream<as02MsnTxRsp>&\tmsnTable2txExh_rsp,ap_uint<32>& fault)')
    s=once(s,'static dmaState  msn_table[MAX_QPS];',r'''static as02MsnOwnedEntry msn_table[MAX_QPS];
    static ap_uint<MAX_QPS> initialized=0;static ap_uint<64> connection_epoch[MAX_QPS];
    static ap_uint<32> error=0;fault=error;if(error)return;''')
    # Original field actions still operate on the SAME actual MSN RAM entry.
    import re
    s=re.sub(r'(msn_table\[[^\]]+\])\.(msn|vaddr|dma_length|lst|r_key)\b',r'\1.normal.\2',s)
    s=once(s,'rxExh2msnTable_upd_req.read(rxRequest);',r'''
        as02RxOwned<rxMsnReq> r=rxExh2msnTable_upd_req.read();rxRequest=r.normal;
        as02RxExecutionOwner owner=r.owner;ap_uint<24> qp=as02_rx_qpn(owner);
        if(!as02_rx_execution_valid(owner) || as02_rx_control(owner) || qp>=MAX_QPS ||
            rxRequest.qpn!=qp || !initialized[qp] || connection_epoch[qp]!=owner.native(459,396)) {error=80;return;}
        ap_uint<8> op=owner.packet(303,296);as02MsnOwnedEntry& entry=msn_table[qp];
        if(op==RC_ACK) {
            if(rxRequest.write) {error=81;return;}
            msnTable2rxExh_rsp.write(as02_rx_tag(entry.normal,owner));return;
        }
        bool first=op==RC_RDMA_READ_RESP_FIRST || op==RC_RDMA_READ_RESP_ONLY;
        bool last=op==RC_RDMA_READ_RESP_LAST || op==RC_RDMA_READ_RESP_ONLY;
        if(!rxRequest.write) {
            if(first) {
                if(entry.read_active || entry.pending ||
                    (entry.owner.native!=0 && owner.native(523,460)<=entry.owner.native(523,460))) {error=82;return;}
            } else if(!entry.read_active || entry.pending || entry.owner.native!=owner.native ||
                entry.owner.packet(247,0)!=owner.packet(247,0) || entry.next_psn!=owner.packet(295,272) ||
                entry.normal.vaddr!=as02_rx_address(owner)) {error=83;return;}
            entry.owner=owner;entry.pending=true;entry.read_active=true;
        } else {
            ap_uint<32> bytes=as02_rx_length(owner)-ap_uint<33>(as02_rx_delta(owner))*PMTU;
            if(bytes>PMTU)bytes=PMTU;
            if(!entry.read_active || !entry.pending || !as02_rx_same_owner(entry.owner,owner) ||
                rxRequest.msn!=entry.normal.msn || rxRequest.vaddr!=ap_uint<64>(as02_rx_address(owner)+bytes) ||
                rxRequest.dma_length!=bytes || rxRequest.lst!=1) {error=84;return;}
        }
''')
    s=once(s,'msnTable2rxExh_rsp.write(dmaState(msn_table[rxRequest.qpn]));',
        'msnTable2rxExh_rsp.write(as02_rx_tag(msn_table[rxRequest.qpn].normal,owner));')
    # Exactly the actual original lst write is followed by owned progression.
    s=once(s,'msn_table[rxRequest.qpn].normal.lst = rxRequest.lst;',r'''msn_table[rxRequest.qpn].normal.lst = rxRequest.lst;
            entry.next_psn=ap_uint<24>(owner.packet(295,272))+1;entry.pending=false;
            if(last)entry.read_active=false; // NOT WR/MR/CQ retirement
''')
    s=once(s,'txExh2msnTable_req.read(qpn);',r'''
        as02MsnTxReq request=txExh2msnTable_req.read();
        if(request.qpn>=MAX_QPS || request.epoch==0 || request.sequence==0 ||
            !initialized[request.qpn] || connection_epoch[request.qpn]!=request.epoch) {error=85;return;}
        qpn=request.qpn;
''')
    s=once(s,'msnTable2txExh_rsp.write(txMsnRsp(msn_table[qpn].normal.msn, msn_table[qpn].normal.r_key));',
        'msnTable2txExh_rsp.write(as02MsnTxRsp(txMsnRsp(msn_table[qpn].normal.msn,msn_table[qpn].normal.r_key),request));')
    s=once(s,'if2msnTable_init.read(ifRequest);',r'''
        as02MsnInit request=if2msnTable_init.read();
        if(request.qpn>=MAX_QPS || request.epoch==0 || request.sequence==0 || initialized[request.qpn]) {error=86;return;}
        ifRequest.qpn=request.qpn;ifRequest.r_key=request.rkey;
''')
    last='msn_table[ifRequest.qpn].normal.lst = 0;'
    s=once(s,last,last+r'''
        msn_table[ifRequest.qpn].owner=as02RxExecutionOwner();
        msn_table[ifRequest.qpn].read_active=false;msn_table[ifRequest.qpn].pending=false;msn_table[ifRequest.qpn].next_psn=0;
        connection_epoch[ifRequest.qpn]=request.epoch;initialized[ifRequest.qpn]=1;''')
    return s

def derive(state_text,msn_text):
    license=state_text[:state_text.index('#include')]
    return license+'''#pragma once
#include "owned_rx_execution.hpp"
'''+state.TYPES+'\n'+TYPES+'\n'+derive_state(state_text)+'\n'+derive_msn(msn_text)+'\n'
