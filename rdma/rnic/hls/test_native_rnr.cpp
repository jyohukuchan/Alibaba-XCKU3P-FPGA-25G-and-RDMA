// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual SAME ACK event, meta, MSN consumer and EXH generator; not a wire model.
#include <cassert>
#include <iostream>
#include "ib_transport_protocol/ib_transport_protocol.cpp"

static hls::stream<ackEvent> exh,ibh,merged;
static hls::stream<as02RnrEvent> rnr;
static hls::stream<event> read_events,app_events,exh_meta;
static hls::stream<ibhMeta> ibh_meta;
static hls::stream<ap_uint<16>> conn_queries,msn_queries,lengths;
static hls::stream<rxMsnReq> rx_updates;
static hls::stream<ifMsnReq> initial;
static hls::stream<dmaState> rx_replies;
static hls::stream<txMsnRsp> tx_replies;
static hls::stream<txPacketInfo> info;
static hls::stream<ap_uint<24>> timers;
static hls::stream<net_axis<512>> headers;
static ap_uint<1> fault=0;
static void tick(bool table=true) {
    as02_native_rnr_merger<91>(exh,ibh,rnr,merged,fault);
    meta_merger<91>(merged,read_events,app_events,conn_queries,ibh_meta,exh_meta);
    generate_exh<512,91>(exh_meta,tx_replies,msn_queries,lengths,info,timers,headers);
    if(table)msn_table<91>(rx_updates,msn_queries,initial,rx_replies,tx_replies);
}
static void check(unsigned syndrome,unsigned msn,unsigned psn) {
    for(unsigned i=0;i<32 && headers.empty();i++)tick();
    assert(!fault && !headers.empty());auto word=headers.read();
    AckExHeader<512> a;a.setRawHeader(word.data(31,0));
    assert(a.getSyndrome()==syndrome && a.getMsn()==msn && word.keep==15 && word.last);
    assert(lengths.read()==20);auto pi=info.read();assert(pi.isAETH && !pi.hasPayload);
    auto b=ibh_meta.read();assert(b.op_code==RC_ACK && b.dest_qp==2 && b.psn==psn && b.validPSN);
    assert(conn_queries.read()==2 && timers.empty());
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"capacity changed");
    initial.write(ifMsnReq(2,0x81234567));for(unsigned i=0;i<4;i++)tick();
    as02RnrEvent e;e.qpn=2;e.psn=0x987654;rnr.write(e);
    for(unsigned i=0;i<30;i++){tick(false);assert(headers.empty());}
    check(0x20,0,0x987654); // actual consumer withheld, no invented MSN
    // Genuine RX update on SAME table; RNR must report the existing value,
    // not increment it and not keep an independent ACK/RNR shadow counter.
    rx_updates.write(rxMsnReq(2,0x123456));for(unsigned i=0;i<4;i++)tick();
    rnr.write(e);check(0x20,0x123456,0x987654);
    exh.write(ackEvent(2,0x987654,false));check(0,0x123456,0x987654);
    rnr.write(e);check(0x20,0x123456,0x987654);
    // Full24-bit high QPN cannot narrow to the same live QP2.
    e.qpn=0x800002;rnr.write(e);for(unsigned i=0;i<16;i++)tick();
    assert(fault && headers.empty() && conn_queries.empty() && ibh_meta.empty());
    e.qpn=2;rnr.write(e);for(unsigned i=0;i<16;i++)tick();assert(headers.empty());
    std::cout<<"NATIVE_RNR_HLS {\"pass_test\":true,\"actual_ACK_meta_MSN_EXH\":true,"
        "\"RNRs\":3,\"normal_ACKs\":1,\"blocked_MSN_consumer_withholds_ACK\":true,"
        "\"MSN_not_advanced_by_RNR\":true,\"high_full_QPN_quarantined\":true,"
        "\"whole_core_drain\":false,\"native_DMA_CQ\":false}"<<std::endl;
}
