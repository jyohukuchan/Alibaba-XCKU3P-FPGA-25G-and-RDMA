// SPDX-License-Identifier: BSD-2-Clause-Views
// Real emitter/replay/ACK/timer/shared PSN/whole-WR retirement consumers.
// Peer, connection and source contents are MODELS, not native MR/DMA/CQ.
#include "read_prior.cpp"

static unsigned char immediate_byte(unsigned off) {return ((off*53)^0x97)&255;}

template<int I> struct ImmediateSegmentedEndpoint:RequestEndpoint<I> {
    void clean_large() {
        this->clean();assert(!this->h.pf && !this->h.recv_fault);
        assert(this->h.destination_cmd.empty() && this->h.memory.empty());
    }
    std::vector<unsigned char> fragment(ap_uint<748> n,unsigned offset,unsigned psn,bool replay,bool timers) {
        auto& h=this->h;unsigned total=unsigned(n(307,276));unsigned bytes=std::min(4096U,total-offset);
        bool first=offset==0,last=offset+bytes==total,send=n(339,324)==5;
        // Independent wire constants: SEND FIRST/MIDDLE/LAST_IMM=0/1/3,
        // WRITE FIRST/MIDDLE/LAST_IMM=6/7/9. FIRST WRITE alone carries RETH.
        unsigned op=send ? (first ? 0:last ? 3:1):(first ? 6:last ? 9:7);
        assert(h.source_cmd.size()==1 && h.headers.size()==1 && h.conn.size()==1 && h.conn.read()==2);
        auto c=h.source_cmd.read();
        assert(c.origin==2 && c.host && c.len==bytes && bool(c.ctl)==last &&
            c.addr==((uint64_t(n(243,180))+offset)&0xffffffffffffULL));
        for(unsigned off=0;off<bytes;off+=64) {
            net_axis<512> w;w.data=~ap_uint<512>(0);w.keep=0;
            for(unsigned b=0;b<64 && off+b<bytes;b++) {
                w.data(b*8+7,b*8)=immediate_byte(offset+off+b);w.keep[b]=1;
            }
            w.last=off+64>=bytes;this->source_data.write(w);
        }
        this->ticks(100,timers);clean_large();assert(!this->tx_assembled.empty());
        auto head=h.headers.read().getRawHeader();std::vector<unsigned char> actual;
        for(unsigned b=0;b<12;b++)actual.push_back(unsigned(head(b*8+7,b*8)));
        bool eof=false;
        while(!this->tx_assembled.empty()) {
            auto w=this->tx_assembled.read();assert(!eof);unsigned valid=0;
            for(unsigned b=0;b<64;b++)if(w.keep[b]){actual.push_back(unsigned(w.data(b*8+7,b*8)));valid++;}
            assert(valid && w.keep==((ap_uint<65>(1)<<valid)-1));eof=w.last;
        }
        unsigned pad=(-bytes)&3,reth=!send && first ? 16:0,imm=last ? 4:0;
        std::vector<unsigned char> expected(12+reth+imm+bytes+pad,0);
        expected[0]=op;expected[1]=0x40|(pad<<4);put_be(expected,2,2,0xffff);
        put_be(expected,5,3,196);expected[8]=0x80;put_be(expected,9,3,psn);
        if(reth) {
            put_be(expected,12,8,uint64_t(n(115,52)));put_be(expected,20,4,unsigned(n(51,20)));
            put_be(expected,24,4,total);
        }
        if(imm)put_be(expected,12,4,unsigned(n(619,588)));
        for(unsigned b=0;b<bytes;b++)expected[12+reth+imm+b]=immediate_byte(offset+b);
        assert(eof && actual==expected && h.length.size()==1 && h.length.read()==actual.size()+4);
        std::cout<<std::dec<<"IMMEDIATE_SEGMENT_WIRE "<<unsigned(n(339,324))<<" "<<total<<" "<<offset
            <<" "<<psn<<" "<<replay<<" "<<unsigned(n(619,588))<<" ";
        for(auto b:actual){const char*d="0123456789abcdef";std::cout<<d[b>>4]<<d[b&15];}
        std::cout<<std::endl;return actual;
    }
};

static void immediate_segmented_positive(unsigned op) {
    ImmediateSegmentedEndpoint<1801> e;e.h.init();unsigned seq=0,psn=0xfffffe,packets=0,replays=0;
    const unsigned lengths[]={4097,8192,8193,12289,65537,1048576};
    for(unsigned k=0;k<6;k++) {
        auto n=atomic_owner(++seq,op);n(307,276)=lengths[k];
        n(619,588)=k==0 ? 0:k==1 ? 0xffffffffU:0x89abcdefU+k;
        assert(as02_req_owner_valid(n));
        unsigned initial=psn,packet=0;e.h.owners.write(n);e.h.sq.write(atomic_metadata(n));
        for(unsigned offset=0;offset<lengths[k];offset+=4096,packet++,packets++) {
            unsigned count=std::min(4096U,lengths[k]-offset);bool last=offset+count==lengths[k];
            e.h.dest.write(196);e.ticks(100,packet!=0);e.clean_large();assert(e.h.done.empty());
            auto wire=e.fragment(n,offset,psn,false,packet!=0);
            e.ticks(40,packet!=0);assert(e.h.source_cmd.empty() && e.h.app.empty() && e.h.headers.empty() && e.h.done.empty());
            if(packet==0 || last || (k==2 && packet==1)) {
                e.h.retry.write(retransmission(2,psn));e.h.dest.write(196);e.ticks(80,packet!=0);
                assert(e.fragment(n,offset,psn,true,packet!=0)==wire);replays++;
            }
            e.response(RC_ACK,psn);
            if(packet==0) {
                e.ticks(100,false);e.clean_large();
                assert(e.h.source_cmd.empty() && e.h.done.empty() && !e.h.tx_timer_done.size());
                e.h.atomic_psn_table_enabled=false;e.ticks(100);e.clean_large();
                assert(e.h.source_cmd.empty() && e.h.done.empty() && !e.h.state_req.empty());
                e.h.atomic_psn_table_enabled=true;
            }
            e.ticks(150);e.clean_large();psn=(psn+1)&0xffffff;
            if(last) {
                assert(e.h.done.size()==1);auto d=e.h.done.read();
                assert(d.context==n && d.psn==initial && d.next==psn && d.opcode==(op==5 ? 5:11) && !d.error && !d.reserved);
            } else assert(e.h.done.empty());
        }
        e.h.qp_state.write(ifStateReq(2));e.ticks(16);auto s=e.h.qp_rsp.read();
        assert(s.req_next_psn==psn && s.req_old_unack==psn && e.h.segment_continue.empty() && e.h.rx_owners.empty());
        e.ticks(16);assert(e.h.done.empty() && e.h.source_cmd.empty());
    }
    std::cout<<std::dec<<"SEGMENTED_IMMEDIATE_HLS {\"pass_test\":true,\"WR_opcode\":"<<op
        <<",\"whole_WRs\":6,\"packets\":"<<packets<<",\"stored_replays\":"<<replays
        <<",\"max_bytes\":1048576,\"Immediate_only_on_LAST\":true,\"whole_owner_and_shared_PSN\":true,"
        "\"actual_ACK_pointer_pool_timer_consumers\":true,\"withheld_ACK_timer_state_blocks_next\":true,"
        "\"native_MR_DMA_MAC_CQ_Linux_physical\":false}"<<std::endl;
}

template<int I> static void immediate_segmented_bad(unsigned kind) {
    RequestEndpoint<I> e;e.h.init();auto n=atomic_owner(1,kind&1 ? 6:5);n(307,276)=8193;
    if(kind<2)n(307,276)=1048577;
    else if(kind<4)n(243,180)=0xffffffffffffe000ULL;
    else if(kind==4){n(339,324)=6;n(115,52)=0xffffffffffffe000ULL;}
    else if(kind==5)n(355,340)=0;
    else if(kind==6)n(683,620)=1;
    else if(kind==7)n(747,684)=1;
    else assert(false);
    assert(!as02_req_owner_valid(n));e.h.owners.write(n);e.h.sq.write(atomic_metadata(n));e.ticks(40);
    assert(e.h.af && e.h.admitted.empty() && e.h.rx_owners.empty() && e.h.app.empty() &&
        e.h.local_mem.empty() && e.h.source_cmd.empty() && e.h.headers.empty() && e.h.done.empty());
    std::cout<<"SEGMENTED_IMMEDIATE_NEGATIVE "<<kind<<std::endl;
}

int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry");assert(argc==2);
    std::string mode=argv[1];
    if(mode=="imm-send"){immediate_segmented_positive(5);return 0;}
    if(mode=="imm-write"){immediate_segmented_positive(6);return 0;}
    if(mode=="imm-bad0")immediate_segmented_bad<1802>(0);
    else if(mode=="imm-bad1")immediate_segmented_bad<1803>(1);
    else if(mode=="imm-bad2")immediate_segmented_bad<1804>(2);
    else if(mode=="imm-bad3")immediate_segmented_bad<1805>(3);
    else if(mode=="imm-bad4")immediate_segmented_bad<1806>(4);
    else if(mode=="imm-bad5")immediate_segmented_bad<1807>(5);
    else if(mode=="imm-bad6")immediate_segmented_bad<1808>(6);
    else if(mode=="imm-bad7")immediate_segmented_bad<1809>(7);
    else return preceding_read_main(argc,argv);
    return 0;
}
