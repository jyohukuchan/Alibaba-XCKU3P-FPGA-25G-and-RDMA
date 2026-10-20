#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual same-table RX owner lookup, no shadow owner/CQ/retirement shortcut.

Queries still require genuine packet/QP epoch admission. Full RX wire producer,
native/board integration and standard verbs remain incomplete.
"""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('owned_timer',Path(__file__).with_name('owned_timer_profile.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
ROOT=base.ROOT;BASE=base.BASE;META=base.META;TIMER=base.TIMER;TOP=base.TOP
once=base.once;block=base.block
derive_timer=base.derive_timer

TYPES=r'''
// The epoch must be captured by trusted packet/connection admission. It is
// NOT present on wire and must not be invented by a late current-owner lookup.
struct as02RxLookupQuery {
    ap_uint<24> qpn=0,psn=0;ap_uint<8> opcode=0,syndrome=0;
    ap_uint<64> epoch=0;bool has_aeth=false,marker=false,bad=false;
    ap_uint<168> owner=0;
};
'''

STATES=r'''
    case RX_CAPTURE:
        if(rx_query.bad) {error=30;break;}
        if(rx_query.marker) {
            if(rx_query.qpn!=0 || rx_query.psn!=0 || rx_query.opcode!=0 || rx_query.epoch!=0 ||
                rx_query.syndrome!=0 || rx_query.has_aeth) {error=30;break;}
            as02_seen_marker(rx_query.owner,seen,token,error,4);state=MAIN;break;
        }
        if(rx_query.owner!=0 || rx_query.qpn>=MAX_QPS || rx_query.epoch==0 ||
            rx_query.opcode<RC_RDMA_READ_RESP_FIRST || rx_query.opcode>RC_ACK ||
            (rx_query.has_aeth!=(rx_query.opcode!=RC_RDMA_READ_RESP_MIDDLE)) ||
            (!rx_query.has_aeth && rx_query.syndrome!=0)) {error=30;break;}
        lookup_found=0;lookup_delta=0;lookup_head=false;lookup_walked=0;lookup_matches=0;
        lookup_status=1;lookup_generation=0;lookup_sequence=0;lookup_epoch=0;
        state=RX_PREQ;break;
    case RX_PREQ:
        preq.write(pointerReq(ap_uint<16>(rx_query.qpn),true));state=RX_PTR;break;
    case RX_PTR:
        if(!prsp.empty()) {
            ptr=prsp.read();
            if(!ptr.valid)state=RX_RESULT;
            else if(ptr.head>=META_TABLE_SIZE || ptr.tail>=META_TABLE_SIZE)error=31;
            else {curr=ptr.head;state=RX_READ;}
        }
        break;
    case RX_READ:
        mreq.write(as02OwnedMetaReq(curr));state=RX_WAIT;break;
    case RX_WAIT:
        if(!mrsp.empty()) {meta=mrsp.read();state=RX_CHECK;}
        break;
    case RX_CHECK:
        if(!meta.valid || meta.lease(15,0)!=curr || meta.lease(79,16)==0 ||
            meta.lease(95,80)!=rx_query.qpn || meta.lease(183,120)==0 || meta.lease(247,184)==0) {error=31;break;}
        if(lookup_walked==0) {
            lookup_epoch=meta.lease(183,120);
            if(lookup_epoch!=rx_query.epoch) {lookup_walked=1;lookup_status=3;state=RX_RESULT;break;}
        }
        if(meta.lease(183,120)!=lookup_epoch || meta.lease(79,16)<=lookup_generation ||
            meta.lease(247,184)<lookup_sequence) {error=32;break;}
        lookup_generation=meta.lease(79,16);lookup_sequence=meta.lease(247,184);
        lookup_walked++;state=RX_RANGE;break;
    case RX_RANGE: {
        bool read=meta.opCode==RC_RDMA_READ_REQUEST;
        bool request=read || meta.opCode==RC_RDMA_WRITE_ONLY || meta.opCode==RC_RDMA_WRITE_FIRST ||
            meta.opCode==RC_RDMA_WRITE_MIDDLE || meta.opCode==RC_RDMA_WRITE_LAST ||
            meta.opCode==RC_SEND_ONLY || meta.opCode==RC_SEND_FIRST || meta.opCode==RC_SEND_MIDDLE || meta.opCode==RC_SEND_LAST;
        bool response_read=rx_query.opcode!=RC_ACK;
        bool control=rx_query.has_aeth && rx_query.syndrome(7,5)!=0;
        lookup_type_ok=request && (response_read?read:(control || !read));
        // Widen BEFORE rounding; full lengthFFFFFFFF must not wrap to zero.
        lookup_span=1;
        if(read) {
            ap_uint<33> rounded=ap_uint<33>(meta.length)+ap_uint<33>(PMTU-1);
            lookup_span=rounded/PMTU;
        }
        lookup_candidate_delta=ap_uint<24>(rx_query.psn-meta.psn);
        state=RX_MATCH;break;
    }
    case RX_MATCH:
        if(lookup_span==0 || lookup_span>=8388608) {error=34;break;}
        if(lookup_type_ok && lookup_candidate_delta<lookup_span) {
            if(lookup_matches==0) {
                lookup_found=meta.lease;lookup_delta=lookup_candidate_delta;lookup_head=curr==ptr.head;
            }
            lookup_matches++;
        }
        state=RX_NEXT;break;
    case RX_NEXT:
        if(meta.isTail) {
            if(curr!=ptr.tail) {error=33;break;}
            state=RX_RESULT;
        } else {
            if(curr==ptr.tail || meta.next>=META_TABLE_SIZE || lookup_walked>=META_TABLE_SIZE) {error=33;break;}
            curr=meta.next;state=RX_READ;
        }
        break;
    case RX_RESULT:
        if(lookup_status!=3)lookup_status=lookup_matches==1?0:(lookup_matches==0?1:2);
        lookup_result=0;
        if(lookup_status==0) {lookup_result(247,0)=lookup_found;lookup_result(391,368)=lookup_delta;lookup_result[421]=lookup_head;}
        lookup_result(271,248)=rx_query.qpn;lookup_result(295,272)=rx_query.psn;
        lookup_result(303,296)=rx_query.opcode;lookup_result(367,304)=rx_query.epoch;
        lookup_result(399,392)=lookup_status;lookup_result(411,400)=lookup_walked;
        lookup_result(419,412)=rx_query.syndrome;lookup_result[420]=rx_query.has_aeth;lookup_result[422]=1;
        state=RX_EMIT;break;
    case RX_EMIT:
        if(!rx_bindings.full()) {rx_bindings.write(lookup_result);state=RX_ACCEPT;}
        break;
    case RX_ACCEPT:
        if(!rx_accepts.empty()) {lookup_receipt=rx_accepts.read();state=RX_ACCEPT_CHECK;}
        break;
    case RX_ACCEPT_CHECK:
        if(lookup_receipt!=lookup_result) {error=35;break;}
        state=RX_UNLOCK;break;
    case RX_UNLOCK:
        // Release ONLY the actual table lock, with its exact unchanged entry.
        // NO metadata write, pool return, timer clear, nativeCQ/MR release.
        pupd.write(pointerUpdate(ap_uint<16>(rx_query.qpn),ptr));state=MAIN;break;
'''

DECODE=r'''
void as02_rx_lookup_decode(stream<ap_uint<320>>& in,stream<as02RxLookupQuery>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        ap_uint<320> r=in.read();as02RxLookupQuery q;
        q.qpn=r(23,0);q.psn=r(47,24);q.opcode=r(55,48);q.epoch=r(119,56);
        q.syndrome=r(127,120);q.has_aeth=r[128];q.marker=r[129];q.owner=r(297,130);
        q.bad=r(319,298)!=0;out.write(q);
    }
}
'''

def derive(original):
    s=base.derive(original);a,_,e=block(s,'void as02_process_owned_retransmissions(');f=s[a:e]
    f=once(f,'    stream<ap_uint<32>>& timer_faults,',r'''    stream<ap_uint<32>>& timer_faults,
    stream<as02RxLookupQuery>& rx_queries,stream<ap_uint<448>>& rx_bindings,stream<ap_uint<448>>& rx_accepts,''')
    f=once(f,'HEAD_WAIT,HEAD_CHECK,HEAD_EMIT};',r'''HEAD_WAIT,HEAD_CHECK,HEAD_EMIT,
        RX_CAPTURE,RX_PREQ,RX_PTR,RX_READ,RX_WAIT,RX_CHECK,RX_RANGE,RX_MATCH,RX_NEXT,
        RX_RESULT,RX_EMIT,RX_ACCEPT,RX_ACCEPT_CHECK,RX_UNLOCK};''')
    f=once(f,'static ap_uint<4> seen=0','static ap_uint<5> seen=0')
    f=once(f,'    static State state=MAIN;',r'''    static State state=MAIN;
    static as02RxLookupQuery rx_query;
    static ap_uint<448> lookup_result=0,lookup_receipt=0;
    static ap_uint<248> lookup_found=0;
    static ap_uint<24> lookup_delta=0,lookup_candidate_delta=0;
    static ap_uint<33> lookup_span=0;
    static ap_uint<12> lookup_walked=0,lookup_matches=0;
    static ap_uint<64> lookup_epoch=0,lookup_generation=0,lookup_sequence=0;
    static ap_uint<8> lookup_status=1;
    static bool lookup_head=false,lookup_type_ok=false;''')
    f=once(f,'if(seen==15 && !have_insert)','if(seen==31 && !have_insert)')
    f=once(f,'else if((seen & 11)==11 && !have_insert && !timer_closed)',
        'else if((seen & 11)==11 && seen[4] && !have_insert && !timer_closed)')
    f=once(f,'        else if(!seen[0] && !updates.empty())',r'''
        else if(!seen[4] && pool_initialized && !rx_queries.empty()) {rx_query=rx_queries.read();state=RX_CAPTURE;}
        else if(!seen[0] && !updates.empty())''')
    f=once(f,'r(179,176)=seen;','r(179,176)=seen(3,0);')
    f=once(f,'r(309,303)=timer_state(6,0);','r(309,303)=timer_state(6,0);r[310]=seen[4];')
    f=f[:-1].rstrip()
    if not f.endswith('    }'):raise ValueError('actual process switch anchor')
    f=f[:-5]+STATES+'    }\n}\n'
    at=s.rfind('template <int INSTID=0>',0,a)
    if at<0:raise ValueError('actual process template anchor')
    return s[:at]+TYPES+s[at:a]+f+s[e:]

def derive_top(original):
    s=base.derive_top(original).replace('as02_owned_timer_retrans_top','as02_owned_rx_lookup_top')
    s=once(s,'void as02_owned_rx_lookup_top(',DECODE+'\nvoid as02_owned_rx_lookup_top(')
    s=once(s,'hls::stream<ap_uint<320>>& m_fence,',r'''hls::stream<ap_uint<320>>& m_fence,
    hls::stream<ap_uint<320>>& s_rx_query,hls::stream<ap_uint<448>>& m_rx_binding,hls::stream<ap_uint<448>>& s_rx_accept,''')
    s=once(s,'#pragma HLS interface axis register port=m_fence',r'''#pragma HLS interface axis register port=m_fence
#pragma HLS interface axis register port=s_rx_query
#pragma HLS interface axis register port=m_rx_binding
#pragma HLS interface axis register port=s_rx_accept''')
    s=once(s,'    owned_insert_decode(s_insert,inserts);',r'''
    static hls::stream<as02RxLookupQuery> rx_queries("rx_queries");
#pragma HLS stream variable=rx_queries depth=2
#pragma HLS aggregate variable=rx_queries compact=bit
    as02_rx_lookup_decode(s_rx_query,rx_queries);
    owned_insert_decode(s_insert,inserts);''')
    s=once(s,'timer_faults,pool_credit','timer_faults,rx_queries,m_rx_binding,s_rx_accept,pool_credit')
    return s

def derive_wrapper(original):
    s=once(original,'// SPDX-License-Identifier: BSD-2-Clause-Views',
        '// SPDX-License-Identifier: BSD-2-Clause-Views\n// Same real tables/pool with RX lookup. Only real binding-output acceptance\n// creates a private receipt; lookup/unlock is NOT WR/MR/CQ retirement.\n// Native packet/QP admission and complete wire RX producers remain unconnected.')
    s=once(s,'module rocev2_owned_timer_retrans(','module rocev2_owned_rx_lookup(')
    s=once(s,' input wire [415:0] s_insert_data,',r''' input wire [319:0] s_rx_query_data,input wire s_rx_query_valid,output wire s_rx_query_ready,
 output wire [447:0] m_rx_binding_data,output wire m_rx_binding_valid,input wire m_rx_binding_ready,
 input wire [415:0] s_insert_data,''')
    s=once(s,'wire [31:0] process_fault;',r'''wire [31:0] process_fault;
wire [447:0] raw_binding;wire raw_binding_valid,raw_binding_ready,lookup_ack_ready;
reg [447:0] lookup_ack=0;reg lookup_ack_valid=0;
wire lookup_room=!lookup_ack_valid || lookup_ack_ready;
assign m_rx_binding_data=raw_binding;
assign m_rx_binding_valid=raw_binding_valid && lookup_room;
assign raw_binding_ready=m_rx_binding_ready && lookup_room;''')
    s=once(s,'  event_ack_valid<=0;','  lookup_ack_valid<=0;lookup_ack<=0;\n  event_ack_valid<=0;')
    s=once(s,' end else begin\n  if(event_ack_valid',r''' end else begin
  if(lookup_ack_valid && lookup_ack_ready)lookup_ack_valid<=0;
  if(m_rx_binding_valid && m_rx_binding_ready)begin
   lookup_ack<=m_rx_binding_data;lookup_ack_valid<=1;
  end
  if(event_ack_valid''')
    s=once(s,"if(raw_fence[319:310]!==10'd0)","if(raw_fence[319:311]!==9'd0 || raw_fence[310]!==1'b1)")
    s=once(s,'as02_owned_timer_retrans_top process_and_tables(',r'''as02_owned_rx_lookup_top process_and_tables(
 .s_rx_query_TDATA(s_rx_query_data),.s_rx_query_TVALID(s_rx_query_valid),.s_rx_query_TREADY(s_rx_query_ready),
 .m_rx_binding_TDATA(raw_binding),.m_rx_binding_TVALID(raw_binding_valid),.m_rx_binding_TREADY(raw_binding_ready),
 .s_rx_accept_TDATA(lookup_ack),.s_rx_accept_TVALID(lookup_ack_valid),.s_rx_accept_TREADY(lookup_ack_ready),''')
    return s
