// SPDX-License-Identifier: BSD-2-Clause-Views
// Execute the same real local emitter, headers/payload, shared PSN, stored
// replay, parser/ACK/pointer/pool/timer/state consumers. Physical endpoints
// and the source memory contents remain MODELS, not native/HW qualification.
#include "zero_service_prior.cpp"

static unsigned char large_byte(unsigned off) {return ((off*37)^0xa5)&255;}

template<int I> struct SegmentedEndpoint:RequestEndpoint<I> {
    void clean_large() {
        this->clean();assert(!this->h.pf && !this->h.recv_fault);
        assert(this->h.destination_cmd.empty() && this->h.memory.empty());
    }
    std::vector<unsigned char> fragment(ap_uint<748> n,unsigned offset,unsigned psn,bool replay=false,bool timers=true) {
        auto& h=this->h;unsigned total=unsigned(n(307,276));unsigned bytes=std::min(4096U,total-offset);
        bool first=offset==0,last=offset+bytes==total,send=n(339,324)==3;
        unsigned op=send ? (first ? 0:last ? 2:1):(first ? 6:last ? 8:7);
        assert(h.source_cmd.size()==1 && h.headers.size()==1 && h.conn.size()==1 && h.conn.read()==2);
        auto c=h.source_cmd.read();
        assert(c.origin==2 && c.host && c.len==bytes && c.ctl==last &&
            c.addr==((uint64_t(n(243,180))+offset)&0xffffffffffffULL));
        for(unsigned off=0;off<bytes;off+=64) {
            net_axis<512> w;w.data=~ap_uint<512>(0);w.keep=0;
            for(unsigned b=0;b<64 && off+b<bytes;b++) {
                w.data(b*8+7,b*8)=large_byte(offset+off+b);w.keep[b]=1;
            }
            w.last=off+64>=bytes;this->source_data.write(w);
        }
        this->ticks(100,timers);clean_large();assert(!this->tx_assembled.empty());
        auto header=h.headers.read();auto raw=header.getRawHeader();
        std::vector<unsigned char> actual;
        for(unsigned b=0;b<12;b++)actual.push_back(unsigned(raw(b*8+7,b*8)));
        bool eof=false;
        while(!this->tx_assembled.empty()) {
            auto w=this->tx_assembled.read();assert(!eof);unsigned valid=0;
            for(unsigned b=0;b<64;b++)if(w.keep[b]){actual.push_back(unsigned(w.data(b*8+7,b*8)));valid++;}
            assert(valid && w.keep==((ap_uint<65>(1)<<valid)-1));eof=w.last;
        }
        unsigned pad=(-bytes)&3,extra=!send && first ? 16:0;
        std::vector<unsigned char> expected(12+extra+bytes+pad,0);
        expected[0]=op;expected[1]=0x40|(pad<<4);put_be(expected,2,2,0xffff);
        put_be(expected,5,3,196);expected[8]=0x80;put_be(expected,9,3,psn);
        if(extra) {
            put_be(expected,12,8,uint64_t(n(115,52)));put_be(expected,20,4,unsigned(n(51,20)));
            put_be(expected,24,4,total);
        }
        for(unsigned b=0;b<bytes;b++)expected[12+extra+b]=large_byte(offset+b);
        assert(eof && actual==expected && h.length.size()==1 && h.length.read()==actual.size()+4);
        std::cout<<std::dec<<"SEGMENT_WIRE "<<unsigned(n(339,324))<<" "<<total<<" "<<offset<<" "<<psn<<" "<<replay<<" ";
        for(auto b:actual){const char*d="0123456789abcdef";std::cout<<d[b>>4]<<d[b&15];}
        std::cout<<std::endl;return actual;
    }
};

static void segmented_positive() {
    SegmentedEndpoint<1601> e;e.h.init();unsigned seq=0,psn=0xfffffe;
    const unsigned lengths[]={4097,8192,12289,8193,65537,1048576};
    const unsigned ops[]={1,3,1,3,1,3};unsigned packets=0,replays=0;
    for(unsigned k=0;k<6;k++) {
        auto n=owner(++seq,ops[k]);n(307,276)=lengths[k];assert(as02_req_owner_valid(n));
        auto token=as02_req_token(n);e.h.owners.write(n);e.h.sq.write(atomic_metadata(n));
        unsigned first_psn=psn,packet=0;
        for(unsigned offset=0;offset<lengths[k];offset+=4096,packet++,packets++) {
            unsigned bytes=std::min(4096U,lengths[k]-offset);bool last=offset+bytes==lengths[k];
            e.h.dest.write(196);e.ticks(100,packet!=0);e.clean_large();assert(e.h.done.empty());
            auto wire=e.fragment(n,offset,psn,false,packet!=0);
            // No positive ACK yet: no next fragment, even after arbitrary idle.
            e.ticks(40,packet!=0);assert(e.h.source_cmd.empty() && e.h.app.empty() && e.h.headers.empty() && e.h.done.empty());
            if(packet==0 || (last && k==3)) {
                e.h.retry.write(retransmission(2,psn));e.h.dest.write(196);e.ticks(80,packet!=0);
                assert(e.fragment(n,offset,psn,true,packet!=0)==wire);replays++;
            }
            e.response(RC_ACK,psn);
            if(packet==0) {
                // Actual consumed timers and common state must precede grant.
                e.ticks(100,false);e.clean_large();
                assert(e.h.source_cmd.empty() && e.h.done.empty() && !e.h.tx_timer_done.size());
                e.h.atomic_psn_table_enabled=false;e.ticks(100);e.clean_large();
                assert(e.h.source_cmd.empty() && e.h.done.empty() && !e.h.state_req.empty());
                e.h.atomic_psn_table_enabled=true;
            }
            e.ticks(150);e.clean_large();psn=(psn+1)&0xffffff;
            if(last) {
                assert(e.h.done.size()==1);auto d=e.h.done.read();
                assert(d.context==n && d.psn==first_psn && d.next==psn && d.opcode==as02_req_opcode(n) && !d.error && !d.reserved);
            } else assert(e.h.done.empty());
        }
        e.h.qp_state.write(ifStateReq(2));e.ticks(16);auto s=e.h.qp_rsp.read();
        assert(s.req_next_psn==psn && s.req_old_unack==psn && e.h.segment_continue.empty());
        e.ticks(16);assert(e.h.done.empty() && e.h.source_cmd.empty());
    }
    std::cout<<std::dec<<"SEGMENTED_REQUEST_HLS {\"pass_test\":true,\"whole_WRs\":6,\"packets\":"<<packets
        <<",\"stored_replays\":"<<replays<<",\"max_payload_bytes\":1048576,\"actual_FIRST_MIDDLE_LAST\":true,"
        "\"single_whole_WR_receipt\":true,\"exact_RETH_payload_zero_padding_BTH_PSN\":true,"
        "\"same_domain_PSN_wrap\":true,\"withheld_ACK_timer_state_blocks_next\":true,"
        "\"native_MAC_CQ_Linux_physical\":false}"<<std::endl;
}

template<int I> static void segmented_policy_negative(unsigned op,unsigned length) {
    RequestEndpoint<I> e;e.h.init();auto n=atomic_owner(1,op);n(307,276)=length;
    assert(!as02_req_owner_valid(n));e.h.owners.write(n);e.h.sq.write(atomic_metadata(n));e.ticks(32);
    assert(e.h.af && e.h.admitted.empty() && e.h.rx_owners.empty() && e.h.app.empty() &&
        e.h.local_mem.empty() && e.h.source_cmd.empty() && e.h.headers.empty() && e.h.done.empty());
}

int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original capacities retained");
    assert(previous_zero_service_main()==0);segmented_positive();
    segmented_policy_negative<1602>(1,1048577);segmented_policy_negative<1603>(3,1048577);
    segmented_policy_negative<1604>(2,4097);segmented_policy_negative<1605>(5,4097);
    segmented_policy_negative<1606>(6,4097);
    std::cout<<std::dec<<"SEGMENTED_REQUEST_POLICY {\"pass_test\":true,\"actual_no_issue_negatives\":5}"<<std::endl;
    return 0;
}
