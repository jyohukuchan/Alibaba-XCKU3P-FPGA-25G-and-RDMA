// SPDX-License-Identifier: BSD-2-Clause-Views
// Isolated REAL eight-entry timer consumer proof, NOT a whole RoCE core fence.
#include "ib_transport_protocol/transport_timer_fence.hpp"

void timer_fence_decode(hls::stream<ap_uint<176>>& in,
                        hls::stream<as02TimerUpdate>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        ap_uint<176> raw=in.read();
        as02TimerUpdate q;
        q.qpn=raw(15,0);q.stop=raw[16];q.is_fence=raw[17];
        q.psn=raw(41,18);q.epoch=raw(105,42);q.sequence=raw(169,106);
        q.bad_encoding=raw(175,170)!=0;
        out.write(q);
    }
}
void timer_fence_encode(hls::stream<as02TimerStateRsp>& in,
                        hls::stream<ap_uint<240>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        as02TimerStateRsp q=in.read();
        ap_uint<240> raw=0;
        raw(15,0)=q.qpn;raw(39,16)=q.psn;raw(103,40)=q.epoch;raw(167,104)=q.sequence;
        raw(175,168)=q.status;raw[176]=q.snapshot_valid;raw[177]=q.active;
        raw(209,178)=q.time;raw(213,210)=q.retries;raw(237,214)=q.failed_qpn;
        out.write(raw);
    }
}
void timer_timeout_encode(hls::stream<retransmission>& in,
                          hls::stream<ap_uint<40>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        retransmission q=in.read();ap_uint<40> raw=0;
        raw(15,0)=q.qpn;raw(39,16)=q.psn;out.write(raw);
    }
}
void as02_timer_fence_top(hls::stream<ap_uint<176>>& s_rx,
                         hls::stream<ap_uint<24>>& s_tx,
                         hls::stream<ap_uint<40>>& m_timeout,
                         hls::stream<ap_uint<240>>& m_fence) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_rx
#pragma HLS interface axis register port=s_tx
#pragma HLS interface axis register port=m_timeout
#pragma HLS interface axis register port=m_fence
#pragma HLS dataflow disable_start_propagation
    static hls::stream<as02TimerUpdate> updates("updates");
    static hls::stream<as02TimerStateRsp> readbacks("readbacks");
    static hls::stream<retransmission> timeouts("timeouts");
#pragma HLS stream variable=updates depth=2
#pragma HLS stream variable=readbacks depth=2
#pragma HLS stream variable=timeouts depth=2
#pragma HLS aggregate variable=updates compact=bit
#pragma HLS aggregate variable=readbacks compact=bit
#pragma HLS aggregate variable=timeouts compact=bit
    timer_fence_decode(s_rx,updates);
    as02_timer_state_fence_consumer<42>(updates,s_tx,timeouts,readbacks);
    timer_fence_encode(readbacks,m_fence);
    timer_timeout_encode(timeouts,m_timeout);
}
