// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual complete owned transport consumers; peer/connection/memory endpoints
// are models. No modeled Atomic result data or invented retirement receipt.
#include <vector>
#include <string>
#define main preceding_request_main
#include "atomic_request_base.hpp"
#undef main

static void put_be(std::vector<unsigned char>& b,unsigned off,unsigned n,unsigned long long v) {
    for(unsigned i=0;i<n;i++)b[off+i]=(v>>(8*(n-i-1)))&255;
}
static ap_uint<748> atomic_owner(unsigned seq,unsigned op) {
    auto n=owner(seq,op==3 || op==5 ? 3:1);n(339,324)=op;
    if(op==7 || op==8) {
        n(307,276)=8;n(115,52)=0xe23456789abcd008ULL;
        n(683,620)=op==7 ? 0xfedcba9876543210ULL:0;
        n(747,684)=0x8123456789abcdefULL+seq;
    }
    if(op==5 || op==6)n(619,588)=0x89abcdef;
    assert(as02_req_owner_valid(n));return n;
}
static txMeta atomic_metadata(ap_uint<748> n) {
    ap_uint<192> p=0;p(63,0)=n(243,180);p(127,64)=n(115,52);
    p(159,128)=n(307,276);p(191,160)=n(51,20);
    txMeta m(ibOpCode(unsigned(as02_req_opcode(n))),2,1,1,0,p,1);
    m.immediate=n(619,588);m.compare=n(683,620);m.swap_add=n(747,684);return m;
}
template<int I> struct RequestEndpoint {
    Harness<I> h;
    hls::stream<net_axis<512>> input,bth_forward,exh_in,exh_payload,filtered;
    hls::stream<net_axis<512>> reth_raw,aeth_raw,tx_assembled,tx_aeth,tx_reth,tx_raw,source_data;
    hls::stream<ibOpCode> rx_op;
    ap_uint<32> rx_count=0;
    void tick(bool timers=true,bool payload=true,bool tables=true) {
        h.tick(timers,payload,tables);
        rx_process_ibh<512,I>(
#ifdef DBG_IBV_IBH_PROCESS
            h.psn_debug,
#endif
            input,h.rx_bth,rx_op,bth_forward,rx_count);
        rshiftWordByOctet<net_axis<512>,512,11,I>(12,bth_forward,exh_in);
        rx_process_exh<512,I>(exh_in,rx_op,h.rx_exh,h.rx_headers,exh_payload);
        drop_ooo_ibh<512,I>(exh_payload,h.dropped,filtered);
        rx_exh_payload<512,I>(h.split,filtered,reth_raw,aeth_raw,h.raw);
        rshiftWordByOctet<net_axis<512>,512,12,I>(16,reth_raw,h.reth);
        rshiftWordByOctet<net_axis<512>,512,13,I>(4,aeth_raw,h.aeth);
        tx_pkg_arbiter<512,I>(h.source_info,source_data,tx_aeth,tx_reth,tx_raw);
        append_payload<512,I>(h.packet_info,h.exh_words,tx_aeth,tx_reth,tx_raw,tx_assembled);
    }
    void ticks(unsigned n,bool timers=true,bool payload=true,bool tables=true) {
        for(unsigned i=0;i<n;i++)tick(timers,payload,tables);
    }
    void post(ap_uint<748> n) {
        h.owners.write(n);h.sq.write(atomic_metadata(n));h.dest.write(196);ticks(100);
        assert(h.conn.size()==1 && h.conn.read()==2 && h.headers.size()==1);
        assert(!h.af && !h.mf && !h.tf && !h.jf && h.done.empty());
    }
    std::vector<unsigned char> wire(ap_uint<748> n,unsigned psn,bool replay=false) {
        if(n(339,324)!=2 && n(339,324)!=7 && n(339,324)!=8) {
            assert(h.source_cmd.size()==1);auto c=h.source_cmd.read();
            assert(c.origin==2 && c.host && c.addr==0xba9876543210ULL && c.len==65);
            net_axis<512> w;w.data=0;
            for(unsigned b=0;b<64;b++)w.data(b*8+7,b*8)=b^0xa5;
            w.keep=~ap_uint<64>(0);w.last=0;source_data.write(w);
            w.data=0x5a;w.keep=1;w.last=1;source_data.write(w);ticks(100);
        } else assert(h.source_cmd.empty() && h.source_info.empty());
        assert(h.headers.size()==1 && !tx_assembled.empty());
        auto head=h.headers.read();auto raw=head.getRawHeader();
        assert(head.getOpCode()==as02_req_opcode(n) && head.getPsn()==psn && head.getDstQP()==196);
        assert(raw[71] && raw(70,64)==0);
        std::vector<unsigned char> data;
        for(unsigned b=0;b<12;b++)data.push_back(unsigned(raw(b*8+7,b*8)));
        bool last=false;
        while(!tx_assembled.empty()) {
            auto w=tx_assembled.read();assert(!last);unsigned count=0;
            for(unsigned b=0;b<64;b++)if(w.keep[b]){data.push_back(unsigned(w.data(b*8+7,b*8)));count++;}
            assert(count && w.keep==((ap_uint<65>(1)<<count)-1));last=w.last;
        }
        assert(last && h.length.size()==1 && h.length.read()==data.size()+4);
        auto expected=std::vector<unsigned char>(data.size(),0);expected[0]=unsigned(as02_req_opcode(n));
        expected[1]=0x40;put_be(expected,2,2,0xffff);put_be(expected,5,3,196);
        expected[8]=0x80;put_be(expected,9,3,psn);
        unsigned op=unsigned(n(339,324));
        if(op==7 || op==8) {
            assert(data.size()==40);put_be(expected,12,8,0xe23456789abcd008ULL);
            put_be(expected,20,4,0x81234567);put_be(expected,24,8,0x8123456789abcdefULL+unsigned(n(523,460)));
            put_be(expected,32,8,op==7 ? 0xfedcba9876543210ULL:0);
        } else {
            unsigned header=(op==1 || op==2 || op==6) ? 16:0;
            if(header) {
                put_be(expected,12,8,0xe23456789abcdef0ULL);put_be(expected,20,4,0x81234567);
                put_be(expected,24,4,65);
            }
            if(op==5 || op==6){put_be(expected,12+header,4,0x89abcdef);header+=4;}
            if(op!=2) {
                assert(data.size()==12+header+65);
                for(unsigned i=0;i<64;i++)expected[12+header+i]=i^0xa5;
                expected[12+header+64]=0x5a;
            } else assert(data.size()==28);
        }
        assert(data==expected);
        std::cout<<"ATOMIC_REQUEST_WIRE "<<(replay ? "replay ":"fresh ");
        for(auto c:data){const char* d="0123456789abcdef";std::cout<<d[c>>4]<<d[c&15];}
        std::cout<<std::endl;return data;
    }
    void packet(const std::vector<unsigned char>& data,int udp_override=-1) {
        h.udp.write(udp_override<0 ? data.size()+12:udp_override);
        for(unsigned p=0;p<data.size();p+=64) {
            net_axis<512> w;w.data=0;w.keep=0;
            for(unsigned b=0;b<64 && p+b<data.size();b++){w.data(b*8+7,b*8)=data[p+b];w.keep[b]=1;}
            w.last=p+64>=data.size();input.write(w);
        }
    }
    void response(unsigned opcode,unsigned psn,unsigned syndrome=0,unsigned long long value=0,int length=-1) {
        unsigned size=opcode==RC_ATOMIC_ACK ? 24:opcode==RC_RDMA_READ_RESP_ONLY ? 84:16;
        std::vector<unsigned char> b(size,0);b[0]=opcode;put_be(b,2,2,0xffff);
        put_be(b,5,3,2);put_be(b,9,3,psn);b[12]=syndrome;put_be(b,13,3,1);
        if(opcode==RC_ATOMIC_ACK)put_be(b,16,8,value);
        if(opcode==RC_RDMA_READ_RESP_ONLY)for(unsigned i=0;i<65;i++)b[16+i]=i^0x5a;
        packet(b,length);
    }
    void clean() {
        assert(!h.af && !h.rf && !h.ef && !h.mf && !h.tf && !h.ff && !h.jf && !h.recv_fault && !h.psn_drops);
    }
};

static void positive() {
    RequestEndpoint<391> e;e.h.init();unsigned sequence=0,expected_psn=0xfffffe;
    const unsigned ops[]={7,8,1,2,3,5,6,7,8};
    for(unsigned op:ops) {
        auto n=atomic_owner(++sequence,op);e.post(n);auto wire=e.wire(n,expected_psn);
        if(op==7 || op==8) {
            // Genuine stored retransmission lookup, not direct event injection.
            e.h.retry.write(retransmission(2,expected_psn));e.h.dest.write(196);e.ticks(100);
            assert(e.h.conn.size()==1 && e.h.conn.read()==2 && e.h.retrans_count!=0);
            assert(e.wire(n,expected_psn,true)==wire && e.h.issued.empty() && e.h.done.empty());
            unsigned long long old=0xfedcba9876543210ULL^sequence;
            e.response(RC_ATOMIC_ACK,expected_psn,sequence%2 ? 0:0x1f,old);
            // Stop the ACTUAL result-data and timer consumers independently.
            e.ticks(100,false,false);e.clean();assert(e.h.memory.empty() && e.h.done.empty());
            assert(e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();
            assert(c.addr==0xba9876543210ULL && c.len==8 && c.origin==2 && c.host && c.ctl &&
                c.pid==2 && c.vfid==0 && c.strm==1 && c.sync==0 && c.tdst==12);
            e.ticks(100,false,true);e.clean();assert(e.h.memory.size()==1 && e.h.done.empty());
            auto w=e.h.memory.read();assert(w.keep==0xff && w.last && w.data(511,64)==0);
            for(unsigned b=0;b<8;b++)assert(w.data(b*8+7,b*8)==((old>>(8*b))&255));
            assert(e.h.aeth.empty() && e.h.raw.empty() && e.h.split.empty() && e.h.dropped.empty());
            // Timers alone cannot replace the same common-state readback.
            e.ticks(100,true,true,false);assert(e.h.done.empty() && e.h.state_req.size()==1);
            e.ticks(100);e.clean();
        } else {
            e.response(op==2 ? RC_RDMA_READ_RESP_ONLY:RC_ACK,expected_psn);e.ticks(300);e.clean();
            if(op==2) {
                assert(e.h.destination_cmd.size()==1 && e.h.memory.size()==2);
                auto c=e.h.destination_cmd.read();assert(c.origin==2 && c.len==68 && c.addr==0xba9876543210ULL);
                unsigned off=0;
                while(!e.h.memory.empty()){
                    auto w=e.h.memory.read();for(unsigned b=0;b<64;b++)if(w.keep[b]){
                        assert(w.data(b*8+7,b*8)==(off<65 ? off^0x5a:0));off++;
                    }
                }
                assert(off==68);
            } else assert(e.h.destination_cmd.empty() && e.h.memory.empty());
        }
        assert(e.h.done.size()==1);auto d=e.h.done.read();expected_psn=(expected_psn+1)&0xffffff;
        assert(d.context==n && d.next==expected_psn && d.opcode==as02_req_opcode(n) && !d.error && !d.reserved);
        e.h.qp_state.write(ifStateReq(2));e.ticks(8);assert(e.h.qp_rsp.size()==1);
        auto s=e.h.qp_rsp.read();assert(s.req_next_psn==expected_psn && s.req_old_unack==expected_psn && s.resp_epsn==0x987654);
        e.ticks(16);assert(e.h.done.empty() && e.h.tx_timer_done.empty() && e.h.rx_timer_done.empty());
    }
}

template<int I> static void bind_negative(bool padding) {
    RequestEndpoint<I> e;e.h.init();auto n=atomic_owner(1,7);auto m=atomic_metadata(n);
    if(padding)m.atomic_padding=1;else m.compare=m.compare^1;
    e.h.owners.write(n);e.h.sq.write(m);e.ticks(12);
    assert(e.h.af && e.h.admitted.empty() && e.h.source_cmd.empty() && e.h.local_mem.empty() &&
        e.h.headers.empty() && e.h.done.empty() && e.h.rx_owners.empty());
}
template<int I> static void response_negative(unsigned op,unsigned response_op,unsigned syndrome,int udp_length=-1) {
    RequestEndpoint<I> e;e.h.init();auto n=atomic_owner(1,op);e.post(n);e.wire(n,0xfffffe);
    e.response(response_op,0xfffffe,syndrome,0xfedcba9876543210ULL,udp_length);e.ticks(300);
    assert((e.h.rf || e.h.ef || e.h.tf) && e.h.done.empty() && e.h.destination_cmd.empty() && e.h.memory.empty());
}
template<int I> static void malformed_parser(unsigned keep,bool last,unsigned syn) {
    hls::stream<net_axis<512>> input,payload;hls::stream<ibOpCode> ops;
    hls::stream<exhMeta> meta;hls::stream<ExHeader<512>> headers;
    net_axis<512> w;w.data=syn;w.keep=keep;w.last=last;input.write(w);ops.write(RC_ATOMIC_ACK);
    for(unsigned i=0;i<4;i++)rx_process_exh<512,I>(input,ops,meta,headers,payload);
    assert(meta.size()==1 && meta.read().isNak && headers.size()==1 && payload.empty());
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original capacities retained");
    positive();bind_negative<392>(false);bind_negative<393>(true);
    response_negative<394>(1,RC_ATOMIC_ACK,0);response_negative<395>(7,RC_ACK,0);
    response_negative<396>(7,RC_ATOMIC_ACK,0x20);response_negative<397>(8,RC_ATOMIC_ACK,0,35);
    malformed_parser<401>(0x7ff,true,0);malformed_parser<402>(0x1fff,true,0);
    malformed_parser<403>(0xfff,false,0);malformed_parser<404>(0xfff,true,0x60);
    malformed_parser<405>(0xfff,true,0x80);
    std::cout<<"ATOMIC_REQUEST_HLS {\"pass_test\":true,\"fresh_requests\":9,\"atomic_results\":4,"
        "\"actual_stored_replays\":4,\"WRITE_READ_SEND_Immediate\":true,\"owner_bits\":748,\"SQ_bits\":408,"
        "\"padding_preserved\":true,\"result_from_actual_ACK_parser\":true,\"LE8_result\":true,"
        "\"withheld_actual_result_timer_state_consumers\":true,\"same_PSN_wrap\":true,"
        "\"operand_padding_responseclass_syndrome_length_negatives\":true,\"no_atomic_source_DMA\":true,"
        "\"native_RTL_MAC_CQ_API_hardware\":false}"<<std::endl;
    return 0;
}
