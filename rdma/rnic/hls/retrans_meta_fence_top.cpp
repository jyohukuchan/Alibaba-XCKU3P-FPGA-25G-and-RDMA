// SPDX-License-Identifier: BSD-2-Clause-Views
#include "ib_transport_protocol/retransmitter/retrans_meta_fence.hpp"
static ap_uint<288> meta_pack(retransMetaEntry e) {
#pragma HLS inline
    ap_uint<288> r=0;r(31,0)=e.rkey;r[32]=e.rkey_valid;r[33]=e.host;
    r(57,34)=e.psn;r(73,58)=e.next;r(105,74)=static_cast<unsigned>(e.opCode);
    r(169,106)=e.localAddr;r(233,170)=e.remoteAddr;r(265,234)=e.length;
    r[266]=e.lst;r(270,267)=e.offs;r[271]=e.valid;r[272]=e.isTail;return r;
}
void meta_decode(hls::stream<ap_uint<480>>& in,hls::stream<as02MetaMsg>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static ap_uint<480> held=0;
    static bool have=false;
    static as02MetaMsg decoded;
    static bool decoded_valid=false;
    bool emit=decoded_valid && !out.full();
    if(emit)out.write(decoded);
    bool transform=have && (!decoded_valid || emit);
    if(transform) {
        ap_uint<480> r=held;as02MetaMsg m;ap_uint<273> d=r(459,187);
        m.normal.idx=r(15,0);m.normal.write=r[16];m.normal.append=r[17];m.marker=r[18];
        m.qpn=r(34,19);m.psn=r(58,35);m.epoch=r(122,59);m.sequence=r(186,123);
        m.normal.entry.rkey=d(31,0);m.normal.entry.rkey_valid=d[32];m.normal.entry.host=d[33];
        m.normal.entry.psn=d(57,34);m.normal.entry.next=d(73,58);
        ap_uint<32> opcode=d(105,74);
        m.normal.entry.opCode=static_cast<ibOpCode>(opcode<=RC_ACK ? opcode.to_uint() : 0U);
        m.normal.entry.localAddr=d(169,106);m.normal.entry.remoteAddr=d(233,170);m.normal.entry.length=d(265,234);
        m.normal.entry.lst=d[266];m.normal.entry.offs=d(270,267);m.normal.entry.valid=d[271];m.normal.entry.isTail=d[272];
        m.bad=r(479,460)!=0 || (m.marker && d!=0) || (m.normal.write && opcode>RC_ACK);
        decoded=m;decoded_valid=true;
    }
    else if(emit)decoded_valid=false;
    if(!have || transform) {
        if(!in.empty()) {held=in.read();have=true;}
        else have=false;
    }
}
void meta_normal_encode(hls::stream<retransMetaEntry>& in,hls::stream<ap_uint<288>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full())out.write(meta_pack(in.read()));
}
void meta_fence_encode(hls::stream<as02MetaReadback>& in,hls::stream<ap_uint<512>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full()) {
        auto e=in.read();ap_uint<512> r=0;
        r(15,0)=e.token.normal.idx;r(31,16)=e.token.qpn;r(55,32)=e.token.psn;
        r(119,56)=e.token.epoch;r(183,120)=e.token.sequence;r(191,184)=e.status;r[192]=e.snapshot_valid;
        r(465,193)=meta_pack(e.entry)(272,0);r(481,466)=e.failed_idx;out.write(r);
    }
}
void as02_meta_fence_top(hls::stream<ap_uint<480>>& s_meta,
    hls::stream<ap_uint<288>>& m_normal,hls::stream<ap_uint<512>>& m_fence) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_meta
#pragma HLS interface axis register port=m_normal
#pragma HLS interface axis register port=m_fence
#pragma HLS dataflow disable_start_propagation
    static hls::stream<as02MetaMsg> requests("requests");
    static hls::stream<retransMetaEntry> normal("normal");
    static hls::stream<as02MetaReadback> fence("fence");
#pragma HLS stream variable=requests depth=2
#pragma HLS stream variable=normal depth=2
#pragma HLS stream variable=fence depth=2
#pragma HLS aggregate variable=requests compact=bit
#pragma HLS aggregate variable=normal compact=bit
#pragma HLS aggregate variable=fence compact=bit
    meta_decode(s_meta,requests);
    as02_retrans_meta_fence_consumer<45>(requests,normal,fence);
    meta_normal_encode(normal,m_normal);meta_fence_encode(fence,m_fence);
}
