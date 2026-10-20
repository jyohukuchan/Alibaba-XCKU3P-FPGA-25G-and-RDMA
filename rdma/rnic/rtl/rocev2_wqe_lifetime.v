// SPDX-License-Identifier: BSD-2-Clause-Views
// One retained FULL authorized WR: actual dedicated HLS-TX acceptance ->
// issued PSN/response expectation; join independent memory/response/HLS-ACK/
// MAC-completion evidence before a CQ publication TICKET. Ticket acceptance
// is NOT CQ commit/unpin. Release only on exact commit + current real drains.
// TX observation MUST be after the real TX-integrity stage and on this WR's
// dedicated stream, never arbitrary host TX. MAC proof/transport drain/CQ
// publisher must be real production owners, not default-success booleans.
// No error recovery/verbs or zero/large/multi-SGE/full concurrency claim.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_lifetime #(
    parameter MAX_QPS=8
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [587:0] s_owner_context,
    input wire [31:0] s_owner_local_ip,
    input wire [31:0] s_owner_peer_ip,
    input wire [23:0] s_owner_peer_qpn,
    input wire s_owner_valid,
    output wire s_owner_ready,
    // Passive acceptance monitor on the actual post-integrity HLS IP stream.
    input wire [127:0] s_tx_data,
    input wire [15:0] s_tx_keep,
    input wire s_tx_last,
    input wire s_tx_user,
    input wire s_tx_valid,
    input wire s_tx_ready,
    output wire [587:0] m_expect_context,
    output wire [31:0] m_expect_local_ip,
    output wire [31:0] m_expect_peer_ip,
    output reg [23:0] m_expect_psn=0,
    output reg m_expect_valid=0,
    input wire m_expect_ready,
    // Upstream RX FIFO MUST hold owned responses while this is0; do not
    // feed them to an unowned/discarding RX guard before expectation capture.
    output wire response_admission_ready,
    input wire [587:0] s_memory_context,
    input wire [7:0] s_memory_error,
    input wire s_memory_valid,
    output wire s_memory_ready,
    input wire [587:0] s_response_context,
    input wire [23:0] s_response_psn,
    input wire [7:0] s_response_opcode,
    input wire [7:0] s_response_syndrome,
    input wire s_response_valid,
    output wire s_response_ready,
    input wire [39:0] s_hls_ack,
    input wire s_hls_ack_valid,
    output wire s_hls_ack_ready,
    input wire [587:0] s_mac_context,
    input wire [7:0] s_mac_error,
    input wire s_mac_valid,
    output wire s_mac_ready,
    input wire memory_drained,
    input wire transport_drained,
    output wire [587:0] m_cq_context,
    output reg m_cq_valid=0,
    input wire m_cq_ready,
    input wire [587:0] s_cq_commit_context,
    input wire [7:0] s_cq_commit_error,
    input wire s_cq_commit_valid,
    output wire s_cq_commit_ready,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [7:0] failed_status=0,
    output wire [6:0] proof_flags,
    output reg [31:0] committed_count=0
);
reg [587:0] owner=0;
reg [31:0] local_ip=0,peer_ip=0;
reg [23:0] peer_qpn=0;
reg active=0,issue_seen=0,expect_sent=0,memory_seen=0,response_seen=0,ack_seen=0,mac_seen=0,ticket_sent=0;
reg [511:0] header=0;
reg [8:0] tx_words=0;
reg [15:0] tx_bytes=0;
reg tx_check=0,tx_bad=0;
wire [63:0] in_id,in_seq,in_epoch,in_va,in_offset,in_remote;
wire [23:0] in_qpn;
wire [15:0] in_pd,in_tag,in_op,in_flags;
wire [31:0] in_length,in_key,in_rkey;
wire [7:0] in_error,in_fetch;
wire [1:0] in_source;
wire in_available,in_authorized;
assign {in_id,in_seq,in_epoch,in_qpn,in_pd,in_tag,in_op,in_flags,in_length,in_key,in_va,in_offset,
    in_remote,in_rkey,in_error,in_source,in_fetch,in_available,in_authorized}=s_owner_context;
wire [63:0] wr_id,sequence_value,epoch,va,offset,remote_address;
wire [23:0] qpn;
wire [15:0] pd,tag,opcode,flags;
wire [31:0] length,key,remote_key;
wire [7:0] error,fetch_error;
wire [1:0] error_source;
wire available,authorized;
assign {wr_id,sequence_value,epoch,qpn,pd,tag,opcode,flags,length,key,va,offset,
    remote_address,remote_key,error,error_source,fetch_error,available,authorized}=owner;
wire owner_known=(^{s_owner_context,s_owner_local_ip,s_owner_peer_ip,s_owner_peer_qpn})!==1'bx;
wire [64:0] va_end={1'b0,in_va}+{33'd0,in_length};
wire [64:0] off_end={1'b0,in_offset}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,in_remote}+{33'd0,in_length};
wire owner_ok=owner_known && in_qpn<MAX_QPS && in_seq!=0 && in_epoch!=0 && in_tag!=0 &&
    in_authorized && in_available && in_error==0 && in_source==0 && in_fetch==0 &&
    (in_op==1 || in_op==2 || (in_op==3 && in_remote==0 && in_rkey==0)) && (in_flags&16'hfffe)==0 && in_length!=0 && in_length<=4096 &&
    (!va_end[64] || va_end==65'h10000000000000000) &&
    (!off_end[64] || off_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000);
wire bad_owner=enable && !active && ((s_owner_valid!==1'b0 && s_owner_valid!==1'b1) || (s_owner_valid && !owner_ok));
assign s_owner_ready=!active && !fault && enable && !rst && owner_ok;
assign queue_guard=(fault || bad_owner) ? {MAX_QPS{1'b1}} : active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn) :
    (s_owner_valid && owner_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : {MAX_QPS{1'b0}};
assign busy=active || fault;
assign m_expect_context=owner;assign m_expect_local_ip=local_ip;assign m_expect_peer_ip=peer_ip;
assign response_admission_ready=active && expect_sent && !fault;
assign m_cq_context=owner;
assign proof_flags={ticket_sent,mac_seen,ack_seen,response_seen,memory_seen,expect_sent,issue_seen};
function [15:0] be16;
    input [511:0] d;input integer p;
    begin be16={d[p*8+:8],d[(p+1)*8+:8]};end
endfunction
function [31:0] be32;
    input [511:0] d;input integer p;
    begin be32={d[p*8+:8],d[(p+1)*8+:8],d[(p+2)*8+:8],d[(p+3)*8+:8]};end
endfunction
function [63:0] be64;
    input [511:0] d;input integer p;
    begin be64={be32(d,p),be32(d,p+4)};end
endfunction
wire [23:0] tx_qpn={header[33*8+:8],header[34*8+:8],header[35*8+:8]};
wire [23:0] tx_psn={header[37*8+:8],header[38*8+:8],header[39*8+:8]};
wire [31:0] padded=(length+3)&32'hfffffffc;
reg [20:0] ip_sum;
integer p;
always @*begin ip_sum=0;for(p=0;p<20;p=p+2)ip_sum=ip_sum+{5'd0,be16(header,p)};end
wire header_ok=(^header)!==1'bx && !tx_bad && tx_bytes>=(opcode==3 ? 44 : 60) &&
    header[0+:8]==8'h45 && header[9*8+:8]==17 && be16(header,2)==tx_bytes &&
    ip_sum[15:0]==~{11'd0,ip_sum[20:16]} && (be16(header,6)&16'hbfff)==0 &&
    be32(header,12)==local_ip && be32(header,16)==peer_ip && be16(header,22)==4791 &&
    be16(header,24)==tx_bytes-20 && be16(header,26)==0 &&
    header[28*8+:8]==(opcode==1 ? 8'h0a : opcode==3 ? 8'h04 : 8'h0c) && (header[29*8+:8]&8'h8f)==0 &&
    header[29*8+4+:2]==(opcode==2 ? 0 : ((-length)&3)) && be16(header,30)==16'hffff &&
    (header[32*8+:8]&8'h3f)==0 && (header[36*8+:8]&8'h7f)==0 && tx_qpn==peer_qpn &&
    (opcode==3 || (be64(header,40)==remote_address && be32(header,48)==remote_key && be32(header,52)==length)) &&
    tx_bytes==(opcode==1 ? 60+padded : opcode==3 ? 44+padded : 60);
reg [4:0] keep_count;
reg tx_data_known;
integer b;
always @*begin
    keep_count=0;tx_data_known=1;
    for(b=0;b<16;b=b+1)begin
        keep_count=keep_count+s_tx_keep[b];
        if(s_tx_keep[b] && (^s_tx_data[b*8+:8])===1'bx)tx_data_known=0;
    end
end
wire tx_shape=(^{s_tx_keep,s_tx_last,s_tx_user})!==1'bx && tx_data_known && !s_tx_user &&
    s_tx_keep!=0 && !(|(s_tx_keep[15:1]&~s_tx_keep[14:0])) &&
    (s_tx_last ? keep_count[1:0]==0 : s_tx_keep==16'hffff);
wire memory_match=(^{s_memory_context,s_memory_error})!==1'bx && s_memory_context==owner;
wire response_match=(^{s_response_context,s_response_psn,s_response_opcode,s_response_syndrome})!==1'bx &&
    s_response_context==owner && s_response_psn==m_expect_psn &&
    s_response_opcode==(opcode==2 ? 8'h10 : 8'h11) && (s_response_syndrome&8'he0)==0;
wire ack_match=(^s_hls_ack)!==1'bx && s_hls_ack=={5'd0,m_expect_psn,qpn[9:0],(opcode!=2)};
wire mac_match=(^{s_mac_context,s_mac_error})!==1'bx && s_mac_context==owner;
wire commit_match=(^{s_cq_commit_context,s_cq_commit_error})!==1'bx && s_cq_commit_context==owner;
wire drains=memory_drained===1'b1 && transport_drained===1'b1;
wire bad_tx=(s_tx_valid!==1'b0 && s_tx_valid!==1'b1) || (s_tx_valid && (!active || issue_seen || tx_check));
wire bad_memory=(s_memory_valid!==1'b0 && s_memory_valid!==1'b1) ||
    (s_memory_valid && (!active || memory_seen || !memory_match || (opcode==2 && !issue_seen)));
wire bad_response=(s_response_valid!==1'b0 && s_response_valid!==1'b1) ||
    (s_response_valid && (!active || !expect_sent || response_seen || !response_match));
wire bad_ack=(s_hls_ack_valid!==1'b0 && s_hls_ack_valid!==1'b1) ||
    (s_hls_ack_valid && (!active || !expect_sent || ack_seen || !ack_match));
wire bad_mac=(s_mac_valid!==1'b0 && s_mac_valid!==1'b1) ||
    (s_mac_valid && (!active || !issue_seen || mac_seen || !mac_match));
wire bad_commit=(s_cq_commit_valid!==1'b0 && s_cq_commit_valid!==1'b1) ||
    (s_cq_commit_valid && (!active || !ticket_sent || !commit_match || s_cq_commit_error!=0 || !drains));
wire incoming_fault=bad_owner || bad_tx || bad_memory || bad_response || bad_ack || bad_mac || bad_commit ||
    (s_memory_valid && memory_match && s_memory_error!=0) || (s_mac_valid && mac_match && s_mac_error!=0);
assign s_memory_ready=active && !memory_seen && memory_match && (opcode!=2 || issue_seen) && !fault && !rst;
assign s_response_ready=active && expect_sent && !response_seen && response_match && !fault && !rst;
assign s_hls_ack_ready=active && expect_sent && !ack_seen && ack_match && !fault && !rst;
assign s_mac_ready=active && issue_seen && !mac_seen && mac_match && !fault && !rst;
// A concurrent invalid/errored proof must not acknowledge even an otherwise
// exact commit at this edge. CQ/MR release cannot outrun sticky fault capture.
assign s_cq_commit_ready=active && ticket_sent && commit_match && s_cq_commit_error==0 && drains &&
    !incoming_fault && !fault && !rst;
integer lane;
initial if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed lifetime QP capacity");
always @(posedge clk)begin
    if(rst)begin
        owner<=0;local_ip<=0;peer_ip<=0;peer_qpn<=0;active<=0;issue_seen<=0;expect_sent<=0;
        memory_seen<=0;response_seen<=0;ack_seen<=0;mac_seen<=0;ticket_sent<=0;
        header<=0;tx_words<=0;tx_bytes<=0;tx_check<=0;tx_bad<=0;m_expect_psn<=0;m_expect_valid<=0;
        m_cq_valid<=0;fault<=0;fault_code<=0;failed_status<=0;committed_count<=0;
    end else begin
        if(s_owner_valid && s_owner_ready)begin
            owner<=s_owner_context;local_ip<=s_owner_local_ip;peer_ip<=s_owner_peer_ip;peer_qpn<=s_owner_peer_qpn;
            active<=1;issue_seen<=0;expect_sent<=0;memory_seen<=0;response_seen<=0;ack_seen<=0;mac_seen<=0;ticket_sent<=0;
            header<=0;tx_words<=0;tx_bytes<=0;tx_check<=0;tx_bad<=0;
        end
        if(s_tx_valid && s_tx_ready && active && !issue_seen && !tx_check && !fault)begin
            if(tx_words<4)for(lane=0;lane<16;lane=lane+1)
                header[tx_words*128+lane*8+:8]<=s_tx_keep[lane] ? s_tx_data[lane*8+:8] : 8'd0;
            if(!tx_shape)tx_bad<=1;
            if(tx_words<260)tx_words<=tx_words+1'b1;else tx_bad<=1;
            tx_bytes<=tx_bytes+keep_count;
            if(s_tx_last)tx_check<=1;
        end
        if(tx_check && !fault && !incoming_fault)begin
            if(!header_ok)begin fault<=1;fault_code<=8'hb2;end
            else begin issue_seen<=1;m_expect_psn<=tx_psn;m_expect_valid<=1;tx_check<=0;end
        end
        if(m_expect_valid && m_expect_ready)begin m_expect_valid<=0;expect_sent<=1;end
        if(s_memory_valid && s_memory_ready)begin
            if(s_memory_error!=0)begin fault<=1;fault_code<=8'hb3;failed_status<=s_memory_error;end
            else memory_seen<=1;
        end
        if(s_response_valid && s_response_ready)response_seen<=1;
        if(s_hls_ack_valid && s_hls_ack_ready)ack_seen<=1;
        if(s_mac_valid && s_mac_ready)begin
            if(s_mac_error!=0)begin fault<=1;fault_code<=8'hb6;failed_status<=s_mac_error;end
            else mac_seen<=1;
        end
        if(active && issue_seen && expect_sent && memory_seen && response_seen && ack_seen && mac_seen &&
           drains && !m_cq_valid && !ticket_sent && !fault && !incoming_fault)m_cq_valid<=1;
        // Persistent prepared ticket is NOT a CQE or permission to unpin.
        if(m_cq_valid && m_cq_ready)begin m_cq_valid<=0;ticket_sent<=1;end
        if(s_cq_commit_valid && s_cq_commit_ready)begin active<=0;committed_count<=committed_count+1'b1;end
        if(!fault)begin
            if(bad_owner)begin fault<=1;fault_code<=8'hb1;end
            if(bad_tx)begin fault<=1;fault_code<=8'hb2;end
            if(bad_memory)begin fault<=1;fault_code<=8'hb3;end
            if(bad_response)begin fault<=1;fault_code<=8'hb4;end
            if(bad_ack)begin fault<=1;fault_code<=8'hb5;end
            if(bad_mac)begin fault<=1;fault_code<=8'hb6;end
            if(bad_commit)begin fault<=1;fault_code<=8'hb7;end
        end
    end
end
endmodule
`resetall
