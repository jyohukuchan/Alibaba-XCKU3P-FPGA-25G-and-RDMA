// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual BTH/EXH/payload/ACK/MSN/PSN consumers and the whole-message join.
// Packets and posted owners are models; NOT native MR/DMA/MAC/CQ proof.
#include "immediate_prior.cpp"

template<int I> struct ReceiveEndpoint:Endpoint<I> {
    hls::stream<as02RecvDone> packets;
    hls::stream<as02RecvMessage> messages;
    ap_uint<1> message_fault=0;
    void step(bool data=true,bool ack=true,bool table=true,bool group=true) {
        zero_rq_ack_enabled=ack;this->tick(true,data,table);
        if(group)as02_recv_message_join<I>(this->received,packets,messages,message_fault);
    }
    void steps(unsigned count,bool data=true,bool ack=true,bool table=true,bool group=true) {
        for(unsigned j=0;j<count;j++)step(data,ack,table,group);
    }
    void clean() {
        auto& h=this->h;
        if(this->recv_join_fault || message_fault || h.recv_fault || h.pf || h.af || h.rf || h.ef ||
            h.mf || h.tf || h.ff || h.jf || h.psn_drops)
            std::cerr<<"RECEIVE_FAULT "<<I<<" packet_join="<<this->recv_join_fault<<" message="<<message_fault
                <<" bind="<<h.recv_fault<<" payload="<<h.pf<<" admission="<<h.af<<" RX="<<h.rf<<" EXH="<<h.ef
                <<" merge="<<h.mf<<" replay="<<h.tf<<" timer="<<h.ff<<" request_join="<<h.jf<<" drops="<<h.psn_drops<<std::endl;
        assert(!this->recv_join_fault && !message_fault && !h.recv_fault && !h.pf &&
            !h.af && !h.rf && !h.ef && !h.mf && !h.tf && !h.ff && !h.jf && !h.psn_drops);
    }
};
static as02RecvOwner segmented_rq(unsigned seq,unsigned psn,unsigned length,unsigned capacity=1048576) {
    as02RecvOwner o;o.context=owner(seq,3);o.context(339,324)=4;o.context(307,276)=capacity;
    o.length=length;o.psn=psn;assert(as02_recv_owner_valid(o));return o;
}
static unsigned char receive_byte(unsigned offset){return ((offset*91)^0x69)&255;}
static std::vector<unsigned char> receive_packet(unsigned op,unsigned total,unsigned offset,unsigned psn,unsigned imm) {
    unsigned count=std::min(4096U,total-offset);bool first=offset==0,last=offset+count==total;
    unsigned opcode=first ? 0:last ? (op==5 ? 3:2):1;
    unsigned header=last && op==5 ? 4:0,pad=(-count)&3;
    std::vector<unsigned char> b(12+header+count+pad,0);
    b[0]=opcode;b[1]=0x40|(pad<<4);put_be(b,2,2,0xffff);put_be(b,5,3,2);b[8]=0x80;put_be(b,9,3,psn);
    if(header)put_be(b,12,4,imm);
    for(unsigned i=0;i<count;i++)b[12+header+i]=receive_byte(offset+i);
    return b;
}
static void receive_hex(const std::vector<unsigned char>& b) {
    for(auto c:b){const char*d="0123456789abcdef";std::cout<<d[c>>4]<<d[c&15];}std::cout<<std::endl;
}
template<int I> static void receive_positive(unsigned op) {
    ReceiveEndpoint<I> e;e.init(0x123400,0xfffffe);unsigned psn=0xfffffe,seq=0,packets=0;
    for(unsigned total:{4097U,8192U,8193U,12289U,65537U,1048576U}) {
        unsigned initial=psn,imm=seq==0 ? 0:seq==1 ? 0xffffffff:0x89abcdef+seq;seq++;
        auto rq=segmented_rq(seq,psn,4096);assert(e.messages.empty() && e.packets.empty());
        for(unsigned offset=0;offset<total;offset+=4096,packets++) {
            unsigned count=std::min(4096U,total-offset);bool first=offset==0,last=offset+count==total;
            auto o=rq;o.length=count;o.psn=psn;e.h.recv_owners.write(o);
            auto wire=receive_packet(op,total,offset,psn,imm);e.input(wire,wire.size()+12);e.h.dest.write(196);
            if(first || last) {
                e.steps(100,false,false);e.clean();assert(e.h.memory.empty() && e.packets.empty() && e.messages.empty());
                e.steps(100,true,false);e.clean();assert(e.packets.empty() && e.messages.empty());
                e.steps(100,true,true,false);e.clean();assert(e.packets.empty() && e.messages.empty() && !e.h.recv_state_req.empty());
                e.steps(100,true,true,true,false);e.clean();assert(e.received.size()==1 && e.packets.empty() && e.messages.empty());
            } else {e.steps(180);e.clean();}
            assert(e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();
            assert(c.origin==1 && c.host==0 && c.addr==offset && c.len==((count+3)&~3U) &&
                bool(c.ctl)==last && c.pid==2 && c.vfid==0);
            std::vector<unsigned char> data;bool eof=false;
            while(!e.h.memory.empty()) {
                auto w=e.h.memory.read();assert(!eof);unsigned valid=0;
                for(unsigned b=0;b<64;b++)if(w.keep[b]){valid++;data.push_back(unsigned(w.data(b*8+7,b*8)));}
                assert(valid && w.keep==((ap_uint<65>(1)<<valid)-1));eof=w.last;
            }
            assert(eof && data.size()==((count+3)&~3U));
            for(unsigned b=0;b<data.size();b++)assert(data[b]==(b<count ? receive_byte(offset+b):0));
            std::cout<<std::dec<<"SEGMENTED_RECEIVE_DATA "<<op<<" "<<total<<" "<<offset<<" ";receive_hex(data);
            auto ack=e.packet(false);unsigned expected_msn=last ? seq:seq-1;
            std::vector<unsigned char> expected(16,0);expected[0]=17;expected[1]=0x40;
            put_be(expected,2,2,0xffff);put_be(expected,5,3,196);put_be(expected,9,3,psn);
            put_be(expected,13,3,expected_msn);assert(ack==expected && e.h.length.size()==1 && e.h.length.read()==20);
            std::cout<<std::dec<<"SEGMENTED_RECEIVE_ACK "<<op<<" "<<total<<" "<<offset<<" ";receive_hex(ack);
            e.steps(20);e.clean();assert(e.packets.size()==1);auto p=e.packets.read();
            assert(!p.error && p.proof.owner.context==rq.context && p.proof.owner.length==count &&
                p.proof.owner.psn==psn && p.proof.owner.reserved==0 && p.proof.msn==expected_msn &&
                p.proof.flags==(first ? 4:last ? (op==5 ? 17:16):8) &&
                p.proof.immediate==(last && op==5 ? imm:0));
            if(last) {
                assert(e.messages.size()==1);auto m=e.messages.read();
                assert(m.context==rq.context && m.bytes==total && m.first_psn==initial && m.last_psn==psn &&
                    m.msn==seq && m.flags==(op==5 ? 1:0) && m.immediate==(op==5 ? imm:0) && !m.error);
                std::cout<<std::dec<<"SEGMENTED_RECEIVE_MESSAGE "<<op<<" "<<total<<" "<<initial<<" "<<psn<<" "<<seq
                    <<" "<<unsigned(m.immediate)<<" "<<unsigned(m.context(307,276))<<std::endl;
            } else assert(e.messages.empty());
            e.steps(8);assert(e.messages.empty() && e.packets.empty() && e.received.empty());psn=(psn+1)&0xffffff;
        }
    }
    std::cout<<std::dec<<"SEGMENTED_RECEIVE_HLS {\"pass_test\":true,\"opcode\":"<<op
        <<",\"whole_messages\":6,\"packets\":"<<packets<<",\"max_bytes\":1048576,\"full620_posted_context\":true,"
        "\"capacity_not_actual_length\":true,\"MSN_only_on_LAST\":true,\"actual_payload_ACK_PSN_required\":true,"
        "\"separate_packet_and_whole_receipts\":true,\"PSN_wrap\":true,\"native_DMA_MAC_CQ_Linux_physical\":false}"<<std::endl;
}

static void receive_negative(unsigned kind) {
    ReceiveEndpoint<5503> e;e.init(0x123400,0xfffffe);unsigned psn=0xfffffe;
    unsigned capacity=kind==10 ? 8191:kind==13 ? 4097:1048576;
    auto o=segmented_rq(1,psn,4096,capacity);auto wire=receive_packet(5,8193,0,psn,0x89abcdef);
    bool continuation=kind>=5 && kind<=14 || kind==20;
    if(continuation) {
        e.h.recv_owners.write(o);e.input(wire,wire.size()+12);e.h.dest.write(196);e.steps(200);e.clean();
        assert(e.packets.size()==1 && e.messages.empty());e.packets.read();e.h.destination_cmd.read();
        while(!e.h.memory.empty())e.h.memory.read();e.packet(false);e.h.length.read();
        psn=0xffffff;o.psn=psn;wire=receive_packet(5,8193,4096,psn,0x89abcdef);
    }
    if(kind==0)wire[0]=1;
    if(kind==1){wire[0]=2;}
    if(kind==2){o.length=4095;wire=receive_packet(5,4095,0,psn,0);}
    if(kind==3)wire[1]|=0x10;
    if(kind==4)o.psn++;
    if(kind==5)o.context(523,460)=2;
    if(kind==6)o.context(371,356)=18;
    if(kind==7)o.context(459,396)=0x9123456700000002ULL;
    if(kind==8)o.context(275,244)=9;
    if(kind==9)o.context(243,180)=0xfedcba9876543211ULL;
    // For cases10/13 the exact same posted capacity was retained at FIRST;
    // overflow is not disguised as an easier changed-context rejection.
    if(kind==11)wire[0]=4;
    if(kind==12){o.length=4095;wire=receive_packet(5,8191,4096,psn,0);wire[0]=1;}
    if(kind==13)wire[0]=2;
    if(kind==14){o.length=1;wire=receive_packet(5,4097,4096,psn,0x89abcdef);wire.back()=1;}
    if(kind==15)o.context(395,372)=0x800002;
    if(kind==16)o.context(243,180)=0xfffffffffffff000ULL;
    if(kind==17)o.reserved=1;
    if(kind==18)o.context(307,276)=1048577;
    if(kind==19)o.context(339,324)=3;
    if(kind==20)wire[0]=0;
    e.h.recv_owners.write(o);e.input(wire,wire.size()+12);e.h.dest.write(196);e.steps(200);
    assert(e.messages.empty() && e.packets.empty() && e.received.empty());
    if(kind==14)assert(e.h.pf && e.h.recv_data.empty());
    else assert(e.h.recv_fault && e.h.destination_cmd.empty() && e.h.memory.empty());
    std::cout<<std::dec<<"SEGMENTED_RECEIVE_NEGATIVE "<<kind<<std::endl;
}

int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    std::string mode=argc>1 ? argv[1]:"rx-send";
    if(mode=="rx-send")receive_positive<5501>(3);
    else if(mode=="rx-imm")receive_positive<5502>(5);
    else if(mode.rfind("rx-bad",0)==0)receive_negative(std::stoul(mode.substr(6)));
    else return preceding_immediate_main(argc,argv);
    return 0;
}
