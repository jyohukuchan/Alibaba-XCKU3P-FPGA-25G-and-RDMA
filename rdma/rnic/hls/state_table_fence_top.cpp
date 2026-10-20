// SPDX-License-Identifier: BSD-2-Clause-Views
// Private real-state-table rendezvous, not whole-core drain/MR/CQ permission.
#include "ib_transport_protocol/state_table_fence.hpp"

template<int ID> void state_decode(hls::stream<ap_uint<224>>& in,hls::stream<as02StateReq>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        ap_uint<224> r=in.read();as02StateReq m;
        m.qpn=r(15,0);m.a=r(39,16);m.b=r(63,40);m.rc=r(66,64);
        m.write=r[67];m.response=r[68];m.is_fence=r[69];
        m.epoch=r(133,70);m.sequence=r(197,134);m.state=r(200,198);
        m.bad=r(223,201)!=0;
        out.write(m);
    }
}
static ap_uint<128> state_encode_entry(stateTableEntry e) {
#pragma HLS inline
    ap_uint<128> r=0;r(23,0)=e.resp_epsn;r(47,24)=e.resp_old_outstanding;
    r(71,48)=e.req_next_psn;r(95,72)=e.req_old_unack;
    r(119,96)=e.req_old_valid;r(122,120)=e.retryCounter;return r;
}
void state_rx_encode(hls::stream<rxStateRsp>& in,hls::stream<ap_uint<80>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        rxStateRsp e=in.read();ap_uint<80> r=0;
        r(23,0)=e.epsn;r(47,24)=e.oldest_outstanding_psn;
        r(71,48)=e.max_forward;r(74,72)=e.retryCounter;out.write(r);
    }
}
template<int ID> void state_entry_encode(hls::stream<stateTableEntry>& in,hls::stream<ap_uint<128>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full())out.write(state_encode_entry(in.read()));
}
void state_fence_encode(hls::stream<as02StateReadback>& in,hls::stream<ap_uint<336>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        as02StateReadback e=in.read();ap_uint<336> r=0;
        r(15,0)=e.qpn;r(39,16)=e.psn;r(103,40)=e.epoch;r(167,104)=e.sequence;
        r(175,168)=e.status;r[176]=e.snapshot_valid;r(179,177)=e.seen;
        r(302,180)=state_encode_entry(e.entry)(122,0);
        r(304,303)=e.failed_source;r(320,305)=e.failed_qpn;out.write(r);
    }
}
void as02_state_fence_top(hls::stream<ap_uint<224>>& s_rx,
    hls::stream<ap_uint<224>>& s_tx,hls::stream<ap_uint<224>>& s_qpi,
    hls::stream<ap_uint<80>>& m_rx,hls::stream<ap_uint<128>>& m_tx,
    hls::stream<ap_uint<128>>& m_qpi,hls::stream<ap_uint<336>>& m_fence) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_rx
#pragma HLS interface axis register port=s_tx
#pragma HLS interface axis register port=s_qpi
#pragma HLS interface axis register port=m_rx
#pragma HLS interface axis register port=m_tx
#pragma HLS interface axis register port=m_qpi
#pragma HLS interface axis register port=m_fence
#pragma HLS dataflow disable_start_propagation
    static hls::stream<as02StateReq> rx("rx"),tx("tx"),qpi("qpi");
    static hls::stream<rxStateRsp> rr("rr");
    static hls::stream<stateTableEntry> tr("tr"),qr("qr");
    static hls::stream<as02StateReadback> fr("fr");
#pragma HLS stream variable=rx depth=2
#pragma HLS stream variable=tx depth=2
#pragma HLS stream variable=qpi depth=2
#pragma HLS stream variable=rr depth=2
#pragma HLS stream variable=tr depth=2
#pragma HLS stream variable=qr depth=2
#pragma HLS stream variable=fr depth=2
#pragma HLS aggregate variable=rx compact=bit
#pragma HLS aggregate variable=tx compact=bit
#pragma HLS aggregate variable=qpi compact=bit
#pragma HLS aggregate variable=rr compact=bit
#pragma HLS aggregate variable=tr compact=bit
#pragma HLS aggregate variable=qr compact=bit
#pragma HLS aggregate variable=fr compact=bit
    state_decode<0>(s_rx,rx);state_decode<1>(s_tx,tx);state_decode<2>(s_qpi,qpi);
    as02_state_table_fence_consumer<43>(rx,tx,qpi,rr,tr,qr,fr);
    state_rx_encode(rr,m_rx);state_entry_encode<1>(tr,m_tx);state_entry_encode<2>(qr,m_qpi);
    state_fence_encode(fr,m_fence);
}
