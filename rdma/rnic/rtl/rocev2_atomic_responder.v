// SPDX-License-Identifier: BSD-2-Clause-Views
// Candidate RC64 CAS/FADD responder, not enabled in native graph/capabilities.
// Input: EXACT 40B BTH+AtomicETH, low byte first, AFTER integrity/peer checks.
// Epoch/PD/peer QPN are TRUSTED management, never taken from the remote packet.
// Own candidate PSN/MSN table; must merge with the shared HLS QP table before
// mixed native READ/WRITE/SEND/Atomic publication. One replay resource per QP.
// Full MR op4 authorization -> exclusive shared paged memory RMW -> real
// write visibility status -> wire AtomicACK(old value). No CPU payload path.
// Fault/reset is NOT safe drain/unpin. Scope excludes CPU/other-device writes.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_responder #(
    parameter MAX_QPS=8,
    // Matched shared HLS service supplies the authoritative PSN/MSN. Legacy
    // standalone tests retain the private table; native must use this mode.
    parameter SHARED_SEQUENCE_ENABLE=0
)(
    input wire clk, input wire rst, input wire enable,
    input wire cfg_quiescent,
    input wire [23:0] cfg_qpn, input wire [23:0] cfg_peer_qpn,
    input wire [15:0] cfg_pd, input wire [63:0] cfg_epoch,
    input wire [23:0] cfg_psn, input wire [23:0] cfg_msn,
    input wire cfg_valid, output wire cfg_ready,
    output reg [7:0] cfg_error=0, output reg cfg_response_valid=0,
    input wire cfg_response_ready,
    input wire [319:0] s_request_header, input wire [5:0] s_request_bytes,
    input wire [63:0] s_request_epoch,
    input wire [23:0] s_request_expected_psn, input wire [23:0] s_request_msn,
    input wire s_request_valid, output wire s_request_ready,
    output reg [191:0] m_response_header=0, output reg [5:0] m_response_bytes=0,
    output reg [23:0] m_response_qpn=0, output reg [63:0] m_response_epoch=0,
    output reg m_response_advance=0, output reg m_response_drop=0,
    output reg m_response_valid=0, input wire m_response_ready,
    output wire [15:0] m_mr_pd, output wire [31:0] m_mr_key,
    output wire [63:0] m_mr_address, output wire [31:0] m_mr_length,
    output wire [2:0] m_mr_operation, output wire [15:0] m_mr_tag,
    output wire m_mr_valid, input wire m_mr_ready,
    input wire [15:0] s_mr_tag, input wire [7:0] s_mr_error,
    input wire [63:0] s_mr_offset, input wire [31:0] s_mr_length,
    input wire s_mr_valid, output wire s_mr_ready,
    output wire memory_lock_request, input wire memory_lock_granted,
    output wire m_memory_write, output wire [63:0] m_memory_offset,
    output wire [31:0] m_memory_key, output wire [31:0] m_memory_length,
    output wire [15:0] m_memory_tag, output wire m_memory_valid,
    input wire m_memory_ready,
    output wire [511:0] m_axis_write_tdata, output wire [63:0] m_axis_write_tkeep,
    output wire m_axis_write_tlast, output wire m_axis_write_tvalid,
    input wire m_axis_write_tready,
    input wire [511:0] s_axis_read_tdata, input wire [63:0] s_axis_read_tkeep,
    input wire s_axis_read_tlast, input wire s_axis_read_tvalid,
    output wire s_axis_read_tready,
    input wire [15:0] s_memory_status_tag, input wire [7:0] s_memory_status_error,
    input wire s_memory_status_valid, output wire s_memory_status_ready,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy, output wire configuration_guard,
    output reg fault=0, output reg [7:0] fault_code=0,
    output reg [31:0] executed_count=0, output reg [31:0] replay_count=0,
    output reg [31:0] dropped_count=0
);
localparam IDLE=0,CLASSIFY=1,LOCK=2,MR_SEND=3,MR_WAIT=4,
    READ_CMD=5,READ_DATA=6,READ_STATUS=7,WRITE_CMD=8,WRITE_DATA=9,
    WRITE_STATUS=10,COMMIT=11,REPLY=12;
localparam QP_INDEX_WIDTH=MAX_QPS<2 ? 1:$clog2(MAX_QPS);
localparam SHARED_SEQUENCE=(SHARED_SEQUENCE_ENABLE!=0);
reg [3:0] state=IDLE;
reg configured[0:MAX_QPS-1],cache_valid[0:MAX_QPS-1],qp_error[0:MAX_QPS-1];
reg [63:0] epochs[0:MAX_QPS-1];reg [15:0] pds[0:MAX_QPS-1];
reg [23:0] peers[0:MAX_QPS-1],epsn[0:MAX_QPS-1],msn[0:MAX_QPS-1];
reg [319:0] cache_request[0:MAX_QPS-1];
reg [191:0] cache_response[0:MAX_QPS-1];
reg [319:0] request=0;
reg [63:0] request_epoch=0,offset=0,old_value=0,new_value=0;
reg [5:0] request_bytes=0;
reg [23:0] expected_psn=0,request_msn=0;
reg [15:0] tag=1;
reg held_lock=0;
function [23:0] be24;input [23:0] x;begin be24={x[7:0],x[15:8],x[23:16]};end endfunction
function [31:0] be32;input [31:0] x;begin be32={x[7:0],x[15:8],x[23:16],x[31:24]};end endfunction
function [63:0] be64;input [63:0] x;integer b;begin for(b=0;b<8;b=b+1)be64[b*8+:8]=x[(7-b)*8+:8];end endfunction
wire [23:0] incoming_qpn=be24(s_request_header[63:40]);
wire [23:0] qpn=be24(request[63:40]);
wire [23:0] psn=be24(request[95:72]);
wire [QP_INDEX_WIDTH-1:0] qi=qpn[QP_INDEX_WIDTH-1:0],ci=cfg_qpn[QP_INDEX_WIDTH-1:0];
wire [23:0] active_epsn=SHARED_SEQUENCE ? expected_psn:epsn[qi];
wire [23:0] active_msn=SHARED_SEQUENCE ? request_msn:msn[qi];
wire [23:0] psn_delta=psn-active_epsn;
// AXIS invalid lanes are intentionally not part of the eight-byte value.
wire unused_read_lanes=^s_axis_read_tdata[511:64];
wire [7:0] opcode=request[7:0];
wire [63:0] address=be64(request[159:96]);
wire [31:0] key=be32(request[191:160]);
wire [63:0] swap_add=be64(request[255:192]),compare_value=be64(request[319:256]);
wire request_known=(^{request,request_bytes,request_epoch})!==1'bx &&
    (!SHARED_SEQUENCE || (^{expected_psn,request_msn})!==1'bx);
wire header_ok=request_known && request_bytes==40 && (opcode==8'h13 || opcode==8'h14) &&
    request[15:8]==0 && request[31:16]==16'hffff && request[39:32]==0 &&
    request[70:64]==0 && address[2:0]==0 && (opcode!=8'h14 || compare_value==0);
wire qpn_valid=(^qpn)!==1'bx && qpn<MAX_QPS;
wire cfg_known=(^{cfg_qpn,cfg_peer_qpn,cfg_pd,cfg_epoch,cfg_psn,cfg_msn})!==1'bx;
assign busy=state!=IDLE || fault || m_response_valid;
assign configuration_guard=busy || (enable && s_request_valid!==1'b0);
assign cfg_ready=!rst && cfg_quiescent && !configuration_guard && !cfg_response_valid;
assign s_request_ready=!rst && enable && !busy && !cfg_response_valid && !cfg_valid;
assign queue_guard=fault ? {MAX_QPS{1'b1}}:
    state!=IDLE && qpn_valid ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn):
    (s_request_valid && incoming_qpn<MAX_QPS) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<incoming_qpn):{MAX_QPS{1'b0}};
assign memory_lock_request=held_lock;
assign m_mr_pd=qpn_valid ? pds[qi]:16'd0;
assign m_mr_key=key;assign m_mr_address=address;assign m_mr_length=8;
assign m_mr_operation=4;assign m_mr_tag=tag;
assign m_mr_valid=state==MR_SEND && !fault;
assign s_mr_ready=state==MR_WAIT && !fault;
assign m_memory_write=state==WRITE_CMD;
assign m_memory_offset=offset;assign m_memory_length=8;
assign m_memory_key=key;assign m_memory_tag=tag;
assign m_memory_valid=(state==READ_CMD || state==WRITE_CMD) && !fault;
assign m_axis_write_tdata={448'd0,new_value};assign m_axis_write_tkeep=64'hff;
assign m_axis_write_tlast=1;assign m_axis_write_tvalid=state==WRITE_DATA && !fault;
assign s_axis_read_tready=state==READ_DATA && !fault;
assign s_memory_status_ready=(state==READ_STATUS || state==WRITE_STATUS || state==READ_DATA) && !fault;
// Header fields are wire-big-endian; memory lanes are native little-endian.
function [191:0] response;
    input [7:0] op,syndrome;input [23:0] dest,packet_psn,message;
    input [63:0] original;
    begin
        response=0;response[7:0]=op;response[31:16]=16'hffff;
        response[63:40]=be24(dest);response[95:72]=be24(packet_psn);
        response[103:96]=syndrome;response[127:104]=be24(message);
        response[191:128]=be64(original);
    end
endfunction
task nak;
    input [7:0] syndrome;
    input [23:0] response_psn;
    begin
        m_response_header<=response(8'h11,syndrome,peers[qi],response_psn,active_msn,0);
        m_response_bytes<=16;m_response_qpn<=qpn;m_response_epoch<=request_epoch;
        m_response_valid<=1;state<=REPLY;
    end
endtask
task drop_request;
    begin
        dropped_count<=dropped_count+1;
        if(SHARED_SEQUENCE)begin
            // Every accepted service request needs a completion, even when
            // it produces no packet. No sequence advancement on a drop.
            m_response_header<=0;m_response_bytes<=0;m_response_qpn<=qpn;
            m_response_epoch<=request_epoch;m_response_drop<=1;
            m_response_valid<=1;state<=REPLY;
        end else state<=IDLE;
    end
endtask
integer i;
initial if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unsupported atomic QP capacity");
always @(posedge clk)begin
    if(rst)begin
        state<=IDLE;request<=0;request_bytes<=0;request_epoch<=0;offset<=0;
        old_value<=0;new_value<=0;held_lock<=0;tag<=1;fault<=0;fault_code<=0;
        expected_psn<=0;request_msn<=0;m_response_advance<=0;m_response_drop<=0;
        m_response_header<=0;m_response_bytes<=0;m_response_qpn<=0;m_response_epoch<=0;
        m_response_valid<=0;cfg_error<=0;cfg_response_valid<=0;
        executed_count<=0;replay_count<=0;dropped_count<=0;
        for(i=0;i<MAX_QPS;i=i+1)begin
            configured[i]<=0;cache_valid[i]<=0;qp_error[i]<=0;epochs[i]<=0;pds[i]<=0;
            peers[i]<=0;epsn[i]<=0;msn[i]<=0;cache_request[i]<=0;cache_response[i]<=0;
        end
    end else begin
        if(cfg_response_valid && cfg_response_ready)cfg_response_valid<=0;
        if(cfg_valid && cfg_ready)begin
            cfg_error<=0;cfg_response_valid<=1;
            if(!cfg_known || cfg_qpn>=MAX_QPS || cfg_epoch==0)cfg_error<=8'd1;
            else if(configured[ci] && cfg_epoch<=epochs[ci])cfg_error<=8'd2;
            else begin
                configured[ci]<=1;cache_valid[ci]<=0;qp_error[ci]<=0;
                epochs[ci]<=cfg_epoch;pds[ci]<=cfg_pd;peers[ci]<=cfg_peer_qpn;
                epsn[ci]<=cfg_psn;msn[ci]<=cfg_msn;
            end
        end
        if(!fault)case(state)
            IDLE:if(s_request_valid && s_request_ready)begin
                request<=s_request_header;request_bytes<=s_request_bytes;
                request_epoch<=s_request_epoch;expected_psn<=s_request_expected_psn;
                request_msn<=s_request_msn;m_response_advance<=0;m_response_drop<=0;state<=CLASSIFY;
            end
            CLASSIFY:begin
                if(!request_known || !qpn_valid || !configured[qi] ||
                    request_epoch!=epochs[qi] || qp_error[qi])begin
                    drop_request();
                end else if(!header_ok)begin qp_error[qi]<=1;nak(8'h61,psn);end
                else if(cache_valid[qi] && psn==be24(cache_request[qi][95:72]))begin
                    // ACK-request may change on retransmission; it does not
                    // change the atomic operation or its exactly-once result.
                    if((request & ~(320'd1<<71))!=(cache_request[qi] & ~(320'd1<<71)))begin
                        qp_error[qi]<=1;nak(8'h61,psn);
                    end
                    else begin
                        m_response_header<=cache_response[qi];m_response_bytes<=24;
                        m_response_qpn<=qpn;m_response_epoch<=request_epoch;m_response_valid<=1;
                        replay_count<=replay_count+1;state<=REPLY;
                    end
                end else if(psn_delta!=0)begin
                    // Signed modulo24-bit comparison; old unretained requests
                    // are dropped, NEVER re-executed after replay eviction.
                    if(psn_delta[23])drop_request();
                    else nak(8'h60,active_epsn);
                end else begin held_lock<=1;state<=LOCK;end
            end
            LOCK:if(memory_lock_granted)state<=MR_SEND;
            MR_SEND:if(m_mr_valid && m_mr_ready)state<=MR_WAIT;
            MR_WAIT:if(s_mr_valid && s_mr_ready)begin
                if((^{s_mr_tag,s_mr_error,s_mr_offset,s_mr_length})===1'bx || s_mr_tag!=tag)begin
                    fault<=1;fault_code<=8'h71;
                end else if(s_mr_error!=0)begin qp_error[qi]<=1;nak(8'h62,psn);end
                // Relative offset need not be aligned when MR base is not.
                // MR op4 checks the FULL VA and translated address alignment.
                else if(s_mr_length!=8)begin fault<=1;fault_code<=8'h72;end
                else begin offset<=s_mr_offset;state<=READ_CMD;end
            end
            READ_CMD:if(m_memory_valid && m_memory_ready)state<=READ_DATA;
            READ_DATA:if(s_axis_read_tvalid && s_axis_read_tready)begin
                if((^{s_axis_read_tdata[63:0],s_axis_read_tkeep,s_axis_read_tlast})===1'bx ||
                    s_axis_read_tkeep!=64'hff || !s_axis_read_tlast)begin fault<=1;fault_code<=8'h73;end
                else begin
                    old_value<=s_axis_read_tdata[63:0];
                    new_value<=opcode==8'h14 ? s_axis_read_tdata[63:0]+swap_add:swap_add;
                    state<=READ_STATUS;
                end
            end
            READ_STATUS:begin end
            WRITE_CMD:if(m_memory_valid && m_memory_ready)state<=WRITE_DATA;
            WRITE_DATA:if(m_axis_write_tvalid && m_axis_write_tready)state<=WRITE_STATUS;
            WRITE_STATUS:begin end
            COMMIT:begin
                // Only reached after read success AND (if changed) real
                // write visibility/fence success. Cache before ACK exposure.
                cache_valid[qi]<=1;cache_request[qi]<=request;
                cache_response[qi]<=response(8'h12,8'h1f,peers[qi],psn,active_msn+24'd1,old_value);
                m_response_header<=response(8'h12,8'h1f,peers[qi],psn,active_msn+24'd1,old_value);
                m_response_bytes<=24;m_response_qpn<=qpn;m_response_epoch<=request_epoch;
                m_response_valid<=1;m_response_advance<=1;
                if(!SHARED_SEQUENCE)begin epsn[qi]<=psn+24'd1;msn[qi]<=msn[qi]+24'd1;end
                executed_count<=executed_count+1;state<=REPLY;
            end
            REPLY:if(m_response_valid && m_response_ready)begin
                m_response_valid<=0;held_lock<=0;state<=IDLE;
                if(tag==16'hffff)begin fault<=1;fault_code<=8'h77;end else tag<=tag+1'b1;
            end
            default:begin fault<=1;fault_code<=8'h7f;end
        endcase
        if(!fault && s_memory_status_valid && s_memory_status_ready)begin
            if((^{s_memory_status_tag,s_memory_status_error})===1'bx ||
                s_memory_status_tag!=tag || s_memory_status_error!=0 || state==READ_DATA)begin
                fault<=1;fault_code<=8'h74;
            end else if(state==READ_STATUS)
                state<=(opcode==8'h13 && old_value!=compare_value) ? COMMIT:WRITE_CMD;
            else if(state==WRITE_STATUS)state<=COMMIT;
        end
        if(!fault && held_lock && state!=LOCK && memory_lock_granted!==1'b1)begin fault<=1;fault_code<=8'h75;end
    end
end
endmodule
`resetall
