// SPDX-License-Identifier: BSD-2-Clause-Views
// Full SAME-MR WQE owner -> checked HLS command -> authorized shared memory.
// HLS's narrowed address/routing is NEVER DMA authority. The saved full key,
// relative offset, length and tag are the only backend command authority.
// READ placement additionally needs an identical trusted response context
// from a real integrity/peer/QP/PSN/length-protecting receive controller. This
// module does NOT implement that controller, ACK, wire/MAC/CQ or WR completion.
// A memory event transfers ownership ONLY to an already-guarded downstream
// owner. Backend errors retain all guards; reset is NOT safe recovery/unpin.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_memory_executor #(
    parameter MAX_QPS=8
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire halt,
    input wire [587:0] s_owner_context,
    input wire s_owner_valid,
    output wire s_owner_ready,
    input wire [587:0] s_read_response_context,
    input wire s_read_response_valid,
    output wire s_read_response_ready,
    input wire [95:0] s_hls_read_command,
    input wire s_hls_read_command_valid,
    output wire s_hls_read_command_ready,
    input wire [95:0] s_hls_write_command,
    input wire s_hls_write_command_valid,
    output wire s_hls_write_command_ready,
    input wire [511:0] s_axis_hls_write_tdata,
    input wire [63:0] s_axis_hls_write_tkeep,
    input wire s_axis_hls_write_tlast,
    input wire s_axis_hls_write_tvalid,
    output wire s_axis_hls_write_tready,
    output wire [511:0] m_axis_hls_read_tdata,
    output wire [63:0] m_axis_hls_read_tkeep,
    output wire m_axis_hls_read_tlast,
    output wire m_axis_hls_read_tvalid,
    input wire m_axis_hls_read_tready,
    output wire m_memory_command_write,
    output wire [63:0] m_memory_command_offset,
    output wire [31:0] m_memory_command_length,
    output wire [31:0] m_memory_command_key,
    output wire [15:0] m_memory_command_tag,
    output reg m_memory_command_valid=0,
    input wire m_memory_command_ready,
    output wire [511:0] m_axis_memory_write_tdata,
    output wire [63:0] m_axis_memory_write_tkeep,
    output wire m_axis_memory_write_tlast,
    output wire m_axis_memory_write_tvalid,
    input wire m_axis_memory_write_tready,
    input wire [511:0] s_axis_memory_read_tdata,
    input wire [63:0] s_axis_memory_read_tkeep,
    input wire s_axis_memory_read_tlast,
    input wire s_axis_memory_read_tvalid,
    output wire s_axis_memory_read_tready,
    input wire [15:0] s_memory_status_tag,
    input wire [7:0] s_memory_status_error,
    input wire s_memory_status_valid,
    output wire s_memory_status_ready,
    output reg [587:0] m_memory_event_context=0,
    output reg [7:0] m_memory_event_error=0,
    output reg m_memory_event_valid=0,
    input wire m_memory_event_ready,
    input wire [MAX_QPS-1:0] downstream_queue_guard,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] owner_count=0,
    output reg [31:0] command_count=0,
    output reg [31:0] memory_status_count=0
);
reg active=0,raw_seen=0,issued=0,placement_seen=0,data_done=0;
reg [31:0] remaining=0;
reg [511:0] beat_data=0;
reg [63:0] beat_keep=0;
reg beat_last=0,beat_valid=0;
wire [63:0] in_id,in_sequence,in_epoch,in_address,in_offset,in_remote;
wire [23:0] in_qpn;
wire [15:0] in_pd,in_tag,in_opcode,in_flags;
wire [31:0] in_length,in_key,in_rkey;
wire [7:0] in_error,in_fetch;
wire [1:0] in_source;
wire in_available,in_authorized;
assign {in_id,in_sequence,in_epoch,in_qpn,in_pd,in_tag,in_opcode,in_flags,in_length,
    in_key,in_address,in_offset,in_remote,in_rkey,in_error,in_source,in_fetch,in_available,in_authorized}=s_owner_context;
wire [63:0] id,sequence_value,epoch,address,offset,remote_address;
wire [23:0] qpn;
wire [15:0] pd,tag,opcode,flags;
wire [31:0] length,key,remote_key;
wire [7:0] error,fetch_error;
wire [1:0] error_source;
wire available,authorized;
assign {id,sequence_value,epoch,qpn,pd,tag,opcode,flags,length,key,address,offset,
    remote_address,remote_key,error,error_source,fetch_error,available,authorized}=m_memory_event_context;
wire known=(^s_owner_context)!==1'bx;
wire [64:0] va_end={1'b0,in_address}+{33'd0,in_length};
wire [64:0] offset_end={1'b0,in_offset}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,in_remote}+{33'd0,in_length};
wire identity_ok=known && in_qpn<MAX_QPS && in_tag!=0 && in_sequence!=0 && in_epoch!=0;
wire good_work=in_error==0 && in_source==0 && in_fetch==0 && in_available && in_authorized &&
    (in_opcode==1 || in_opcode==2 || (in_opcode==3 && in_remote==0 && in_rkey==0)) && (in_flags & 16'hfffe)==0 && in_length!=0 && in_length<=4096 &&
    (!va_end[64] || va_end==65'h10000000000000000) &&
    (!offset_end[64] || offset_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000);
wire denied_work=in_error!=0 && !in_authorized &&
    ((in_source==1 && in_fetch==in_error && in_fetch<=15 && !in_available) || (in_source==2 && in_fetch==0)) &&
    {in_opcode,in_flags,in_length,in_key,in_address,in_offset,in_remote,in_rkey}==0;
wire bad_owner=!active && enable && ((s_owner_valid!==1'b0 && s_owner_valid!==1'b1) ||
    (s_owner_valid && (!identity_ok || (!good_work && !denied_work))));
assign s_owner_ready=!rst && !active && !fault && enable && !halt && identity_ok && (good_work || denied_work);
assign queue_guard=(fault || bad_owner) ? {MAX_QPS{1'b1}} :
    active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn) :
    (s_owner_valid && identity_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : {MAX_QPS{1'b0}};
assign busy=active || fault;
wire placement=opcode==2;
wire response_known=(^s_read_response_context)!==1'bx;
wire response_match=response_known && s_read_response_context==m_memory_event_context;
assign s_read_response_ready=active && authorized && placement && !placement_seen && !fault && !rst && response_match;
// All96bits, including padding, must match the actual memCmd ABI. host=1,
// sync=0, strm/tdst derive from VA; no field supplies a physical address.
wire [95:0] expected_raw={2'd0,qpn[9:0],address[51:48],1'b1,1'b0,address[52],1'b1,length[27:0],address[47:0]};
wire [95:0] selected_raw=placement ? s_hls_write_command : s_hls_read_command;
wire selected_valid=placement ? s_hls_write_command_valid : s_hls_read_command_valid;
wire opposite_valid=placement ? s_hls_read_command_valid : s_hls_write_command_valid;
wire raw_match=(^selected_raw)!==1'bx && selected_raw==expected_raw;
wire raw_bad=(s_hls_read_command_valid!==1'b0 && s_hls_read_command_valid!==1'b1) ||
    (s_hls_write_command_valid!==1'b0 && s_hls_write_command_valid!==1'b1) ||
    ((s_hls_read_command_valid || s_hls_write_command_valid) &&
     (!active || !authorized || opposite_valid || raw_seen || !raw_match));
wire response_bad=(s_read_response_valid!==1'b0 && s_read_response_valid!==1'b1) ||
    (s_read_response_valid && (!active || !authorized || !placement || placement_seen || !response_match));
wire take_raw=active && authorized && !raw_seen && !fault && !rst && !raw_bad && !response_bad &&
    raw_match && (!placement || placement_seen);
assign s_hls_read_command_ready=take_raw && !placement;
assign s_hls_write_command_ready=take_raw && placement;
assign m_memory_command_write=placement;
assign m_memory_command_offset=offset;
assign m_memory_command_length=length;
assign m_memory_command_key=key;
assign m_memory_command_tag=tag;
function [63:0] mask64;
    input [31:0] n;integer lane;
    begin for(lane=0;lane<64;lane=lane+1)mask64[lane]=n>lane;end
endfunction
wire [511:0] input_data=placement ? s_axis_hls_write_tdata : s_axis_memory_read_tdata;
wire [63:0] input_keep=placement ? s_axis_hls_write_tkeep : s_axis_memory_read_tkeep;
wire input_last=placement ? s_axis_hls_write_tlast : s_axis_memory_read_tlast;
wire input_valid=placement ? s_axis_hls_write_tvalid : s_axis_memory_read_tvalid;
reg bytes_known;
integer k;
always @*begin
    bytes_known=1;
    for(k=0;k<64;k=k+1)if(input_keep[k] && (^input_data[k*8+:8])===1'bx)bytes_known=0;
end
wire shape_ok=(^{input_keep,input_last})!==1'bx && bytes_known &&
    input_keep==mask64(remaining) && input_last==(remaining<=64);
wire status_known=(^{s_memory_status_tag,s_memory_status_error})!==1'bx;
wire error_offer=s_memory_status_valid && status_known && s_memory_status_error!=0;
wire take_data=active && issued && !data_done && remaining!=0 && !beat_valid &&
    !m_memory_event_valid && !fault && !rst && !error_offer && shape_ok;
assign s_axis_hls_write_tready=take_data && placement;
assign s_axis_memory_read_tready=take_data && !placement;
assign m_axis_memory_write_tdata=beat_data;
assign m_axis_memory_write_tkeep=beat_keep;
assign m_axis_memory_write_tlast=beat_last;
assign m_axis_memory_write_tvalid=beat_valid && placement;
assign m_axis_hls_read_tdata=beat_data;
assign m_axis_hls_read_tkeep=beat_keep;
assign m_axis_hls_read_tlast=beat_last;
assign m_axis_hls_read_tvalid=beat_valid && !placement;
wire beat_transfer=beat_valid && (placement ? m_axis_memory_write_tready : m_axis_hls_read_tready);
assign s_memory_status_ready=active && issued && !m_memory_event_valid && !beat_valid &&
    status_known && s_memory_status_tag==tag && (data_done || s_memory_status_error!=0) && !fault && !rst;
wire downstream_held=qpn<MAX_QPS && downstream_queue_guard[qpn]===1'b1 &&
    (^downstream_queue_guard)!==1'bx;
integer lane;
initial if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed executor QP capacity");
always @(posedge clk)begin
    if(rst)begin
        active<=0;raw_seen<=0;issued<=0;placement_seen<=0;data_done<=0;remaining<=0;
        beat_data<=0;beat_keep<=0;beat_last<=0;beat_valid<=0;m_memory_command_valid<=0;
        m_memory_event_context<=0;m_memory_event_error<=0;m_memory_event_valid<=0;
        fault<=0;fault_code<=0;owner_count<=0;command_count<=0;memory_status_count<=0;
    end else begin
        if(s_owner_valid && s_owner_ready)begin
            active<=1;raw_seen<=0;issued<=0;placement_seen<=0;data_done<=0;remaining<=in_length;
            m_memory_event_context<=s_owner_context;m_memory_event_error<=in_error;
            m_memory_event_valid<=!in_authorized;owner_count<=owner_count+1'b1;
        end
        if(s_read_response_valid && s_read_response_ready)placement_seen<=1;
        if(selected_valid && take_raw)begin raw_seen<=1;m_memory_command_valid<=1;end
        // Already-offered command/beat/event cannot be retracted by halt,
        // disable or fault. A fault quarantines the lifetime, not reset/drain.
        if(m_memory_command_valid && m_memory_command_ready)begin
            m_memory_command_valid<=0;issued<=1;command_count<=command_count+1'b1;
        end
        if(input_valid && take_data)begin
            for(lane=0;lane<64;lane=lane+1)beat_data[lane*8+:8]<=input_keep[lane] ? input_data[lane*8+:8] : 8'd0;
            beat_keep<=input_keep;beat_last<=input_last;beat_valid<=1;
            remaining<=remaining<=64 ? 0 : remaining-64;
        end
        if(beat_transfer)begin beat_valid<=0;if(beat_last)data_done<=1;end
        if(s_memory_status_valid && s_memory_status_ready)begin
            m_memory_event_error<=s_memory_status_error;m_memory_event_valid<=1;
            memory_status_count<=memory_status_count+1'b1;
            if(s_memory_status_error!=0)begin fault<=1;fault_code<=8'h89;end
        end
        if(m_memory_event_valid && m_memory_event_ready && downstream_held)begin
            m_memory_event_valid<=0;
            if(!fault && m_memory_event_error==0)begin active<=0;issued<=0;end
            // A denied WQE owns no DMA, but its error/identity is now retained
            // by the real error/CQ owner. Backend DMA errors never release.
            if(!fault && !authorized)active<=0;
        end
        if(!fault)begin
            if(bad_owner)begin fault<=1;fault_code<=8'h81;end
            if(raw_bad)begin fault<=1;fault_code<=8'h82;end
            if(response_bad)begin fault<=1;fault_code<=8'h83;end
            if(active && issued && !data_done && remaining!=0 && !beat_valid && input_valid && !shape_ok)begin fault<=1;fault_code<=8'h84;end
            if((s_axis_hls_write_tvalid || s_axis_memory_read_tvalid) &&
               (!active || !authorized || (placement ? s_axis_memory_read_tvalid : s_axis_hls_write_tvalid) ||
                (issued && (data_done || remaining==0) && !m_memory_event_valid)))begin fault<=1;fault_code<=8'h85;end
            if((s_memory_status_valid!==1'b0 && s_memory_status_valid!==1'b1) ||
               (s_memory_status_valid && (!active || !issued || m_memory_event_valid || !status_known || s_memory_status_tag!=tag)))begin fault<=1;fault_code<=8'h86;end
            if(m_memory_event_valid && m_memory_event_ready && !downstream_held)begin fault<=1;fault_code<=8'h87;end
            if((s_axis_hls_write_tvalid!==1'b0 && s_axis_hls_write_tvalid!==1'b1) ||
               (s_axis_memory_read_tvalid!==1'b0 && s_axis_memory_read_tvalid!==1'b1))begin fault<=1;fault_code<=8'h88;end
        end
    end
end
endmodule
`resetall
