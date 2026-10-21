// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual parser/retire checkpoint/MSN/PSN/clear consumers. Native/backend/
// fresh MAC proof and management inputs are MODELS; not QP/global drain.
#include "abort_prior.cpp"

static as02WriteAbortOwner abort_request(as02WriteOwner p,unsigned expected,unsigned msn,
    unsigned tag=0x6001,unsigned flags=15,unsigned serial=1,unsigned syndrome=0x62) {
    as02WriteAbortOwner o;auto c=control_owner(syndrome,expected,expected,serial);
    o.token=p.token;o.token(903,424)=c.token;o.token(927,904)=msn;
    o.token(943,928)=tag;o.token(951,944)=flags;return o;
}
template<int I> static as02WriteOwner abort_write(ReceiveEndpoint<I>& e,unsigned seq,unsigned total,
    unsigned off,unsigned psn,unsigned first,unsigned tag,unsigned msn,unsigned q=2) {
    auto w=write_owner(seq,total,off,psn,first,tag);w.token(423,400)=q;
    auto b=write_packet(false,total,off,psn,0);put_be(b,5,3,q);
    e.h.write_owners.write(w);e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);e.clean();
    assert(!e.h.write_abort_fault && e.h.destination_cmd.size()==1);auto c=e.h.destination_cmd.read();
    const unsigned payload=std::min(4096U,total-off),stored=(payload+3)&~3U;
    assert(c.len==stored && c.addr==((WRITE_VA+off)&0xffffffffffffULL) && c.host && c.pid==q);
    unsigned bytes=0;bool last=false;
    while(!e.h.memory.empty()) {auto x=e.h.memory.read();assert(!last);last=x.last;
        for(unsigned j=0;j<64;j++)if(x.keep[j]) {
            assert(x.data(j*8+7,j*8)==(bytes<payload ? write_byte(off+bytes):0));bytes++;
        }}
    assert(last && bytes==stored);
    auto ack=e.packet(false);std::vector<unsigned char> expected(16,0);
    expected[0]=17;expected[1]=0x40;put_be(expected,2,2,0xffff);put_be(expected,5,3,196);
    put_be(expected,9,3,psn);put_be(expected,13,3,msn);
    assert(ack==expected && e.h.length.read()==20);
    take_write_receipt(e.h,w,msn);return w;
}
template<int I> static void abort_no_grants(ReceiveEndpoint<I>& e) {
    e.clean();assert(!e.h.write_abort_fault && e.h.destination_cmd.empty() && e.h.memory.empty() &&
        e.h.write_done.empty() && e.h.headers.empty() && e.h.control_done.empty() &&
        e.packets.empty() && e.messages.empty() && e.received.empty() && e.h.done.empty());
}
template<int I> static void abort_receipt(ReceiveEndpoint<I>& e,as02WriteAbortOwner o,
    unsigned msn,unsigned expected,const std::string& mode) {
    e.steps(200);abort_no_grants(e);assert(e.h.write_abort_done.size()==1);
    e.steps(71);abort_no_grants(e);assert(e.h.write_abort_done.size()==1);
    auto d=e.h.write_abort_done.read();assert(!d.error && d.owner.token==o.token && d.msn==msn);
    control_query_psn(e,expected);assert(!e.h.write_abort_fault);
    ap_uint<992> packed=d.owner.token;packed(983,960)=d.msn;packed(991,984)=d.error;
    std::cout<<std::dec<<"WRITE_ABORT_DONE "<<mode<<" "<<msn<<" "<<expected<<" "<<o.token.to_string(16,false)
        <<" "<<packed.to_string(16,false)<<std::endl;
}
static void abort_positive(const std::string& mode) {
    ReceiveEndpoint<5901> e;e.init(0x123400,0xfffffe);
    bool empty=mode=="abort-empty" || mode=="abort-empty-after-last";
    unsigned next=0xffffff,msn=0;as02WriteOwner w;
    if(mode=="abort-empty")next=0xfffffe;
    else if(mode=="abort-empty-after-last") {
        abort_write(e,1,4097,0,0xfffffe,0xfffffe,1,0);
        abort_write(e,1,4097,4096,0xffffff,0xfffffe,2,1);next=0;msn=1;
    } else if(mode=="abort-fence-hold") {
        w=write_owner(1,8193,0,0xfffffe,0xfffffe,1);auto b=write_packet(false,8193,0,0xfffffe,0);
        e.h.write_owners.write(w);e.input(b,b.size()+12);e.h.dest.write(196);e.steps(150,false);e.clean();
        assert(e.h.write_done.empty() && e.h.memory.empty());
    } else {
        w=abort_write(e,1,8193,0,0xfffffe,0xfffffe,1,0);
        if(mode=="abort-partial-two") {w=abort_write(e,1,8193,4096,0xffffff,0xfffffe,2,0);next=0;}
    }
    if(mode=="abort-perqp") {
        e.h.qp_state.write(ifStateReq(3,READY_SEND,0x123400,0x123456));e.h.msn_init.write(ifMsnReq(3,0x81234567));e.steps(2100);
        abort_write(e,1,4097,0,0x123456,0x123456,1,0,3);
    }
    unsigned syndrome=mode=="abort-partial-one" ? 0x61:mode=="abort-empty" ? 0x63:0x62;
    auto o=abort_request(w,next,msn,empty ? 0:mode=="abort-partial-two" ? 0x6002:0x6001,empty ? 0:15,1,syndrome);
    assert(as02_write_abort_valid(o));e.h.write_abort_owners.write(o);
    if(mode=="abort-fence-hold") {
        e.steps(160,false);e.clean();assert(!e.h.write_abort_fault && e.h.write_abort_done.empty() && e.h.write_done.empty());
        e.steps(240);e.clean();assert(!e.h.write_abort_fault && e.h.write_done.size()==1);
        assert(e.h.destination_cmd.size()==1);e.h.destination_cmd.read();unsigned bytes=0;bool last=false;
        while(!e.h.memory.empty()){auto x=e.h.memory.read();assert(!last);last=x.last;
            for(unsigned j=0;j<64;j++)if(x.keep[j])assert(x.data(j*8+7,j*8)==write_byte(bytes++));}
        assert(last && bytes==4096);e.packet(false);assert(e.h.length.read()==20);take_write_receipt(e.h,w,0);
    }
    if(mode=="abort-table-hold") {
        e.steps(120,true,true,false);abort_no_grants(e);
        assert(e.h.write_abort_done.empty() && e.h.write_abort_state_req.size()==1);
    }
    if(mode=="abort-msn-hold") {
        e.h.atomic_msn_table_enabled=false;e.steps(120);abort_no_grants(e);
        assert(e.h.write_abort_done.empty() && e.h.msn_update.size()==1);e.h.atomic_msn_table_enabled=true;
    }
    abort_receipt(e,o,msn,next,mode);
    if(mode=="abort-reinit") {
        // Actual QPI/MSN management initialization, NOT permission to resume a
        // fatal native QP without its missing native quarantine/close protocol.
        e.init(0x123400,next);
        abort_write(e,2,4097,0,next,next,3,0);
        abort_write(e,2,4097,4096,(next+1)&0xffffff,next,4,1);control_query_psn(e,(next+2)&0xffffff);
    }
    if(mode=="abort-perqp") {
        abort_write(e,1,4097,4096,0x123457,0x123456,2,1,3);
        e.h.write_state_req.write(3);e.steps(12);assert(e.h.write_state_rsp.size()==1);
        auto s=e.h.write_state_rsp.read();assert(s(55,48)==0 && s(23,0)==3 && s(47,24)==0x123458);
    }
    abort_no_grants(e);assert(e.h.write_abort_done.empty());
    std::cout<<"WRITE_ABORT_HLS {\"pass_test\":true,\"owner_bits\":960,\"receipt_bits\":992,"
        "\"actual_retire_checkpoint_and_same_tables\":true,\"actual_selected_state_clear_verified\":true,"
        "\"not_QP_global_or_native_DMA_drain\":true}"<<std::endl;
}
static void abort_bad(unsigned kind) {
    ReceiveEndpoint<5902> e;e.init(0x123400,0xfffffe);unsigned psn=0xfffffe,first=psn,msn=0,seq=1;
    if(kind==23) {
        abort_write(e,1,4097,0,psn,first,1,0);abort_write(e,1,4097,4096,0xffffff,first,2,1);
        first=psn=0;msn=1;seq=2;
    }
    auto w=abort_write(e,seq,8193,0,psn,first,kind==23 ? 3:1,msn);auto o=abort_request(w,(psn+1)&0xffffff,msn);
    auto& t=o.token;
    switch(kind) {
     case 0:t(959,952)=1;break;
     case 1:t(951,944)=1;break;
     case 2:t(943,928)=0;break;
     case 3:t(943,928)=0x4001;break;
     case 4:t(943,928)=0x6000;break;
     case 5:t(899,892)=0x60;break;
     case 6:t(843,780)=0;break;
     case 7:t(447,424)=0x800002;break;
     case 8:t(463,448)=0;break;
     case 9:t(527,464)=0;break;
     case 10:t(591,528)=0;break;
     case 11:t[256]=!t[256];break;
     case 12:t(15,0)=19;break;
     case 13:t(399,384)=18;break;
     case 14:t(103,72)=4096;break;
     case 15:t(927,904)=msn+1;break;
     case 16:t(891,868)=(psn+2)&0xffffff;t(867,844)=(psn+2)&0xffffff;break;
     case 17:t(951,944)=0;break;
     case 18:t(951,944)=0;t(943,928)=0;t(423,0)=0;assert(as02_write_abort_valid(o));break;
     case 19:t[224]=!t[224];break;
     case 20:t[160]=!t[160];break;
     case 21:t(319,256)=0;break;
     case 22:t(951,944)=0;t(423,0)=0;break;
     case 23:e.h.msn_init.write(ifMsnReq(2,0x81234567));e.steps(40);break;
     default:assert(false);
    }
    e.h.write_abort_owners.write(o);e.steps(220);e.clean();
    assert(e.h.write_abort_fault && e.h.write_abort_done.empty() && e.h.destination_cmd.empty() && e.h.memory.empty());
    e.h.write_abort_owners.write(abort_request(w,(psn+1)&0xffffff,msn,0x6001,15,2));e.steps(40);
    assert(e.h.write_abort_fault && e.h.write_abort_owners.size()==1 && e.h.write_abort_done.empty());
    std::cout<<std::dec<<"WRITE_ABORT_NEGATIVE "<<kind<<std::endl;
}
static void abort_replay() {
    ReceiveEndpoint<5903> e;e.init(0x123400,0xfffffe);
    auto w=abort_write(e,1,8193,0,0xfffffe,0xfffffe,1,0);auto o=abort_request(w,0xffffff,0);
    e.h.write_abort_owners.write(o);e.steps(240);assert(e.h.write_abort_done.size()==1);e.h.write_abort_done.read();
    e.init(0x123400,0xffffff);w=abort_write(e,2,8193,0,0xffffff,0xffffff,2,0);
    o=abort_request(w,0,0);assert(as02_write_abort_valid(o));e.h.write_abort_owners.write(o);e.steps(240);
    assert(e.h.write_abort_fault && e.h.write_abort_done.empty());
    std::cout<<"WRITE_ABORT_REPLAY {\"pass_test\":true,\"serial_survives_QPI_init\":true}"<<std::endl;
}
static void abort_wrong_msn() {
    ReceiveEndpoint<5904> e;e.init(0x123400,0xfffffe);
    abort_write(e,1,4097,0,0xfffffe,0xfffffe,1,0);abort_write(e,1,4097,4096,0xffffff,0xfffffe,2,1);
    as02WriteOwner none;auto o=abort_request(none,0,0,0,0);assert(as02_write_abort_valid(o));
    e.h.write_abort_owners.write(o);e.steps(200);assert(e.h.write_abort_fault && e.h.write_abort_done.empty());
    std::cout<<"WRITE_ABORT_MSN_NEGATIVE {\"pass_test\":true,\"actual_MSN_read_required\":true}"<<std::endl;
}
int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    std::string mode=argc>1 ? argv[1]:"abort-partial-one";
    if(mode.rfind("abort-bad",0)==0)abort_bad(std::stoul(mode.substr(9)));
    else if(mode=="abort-replay")abort_replay();
    else if(mode=="abort-msn-wrong")abort_wrong_msn();
    else if(mode.rfind("abort-",0)==0)abort_positive(mode);
    else return preceding_control_main(argc,argv);
    return 0;
}
