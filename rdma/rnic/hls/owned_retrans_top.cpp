// SPDX-License-Identifier: BSD-2-Clause-Views
#include "ib_transport_protocol/retransmitter/owned_retrans.hpp"

void owned_insert_decode(hls::stream<ap_uint<416>>& in,hls::stream<as02OwnedInsert>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<416> held=0;static bool have=false,valid=false;static as02OwnedInsert decoded;
    bool emit=valid && !out.full();if(emit)out.write(decoded);
    bool transform=have && (!valid || emit);
    if(transform) {
        ap_uint<416> r=held;as02OwnedInsert m;
        m.normal.qpn=r(15,0);m.normal.psn=r(39,16);ap_uint<32> op=r(71,40);
        m.normal.opCode=static_cast<ibOpCode>(op<=RC_ACK?op.to_uint():0U);
        m.normal.rkey=r(103,72);m.normal.rkey_valid=r[104];m.normal.host=r[105];
        m.normal.localAddr=r(169,106);m.normal.remoteAddr=r(233,170);m.normal.length=r(265,234);
        m.normal.lst=r[266];m.normal.offs=r(270,267);m.epoch=r(334,271);m.sequence=r(398,335);
        m.bad=r(415,399)!=0 || op>RC_ACK;
        decoded=m;valid=true;
    }
    else if(emit)valid=false;
    if(!have || transform) {if(!in.empty()) {held=in.read();have=true;}else have=false;}
}
void owned_update_decode(hls::stream<ap_uint<224>>& in,hls::stream<as02OwnedUpdate>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<224> held=0;static bool have=false,valid=false;static as02OwnedUpdate decoded;
    bool emit=valid && !out.full();if(emit)out.write(decoded);
    bool transform=have && (!valid || emit);
    if(transform) {
        ap_uint<224> r=held;as02OwnedUpdate m;
        m.normal.qpn=r(15,0);m.normal.latest_acked_req=r(39,16);ap_uint<32> op=r(71,40);
        m.normal.op_code=static_cast<ibOpCode>(op<=RC_ACK?op.to_uint():0U);
        m.epoch=r(135,72);m.sequence=r(199,136);m.bad=r(223,200)!=0 || op>RC_ACK;decoded=m;valid=true;
    }
    else if(emit)valid=false;
    if(!have || transform) {if(!in.empty()) {held=in.read();have=true;}else have=false;}
}
template<int ID>
void owned_retry_decode(hls::stream<ap_uint<192>>& in,hls::stream<as02OwnedRetry>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<192> held=0;static bool have=false,valid=false;static as02OwnedRetry decoded;
    bool emit=valid && !out.full();if(emit)out.write(decoded);
    bool transform=have && (!valid || emit);
    if(transform) {
        ap_uint<192> r=held;as02OwnedRetry m;
        m.normal.qpn=r(15,0);m.normal.psn=r(39,16);m.epoch=r(103,40);m.sequence=r(167,104);
        m.bad=r(191,168)!=0;decoded=m;valid=true;
    }
    else if(emit)valid=false;
    if(!have || transform) {if(!in.empty()) {held=in.read();have=true;}else have=false;}
}
void owned_event_encode(hls::stream<as02OwnedEvent>& in,hls::stream<ap_uint<576>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        as02OwnedEvent m=in.read();retransEvent e=m.normal;ap_uint<576> r=0;
        r(23,0)=e.qpn;r(47,24)=e.psn;r(79,48)=static_cast<unsigned>(e.op_code);
        r(111,80)=e.rkey;r[112]=e.rkey_valid;r[113]=e.host;r(177,114)=e.localAddr;
        r(241,178)=e.remoteAddr;r(273,242)=e.length;r[274]=e.lst;r(278,275)=e.offs;
        r[279]=e.validPsn;r[280]=e.isNak;r(528,281)=m.lease;out.write(r);
    }
}
void owned_rdinit_encode(hls::stream<as02OwnedRdInit>& in,hls::stream<ap_uint<320>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        as02OwnedRdInit m=in.read();ap_uint<320> r=0;r(63,0)=m.normal.laddr;r[64]=m.normal.lst;
        r(312,65)=m.lease;out.write(r);
    }
}
void as02_owned_retrans_top(hls::stream<ap_uint<416>>& s_insert,
    hls::stream<ap_uint<224>>& s_update,hls::stream<ap_uint<192>>& s_retry,hls::stream<ap_uint<192>>& s_timer,
    hls::stream<ap_uint<192>>& m_pool_alloc,hls::stream<ap_uint<256>>& s_pool_alloc,
    hls::stream<ap_uint<256>>& m_pool_release,hls::stream<ap_uint<256>>& s_pool_release,
    hls::stream<ap_uint<576>>& m_event,hls::stream<ap_uint<320>>& m_rdinit,
    ap_uint<12> pool_credit,bool pool_initialized,bool pool_fault_in,
    ap_uint<32>& fault,ap_uint<8>& phase,ap_uint<32>& inserted,ap_uint<32>& released,ap_uint<32>& partial) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_insert
#pragma HLS interface axis register port=s_update
#pragma HLS interface axis register port=s_retry
#pragma HLS interface axis register port=s_timer
#pragma HLS interface axis register port=m_pool_alloc
#pragma HLS interface axis register port=s_pool_alloc
#pragma HLS interface axis register port=m_pool_release
#pragma HLS interface axis register port=s_pool_release
#pragma HLS interface axis register port=m_event
#pragma HLS interface axis register port=m_rdinit
#pragma HLS interface ap_none port=pool_credit
#pragma HLS interface ap_none port=pool_initialized
#pragma HLS interface ap_none port=pool_fault_in
#pragma HLS interface ap_none port=fault
#pragma HLS interface ap_none port=phase
#pragma HLS interface ap_none port=inserted
#pragma HLS interface ap_none port=released
#pragma HLS interface ap_none port=partial
#pragma HLS dataflow disable_start_propagation
    static hls::stream<as02OwnedInsert> inserts("inserts");
    static hls::stream<as02OwnedUpdate> updates("updates");
    static hls::stream<as02OwnedRetry> retries("retries"),timers("timers");
    static hls::stream<as02OwnedEvent> events("events");
    static hls::stream<as02OwnedRdInit> rdinits("rdinits");
    static hls::stream<pointerReq> preq("preq");
    static hls::stream<pointerUpdate> pupd("pupd");
    static hls::stream<retransPointerEntry> prsp("prsp");
    static hls::stream<as02OwnedMetaReq> mreq("mreq");
    static hls::stream<as02OwnedMetaEntry> mrsp("mrsp");
    static hls::stream<ap_uint<32>> pointer_faults("pointer_faults"),metadata_faults("metadata_faults");
#pragma HLS stream variable=inserts depth=2
#pragma HLS stream variable=updates depth=2
#pragma HLS stream variable=retries depth=2
#pragma HLS stream variable=timers depth=2
#pragma HLS stream variable=events depth=2
#pragma HLS stream variable=rdinits depth=2
#pragma HLS stream variable=preq depth=2
#pragma HLS stream variable=pupd depth=2
#pragma HLS stream variable=prsp depth=2
#pragma HLS stream variable=mreq depth=2
#pragma HLS stream variable=mrsp depth=2
#pragma HLS stream variable=pointer_faults depth=2
#pragma HLS stream variable=metadata_faults depth=2
#pragma HLS aggregate variable=inserts compact=bit
#pragma HLS aggregate variable=updates compact=bit
#pragma HLS aggregate variable=retries compact=bit
#pragma HLS aggregate variable=timers compact=bit
#pragma HLS aggregate variable=events compact=bit
#pragma HLS aggregate variable=rdinits compact=bit
#pragma HLS aggregate variable=preq compact=bit
#pragma HLS aggregate variable=pupd compact=bit
#pragma HLS aggregate variable=prsp compact=bit
#pragma HLS aggregate variable=mreq compact=bit
#pragma HLS aggregate variable=mrsp compact=bit
    owned_insert_decode(s_insert,inserts);owned_update_decode(s_update,updates);
    owned_retry_decode<0>(s_retry,retries);owned_retry_decode<1>(s_timer,timers);
    as02_owned_pointer_table<46>(preq,pupd,prsp,pointer_faults);
    as02_owned_meta_table<46>(mreq,mrsp,metadata_faults);
    as02_process_owned_retransmissions<46>(updates,rdinits,retries,timers,inserts,preq,pupd,prsp,mreq,mrsp,
        m_pool_alloc,s_pool_alloc,m_pool_release,s_pool_release,events,pool_credit,pool_initialized,pool_fault_in,
        pointer_faults,metadata_faults,fault,phase,inserted,released,partial);
    owned_event_encode(events,m_event);owned_rdinit_encode(rdinits,m_rdinit);
}
