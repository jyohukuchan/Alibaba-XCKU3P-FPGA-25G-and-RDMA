// SPDX-License-Identifier: BSD-2-Clause-Views
// Same actual transport/PSN/retransmission/parser/timer consumers. Only peer,
// connection and memory endpoints are models; not native DMA/MAC/CQ proof.
#include "atomic_request_prior.cpp"

static ap_uint<748> zero_owner(unsigned seq,unsigned op) {
    auto n=atomic_owner(seq,op);n(307,276)=0;n(275,116)=0;
    if(op==1 || op==2 || op==6) {
        // A zero remote request need not name an MR. Preserve exact arbitrary
        // remote VA/rkey on the wire rather than interpreting them locally.
        n(115,52)=0xffffffffffffffffULL;n(51,20)=0xfedcba98;
    }
    assert(as02_req_owner_valid(n));return n;
}

template<int I> struct ZeroEndpoint:RequestEndpoint<I> {
    std::vector<unsigned char> wire_zero(ap_uint<748> n,unsigned psn,bool replay=false) {
        auto &h=this->h;
        assert(h.source_cmd.empty() && h.source_info.empty() && h.local_mem.empty());
        assert(h.destination_cmd.empty() && h.memory.empty() && h.headers.size()==1 && !this->tx_assembled.empty());
        auto bth=h.headers.read();auto b=bth.getRawHeader();std::vector<unsigned char> actual;
        for(unsigned i=0;i<12;i++)actual.push_back(unsigned(b(i*8+7,i*8)));
        bool last=false;unsigned markers=0;
        while(!this->tx_assembled.empty()) {
            auto w=this->tx_assembled.read();assert(!last);unsigned count=0;
            for(unsigned i=0;i<64;i++)if(w.keep[i]){actual.push_back(unsigned(w.data(i*8+7,i*8)));count++;}
            assert(w.keep==((ap_uint<65>(1)<<count)-1));last=w.last;
            if(!count){assert(n(339,324)==3 && w.last);markers++;}
        }
        assert(last && markers==unsigned(n(339,324)==3));
        unsigned op=unsigned(n(339,324));unsigned header=(op==1 || op==2 || op==6) ? 16:0;
        bool imm=op==5 || op==6;
        std::vector<unsigned char> expected(12+header+(imm ? 4:0),0);
        expected[0]=unsigned(as02_req_opcode(n));expected[1]=0x40;put_be(expected,2,2,0xffff);
        put_be(expected,5,3,196);expected[8]=0x80;put_be(expected,9,3,psn);
        if(header){put_be(expected,12,8,0xffffffffffffffffULL);put_be(expected,20,4,0xfedcba98);put_be(expected,24,4,0);}
        if(imm)put_be(expected,12+header,4,0x89abcdef);
        assert(actual==expected && h.length.size()==1 && h.length.read()==actual.size()+4);
        std::cout<<"ZERO_REQUEST_WIRE "<<(replay ? "replay ":"fresh ");
        for(auto c:actual){const char*d="0123456789abcdef";std::cout<<d[c>>4]<<d[c&15];}
        std::cout<<std::endl;return actual;
    }
    void zero_read_reply(unsigned psn,unsigned bytes=16,int udp=-1,unsigned syndrome=0) {
        std::vector<unsigned char>b(bytes,0);b[0]=RC_RDMA_READ_RESP_ONLY;put_be(b,2,2,0xffff);
        put_be(b,5,3,2);put_be(b,9,3,psn);b[12]=syndrome;put_be(b,13,3,1);
        this->packet(b,udp);
    }
    void clean_zero() {
        this->clean();assert(!this->h.pf && this->h.source_cmd.empty() && this->h.source_info.empty() &&
            this->h.destination_cmd.empty() && this->h.memory.empty());
    }
};

static void zero_positive() {
    ZeroEndpoint<501>e;e.h.init();unsigned seq=0,psn=0xfffffe;
    for(unsigned op:{3,1,5,2,6}) {
        auto n=zero_owner(++seq,op);e.post(n);auto packet=e.wire_zero(n,psn);
        // Actual stored-entry replay, including the no-data SEND marker.
        e.h.retry.write(retransmission(2,psn));e.h.dest.write(196);e.ticks(100);
        assert(e.h.conn.size()==1 && e.h.conn.read()==2 && e.h.retrans_count==seq);
        assert(e.wire_zero(n,psn,true)==packet && e.h.done.empty() && e.h.issued.empty());
        if(op==2)e.zero_read_reply(psn);else e.response(RC_ACK,psn);
        e.ticks(100,false,false);e.clean_zero();assert(e.h.done.empty());
        if(op==2) {
            assert(e.h.raw.size()==1);
            // Real header consumer disabled even while actual timers run.
            e.ticks(100,true,false);e.clean_zero();assert(e.h.done.empty() && e.h.raw.size()==1);
        }
        e.ticks(100,true,true,false);e.clean_zero();
        assert(e.h.done.empty() && e.h.state_req.size()==1);
        e.ticks(100);e.clean_zero();assert(e.h.done.size()==1);
        auto d=e.h.done.read();psn=(psn+1)&0xffffff;
        assert(d.context==n && d.psn==((psn-1)&0xffffff) && d.next==psn && d.opcode==as02_req_opcode(n) && !d.error);
        e.h.qp_state.write(ifStateReq(2));e.ticks(8);assert(e.h.qp_rsp.size()==1);
        auto s=e.h.qp_rsp.read();assert(s.req_next_psn==psn && s.req_old_unack==psn && s.resp_epsn==0x987654);
        assert(e.h.raw.empty() && e.h.aeth.empty() && e.h.reth.empty() && e.h.read_consumed.empty());
    }
    // Follow zero READ with a real nonzero READ on this SAME actual domain.
    auto normal=atomic_owner(++seq,2);e.post(normal);e.wire(normal,psn);
    e.response(RC_RDMA_READ_RESP_ONLY,psn);e.ticks(300);e.clean();assert(!e.h.pf);
    assert(e.h.done.size()==1 && e.h.done.read().context==normal);
    assert(e.h.destination_cmd.size()==1 && e.h.destination_cmd.read().len==68 && e.h.memory.size()==2);
    unsigned seen=0;
    while(!e.h.memory.empty()) {
        auto w=e.h.memory.read();for(unsigned i=0;i<64;i++)if(w.keep[i]){
            assert(w.data(i*8+7,i*8)==(seen<65 ? seen^0x5a:0));seen++;
        }
    }
    assert(seen==68 && e.h.raw.empty());
}

template<int I> static void bad_zero_owner(unsigned field) {
    ZeroEndpoint<I>e;e.h.init();auto n=zero_owner(1,1);
    if(field==0)n(275,244)=1;if(field==1)n(243,180)=1;if(field==2)n(179,116)=1;
    if(field==3)n(339,324)=7;
    assert(!as02_req_owner_valid(n));e.h.owners.write(n);e.h.sq.write(atomic_metadata(n));e.ticks(64);
    assert(e.h.af && e.h.done.empty() && e.h.headers.empty() && e.h.local_mem.empty() && e.h.source_cmd.empty());
}
template<int I> static void bad_zero_reply(unsigned bytes,int udp,unsigned syndrome) {
    ZeroEndpoint<I>e;e.h.init();auto n=zero_owner(1,2);e.post(n);e.wire_zero(n,0xfffffe);
    e.zero_read_reply(0xfffffe,bytes,udp,syndrome);e.ticks(300);
    assert((e.h.ef || e.h.rf || e.h.tf || e.h.pf) && e.h.done.empty() &&
        e.h.destination_cmd.empty() && e.h.memory.empty() && e.h.source_cmd.empty());
}
int main() {
    assert(atomic_compat_main()==0);zero_positive();
    bad_zero_owner<502>(0);bad_zero_owner<503>(1);bad_zero_owner<504>(2);bad_zero_owner<505>(3);
    bad_zero_reply<506>(16,29,0);bad_zero_reply<507>(17,28,0);bad_zero_reply<508>(16,28,0x60);
    std::cout<<"ZERO_REQUEST_HLS {\"pass_test\":true,\"zero_requests\":5,\"actual_stored_replays\":5,"
        "\"zero_data_memory_commands\":true,\"WRITE_READ_SEND_Immediate\":true,\"PSN_wrap_and_one_step_READ\":true,"
        "\"withheld_actual_header_timer_state_consumers\":true,\"full_owner_retained\":true,"
        "\"nonzero_READ_after_zero_same_domain\":true,\"canonical_Atomic_and_bad_response_negatives\":7,"
        "\"native_MAC_CQ_kernel_hardware\":false}"<<std::endl;
    return 0;
}
