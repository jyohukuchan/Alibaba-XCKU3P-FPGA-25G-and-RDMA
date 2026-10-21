// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual HLS parser/data/ACK/MSN/PSN and late-RQ message join. Peer, RQ,
// memory endpoints modeled; NOT native remote-MR/DMA/MAC/CQ/physical proof.
#include "receive_prior.cpp"

static const unsigned long long WRITE_VA=0xe23456789abcdef0ULL;
static as02RecvOwner write_rq(unsigned seq,unsigned psn,unsigned count,unsigned capacity) {
    as02RecvOwner o;o.context=owner(seq,3);o.context(339,324)=4;o.context(307,276)=capacity;
    if(!capacity)o.context(275,116)=0;
    else o.context(243,180)=0xa234567890001000ULL;
    o.length=count;o.psn=psn;assert(as02_recv_owner_valid(o,true));return o;
}
static unsigned char write_byte(unsigned offset){return ((offset*113)^(offset>>8)^0xb7)&255;}
static std::vector<unsigned char> write_packet(bool imm,unsigned total,unsigned offset,unsigned psn,unsigned value) {
    unsigned count=std::min(4096U,total-offset);bool first=offset==0,last=offset+count==total;
    unsigned opcode=first ? 6:last ? (imm ? 9:8):7,header=first ? 16:last && imm ? 4:0,pad=(-count)&3;
    std::vector<unsigned char> b(12+header+count+pad,0);
    b[0]=opcode;b[1]=0x40|(pad<<4);put_be(b,2,2,0xffff);put_be(b,5,3,2);b[8]=0x80;put_be(b,9,3,psn);
    if(first){put_be(b,12,8,WRITE_VA);put_be(b,20,4,0x81234567);put_be(b,24,4,total);}
    if(last && imm)put_be(b,12,4,value);
    for(unsigned i=0;i<count;i++)b[12+header+i]=write_byte(offset+i);
    return b;
}
template<int I> static void write_positive(bool imm) {
    ReceiveEndpoint<I> e;e.init(0x123400,0xfffffe);unsigned psn=0xfffffe,seq=0,packets=0;
    for(unsigned total:{4097U,8192U,8193U,12289U,65537U,1048576U}) {
        unsigned initial=psn,value=seq==0 ? 0:seq==1 ? 0xffffffffU:0x89abcdefU+seq;seq++;
        unsigned last_count=((total-1)%4096)+1,capacity=seq==1 || seq==4 ? 0:seq==2 ? 1:seq==3 ? 17:seq==5 ? 8194:1048576;
        auto rq=write_rq(seq,(psn+(total-1)/4096)&0xffffff,last_count,capacity);
        if(imm && seq!=3)e.h.recv_owners.write(rq);
        for(unsigned offset=0;offset<total;offset+=4096,packets++) {
            unsigned count=std::min(4096U,total-offset);bool last=offset+count==total;
            auto b=write_packet(imm,total,offset,psn,value);e.input(b,b.size()+12);e.h.dest.write(196);
            if(imm && last && seq==3) {
                e.steps(150);e.clean();assert(e.h.destination_cmd.empty() && e.h.memory.empty() &&
                    e.packets.empty() && e.messages.empty() && e.h.headers.empty());
                e.h.recv_owners.write(rq);
            }
            if(imm && last) {
                e.steps(100,false,false);e.clean();assert(e.h.memory.empty() && e.packets.empty() && e.messages.empty());
                e.steps(100,true,false);e.clean();assert(e.packets.empty() && e.messages.empty());
                e.steps(100,true,true,false);e.clean();assert(e.packets.empty() && e.messages.empty() && !e.h.recv_state_req.empty());
                e.steps(100,true,true,true,false);e.clean();assert(e.received.size()==1 && e.packets.empty() && e.messages.empty());
            } else {e.steps(200);e.clean();}
            assert(e.h.recv_owners.size()==(imm && !last && seq!=3 ? 1U:0U));
            assert(e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();
            unsigned long long address=WRITE_VA+offset;
            assert(c.origin==1 && c.host==1 && c.addr==(address&0xffffffffffffULL) &&
                c.tdst==((address>>48)&15) && c.strm==((address>>52)&1) && !c.sync &&
                c.len==((count+3)&~3U) && bool(c.ctl)==last && c.pid==2 && c.vfid==0);
            std::vector<unsigned char> data;bool eof=false;
            while(!e.h.memory.empty()) {
                auto w=e.h.memory.read();assert(!eof);unsigned valid=0;
                for(unsigned j=0;j<64;j++)if(w.keep[j]){valid++;data.push_back(unsigned(w.data(j*8+7,j*8)));}
                assert(valid && w.keep==((ap_uint<65>(1)<<valid)-1));eof=w.last;
            }
            assert(eof && data.size()==((count+3)&~3U));
            for(unsigned j=0;j<data.size();j++)assert(data[j]==(j<count ? write_byte(offset+j):0));
            std::cout<<std::dec<<"WRITE_RECEIVE_DATA "<<imm<<" "<<total<<" "<<offset<<" ";receive_hex(data);
            auto ack=e.packet(false);std::vector<unsigned char> expected(16,0);
            expected[0]=17;expected[1]=0x40;put_be(expected,2,2,0xffff);put_be(expected,5,3,196);
            put_be(expected,9,3,psn);put_be(expected,13,3,last ? seq:seq-1);
            assert(ack==expected && e.h.length.size()==1 && e.h.length.read()==20);
            std::cout<<std::dec<<"WRITE_RECEIVE_ACK "<<imm<<" "<<total<<" "<<offset<<" ";receive_hex(ack);
            e.steps(20);e.clean();
            if(imm && last) {
                assert(e.packets.size()==1);auto p=e.packets.read();
                assert(!p.error && p.proof.owner.context==rq.context && p.proof.owner.length==count &&
                    p.proof.owner.psn==psn && p.proof.msn==seq && p.proof.flags==3 && p.proof.immediate==value);
                assert(e.messages.size()==1);auto m=e.messages.read();
                assert(m.context==rq.context && m.bytes==total && m.first_psn==initial && m.last_psn==psn &&
                    m.msn==seq && m.flags==3 && m.immediate==value && !m.error);
                std::cout<<std::dec<<"WRITE_RECEIVE_MESSAGE "<<total<<" "<<initial<<" "<<psn<<" "<<seq
                    <<" "<<value<<" "<<capacity<<std::endl;
            } else assert(e.received.empty() && e.packets.empty() && e.messages.empty());
            e.steps(8);assert(e.h.write_notify.empty() && e.messages.empty() && e.packets.empty());
            psn=(psn+1)&0xffffff;
        }
    }
    std::cout<<std::dec<<"WRITE_RECEIVE_HLS {\"pass_test\":true,\"immediate\":"<<imm
        <<",\"whole_messages\":6,\"packets\":"<<packets<<",\"max_bytes\":1048576,\"late_RQ_only_on_LAST\":true,"
        "\"distinct_RETH_target\":true,\"actual_bytes_not_RQ_capacity\":true,\"MSN_only_on_LAST\":true,"
        "\"PSN_wrap\":true,\"native_MR_DMA_MAC_CQ_Linux_physical\":false}"<<std::endl;
}
static void write_negative(unsigned kind) {
    ReceiveEndpoint<5603> e;e.init(0x123400,0xfffffe);unsigned psn=0xfffffe;
    auto first=write_packet(true,8193,0,psn,0x89abcdef);
    auto b=first;auto rq=write_rq(1,psn,4096,0);
    bool continuation=kind>=8 && kind<=17;
    if(continuation) {
        e.input(first,first.size()+12);e.h.dest.write(196);e.steps(220);e.clean();
        assert(e.h.destination_cmd.size()==1 && e.h.recv_owners.empty() && e.packets.empty() && e.messages.empty());
        e.h.destination_cmd.read();while(!e.h.memory.empty())e.h.memory.read();e.packet(false);e.h.length.read();
        psn=0xffffff;b=write_packet(true,4097,4096,psn,0x89abcdef);rq=write_rq(1,psn,1,0);
        if(kind!=13 && kind!=14 && kind!=15 && kind!=16) {
            // Complete a genuine MIDDLE first so LAST has exactly one byte.
            auto middle=write_packet(true,8193,4096,psn,0x89abcdef);
            e.input(middle,middle.size()+12);e.h.dest.write(196);e.steps(220);e.clean();
            e.h.destination_cmd.read();while(!e.h.memory.empty())e.h.memory.read();e.packet(false);e.h.length.read();
            psn=0;b=write_packet(true,8193,8192,psn,0x89abcdef);rq=write_rq(1,psn,1,0);
        }
    }
    if(kind==0)b[0]=7;
    if(kind==1)b[0]=9;
    if(kind==2)put_be(b,24,4,4096);
    if(kind==3)put_be(b,24,4,1048577);
    if(kind==4)put_be(b,20,4,0);
    if(kind==5)put_be(b,12,8,~0ULL-4095);
    if(kind==6)b[1]|=0x10;
    if(kind==7)b=write_packet(true,4095,0,psn,0);
    if(kind==8)rq.psn++;
    if(kind==9)rq.context(395,372)=0x800002;
    if(kind==10)rq.reserved=1;
    if(kind==11)rq.context(339,324)=3;
    if(kind==12)rq.length=2;
    if(kind==14)b[0]=4;
    if(kind==15)b=write_packet(true,8193,0,psn,0);
    if(kind==16){b=write_packet(true,8191,4096,psn,0);b[0]=7;}
    if(kind==17)b.back()=1;
    if(kind==18)put_be(b,5,3,0x800002);
    if(kind>=8 && kind<=13 || kind==17)e.h.recv_owners.write(rq);
    e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);
    assert(e.messages.empty() && e.packets.empty() && e.received.empty());
    if(kind==17)assert(e.h.pf && e.h.recv_data.empty());
    else assert(e.h.recv_fault && e.h.destination_cmd.empty() && e.h.memory.empty());
    std::cout<<std::dec<<"WRITE_RECEIVE_NEGATIVE "<<kind<<std::endl;
}
int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    std::string mode=argc>1 ? argv[1]:"write-rx-imm";
    if(mode=="write-rx")write_positive<5601>(false);
    else if(mode=="write-rx-imm")write_positive<5602>(true);
    else if(mode.rfind("write-rx-bad",0)==0)write_negative(std::stoul(mode.substr(12)));
    else return preceding_receive_main(argc,argv);
    return 0;
}
