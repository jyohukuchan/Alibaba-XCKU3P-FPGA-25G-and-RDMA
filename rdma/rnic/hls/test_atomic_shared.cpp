// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual shared PSN/MSN/RX/TX consumers. Atomic service replies come from the
// separate actual RTL process, not a C++ success/DMA/counter implementation.
// Normal SEND/WRITE payload sink and peer/connection are explicit models.
#include <vector>
#include <string>
#define main preceding_request_main
#include "atomic_request_base.hpp"
#undef main

struct Endpoint {
    Harness<287> h;
    hls::stream<net_axis<512>> input,bth_forward,exh_in,exh_payload,filtered;
    hls::stream<net_axis<512>> reth_raw,aeth_raw,tx_assembled,tx_aeth,tx_reth,tx_raw;
    hls::stream<ibOpCode> rx_op;
    hls::stream<as02RecvDone> received;
    hls::stream<ackEvent> other_ack;
    hls::stream<as02RnrEvent> rnr;
    ap_uint<1> recv_fault=0,rnr_fault=0;ap_uint<32> rx_count=0;
    void tick() {
        h.tick();
        as02_native_rnr_merger<287>(h.rx_ack_events,other_ack,rnr,h.ack_events,rnr_fault);
        rx_process_ibh<512,287>(
#ifdef DBG_IBV_IBH_PROCESS
            h.psn_debug,
#endif
            input,h.rx_bth,rx_op,bth_forward,rx_count);
        rshiftWordByOctet<net_axis<512>,512,11,287>(12,bth_forward,exh_in);
        rx_process_exh<512,287>(exh_in,rx_op,h.rx_exh,h.rx_headers,exh_payload);
        drop_ooo_ibh<512,287>(exh_payload,h.dropped,filtered);
        rx_exh_payload<512,287>(h.split,filtered,reth_raw,aeth_raw,h.raw);
        rshiftWordByOctet<net_axis<512>,512,12,287>(16,reth_raw,h.reth);
        rshiftWordByOctet<net_axis<512>,512,13,287>(4,aeth_raw,h.aeth);
        append_payload<512,287>(h.packet_info,h.exh_words,tx_aeth,tx_reth,tx_raw,tx_assembled);
        as02_recv_retire_join<287>(h.recv_data,h.recv_ack,h.recv_state_req,h.recv_state_rsp,received,recv_fault);
    }
    void ticks(unsigned n) {for(unsigned i=0;i<n;i++)tick();}
    unsigned expected(unsigned q) {
        h.qp_state.write(ifStateReq(q));ticks(8);assert(h.qp_rsp.size()==1);
        return unsigned(h.qp_rsp.read().resp_epsn);
    }
    unsigned msn(unsigned q) {
        h.msn_query.write(q);ticks(8);assert(h.tx_msn.size()==1);
        return unsigned(h.tx_msn.read().msn);
    }
    void init() {
        h.qp_state.write(ifStateReq(2,READY_SEND,0x456700,0xfffffd));
        h.msn_init.write(ifMsnReq(2,8));
        h.qp_state.write(ifStateReq(3,READY_SEND,0x567800,0x123456));
        h.msn_init.write(ifMsnReq(3,8));ticks(2100);
        assert(expected(2)==0xfffffd && msn(2)==0);
    }
    void packet(const std::vector<unsigned char>& data) {
        h.udp.write(data.size()+8+4);
        for(unsigned p=0;p<data.size();p+=64) {
            net_axis<512> w;w.data=0;w.keep=0;
            for(unsigned b=0;b<64 && p+b<data.size();b++) {w.data(b*8+7,b*8)=data[p+b];w.keep[b]=1;}
            w.last=p+64>=data.size();input.write(w);
        }
    }
    std::vector<unsigned char> output(unsigned q) {
        assert(h.conn.size()==1 && h.conn.read()==q);h.dest.write(0xf12345+q);
        ticks(64);assert(h.headers.size()==1 && !tx_assembled.empty());
        auto head=h.headers.read().getRawHeader();std::vector<unsigned char> data;
        for(unsigned b=0;b<12;b++)data.push_back(unsigned(head(b*8+7,b*8)));
        bool last=false;
        while(!tx_assembled.empty()) {
            auto w=tx_assembled.read();assert(!last);
            for(unsigned b=0;b<64;b++)if(w.keep[b])data.push_back(unsigned(w.data(b*8+7,b*8)));
            last=w.last;
        }
        assert(last && h.length.size()==1 && h.length.read()==data.size()+4);
        std::cout<<"ATOMIC_WIRE ";
        for(auto c:data) {const char* d="0123456789abcdef";std::cout<<d[c>>4]<<d[c&15];}
        std::cout<<std::endl;return data;
    }
};

static void put(std::vector<unsigned char>& b,unsigned off,unsigned n,unsigned long long v) {
    for(unsigned i=0;i<n;i++)b[off+i]=(v>>(8*(n-i-1)))&255;
}
static unsigned get24(const std::vector<unsigned char>& b,unsigned off) {
    return (unsigned(b[off])<<16)|(unsigned(b[off+1])<<8)|b[off+2];
}
static std::vector<unsigned char> header(unsigned op,unsigned q,unsigned psn,unsigned size) {
    std::vector<unsigned char> b(size,0);b[0]=op;put(b,2,2,0xffff);put(b,5,3,q);
    b[8]=0x80;put(b,9,3,psn);return b;
}

static void normal(Endpoint& e,bool send,unsigned psn,unsigned message,unsigned sequence) {
    auto b=header(send ? 4:10,2,psn,send ? 80:96);
    if(!send) {put(b,12,8,0xfedcba9876544080ULL);put(b,20,4,8);put(b,24,4,65);}
    unsigned start=send ? 12:28;
    for(unsigned i=0;i<65;i++)b[start+i]=(i*37)^0x5a;
    if(send) {
        as02RecvOwner o;o.context=owner(sequence,3);o.context(339,324)=4;
        o.length=65;o.psn=psn;assert(as02_recv_owner_valid(o));e.h.recv_owners.write(o);
    }
    e.packet(b);e.ticks(96);
    assert(e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();
    assert(c.origin==1 && c.len==68 && c.pid==2);
    std::vector<unsigned char> data;
    while(!e.h.memory.empty()) {
        auto w=e.h.memory.read();for(unsigned i=0;i<64;i++)if(w.keep[i])data.push_back(unsigned(w.data(i*8+7,i*8)));
    }
    assert(data.size()==68);
    for(unsigned i=0;i<65;i++)assert(data[i]==(((i*37)^0x5a)&255));
    for(unsigned i=65;i<68;i++)assert(data[i]==0);
    auto response=e.output(2);assert(response.size()==16 && response[0]==17 && get24(response,9)==psn && get24(response,13)==message);
    assert(e.expected(2)==((psn+1)&0xffffff) && e.msn(2)==message);
    if(send)assert(e.received.size()==1 && !e.received.read().error);
    assert(!e.recv_fault && !e.h.recv_fault && !e.h.rf && !e.h.ef);
}

static unsigned jobs=0,replays=0,drops=0;
static std::vector<unsigned char> atomic(Endpoint& e,unsigned op,unsigned q,unsigned psn,
    unsigned expect,unsigned message,unsigned long long operand,unsigned long long compare,
    bool advance,bool drop=false,unsigned syndrome=0x1f,unsigned response_psn=0xffffffff) {
    auto b=header(op,q,psn,40);put(b,12,8,0xfedcba9876544000ULL);put(b,20,4,8);
    put(b,24,8,operand);put(b,32,8,compare);e.packet(b);e.ticks(64);
    assert(e.h.atomic_requests.size()==1 && e.expected(q)==expect && e.msn(q)==message);
    auto r=e.h.atomic_requests.read();
    assert(r(343,320)==expect && r(367,344)==message);
    for(unsigned i=0;i<40;i++)assert(unsigned(r(i*8+7,i*8))==b[i]);
    // No completion, PSN advance or ACK while service is withheld.
    e.ticks(40);assert(e.expected(q)==expect && e.msn(q)==message && e.h.conn.empty());
    std::cout<<"ATOMIC_SERVICE "<<r.to_string(16,false)<<std::endl;
    std::string line;assert(std::getline(std::cin,line) && !line.empty());
    as02AtomicReply result(line.c_str(),16);
    assert(result(215,192)==q && result(239,216)==psn && bool(result[246])==advance && bool(result[247])==drop);
    e.h.atomic_replies.write(result);e.ticks(64);jobs++;replays+=!advance && !drop && syndrome==0x1f;drops+=drop;
    assert(e.expected(q)==(advance ? ((psn+1)&0xffffff):expect));
    assert(e.msn(q)==((message+unsigned(advance))&0xffffff));
    assert(!e.h.rf && !e.h.ef);
    if(drop) {assert(e.h.conn.empty());return {};}
    auto response=e.output(q);
    unsigned size=syndrome==0x1f ? 24:16;
    assert(response.size()==size && response[0]==(syndrome==0x1f ? 18:17));
    assert(get24(response,9)==(response_psn==0xffffffff ? psn:response_psn));
    assert(response[12]==syndrome);
    // Exact AETH/AtomicACK bytes come from the actual protected RTL service.
    for(unsigned i=12;i<size;i++)assert(response[i]==unsigned(result(i*8+7,i*8)));
    return response;
}

int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    Endpoint e;e.init();
    normal(e,true,0xfffffd,1,1);
    auto first=atomic(e,19,2,0xfffffe,0xfffffe,1,0x8123456789abcdefULL,0xf123456789abcdefULL,true);
    auto replay=atomic(e,19,2,0xfffffe,0xffffff,2,0x8123456789abcdefULL,0xf123456789abcdefULL,false);
    assert(first==replay);
    normal(e,false,0xffffff,3,2);
    atomic(e,20,2,0,0,3,0x7edcba9876543211ULL,0,true);
    atomic(e,20,2,2,1,4,1,0,false,false,0x60,1);
    auto mismatch=atomic(e,19,2,1,1,4,0xfeedface12345678ULL,1,true);
    atomic(e,19,3,0x123456,0x123456,0,0xfedcba9876543210ULL,0,true);
    auto duplicate=atomic(e,19,2,1,2,5,0xfeedface12345678ULL,1,false);
    assert(mismatch==duplicate);
    atomic(e,19,2,0xfffffe,2,5,0x8123456789abcdefULL,0xf123456789abcdefULL,false,true);
    normal(e,false,2,6,3);
    atomic(e,20,2,3,3,6,0,0,true);
    assert(e.expected(2)==4 && e.msn(2)==7 && e.expected(3)==0x123457 && e.msn(3)==1);
    assert(e.h.atomic_requests.empty() && e.h.atomic_replies.empty() && e.h.atomic_commit.empty());
    assert(e.input.empty() && e.bth_forward.empty() && e.exh_in.empty() && e.exh_payload.empty());
    assert(e.h.dropped.empty() && e.h.rx_headers.empty() && e.h.split.empty() && e.h.shift.empty());
    assert(!e.h.jf && !e.h.ff && !e.h.tf && !e.h.mf && !e.recv_fault);
    std::cout<<"ATOMIC_SHARED_HLS {\"pass_test\":true,\"atomic_jobs\":"<<std::dec<<jobs
        <<",\"cached_replies\":"<<replays<<",\"drops\":"<<drops
        <<",\"normal_SEND\":1,\"normal_WRITE\":2,\"QPs\":2,\"shared_PSN_MSN\":true,\"withheld_service_no_advance\":true}"<<std::endl;
}
