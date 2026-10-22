// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual engine/RAM/readback/collector, not a modeled insertion certificate.
#include <cassert>
#include <iostream>
#include "ib_transport_protocol/retransmitter/retransmitter.hpp"

int main() {
    static_assert(META_TABLE_SIZE==2000 && MAX_QPS==8,"original capacities");
    hls::stream<retransMetaReq> req;
    hls::stream<retransMetaEntry> rsp;
    hls::stream<as02ReqInsert> inserted;
    hls::stream<ap_uint<1>> events;
    auto tick=[&](){as02_retrans_meta_table_event<182>(req,rsp,inserted,events);};
    req.write(retransMetaReq(1999));
    // No status consumer is invoked at all during initialization/readback.
    for(unsigned n=0;n<2000;n++) {
        tick();assert(!req.empty() && rsp.empty() && inserted.empty() && events.empty());
    }
    tick();assert(req.empty() && !rsp.empty());
    auto zero=[](retransMetaEntry e) {
        assert(e.rkey==0 && !e.rkey_valid && e.host==PKG_INT && e.psn==0 && e.next==0 &&
            e.opCode==static_cast<ibOpCode>(0) && e.localAddr==0 && e.remoteAddr==0 &&
            e.length==0 && !e.lst && e.offs==0 && !e.valid && !e.isTail &&
            !e.request_owned && e.request_token==0 && e.immediate==0 && e.compare==0 && e.swap_add==0);
    };
    zero(rsp.read());
    for(unsigned n=0;n<2000;n++){req.write(retransMetaReq(n));tick();assert(!rsp.empty());zero(rsp.read());}
    assert(events.empty() && inserted.empty());
    // An out-of-range real request must produce exactly one sticky error,
    // without consuming later requests or fabricating any insertion proof.
    req.write(retransMetaReq(2000));tick();assert(req.empty() && events.size()==1 && inserted.empty());
    req.write(retransMetaReq(0));
    for(unsigned n=0;n<100;n++){tick();assert(!req.empty() && events.size()==1 && inserted.empty() && rsp.empty());}
    ap_uint<1> fault=0;
    as02_retrans_meta_fault_collect<182>(events,fault);assert(fault==1 && events.empty());
    for(unsigned n=0;n<100;n++) {
        tick();as02_retrans_meta_fault_collect<182>(events,fault);
        assert(fault==1 && events.empty() && !req.empty() && inserted.empty() && rsp.empty());
    }
    std::cout<<"{\"pass_test\":true,\"metadata_entries\":2000,\"normal_zero_reads\":2001,"
        "\"original_2000_call_admission_gate\":true,\"no_status_consumer_during_initialization\":true,"
        "\"all_stored_fields_zero\":true,\"actual_out_of_range_fault_events\":1,"
        "\"sticky_fault_and_no_fake_insertion\":true,\"RTL_reset_or_native_qualification\":false}\n";
}
