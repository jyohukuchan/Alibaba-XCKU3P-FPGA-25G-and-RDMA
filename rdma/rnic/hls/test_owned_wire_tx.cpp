// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual selected FNS producer functions; not a host/native/MAC/CQ model.
#include "ib_transport_protocol/owned_wire_tx.hpp"
#include <cassert>
#include <cstdlib>

ap_uint<192> context(unsigned q,ap_uint<64> epoch,ap_uint<64> seq) {
    ap_uint<192> r=0;r(15,0)=q;r(79,16)=epoch;r(143,80)=seq;return r;
}
ap_uint<248> sq_record(ibOpCode op,unsigned q,ap_uint<32> key,unsigned len) {
    ap_uint<248> r=0;r(31,0)=op;r(41,32)=q;r[42]=1;r[43]=1;r(47,44)=9;
    r(111,48)=0xfedcba9876540000ULL;r(175,112)=0x123456789abc0000ULL;
    r(207,176)=len;r(239,208)=key;r[240]=1;return r;
}
as02WireContext owner(unsigned q=7,ap_uint<64> epoch=0xfedcba9876543210ULL,
    ap_uint<64> seq=0x8765432100000001ULL) {
    as02WireContext c;c.qpn=q;c.epoch=epoch;c.sequence=seq;c.valid=true;return c;
}
as02OwnedEvent replay(bool bad_generation=false,bool marker=false) {
    as02WireContext c=owner();ap_uint<248> lease=0;lease(15,0)=1999;
    lease(79,16)=bad_generation?0:0x8877665544332211ULL;lease(95,80)=c.qpn;
    lease(119,96)=0xfffffe;lease(183,120)=c.epoch;lease(247,184)=c.sequence;
    as02OwnedEvent e(retransEvent(RC_RDMA_WRITE_ONLY,7,0xfedcba9876540000ULL,
        0x123456789abc0000ULL,65,0xffffff,1,9,0xffffffff,1,PKG_HOST),lease);
    e.marker=marker;return e;
}

void positive() {
    stream<ap_uint<248>> sq;stream<ap_uint<192>> contexts;stream<as02WireTxMeta> admitted;
    stream<as02OwnedEvent> retries;stream<as02WireAddrLen> addresses;
    stream<memCmdInternal> mem;stream<as02WireEvent> app,remote;
    stream<ackEvent> acks;stream<ap_uint<16>> connections,msn_req;
    stream<as02WireIBHMeta> ibh_meta;stream<as02WireEvent> exh_meta;
    stream<ap_uint<24>> dst;stream<stateTableEntry> states;stream<txStateReq> state_req;
    stream<as02WireRetransMeta> psns;stream<BaseTransportHeader<64>> bths;
    stream<txMsnRsp> msns;stream<ap_uint<16>> lengths;stream<txPacketInfo> infos;
    stream<as02WireContext> starts;stream<net_axis<64>> exhs;stream<as02OwnedInsert> inserts;
    ap_uint<32> af=0,lf=0,bf=0,ef=0,jf=0,retrans_count=0;
    const ap_uint<64> epoch=0xfedcba9876543210ULL,first=0x8765432100000001ULL;
    for(unsigned i=0;i<4;i++) {
        const unsigned q=i==3?0:7,len=i==2?4161:65;
        const ibOpCode op=(i==1 || i==2)?RC_RDMA_READ_REQUEST:RC_RDMA_WRITE_ONLY;
        const ap_uint<32> key=i%2?0xffffffff:0;
        const ap_uint<24> psn=i==2?0xffffff:0xabcdef+i;
        sq.write(sq_record(op,q,key,len));contexts.write(context(q,epoch,first+i));
        as02_owned_wire_admit<1>(sq,contexts,admitted,af);assert(!af && admitted.size()==1);
        as02_owned_wire_local_req_handler<1>(admitted,retries,addresses,mem,app,retrans_count,lf);
        assert(!lf && app.size()==1 && addresses.size()==1);
        if(op==RC_RDMA_READ_REQUEST)assert(mem.empty());
        else {assert(mem.size()==1);auto c=mem.read();assert(c.host==PKG_HOST && c.addr==0xfedcba9876540000ULL && c.len==65);}
        as02_owned_wire_meta_merger<1>(acks,remote,app,connections,ibh_meta,exh_meta);
        assert(connections.read()==q && ibh_meta.size()==1 && exh_meta.size()==1);
        dst.write(0xdeadbe);
        as02_owned_wire_generate_ibh<64,1>(ibh_meta,dst,states,state_req,psns,bths,bf);
        assert(!bf && state_req.size()==1 && bths.empty());
        auto req=state_req.read();assert(req.qpn==q && !req.write);
        stateTableEntry state;state.req_next_psn=psn;states.write(state);
        as02_owned_wire_generate_ibh<64,1>(ibh_meta,dst,states,state_req,psns,bths,bf);
        assert(!bf && bths.size()==1 && psns.size()==1 && state_req.size()==1);
        auto header=bths.read();assert(header.getPsn()==psn && header.getDstQP()==0xdeadbe && header.getOpCode()==op);
        auto update=state_req.read();assert(update.qpn==q && update.write);
        assert(update.psn==ap_uint<24>(psn+((len+PMTU-1)/PMTU)));
        // EXH and insert producer queues can run in either order. No late QP
        // owner lookup or FIFO-idle certificate is supplied by this bench.
        as02_owned_wire_generate_exh<64,1>(exh_meta,msns,msn_req,lengths,infos,starts,exhs,ef);
        assert(!ef && msn_req.read()==q && starts.size()==1);
        auto start=starts.read();assert(start.qpn==q && start.epoch==epoch && start.sequence==first+i);
        assert(start.valid && !start.retry && start.lease==0);
        msns.write(txMsnRsp(0xabcdef,0x13579bdf));
        for(unsigned n=0;n<8;n++)as02_owned_wire_generate_exh<64,1>(exh_meta,msns,msn_req,lengths,infos,starts,exhs,ef);
        assert(!ef && exhs.size()==2 && infos.size()==1 && lengths.size()==1);
        ap_uint<128> raw=0;auto w0=exhs.read(),w1=exhs.read();raw(63,0)=w0.data;raw(127,64)=w1.data;
        assert(!w0.last && w1.last);RdmaExHeader<64> reth;reth.setRawHeader(raw);
        assert(reth.getRemoteKey()==key && reth.getLength()==len && reth.getVirtualAddress()==0x123456789abc0000ULL);
        infos.read();lengths.read();
        as02_owned_wire_merge_retrans_request(psns,addresses,inserts,jf);
        assert(!jf && inserts.size()==1);auto in=inserts.read();
        assert(in.normal.qpn==q && in.normal.psn==psn && in.normal.opCode==op);
        assert(in.normal.localAddr==0xfedcba9876540000ULL && in.normal.remoteAddr==0x123456789abc0000ULL);
        assert(in.normal.length==len && in.normal.rkey==key && in.normal.rkey_valid && in.normal.host==PKG_HOST);
        assert(in.normal.lst==1 && in.normal.offs==9 && in.epoch==epoch && in.sequence==first+i && !in.bad && !in.marker);
    }
    assert(retrans_count==0);
}

void mismatch(unsigned which) {
    stream<as02WireRetransMeta> p;stream<as02WireAddrLen> a;stream<as02OwnedInsert> out;
    auto c=owner();auto other=c;if(which==2)other.sequence++;else other.epoch++;
    p.write(as02_wire_tag(as02WireRetransMeta(7,0xffffff,RC_RDMA_WRITE_ONLY),c));
    a.write(as02_wire_tag(as02WireAddrLen(1,2,65,1,0,0,1,PKG_HOST),other));
    ap_uint<32> fault=0;as02_owned_wire_merge_retrans_request(p,a,out,fault);
    as02_owned_wire_merge_retrans_request(p,a,out,fault);assert(fault==6 && out.empty());
    // The failed record does NOT authorize retry/free/CQ or accept more work.
    p.write(as02_wire_tag(as02WireRetransMeta(7,1,RC_RDMA_WRITE_ONLY),c));
    a.write(as02_wire_tag(as02WireAddrLen(1,2,65,1,0),c));
    as02_owned_wire_merge_retrans_request(p,a,out,fault);assert(p.size()==1 && a.size()==1 && out.empty());
}
void bad_admit(unsigned which) {
    stream<ap_uint<248>> s;stream<ap_uint<192>> c;stream<as02WireTxMeta> out;
    auto sq=sq_record(RC_RDMA_WRITE_ONLY,7,0,65);auto ctx=context(7,0xfedcba9876543210ULL,0x8765432100000001ULL);
    if(which==4)ctx[191]=1;if(which==5)ctx(15,0)=6;if(which==6)ctx(79,16)=0;if(which==7)ctx(143,80)=0;
    if(which==14)sq[247]=1;
    s.write(sq);c.write(ctx);ap_uint<32> fault=0;
    as02_owned_wire_admit<2>(s,c,out,fault);as02_owned_wire_admit<2>(s,c,out,fault);
    assert(fault==1 && out.empty());
}
void retry_case(unsigned which) {
    stream<as02WireTxMeta> sq;stream<as02OwnedEvent> retries;stream<as02WireAddrLen> addresses;
    stream<memCmdInternal> mem;stream<as02WireEvent> app;
    ap_uint<32> count=0,fault=0;auto r=replay(which==8,which==12);retries.write(r);
    as02_owned_wire_local_req_handler<2>(sq,retries,addresses,mem,app,count,fault);
    if(which==8 || which==12) {
        as02_owned_wire_local_req_handler<2>(sq,retries,addresses,mem,app,count,fault);
        assert(fault==2 && app.empty() && mem.empty() && addresses.empty() && count==0);return;
    }
    assert(!fault && count==1 && app.size()==1 && mem.size()==1 && addresses.empty());
    auto ev=app.read();assert(ev.owner.lease==r.lease && ev.owner.sequence==owner().sequence && ev.owner.epoch==owner().epoch);
    assert(ev.owner.retry && ev.owner.valid && ev.validPsn && ev.psn==0xffffff);
    assert(ev.rkey==0xffffffff && ev.rkey_valid);auto command=mem.read();assert(command.host==PKG_HOST && command.offs==9);
    stream<ackEvent> acks;stream<as02WireEvent> remote,apps,exh_meta;
    stream<ap_uint<16>> connections;stream<as02WireIBHMeta> ibh_meta;apps.write(ev);
    as02_owned_wire_meta_merger<2>(acks,remote,apps,connections,ibh_meta,exh_meta);
    auto ibh_saved=ibh_meta.read();auto exh_saved=exh_meta.read();
    assert(ibh_saved.owner.lease==r.lease && exh_saved.owner.lease==r.lease);
    ibh_meta.write(ibh_saved);exh_meta.write(exh_saved);
    stream<ap_uint<24>> dst;stream<stateTableEntry> states;stream<txStateReq> req;
    stream<as02WireRetransMeta> psns;stream<BaseTransportHeader<64>> headers;ap_uint<32> bf=0;
    dst.write(0x123456);as02_owned_wire_generate_ibh<64,2>(ibh_meta,dst,states,req,psns,headers,bf);
    assert(!bf && headers.read().getPsn()==0xffffff && req.empty() && psns.empty());
    stream<txMsnRsp> msns;stream<ap_uint<16>> msn_req,lengths;stream<txPacketInfo> infos;
    stream<as02WireContext> starts;stream<net_axis<64>> output;ap_uint<32> ef=0;
    as02_owned_wire_generate_exh<64,2>(exh_meta,msns,msn_req,lengths,infos,starts,output,ef);
    assert(!ef && starts.size()==1 && starts.read().lease==r.lease);
}
void zero_read() {
    stream<as02WireTxMeta> sq;stream<as02OwnedEvent> retries;stream<as02WireAddrLen> addresses;
    stream<memCmdInternal> mem;stream<as02WireEvent> app;ap_uint<32> count=0,fault=0;
    as02WireTxMeta m;m.op_code=RC_RDMA_READ_REQUEST;m.qpn=7;m.params=0;m.owner=owner();sq.write(m);
    as02_owned_wire_local_req_handler<3>(sq,retries,addresses,mem,app,count,fault);
    as02_owned_wire_local_req_handler<3>(sq,retries,addresses,mem,app,count,fault);
    assert(fault==3 && addresses.empty() && mem.empty() && app.empty());
}
void pairing() {
    stream<ap_uint<248>> sq;stream<ap_uint<192>> contexts;stream<as02WireTxMeta> out;ap_uint<32> fault=0;
    sq.write(sq_record(RC_RDMA_WRITE_ONLY,7,0,65));as02_owned_wire_admit<3>(sq,contexts,out,fault);
    assert(!fault && out.empty() && sq.size()==1);auto c=owner();contexts.write(context(7,c.epoch,c.sequence));
    as02_owned_wire_admit<3>(sq,contexts,out,fault);assert(!fault && out.size()==1 && sq.empty() && contexts.empty());
}
void remote_response() {
    stream<ackEvent> acks;stream<as02WireEvent> remote,app,exh;
    stream<ap_uint<16>> connections;stream<as02WireIBHMeta> ibh;
    acks.write(ackEvent(7,0xabcdef,false));
    as02_owned_wire_meta_merger<3>(acks,remote,app,connections,ibh,exh);
    auto ibh_saved=ibh.read();auto exh_saved=exh.read();
    assert(connections.read()==7 && !ibh_saved.owner.valid && !exh_saved.owner.valid);
    ibh.write(ibh_saved);exh.write(exh_saved);
    stream<ap_uint<24>> dst;stream<stateTableEntry> states;stream<txStateReq> req;
    stream<as02WireRetransMeta> psns;stream<BaseTransportHeader<64>> headers;ap_uint<32> fault=0;
    dst.write(0x123456);as02_owned_wire_generate_ibh<64,3>(ibh,dst,states,req,psns,headers,fault);
    assert(!fault && headers.read().getPsn()==0xabcdef && req.empty() && psns.empty());
}
template<int W,int BITS>
void header_word_equivalence() {
    // Exhaust ALL65536 original index values, not only the ordinary0/1 path.
    // Old implementation is compiled from the unchanged licensed packet.hpp.
    for(unsigned index=0;index<65536;index++) {
        packetHeader<W,BITS> original,candidate;
        ap_uint<BITS> content=0;ap_uint<W> before=0;
        for(unsigned b=0;b<BITS;b++)content[b]=((b*7+index)%17)<8;
        for(unsigned b=0;b<W;b++)before[b]=((b*13+index)%19)<9;
        original.header=content;original.idx=index;original.ready=index%2;
        candidate=original;ap_uint<W> old_word=before,new_word=before;
        auto old_remaining=original.consumeWord(old_word);
        auto new_remaining=as02_owned_wire_consume_word<W,BITS>(candidate,new_word);
        assert(old_word==new_word && old_remaining==new_remaining);
        assert(original.idx==candidate.idx && original.ready==candidate.ready && original.header==candidate.header);
    }
}
int main(int argc,char**argv) {
    assert(argc==2);unsigned which=std::strtoul(argv[1],nullptr,10);
    if(which==1)positive();else if(which==2 || which==3)mismatch(which);
    else if((which>=4 && which<=7) || which==14)bad_admit(which);
    else if(which==8 || which==9 || which==12)retry_case(which);
    else if(which==10)zero_read();else if(which==11)pairing();else if(which==13)remote_response();
    else if(which==15) {
        header_word_equivalence<32,128>();header_word_equivalence<64,128>();header_word_equivalence<128,128>();
        header_word_equivalence<256,128>();header_word_equivalence<512,128>();
    } else if(which==16) {
        header_word_equivalence<32,32>();header_word_equivalence<64,32>();header_word_equivalence<128,32>();
        header_word_equivalence<256,32>();header_word_equivalence<512,32>();
    } else return 2;
    std::cout<<std::dec<<"{\"pass_test\":true,\"case\":"<<which<<",\"actual_FNS_TX_producers\":true,\"native_CQ\":false,\"whole_core_drain\":false}"<<std::endl;
}
