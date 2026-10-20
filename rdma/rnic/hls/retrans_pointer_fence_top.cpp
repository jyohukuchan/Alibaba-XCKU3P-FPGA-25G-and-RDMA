// SPDX-License-Identifier: BSD-2-Clause-Views
#include "ib_transport_protocol/retransmitter/retrans_pointer_fence.hpp"
template<int ID> void pointer_decode(hls::stream<ap_uint<224>>& in,hls::stream<as02PointerMsg>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        ap_uint<224> r=in.read();as02PointerMsg m;
        m.qpn=r(15,0);m.head=r(31,16);m.tail=r(47,32);m.valid=r[48];m.lock=r[49];m.marker=r[50];
        m.psn=r(74,51);m.epoch=r(138,75);m.sequence=r(202,139);m.bad=r(223,203)!=0;out.write(m);
    }
}
void pointer_normal_encode(hls::stream<retransPointerEntry>& in,hls::stream<ap_uint<40>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        auto e=in.read();ap_uint<40> r=0;r(15,0)=e.head;r(31,16)=e.tail;r[32]=e.valid;out.write(r);
    }
}
void pointer_fence_encode(hls::stream<as02PointerReadback>& in,hls::stream<ap_uint<288>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        auto e=in.read();ap_uint<288> r=0;
        r(15,0)=e.qpn;r(39,16)=e.psn;r(103,40)=e.epoch;r(167,104)=e.sequence;r(175,168)=e.status;
        r(177,176)=e.seen;r[178]=e.snapshot_valid;r(194,179)=e.entry.head;r(210,195)=e.entry.tail;r[211]=e.entry.valid;
        r[212]=e.locked;r[213]=e.waiting;r(229,214)=e.locked_qpn;r(245,230)=e.waiting_qpn;
        r[246]=e.failed_source;r(262,247)=e.failed_qpn;out.write(r);
    }
}
void as02_pointer_fence_top(hls::stream<ap_uint<224>>& s_req,hls::stream<ap_uint<224>>& s_upd,
    hls::stream<ap_uint<40>>& m_normal,hls::stream<ap_uint<288>>& m_fence) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_req
#pragma HLS interface axis register port=s_upd
#pragma HLS interface axis register port=m_normal
#pragma HLS interface axis register port=m_fence
#pragma HLS dataflow disable_start_propagation
    static hls::stream<as02PointerMsg> req("req"),upd("upd");
    static hls::stream<retransPointerEntry> normal("normal");
    static hls::stream<as02PointerReadback> fence("fence");
#pragma HLS stream variable=req depth=2
#pragma HLS stream variable=upd depth=2
#pragma HLS stream variable=normal depth=2
#pragma HLS stream variable=fence depth=2
#pragma HLS aggregate variable=req compact=bit
#pragma HLS aggregate variable=upd compact=bit
#pragma HLS aggregate variable=normal compact=bit
#pragma HLS aggregate variable=fence compact=bit
    pointer_decode<0>(s_req,req);pointer_decode<1>(s_upd,upd);
    as02_retrans_pointer_fence_consumer<44>(req,upd,normal,fence);
    pointer_normal_encode(normal,m_normal);pointer_fence_encode(fence,m_fence);
}
