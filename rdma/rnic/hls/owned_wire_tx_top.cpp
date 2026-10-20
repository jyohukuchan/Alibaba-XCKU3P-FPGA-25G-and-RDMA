// SPDX-License-Identifier: BSD-2-Clause-Views
#include "ib_transport_protocol/owned_wire_tx.hpp"

void as02_owned_wire_header_pack(stream<BaseTransportHeader<64>>& in,stream<ap_uint<96>>& out) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!in.empty() && !out.full())out.write(in.read().getRawHeader());
}
// One actual TX producer graph. Native owner admission, the RX producer graph,
// actual timer/allocator start join, ordered fences and MAC/DMA/CQ are NOT
// instantiated here, and no completion/drained output is exposed.
void as02_owned_wire_tx_top(
    stream<ap_uint<248>>& s_sq,stream<ap_uint<192>>& s_trusted_context,
    stream<as02OwnedEvent>& s_replay,stream<ackEvent>& s_remote_ack,
    stream<as02WireEvent>& s_remote_read,stream<ap_uint<24>>& s_destination,
    stream<stateTableEntry>& s_state,stream<txMsnRsp>& s_msn,
    stream<ap_uint<16>>& m_connection,stream<txStateReq>& m_state,
    stream<ap_uint<16>>& m_msn,stream<memCmdInternal>& m_memory,
    stream<as02OwnedInsert>& m_insert,stream<as02WireContext>& m_tx_start,
    stream<ap_uint<96>>& m_bth,stream<net_axis<64>>& m_exh,
    stream<ap_uint<16>>& m_length,stream<txPacketInfo>& m_packet_info,
    ap_uint<32>& admission_fault,ap_uint<32>& local_fault,
    ap_uint<32>& ibh_fault,ap_uint<32>& exh_fault,ap_uint<32>& merge_fault,
    ap_uint<32>& retransmissions) {
#pragma HLS interface ap_ctrl_none port=return
#pragma HLS interface axis register port=s_sq
#pragma HLS interface axis register port=s_trusted_context
#pragma HLS interface axis register port=s_replay
#pragma HLS interface axis register port=s_remote_ack
#pragma HLS interface axis register port=s_remote_read
#pragma HLS interface axis register port=s_destination
#pragma HLS interface axis register port=s_state
#pragma HLS interface axis register port=s_msn
#pragma HLS interface axis register port=m_connection
#pragma HLS interface axis register port=m_state
#pragma HLS interface axis register port=m_msn
#pragma HLS interface axis register port=m_memory
#pragma HLS interface axis register port=m_insert
#pragma HLS interface axis register port=m_tx_start
#pragma HLS interface axis register port=m_bth
#pragma HLS interface axis register port=m_exh
#pragma HLS interface axis register port=m_length
#pragma HLS interface axis register port=m_packet_info
#pragma HLS interface ap_none port=admission_fault
#pragma HLS interface ap_none port=local_fault
#pragma HLS interface ap_none port=ibh_fault
#pragma HLS interface ap_none port=exh_fault
#pragma HLS interface ap_none port=merge_fault
#pragma HLS interface ap_none port=retransmissions
#pragma HLS dataflow disable_start_propagation
    static stream<as02WireTxMeta> admitted("admitted");
    static stream<as02WireAddrLen> addresses("addresses");
    static stream<as02WireEvent> app("app"),exh("exh");
    static stream<as02WireIBHMeta> ibh("ibh");
    static stream<as02WireRetransMeta> psns("psns");
    static stream<BaseTransportHeader<64>> headers("headers");
#pragma HLS stream variable=admitted depth=2
#pragma HLS stream variable=addresses depth=2
#pragma HLS stream variable=app depth=2
#pragma HLS stream variable=exh depth=2
#pragma HLS stream variable=ibh depth=2
#pragma HLS stream variable=psns depth=2
#pragma HLS stream variable=headers depth=2
#pragma HLS aggregate variable=admitted compact=bit
#pragma HLS aggregate variable=addresses compact=bit
#pragma HLS aggregate variable=app compact=bit
#pragma HLS aggregate variable=exh compact=bit
#pragma HLS aggregate variable=ibh compact=bit
#pragma HLS aggregate variable=psns compact=bit
#pragma HLS aggregate variable=headers compact=bit
    as02_owned_wire_admit<51>(s_sq,s_trusted_context,admitted,admission_fault);
    as02_owned_wire_local_req_handler<51>(admitted,s_replay,addresses,m_memory,app,retransmissions,local_fault);
    as02_owned_wire_meta_merger<51>(s_remote_ack,s_remote_read,app,m_connection,ibh,exh);
    as02_owned_wire_generate_ibh<64,51>(ibh,s_destination,s_state,m_state,psns,headers,ibh_fault);
    as02_owned_wire_generate_exh<64,51>(exh,s_msn,m_msn,m_length,m_packet_info,m_tx_start,m_exh,exh_fault);
    as02_owned_wire_merge_retrans_request(psns,addresses,m_insert,merge_fault);
    as02_owned_wire_header_pack(headers,m_bth);
}
