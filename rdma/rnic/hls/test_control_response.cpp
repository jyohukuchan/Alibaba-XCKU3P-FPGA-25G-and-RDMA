// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual control merger/ACK/MSN consumers; privileged native input modeled.
// No native MR/DMA/MAC/CQ, QP-error teardown or physical peer claim.
#include "control_prior.cpp"

static as02ControlOwner control_owner(unsigned syndrome,unsigned received,unsigned response,unsigned serial=1) {
    as02ControlOwner o;auto& t=o.token;t=0;
    t(23,0)=2;t(39,24)=17;t(103,40)=0x9123456700000001ULL;
    t(167,104)=0xfedcba9889abcdefULL;t(191,168)=196;
    t(223,192)=0xc0a81f01;t(255,224)=0xc0a81f02;
    t(303,256)=0xb8830367c5d0ULL;t(351,304)=0x8af3fbb97531ULL;t(355,352)=14;
    t(419,356)=0xa123456700000000ULL+serial;
    t(443,420)=response;t(467,444)=received;t(475,468)=syndrome;
    return o;
}
template<int I> static void control_query_psn(ReceiveEndpoint<I>& e,unsigned expected) {
    e.h.write_state_req.write(2);e.steps(12);e.clean();
    assert(e.h.write_state_rsp.size()==1);auto s=e.h.write_state_rsp.read();
    assert(s(55,48)==0 && s(47,24)==expected && s(23,0)==2);
}
static void control_headers() {
    ReceiveEndpoint<5801> e;e.init(0x123400,0xfffffe);
    // Establish actual NONZERO MSN1 and wrapped resp_epsn0 with a genuine
    // complete4097-byte WRITE through existing payload/ACK/state consumers.
    for(unsigned off:{0U,4096U}) {
        unsigned psn=(0xfffffe + off/4096)&0xffffff,n=off ? 1:4096,msn=off ? 1:0;
        auto w=write_owner(1,4097,off,psn,0xfffffe,off/4096+1);
        e.h.write_owners.write(w);auto b=write_packet(false,4097,off,psn,0);
        e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);e.clean();
        assert(e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();assert(c.len==((n+3)&~3U));
        unsigned bytes=0;bool last=false;
        while(!e.h.memory.empty()) {auto x=e.h.memory.read();assert(!last);last=x.last;for(unsigned j=0;j<64;j++)if(x.keep[j])bytes++;}
        assert(last && bytes==((n+3)&~3U));e.packet(false);e.h.length.read();take_write_receipt(e.h,w,msn);
    }
    control_query_psn(e,0);unsigned serial=0;
    for(unsigned syndrome:{0x1fU,0x60U,0x61U,0x62U,0x63U}) {
        unsigned received=syndrome==0x1f ? 0xfffffe:syndrome==0x60 ? 5:0;
        unsigned response=syndrome==0x1f ? 0xffffff:0;
        auto o=control_owner(syndrome,received,response,++serial);assert(as02_control_owner_valid(o));
        e.control_owners.write(o);e.h.dest.write(196);
        e.steps(100,true,false);e.clean();assert(!e.control_fault && e.h.control_done.empty() && e.h.exh_words.empty());
        e.steps(100);e.clean();assert(!e.control_fault && e.h.control_done.size()==1);
        // Leaving the real receipt unconsumed cannot turn it into payload,
        // RQ, command, request-WR or WRITE execution completion.
        e.steps(71);e.clean();assert(e.h.control_done.size()==1 && e.h.destination_cmd.empty() && e.h.memory.empty() &&
            e.h.write_done.empty() && e.packets.empty() && e.messages.empty() && e.received.empty() && e.h.done.empty());
        auto d=e.h.control_done.read();assert(!d.error && d.owner.token==o.token && d.msn==1);
        auto ack=e.packet(false);std::vector<unsigned char> expected(16,0);
        expected[0]=17;expected[1]=0x40;put_be(expected,2,2,0xffff);put_be(expected,5,3,196);
        put_be(expected,9,3,response);expected[12]=syndrome;put_be(expected,13,3,1);
        assert(ack==expected && e.h.length.read()==20);control_query_psn(e,0);
        std::cout<<std::dec<<"CONTROL_WIRE "<<syndrome<<" "<<received<<" "<<response<<" "<<serial<<" 1 "
            <<o.token.to_string(16,false)<<" ";receive_hex(ack);
    }
    std::cout<<"CONTROL_RESPONSE_HLS {\"pass_test\":true,\"events\":5,\"owner_bits\":480,\"receipt_bits\":512,"
        "\"actual_MSN\":1,\"same_actual_PSN_table_unchanged\":true,\"actual_ACK_consumer_required\":true,"
        "\"no_payload_RQ_DMA_CQ_completion\":true,\"native_or_MAC_or_physical\":false}"<<std::endl;
}
static void control_priority() {
    hls::stream<ackEvent> exh,ibh,out;hls::stream<as02RnrEvent> rnr;hls::stream<as02ControlOwner> control;
    ap_uint<1> rf=0,cf=0;exh.write(ackEvent(5,11,false));ibh.write(ackEvent(6,12,false));
    as02RnrEvent r;r.qpn=2;r.psn=13;rnr.write(r);auto o=control_owner(0x60,5,0);control.write(o);
    for(unsigned i=0;i<4;i++) {
        as02_native_control_merger<5802>(exh,ibh,rnr,control,out,rf,cf);assert(!rf && !cf && out.size()==1);
        auto a=out.read();assert(a.qpn==(i==0 ? 5:i==1 ? 6:2) && a.psn==(i==0 ? 11:i==1 ? 12:i==2 ? 13:0));
        assert(bool(a.control_owned)==(i==3));if(i==3)assert(a.control_owner.token==o.token && a.syndrome==0x60);
        if(i==2)assert(a.syndrome_valid && a.syndrome==0x20);
    }
    assert(exh.empty() && ibh.empty() && rnr.empty() && control.empty());
    std::cout<<"CONTROL_PRIORITY {\"pass_test\":true,\"old_ACK_RNR_priority_retained\":true,\"full_control_identity\":true}"<<std::endl;
}
static void control_bad(unsigned kind) {
    ReceiveEndpoint<5803> e;e.init(0x123400,0xfffffe);auto o=control_owner(0x60,5,0);auto& t=o.token;
    switch(kind) {
      case 0:t(23,0)=0x800002;break;
      case 1:t(39,24)=0;break;
      case 2:t(103,40)=0;break;
      case 3:t(167,104)=0;break;
      case 4:t(419,356)=0;break;
      case 5:t(479,476)=1;break;
      case 6:t(475,468)=0x64;break;
      case 7:t(467,444)=0;break;
      case 8:t(467,444)=0x800000;break;
      case 9:t(475,468)=0x1f;t(467,444)=1;break;
      case 10:t(475,468)=0x1f;t(467,444)=0x800001;break;
      case 11:t(475,468)=0x61;break;
      case 12:t(475,468)=0x20;break;
      case 13:t(475,468)=0;break;
      case 14:t(475,468)=0x40;break;
      default:assert(false);
    }
    assert(!as02_control_owner_valid(o));e.control_owners.write(o);e.h.dest.write(196);e.steps(40);
    assert(e.control_fault && !e.rnr_fault && e.h.headers.empty() && e.h.control_done.empty() &&
        e.h.destination_cmd.empty() && e.h.memory.empty() && e.h.write_done.empty());
    e.control_owners.write(control_owner(0x60,5,0));e.steps(12);
    assert(e.control_fault && e.control_owners.size()==1 && e.h.headers.empty() && e.h.control_done.empty());
    std::cout<<std::dec<<"CONTROL_NEGATIVE "<<kind<<std::endl;
}
static void control_rnr_bad() {
    hls::stream<ackEvent> exh,ibh,out;hls::stream<as02RnrEvent> rnr;hls::stream<as02ControlOwner> control;
    ap_uint<1> rf=0,cf=0;as02RnrEvent r;r.qpn=2;r.psn=3;r.syndrome=0x60;rnr.write(r);
    as02_native_control_merger<5804>(exh,ibh,rnr,control,out,rf,cf);assert(rf && !cf && out.empty());
    control.write(control_owner(0x60,5,0));as02_native_control_merger<5804>(exh,ibh,rnr,control,out,rf,cf);
    assert(rf && !cf && control.size()==1 && out.empty());
    std::cout<<"CONTROL_RNR_NEGATIVE {\"pass_test\":true,\"old_RNR_only_syndrome20\":true,\"sticky_quarantine\":true}"<<std::endl;
}
int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    std::string mode=argc>1 ? argv[1]:"control-headers";
    if(mode=="control-headers")control_headers();
    else if(mode=="control-priority")control_priority();
    else if(mode=="control-rnr-bad")control_rnr_bad();
    else if(mode.rfind("control-bad",0)==0)control_bad(std::stoul(mode.substr(11)));
    else return preceding_write_owned_main(argc,argv);
    return 0;
}
