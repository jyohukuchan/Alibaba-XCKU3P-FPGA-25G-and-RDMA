// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual typed WRITE parser/payload EOF/ACK/MSN/SAME PSN-table consumers.
// Protected owner/peer/RQ/memory boundaries are models, not native DMA/MAC.
#include "write_prior.cpp"

template<int I> static void drain_first(ReceiveEndpoint<I>& e,unsigned offset,unsigned psn) {
    auto w=write_owner(1,8193,offset,psn,0xfffffe,offset/4096+1);
    e.h.write_owners.write(w);auto b=write_packet(true,8193,offset,psn,0x89abcdef);
    e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);e.clean();
    assert(e.h.destination_cmd.size()==1);e.h.destination_cmd.read();
    while(!e.h.memory.empty())e.h.memory.read();e.packet(false);e.h.length.read();
    take_write_receipt(e.h,w,0);
}
static void typed_owner_negative(unsigned kind) {
    ReceiveEndpoint<5703> e;e.init(0x123400,0xfffffe);
    unsigned off=0,psn=0xfffffe;
    if(kind>=16){drain_first(e,0,psn);off=4096;psn=0xffffff;}
    if(kind>=19){drain_first(e,4096,psn);off=8192;psn=0;}
    auto w=write_owner(1,8193,off,psn,0xfffffe,off/4096+1);auto& t=w.token;
    switch(kind) {
      case 0:t(423,400)=0x800002;break;
      case 1:t(399,384)=0;break;
      case 2:t(383,320)=0;break;
      case 3:t(319,256)=0;break;
      case 4:t(255,224)=0;break;
      case 5:t(223,160)=0xfffffffffffffff0ULL;break;
      case 6:t(159,128)=4096;break;
      case 7:t(159,128)=1048577;break;
      case 8:t(103,72)=1;break;
      case 9:t(71,40)=4095;break;
      case 10:t(39,16)=0xffffff;break;
      case 11:t(15,0)=0;break;
      case 12:t(255,224)=0x81234566;break;
      case 13:t(223,160)=0xe23456789abcdef1ULL;break;
      case 14:t(159,128)=8194;break;
      case 15:t(127,104)=t(39,16)=0xffffff;break;
      case 16:t(399,384)=18;break;
      case 17:t(383,320)=0x1123456700000001ULL;break;
      case 18:t(319,256)=0x7edcba9876543211ULL;break;
    }
    if(kind>=19) {
        auto rq=write_rq(1,psn,1,0);
        if(kind==19)rq.context(371,356)=18;else rq.context(459,396)=0x1123456700000001ULL;
        assert(as02_recv_owner_valid(rq,true));e.h.recv_owners.write(rq);
    }
    e.h.write_owners.write(w);auto b=write_packet(true,8193,off,psn,0x89abcdef);
    e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);
    assert(e.h.recv_fault && e.h.destination_cmd.empty() && e.h.memory.empty() &&
        e.h.write_done.empty() && e.messages.empty() && e.packets.empty());
    std::cout<<std::dec<<"WRITE_PACKET_NEGATIVE "<<kind<<std::endl;
}
static void typed_consumer_holds() {
    ReceiveEndpoint<5704> e;e.init(0x123400,0xfffffe);
    auto w=write_owner(1,8193,0,0xfffffe,0xfffffe,1);
    auto b=write_packet(false,8193,0,0xfffffe,0);
    e.input(b,b.size()+12);e.h.dest.write(196);
    e.steps(150);e.clean();
    assert(e.h.destination_cmd.empty() && e.h.memory.empty() && e.h.write_done.empty() && e.h.headers.empty());
    e.h.write_owners.write(w);
    e.steps(150,false,false);e.clean();assert(e.h.memory.empty() && e.h.write_done.empty());
    e.steps(150,true,false);e.clean();assert(!e.h.memory.empty() && e.h.write_done.empty());
    e.h.write_table_enabled=false;e.steps(150,true,true);e.clean();
    assert(e.h.write_done.empty() && e.h.write_state_req.size()==1);
    e.h.write_join_enabled=false;e.h.write_table_enabled=true;e.steps(150);e.clean();
    assert(e.h.write_done.empty() && e.h.write_state_rsp.size()==1);
    e.h.write_join_enabled=true;e.steps(40);e.clean();
    assert(e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();
    assert(c.addr==(WRITE_VA&0xffffffffffffULL) && c.len==4096 && !c.ctl && c.host && c.pid==2);
    unsigned count=0;bool eof=false;
    while(!e.h.memory.empty()) {
        auto x=e.h.memory.read();assert(!eof && x.keep==~ap_uint<64>(0));
        for(unsigned i=0;i<64;i++,count++)assert(x.data(i*8+7,i*8)==write_byte(count));
        eof=x.last;
    }
    assert(eof && count==4096);auto ack=e.packet(false);std::vector<unsigned char> expected(16,0);
    expected[0]=17;expected[1]=0x40;put_be(expected,2,2,0xffff);put_be(expected,5,3,196);put_be(expected,9,3,0xfffffe);
    assert(ack==expected && e.h.length.read()==20);take_write_receipt(e.h,w,0);
    e.steps(40);e.clean();assert(e.h.write_done.empty() && e.h.write_owners.empty());
    std::cout<<"WRITE_PACKET_HOLD {\"pass_test\":true,\"missing_owner_blocks\":true,\"actual_payload_EOF_required\":true,"
        "\"actual_ACK_MSN_required\":true,\"actual_same_PSN_table_required\":true,\"consumer_withholding_blocks\":true,"
        "\"native_backend_MAC_CQ\":false}"<<std::endl;
}
int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    std::string mode=argc>1 ? argv[1]:"write-owned-hold";
    if(mode=="write-owned-hold")typed_consumer_holds();
    else if(mode.rfind("write-owned-bad",0)==0)typed_owner_negative(std::stoul(mode.substr(15)));
    else return preceding_write_receive_main(argc,argv);
    return 0;
}
