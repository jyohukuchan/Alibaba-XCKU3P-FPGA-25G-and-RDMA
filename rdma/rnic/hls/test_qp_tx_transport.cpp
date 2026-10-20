// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual full-transport QPI and actual SAME state-table consumer, not a model.
#include <cassert>
#include <iostream>
#include "ib_transport_protocol/ib_transport_protocol.cpp"

static hls::stream<qpContext> commands;
static hls::stream<stateTableEntry> qpi_rsp,tx_rsp;
static hls::stream<ifStateReq> qpi_req;
static hls::stream<ifMsnReq> msn_init;
static hls::stream<as02QpApply> applied;
static hls::stream<rxStateReq> rx_req;
static hls::stream<txStateReq> tx_req;
static hls::stream<rxStateRsp> rx_rsp;
static void tick(bool table=true) {
    qp_interface<0>(commands,qpi_rsp,qpi_req,msn_init,applied);
    if(table)state_table<0>(rx_req,tx_req,qpi_req,rx_rsp,tx_rsp,qpi_rsp);
}
static as02QpApply wait_apply() {
    for(unsigned int i=0;i<32 && applied.empty();i++)tick();
    assert(!applied.empty());return applied.read();
}
int main() {
    static_assert(MAX_QPS==8,"capacity changed");
#ifdef AS02_NATIVE_EXTERNAL_REPLAY
    hls::stream<rxTimerUpdate> old_rx_timer;
    hls::stream<ap_uint<24>> old_tx_timer;
    old_rx_timer.write(rxTimerUpdate(2,true));old_tx_timer.write(2);
    for(unsigned int i=0;i<8;i++)as02_native_external_replay_timer<0>(old_rx_timer,old_tx_timer);
    assert(old_rx_timer.empty() && old_tx_timer.empty());
#endif
    qpContext initial(READY_SEND,2,0x123456,0xfffffe,0x81234567,0);
    commands.write(initial);
    as02QpApply init=wait_apply();
    assert(init.flags==1 && init.qpn==2 && init.tx_psn==0x123456 && init.rx_psn==0xfffffe);
    assert(!msn_init.empty());ifMsnReq first=msn_init.read();assert(first.qpn==2);
    // Real responder progress exists BEFORE transition to RTS. It must not
    // be reset to its original RTR seed by a TX-only state update.
    rx_req.write(rxStateReq(2,0xffffff,3,false));tick();
    qpContext update(READY_SEND,2,0xaabbcc,0x111111,0xdeadbeef,0x415332545850ULL);
    commands.write(update);
    for(unsigned int i=0;i<64;i++) {
        tick(false);assert(applied.empty()); // input accepted, consumer not run
    }
    as02QpApply changed=wait_apply();
    assert(changed.flags==3 && changed.qpn==2 && changed.tx_psn==0xaabbcc && changed.rx_psn==0xffffff);
    assert(msn_init.empty()); // no reset of SAME live MSN/address/key state
    rx_req.write(rxStateReq(2,false));tx_req.write(txStateReq(2));
    for(unsigned int i=0;i<8;i++)tick();
    assert(!rx_rsp.empty() && !tx_rsp.empty());
    rxStateRsp rx=rx_rsp.read();stateTableEntry actual=tx_rsp.read();
    assert(rx.epsn==0xffffff && rx.oldest_outstanding_psn==0xfffffe && rx.retryCounter==3);
    assert(actual.resp_epsn==0xffffff && actual.resp_old_outstanding==0xfffffe && actual.retryCounter==3);
    assert(actual.req_next_psn==0xaabbcc && actual.req_old_unack==0xaabbcc && actual.req_old_valid==0xaabbcc);
    // Second setting crosses the 24-bit boundary; only exact TX state moves.
    update.remote_psn=0xffffff;commands.write(update);
    as02QpApply wrap=wait_apply();
    assert(wrap.flags==3 && wrap.tx_psn==0xffffff && wrap.rx_psn==0xffffff && msn_init.empty());
    std::cout << "QP_TX_HLS {\"pass_test\":true,\"actual_QPI_state_consumer\":true,"
        "\"full_configurations\":1,\"TX_only_updates\":2,\"RX_and_MSN_preserved\":true,"
        "\"blocked_consumer_never_acknowledged\":true,\"whole_core_drain_proved\":false}" << std::endl;
}
