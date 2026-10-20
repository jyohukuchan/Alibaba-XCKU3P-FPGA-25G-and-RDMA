// SPDX-License-Identifier: BSD-2-Clause-Views
// Same complete transport consumers; outer QP/owner, peer and physical
// memory/MAC are models. No native/RQ/CQ/driver/hardware claims.
#include "zero_rq_prior.cpp"

static as02ZeroOwner service_owner(unsigned seq,unsigned psn,unsigned op) {
    as02ZeroOwner o=0;o(23,0)=2;o(39,24)=17;o(103,40)=0x9123456700000001ULL;
    o(167,104)=0xfedcba9889abcdefULL;o(183,168)=seq;o(207,184)=psn;o(215,208)=op;
    o(279,216)=seq&1 ? UINT64_MAX:0xe23456789abcdef0ULL;
    o(311,280)=seq&1 ? 0xfedcba98:0x81234567;
    assert(as02_zero_owner_valid(o));return o;
}
static std::vector<unsigned char> service_packet(as02ZeroOwner o) {
    std::vector<unsigned char> p(28,0);p[0]=unsigned(o(215,208));p[1]=0x40;
    put_be(p,2,2,0xffff);put_be(p,5,3,unsigned(o(23,0)));p[8]=0x80;
    put_be(p,9,3,unsigned(o(207,184)));put_be(p,12,8,uint64_t(o(279,216)));
    put_be(p,20,4,unsigned(o(311,280)));return p;
}
template<int I> struct ServiceEndpoint:RequestEndpoint<I> {
    hls::stream<ackEvent> other_ack;
    hls::stream<as02RnrEvent> rnr;
    ap_uint<1> rnr_fault=0;
    void tick(bool timers=true,bool payload=true,bool tables=true) {
        RequestEndpoint<I>::tick(timers,payload,tables);
        // The requester-only fixture has no outgoing responder event path.
        // Execute the real native event merger; never forward a fake receipt.
        as02_native_rnr_merger<I>(this->h.rx_ack_events,other_ack,rnr,this->h.ack_events,rnr_fault);
    }
    void ticks(unsigned n,bool timers=true,bool payload=true,bool tables=true) {
        for(unsigned k=0;k<n;k++)tick(timers,payload,tables);
    }
    void quiet_memory() {
        auto& h=this->h;
        assert(h.source_cmd.empty() && h.source_info.empty() && h.destination_cmd.empty() && h.memory.empty() &&
            h.local_mem.empty() && h.remote_mem.empty() && h.remote_reads.empty() && h.recv_owners.empty() &&
            h.recv_data.empty() && h.recv_ack.empty() && h.atomic_requests.empty() && h.atomic_commit.empty() &&
            h.atomic_owners.empty() && h.atomic_done.empty() && h.owners.empty() && h.admitted.empty() && h.done.empty());
    }
    void clean() {
        auto& h=this->h;quiet_memory();
        assert(!(h.af|h.rf|h.ef|h.mf|h.tf|h.ff|h.jf|h.pf|h.recv_fault|rnr_fault));
    }
    std::vector<unsigned char> response(as02ZeroOwner o,unsigned msn) {
        auto& h=this->h;assert(h.headers.size()==1 && this->tx_assembled.size()==1);
        auto b=h.headers.read();auto raw=b.getRawHeader();auto w=this->tx_assembled.read();
        std::vector<unsigned char> p(16,0);
        for(unsigned k=0;k<12;k++)p[k]=unsigned(raw(8*k+7,8*k));
        assert(w.keep==15 && w.last);
        for(unsigned k=0;k<4;k++)p[12+k]=unsigned(w.data(8*k+7,8*k));
        std::vector<unsigned char> expected(16,0);expected[0]=as02_zero_response(o);expected[1]=0x40;
        put_be(expected,2,2,0xffff);put_be(expected,5,3,196);put_be(expected,9,3,unsigned(o(207,184)));
        put_be(expected,13,3,msn);assert(p==expected && !raw[71] && raw(70,64)==0);
        assert(h.length.size()==1 && h.length.read()==20 && h.conn.size()==1 && h.conn.read()==2);
        std::cout<<"ZERO_SERVICE_WIRE ";for(auto v:p){const char*d="0123456789abcdef";std::cout<<d[v>>4]<<d[v&15];}
        std::cout<<std::endl;return p;
    }
};

static void service_positive() {
    ServiceEndpoint<1501> e;e.h.init();
    e.h.qp_state.write(ifStateReq(2,READY_SEND,0xfffffe,0xfffffe));e.ticks(16);
    unsigned seq=0,psn=0xfffffe;
    // Alternate operations in the SAME actual RX PSN/MSN domain. No RQ is
    // supplied even for READ; no Atomic or local requester owner is supplied.
    for(unsigned op:{unsigned(RC_RDMA_WRITE_ONLY),unsigned(RC_RDMA_READ_REQUEST),
                    unsigned(RC_RDMA_WRITE_ONLY),unsigned(RC_RDMA_READ_REQUEST)}) {
        auto o=service_owner(++seq,psn,op);auto p=service_packet(o);
        e.h.dest.write(196);e.packet(p);e.ticks(100);
        // A valid-looking wire header cannot authorize itself.
        assert(e.h.zero_done.empty() && e.h.headers.empty() && e.h.rx_state.empty());e.clean();
        zero_rq_ack_enabled=false;e.h.zero_owners.write(o);e.ticks(100,true,false);
        assert(e.h.raw.size()==1 && e.h.zero_data.empty() && e.h.zero_commit.empty() &&
            e.h.zero_done.empty() && e.h.headers.empty());e.clean();
        e.h.atomic_msn_table_enabled=false;e.ticks(100);
        assert(!e.h.msn_update.empty() && e.h.zero_done.empty() && e.h.headers.empty());e.clean();
        e.h.atomic_msn_table_enabled=true;e.ticks(100);
        assert(e.h.zero_done.empty() && e.h.zero_tx.empty() && e.h.exh_words.empty());e.clean();
        // Halt the actual shared PSN table after real RX/MSN work. The
        // response can form but no core retirement may precede PSN readback.
        e.h.atomic_psn_table_enabled=false;zero_rq_ack_enabled=true;e.ticks(100);
        assert(e.h.zero_done.empty() && !e.h.rx_state.empty());e.clean();
        e.h.atomic_psn_table_enabled=true;e.ticks(100);e.clean();
        assert(e.h.zero_done.size()==1);auto d=e.h.zero_done.read();
        assert(d(343,0)==o && d(367,344)==ap_uint<24>(psn+1) && d(391,368)==seq && d(399,392)==15);
        e.response(o,seq);e.h.qp_state.write(ifStateReq(2));e.ticks(16);
        auto s=e.h.qp_rsp.read();assert(s.resp_epsn==ap_uint<24>(psn+1) &&
            s.req_next_psn==0xfffffe && s.req_old_unack==0xfffffe);
        assert(e.h.zero_done.empty() && e.h.zero_commit.empty() && e.h.zero_data.empty() && e.h.zero_tx.empty() &&
            e.h.raw.empty() && e.h.aeth.empty() && e.h.reth.empty());
        std::cout<<"ZERO_SERVICE_DONE "<<d.to_string(16,false)<<std::endl;psn=(psn+1)&0xffffff;
    }
    assert(psn==2);
}
template<int I> static void bad_service(unsigned which) {
    ServiceEndpoint<I> e;e.h.init();auto good=service_owner(1,0x987654,RC_RDMA_WRITE_ONLY);auto o=good;
    if(which==0)o(103,40)=0;if(which==1)o(167,104)=0;if(which==2)o(183,168)=0;
    if(which==3)o(23,0)=0x800002;if(which==4)o(207,184)=0x987655;
    if(which==5)o(215,208)=RC_RDMA_READ_REQUEST;if(which==6)o(279,216)=0;
    if(which==7)o(311,280)=0;if(which==8)o(343,312)=1;
    e.h.zero_owners.write(o);e.h.dest.write(196);e.packet(service_packet(good));e.ticks(200);
    assert((e.h.rf || e.h.ef) && e.h.zero_done.empty() && e.h.zero_commit.empty() && e.h.headers.empty());
    e.quiet_memory();
}
template<int I> static void bad_reth(unsigned which) {
    Harness<I> h;h.init();auto o=service_owner(1,0x987654,RC_RDMA_READ_REQUEST);
    pkgShift s(SHIFT_NONE,2);s.zero_service=true;s.zero_owner=o;s.zero_reth=0;
    net_axis<512> w;w.data=0;w.keep=0xffff;w.last=1;
    if(which==0)w.keep=0xfffe;if(which==1)w.keep=0x1ffff;if(which==2)w.last=0;
    if(which==3)w.data=1;if(which==4)s.receive_owned=true;if(which==5)s.request_owned=true;
    h.shift.write(s);h.raw.write(w);h.ticks(32);
    assert(h.pf && h.zero_data.empty() && h.zero_done.empty() && h.memory.empty());
}
static void bad_sequence() {
    ServiceEndpoint<1517> e;e.h.init();auto o=service_owner(1,0x987655,RC_RDMA_READ_REQUEST);
    e.h.zero_owners.write(o);e.h.dest.write(196);e.packet(service_packet(o));e.ticks(200);
    assert(e.h.rf && e.h.zero_done.empty() && e.h.zero_commit.empty() && e.h.headers.empty());e.quiet_memory();
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    assert(previous_zero_rq_main()==0);service_positive();
    bad_service<1502>(0);bad_service<1503>(1);bad_service<1504>(2);bad_service<1505>(3);
    bad_service<1506>(4);bad_service<1507>(5);bad_service<1508>(6);bad_service<1509>(7);bad_service<1510>(8);
    bad_reth<1511>(0);bad_reth<1512>(1);bad_reth<1513>(2);bad_reth<1514>(3);bad_reth<1515>(4);bad_reth<1516>(5);
    bad_sequence();
    std::cout<<"ZERO_SERVICE_HLS {\"pass_test\":true,\"ordinary_WRITE_READ\":2,\"actual_same_domain_services\":4,"
        "\"distinct_owner344_receipt400\":true,\"no_RQ_Atomic_alias_or_memory_command_data\":true,"
        "\"withheld_owner_RETH_TX_PSN_blocks_done\":true,\"withheld_actual_MSN_blocks_done\":true,"
        "\"same_domain_PSN_wrap\":true,\"exact_wire_and_full_owner\":true,"
        "\"owner_and_RETH_negatives\":16,\"native_MAC_CQ_Linux_hardware\":false}"<<std::endl;
    return 0;
}
