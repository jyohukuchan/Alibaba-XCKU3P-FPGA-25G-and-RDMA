// SPDX-License-Identifier: BSD-2-Clause-Views
// Only the actual timer producer, for four-state reset/context testing.
#include "ib_transport_protocol/owned_timer.hpp"
static void tx_decode(hls::stream<ap_uint<256>>& in,hls::stream<as02OwnedTimerTx>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        ap_uint<256> r=in.read();as02OwnedTimerTx t;t.marker=r[249];t.retry=r[248];
        if(t.marker) {t.owner=r(167,0);if(r(247,168)!=0 || r(255,250)!=0)t.owner=0;}
        else {t.lease=r(247,0);if(r(255,250)!=0)t.lease=0;}
        out.write(t);
    }
}
static void ctrl_decode(hls::stream<ap_uint<544>>& in,hls::stream<as02OwnedTimerCtrl>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        ap_uint<544> r=in.read();as02OwnedTimerCtrl c;c.marker=r[498];
        if(c.marker) {c.owner=r(167,0);if(r(497,168)!=0 || r(543,499)!=0)c.owner=0;}
        else {c.old_lease=r(247,0);c.next_lease=r(495,248);c.next_valid=r[496];c.advance=r[497];if(r(543,499)!=0)c.old_lease=0;}
        out.write(c);
    }
}
static void retry_encode(hls::stream<as02OwnedRetry>& in,hls::stream<ap_uint<192>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        auto m=in.read();ap_uint<192> r=0;r(167,0)=as02_owner(m.normal.qpn,m.normal.psn,m.epoch,m.sequence);
        r[168]=m.marker;out.write(r);
    }
}
void as02_owned_timer_probe_top(hls::stream<ap_uint<256>>& s_tx,hls::stream<ap_uint<544>>& s_ctrl,
    hls::stream<ap_uint<192>>& m_retry,hls::stream<ap_uint<256>>& m_barrier,
    hls::stream<ap_uint<192>>& s_resume,hls::stream<ap_uint<32>>& m_fault) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_tx
#pragma HLS interface axis register port=s_ctrl
#pragma HLS interface axis register port=m_retry
#pragma HLS interface axis register port=m_barrier
#pragma HLS interface axis register port=s_resume
#pragma HLS interface axis register port=m_fault
#pragma HLS dataflow disable_start_propagation
    static hls::stream<as02OwnedTimerTx> starts("starts");
    static hls::stream<as02OwnedTimerCtrl> controls("controls");
    static hls::stream<as02OwnedRetry> retries("retries");
#pragma HLS stream variable=starts depth=2
#pragma HLS stream variable=controls depth=2
#pragma HLS stream variable=retries depth=2
#pragma HLS aggregate variable=starts compact=bit
#pragma HLS aggregate variable=controls compact=bit
#pragma HLS aggregate variable=retries compact=bit
    tx_decode(s_tx,starts);ctrl_decode(s_ctrl,controls);
    as02_owned_transport_timer<47>(controls,starts,retries,m_barrier,s_resume,m_fault);
    retry_encode(retries,m_retry);
}
