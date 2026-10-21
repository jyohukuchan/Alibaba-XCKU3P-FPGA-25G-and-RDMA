// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual parser/emitter/payload/retransmission/timer/common-state consumers.
// Packet, connection and memory endpoints are models, not native DMA/CRC.
#include "segmented_prior.cpp"

static unsigned char read_byte(unsigned off) {return ((off*37)^0xc3)&255;}

template<int I> struct ReadEndpoint:RequestEndpoint<I> {
    void request_wire(ap_uint<748> n,unsigned psn,bool replay=false) {
        auto& h=this->h;
        assert(h.source_cmd.empty() && h.source_info.empty() && h.headers.size()==1 && !this->tx_assembled.empty());
        auto header=h.headers.read().getRawHeader();std::vector<unsigned char> actual;
        for(unsigned b=0;b<12;b++)actual.push_back(unsigned(header(b*8+7,b*8)));
        bool last=false;
        while(!this->tx_assembled.empty()) {
            auto w=this->tx_assembled.read();assert(!last);
            for(unsigned b=0;b<64;b++)if(w.keep[b])actual.push_back(unsigned(w.data(b*8+7,b*8)));
            last=w.last;
        }
        std::vector<unsigned char> expected(28,0);expected[0]=12;expected[1]=0x40;
        put_be(expected,2,2,0xffff);put_be(expected,5,3,196);expected[8]=0x80;put_be(expected,9,3,psn);
        put_be(expected,12,8,uint64_t(n(115,52)));put_be(expected,20,4,unsigned(n(51,20)));put_be(expected,24,4,unsigned(n(307,276)));
        assert(last && actual==expected && h.length.size()==1 && h.length.read()==32);
        std::cout<<std::dec<<"SEGMENTED_READ_REQUEST "<<unsigned(n(307,276))<<" "<<psn<<" "<<replay<<" ";
        for(auto b:actual){const char*d="0123456789abcdef";std::cout<<d[b>>4]<<d[b&15];}std::cout<<std::endl;
    }
    std::vector<unsigned char> response_bytes(unsigned total,unsigned offset,unsigned psn) {
        unsigned count=std::min(4096U,total-offset);bool first=offset==0,last=offset+count==total;
        unsigned op=total<=4096 ? 16:first ? 13:last ? 15:14;bool aeth=op!=14;
        std::vector<unsigned char> b(12+(aeth ? 4:0)+count+((-count)&3),0);
        b[0]=op;b[1]=((-count)&3)<<4;put_be(b,2,2,0xffff);put_be(b,5,3,2);put_be(b,9,3,psn);
        if(aeth){b[12]=0x1f;put_be(b,13,3,1);}
        for(unsigned i=0;i<count;i++)b[12+(aeth ? 4:0)+i]=read_byte(offset+i);
        return b;
    }
    void memory_bytes(ap_uint<748> owner,unsigned offset,unsigned bytes,bool last) {
        auto& h=this->h;unsigned padded=(bytes+3)&~3U;
        assert(h.destination_cmd.size()==1);auto c=h.destination_cmd.read();
        assert(c.origin==2 && c.host && c.addr==((uint64_t(owner(243,180))+offset)&0xffffffffffffULL) &&
            c.len==padded && bool(c.ctl)==last);
        std::vector<unsigned char> actual;bool eof=false;
        while(!h.memory.empty()) {
            auto w=h.memory.read();assert(!eof);unsigned valid=0;
            for(unsigned b=0;b<64;b++)if(w.keep[b]){actual.push_back(unsigned(w.data(b*8+7,b*8)));valid++;}
            assert(valid && w.keep==((ap_uint<65>(1)<<valid)-1));eof=w.last;
        }
        std::vector<unsigned char> expected(padded,0);for(unsigned i=0;i<bytes;i++)expected[i]=read_byte(offset+i);
        assert(eof && actual==expected);
        std::cout<<std::dec<<"SEGMENTED_READ_DATA "<<unsigned(owner(307,276))<<" "<<offset<<" ";
        for(auto b:actual){const char*d="0123456789abcdef";std::cout<<d[b>>4]<<d[b&15];}std::cout<<std::endl;
    }
};

static void read_positive() {
    ReadEndpoint<1701> e;e.h.init();unsigned seq=0,psn=0xfffffe,packets=0,replays=0;
    for(unsigned length:{4097U,8193U,65537U,1048576U}) {
        auto n=atomic_owner(++seq,2);n(307,276)=length;assert(as02_req_owner_valid(n));
        unsigned initial=psn,span=(length+4095)/4096;e.post(n);e.request_wire(n,psn);
        e.h.retry.write(retransmission(2,psn));e.h.dest.write(196);e.ticks(100);
        assert(e.h.conn.size()==1 && e.h.conn.read()==2 && e.h.issued.empty());e.request_wire(n,psn,true);replays++;
        for(unsigned offset=0;offset<length;offset+=4096,packets++) {
            unsigned count=std::min(4096U,length-offset);bool first=offset==0,last=offset+count==length;
            e.packet(e.response_bytes(length,offset,psn));
            if(first || last) {
                e.ticks(120,false,false);e.clean();assert(e.h.done.empty() && e.h.memory.empty() && e.h.destination_cmd.size()==1);
                e.ticks(120,false,true);e.clean();assert(e.h.done.empty());
            } else {e.ticks(220);e.clean();assert(e.h.done.empty());}
            e.memory_bytes(n,offset,count,last);
            if(last) {
                e.h.atomic_psn_table_enabled=false;e.ticks(100);e.clean();assert(e.h.done.empty() && !e.h.state_req.empty());
                e.h.atomic_psn_table_enabled=true;e.ticks(100);e.clean();
                assert(e.h.done.size()==1);auto r=e.h.done.read();
                assert(r.context==n && r.psn==initial && r.next==((initial+span)&0xffffff) &&
                    r.opcode==RC_RDMA_READ_REQUEST && !r.error && !r.reserved);
            } else {e.ticks(100);e.clean();assert(e.h.done.empty());}
            psn=(psn+1)&0xffffff;
        }
        e.h.qp_state.write(ifStateReq(2));e.ticks(20);auto r=e.h.qp_rsp.read();
        assert(r.req_next_psn==psn && r.req_old_unack==psn && e.h.rx_owners.empty() && e.h.inserted.empty());
        e.ticks(20);assert(e.h.done.empty());
    }
    std::cout<<std::dec<<"SEGMENTED_READ_HLS {\"pass_test\":true,\"whole_WRs\":4,\"response_packets\":"<<packets
        <<",\"stored_request_replays\":"<<replays<<",\"max_bytes\":1048576,\"one_request_and_whole_WR_receipt\":true,"
        "\"actual_header_parser_payload_pointer_pool_timer_state\":true,\"withheld_payload_timers_state_block_completion\":true,"
        "\"mid_READ_retry_recovery\":false,\"native_DMA_CQ_Linux_physical\":false}"<<std::endl;
}

template<int I> static void read_bad(unsigned kind) {
    ReadEndpoint<I> e;e.h.init();auto n=atomic_owner(1,2);n(307,276)=8193;e.post(n);e.request_wire(n,0xfffffe);
    auto b=e.response_bytes(8193,0,0xfffffe);
    if(kind==0)put_be(b,9,3,0xffffff);
    if(kind==1)b[0]=RC_RDMA_READ_RESP_ONLY;
    e.packet(b,kind==2 ? int(b.size()+11):-1);
    if(kind==3) {
        std::vector<net_axis<512>> words;
        while(!e.input.empty())words.push_back(e.input.read());
        assert(words.size()>2);words[2].keep[2]=0;
        for(auto w:words)e.input.write(w);
    }
    e.ticks(300);
    assert((e.h.rf || e.h.ef || e.h.pf || e.h.jf) && e.h.done.empty());
    std::cout<<"SEGMENTED_READ_NEGATIVE "<<kind<<std::endl;
}

int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry");
    assert(argc==2);
    if(std::string(argv[1])=="prior")return preceding_segmented_main();
    if(std::string(argv[1])=="read"){read_positive();return 0;}
    if(std::string(argv[1])=="bad0")read_bad<1702>(0);
    else if(std::string(argv[1])=="bad1")read_bad<1703>(1);
    else if(std::string(argv[1])=="bad2")read_bad<1704>(2);
    else if(std::string(argv[1])=="bad3")read_bad<1705>(3);
    else assert(false);
    return 0;
}
