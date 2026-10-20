// SPDX-License-Identifier: BSD-2-Clause-Views
// Retained full-WR, whole-IP-frame native retransmission owner. This is the
// real timeout/retry/RNR consumer, not a policy shadow or a CPU payload copy.
// Each attempt obtains a fresh actual MAC owner/tag and waits for receipt,
// EOF and tail proof. Only one final MAC proof goes to the WR lifetime.
// A retry error retains all cache/WR/MR ownership; it is NOT an error CQE or
// permission to unpin. Exact lifetime commit + real core drain stay required.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_replay #(
    parameter MAX_QPS=8,
    parameter CLOCK_PERIOD_PS=4000,
    parameter FRAME_WORDS=260
)(
    input wire clk,
    input wire rst,
    input wire [23:0] cfg_qpn,
    input wire [15:0] cfg_pd,
    input wire [63:0] cfg_cookie,
    input wire [63:0] cfg_epoch,
    input wire [4:0] cfg_timeout,
    input wire [2:0] cfg_retry,
    input wire [2:0] cfg_rnr_retry,
    input wire cfg_valid,
    output wire cfg_ready,
    output reg [23:0] rsp_qpn=0,
    output reg [15:0] rsp_pd=0,
    output reg [63:0] rsp_cookie=0,
    output reg [63:0] rsp_epoch=0,
    output reg [4:0] rsp_timeout=0,
    output reg [2:0] rsp_retry=0,
    output reg [2:0] rsp_rnr_retry=0,
    output reg [7:0] rsp_error=0,
    output reg rsp_valid=0,
    input wire rsp_ready,
    input wire [587:0] s_owner_context,
    input wire [47:0] s_owner_local_mac,
    input wire [47:0] s_owner_peer_mac,
    input wire s_owner_valid,
    output wire s_owner_ready,
    input wire [127:0] s_axis_ip_tdata,
    input wire [15:0] s_axis_ip_tkeep,
    input wire s_axis_ip_tvalid,
    output wire s_axis_ip_tready,
    input wire s_axis_ip_tlast,
    input wire s_axis_ip_tuser,
    output reg [127:0] m_axis_ip_tdata=0,
    output reg [15:0] m_axis_ip_tkeep=0,
    output reg m_axis_ip_tlast=0,
    output reg m_axis_ip_tvalid=0,
    input wire m_axis_ip_tready,
    output wire [587:0] m_replay_context,
    output wire [47:0] m_replay_local_mac,
    output wire [47:0] m_replay_peer_mac,
    output wire m_replay_valid,
    input wire m_replay_ready,
    input wire [587:0] s_mac_context,
    input wire [7:0] s_mac_error,
    input wire s_mac_valid,
    output wire s_mac_ready,
    input wire [23:0] issued_psn,
    input wire [587:0] s_positive_context,
    input wire s_positive_valid,
    input wire [587:0] s_control_context,
    input wire [23:0] s_control_psn,
    input wire [7:0] s_control_syndrome,
    input wire s_control_valid,
    output wire s_control_ready,
    output wire [587:0] m_done_context,
    output reg m_done_valid=0,
    input wire m_done_ready,
    input wire [587:0] s_retire_context,
    input wire s_retire_valid,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output wire io_drained,
    output reg failed=0,
    output reg [7:0] failure_status=0,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] attempt_count=0,
    output reg [31:0] retry_count=0,
    output reg [31:0] rnr_count=0
);
localparam CAPTURE=0,SEND=1,WAIT_MAC=2,WAIT_TIMER=3,REOWNER=4,HOLD=5,FAILED=6;
reg [2:0] state=CAPTURE;
reg active=0,acked=0,done_sent=0;
reg send_committed=0;
reg [587:0] owner=0;
reg [47:0] local_mac=0,peer_mac=0;
reg [127:0] cache_data[0:FRAME_WORDS-1];
reg [15:0] cache_keep[0:FRAME_WORDS-1];
reg [8:0] words=0,send_index=0;
reg [15:0] bytes=0;
reg [63:0] clock_count=0,deadline_start=0,deadline_ticks=0;
reg deadline_enabled=0;
reg [1:0] retry_kind=0; // 0 ACK timeout, 1 sequence NAK, 2 RNR delay
reg [2:0] retries_left=0,rnr_left=0;
reg [4:0] timeout=0;
reg [MAX_QPS-1:0] configured=0;
reg [15:0] policy_pd[0:MAX_QPS-1];
reg [63:0] policy_cookie[0:MAX_QPS-1],policy_epoch[0:MAX_QPS-1];
reg [4:0] policy_timeout[0:MAX_QPS-1];
reg [2:0] policy_retry[0:MAX_QPS-1],policy_rnr[0:MAX_QPS-1];
reg cfg_verify=0;
reg [23:0] cfg_saved_qpn=0;
wire [23:0] in_qpn=s_owner_context[395:372],held_qpn=owner[395:372];
wire [15:0] in_pd=s_owner_context[371:356];
wire [63:0] in_epoch=s_owner_context[459:396];
wire owner_known=(^{s_owner_context,s_owner_local_mac,s_owner_peer_mac})!==1'bx;
wire owner_ok=owner_known && in_qpn<MAX_QPS && in_epoch!=0 && s_owner_context[523:460]!=0 &&
    s_owner_context[355:340]!=0 && s_owner_context[19:2]==0 && s_owner_context[1:0]==3 &&
    configured[in_qpn[2:0]] && in_pd==policy_pd[in_qpn[2:0]] && in_epoch==policy_epoch[in_qpn[2:0]];
wire cfg_known=(^{cfg_qpn,cfg_pd,cfg_cookie,cfg_epoch,cfg_timeout,cfg_retry,cfg_rnr_retry})!==1'bx;
wire cfg_ok=cfg_known && cfg_qpn<MAX_QPS && cfg_pd!=0 && cfg_cookie!=0 && cfg_epoch!=0;
assign cfg_ready=!active && !cfg_verify && !rsp_valid && !fault && !rst;
assign s_owner_ready=!active && !cfg_verify && !rsp_valid && !cfg_valid && owner_ok && !fault && !rst;
assign s_axis_ip_tready=active && state==CAPTURE && words<FRAME_WORDS && !fault && !failed && !rst;
assign m_replay_context=owner;assign m_replay_local_mac=local_mac;assign m_replay_peer_mac=peer_mac;
// Persistent owner offer: an ACK/fault after this offer cannot withdraw it.
assign m_replay_valid=active && state==REOWNER && !rst;
assign s_mac_ready=active && state==WAIT_MAC && s_mac_context===owner && !rst;
assign m_done_context=owner;
assign io_drained=(!active || state==HOLD && done_sent) && !m_axis_ip_tvalid && !failed && !fault && !rst;
assign busy=active || cfg_verify || rsp_valid || fault;
assign queue_guard=fault ? {MAX_QPS{1'b1}} : active ?
    ({{(MAX_QPS-1){1'b0}},1'b1}<<held_qpn) :
    (s_owner_valid && owner_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : 0;
wire positive_match=active && (^s_positive_context)!==1'bx && s_positive_context==owner;
wire positive_now=s_positive_valid && positive_match;
wire terminal_ack=acked || positive_now;
wire control_match=active && (^{s_control_context,s_control_psn,s_control_syndrome,issued_psn})!==1'bx &&
    s_control_context==owner && s_control_psn==issued_psn;
assign s_control_ready=active && control_match && !rst;
function [63:0] ack_ticks;
    input [4:0] exponent;
    reg [63:0] ps;
    begin ps=64'd4096000<<exponent;ack_ticks=(ps+CLOCK_PERIOD_PS-1)/CLOCK_PERIOD_PS;end
endfunction
function [63:0] rnr_ticks;
    input [4:0] code;
    reg [31:0] us;
    begin
        case(code)
        0:us=655360;1:us=10;2:us=20;3:us=30;4:us=40;5:us=60;6:us=80;7:us=120;
        8:us=160;9:us=240;10:us=320;11:us=480;12:us=640;13:us=960;14:us=1280;15:us=1920;
        16:us=2560;17:us=3840;18:us=5120;19:us=7680;20:us=10240;21:us=15360;22:us=20480;23:us=30720;
        24:us=40960;25:us=61440;26:us=81920;27:us=122880;28:us=163840;29:us=245760;30:us=327680;31:us=491520;
        endcase
        rnr_ticks=(64'd1000000*us+CLOCK_PERIOD_PS-1)/CLOCK_PERIOD_PS;
    end
endfunction
wire [63:0] elapsed=clock_count-deadline_start;
wire expired=deadline_enabled && elapsed>=deadline_ticks;
reg [4:0] beat_bytes;
reg beat_known;
always @*begin
    beat_bytes=0;beat_known=1;
    for(integer j=0;j<16;j=j+1)begin
        beat_bytes=beat_bytes+s_axis_ip_tkeep[j];
        if(s_axis_ip_tkeep[j] && (^s_axis_ip_tdata[j*8+:8])===1'bx)beat_known=0;
    end
end
wire frame_shape=(^{s_axis_ip_tkeep,s_axis_ip_tlast,s_axis_ip_tuser})!==1'bx && beat_known &&
    s_axis_ip_tkeep!=0 && !(|(s_axis_ip_tkeep[15:1]&~s_axis_ip_tkeep[14:0])) &&
    (s_axis_ip_tlast || s_axis_ip_tkeep==16'hffff) && !s_axis_ip_tuser &&
    {1'b0,bytes}+beat_bytes<=4156;
task fail_work;
    input [7:0] status;
    begin failed<=1;failure_status<=status;deadline_enabled<=0;
        if(state==WAIT_TIMER || state==HOLD)state<=FAILED;
    end
endtask
integer i;
initial if(MAX_QPS!=8 || FRAME_WORDS!=260 || CLOCK_PERIOD_PS<1 || CLOCK_PERIOD_PS>1000000)
    $fatal(1,"unreviewed retained replay geometry/clock contract");
always @(posedge clk)begin
    if(rst)begin
        active<=0;acked<=0;done_sent<=0;send_committed<=0;owner<=0;local_mac<=0;peer_mac<=0;
        state<=CAPTURE;words<=0;send_index<=0;bytes<=0;clock_count<=0;
        deadline_start<=0;deadline_ticks<=0;deadline_enabled<=0;retry_kind<=0;
        retries_left<=0;rnr_left<=0;timeout<=0;configured<=0;cfg_verify<=0;cfg_saved_qpn<=0;
        rsp_valid<=0;rsp_error<=0;rsp_qpn<=0;rsp_pd<=0;rsp_cookie<=0;rsp_epoch<=0;
        rsp_timeout<=0;rsp_retry<=0;rsp_rnr_retry<=0;
        m_axis_ip_tvalid<=0;m_axis_ip_tdata<=0;m_axis_ip_tkeep<=0;m_axis_ip_tlast<=0;
        m_done_valid<=0;failed<=0;failure_status<=0;fault<=0;fault_code<=0;
        attempt_count<=0;retry_count<=0;rnr_count<=0;
        for(i=0;i<MAX_QPS;i=i+1)begin policy_pd[i]<=0;policy_cookie[i]<=0;policy_epoch[i]<=0;
            policy_timeout[i]<=0;policy_retry[i]<=0;policy_rnr[i]<=0;end
    end else begin
        clock_count<=clock_count+1'b1;
        if(rsp_valid && rsp_ready)rsp_valid<=0;
        if(cfg_valid && cfg_ready)begin
            rsp_qpn<=cfg_qpn;rsp_pd<=cfg_pd;rsp_cookie<=cfg_cookie;rsp_epoch<=cfg_epoch;
            rsp_timeout<=cfg_timeout;rsp_retry<=cfg_retry;rsp_rnr_retry<=cfg_rnr_retry;
            rsp_error<=cfg_ok ? 0 : 8'h01;
            if(cfg_ok)begin
                configured[cfg_qpn[2:0]]<=1;policy_pd[cfg_qpn[2:0]]<=cfg_pd;
                policy_cookie[cfg_qpn[2:0]]<=cfg_cookie;policy_epoch[cfg_qpn[2:0]]<=cfg_epoch;
                policy_timeout[cfg_qpn[2:0]]<=cfg_timeout;policy_retry[cfg_qpn[2:0]]<=cfg_retry;
                policy_rnr[cfg_qpn[2:0]]<=cfg_rnr_retry;cfg_saved_qpn<=cfg_qpn;cfg_verify<=1;
            end else rsp_valid<=1;
        end
        if(cfg_verify)begin
            // Actual table readback after its write, not a shadow echo.
            rsp_qpn<=cfg_saved_qpn;rsp_pd<=policy_pd[cfg_saved_qpn[2:0]];
            rsp_cookie<=policy_cookie[cfg_saved_qpn[2:0]];rsp_epoch<=policy_epoch[cfg_saved_qpn[2:0]];
            rsp_timeout<=policy_timeout[cfg_saved_qpn[2:0]];rsp_retry<=policy_retry[cfg_saved_qpn[2:0]];
            rsp_rnr_retry<=policy_rnr[cfg_saved_qpn[2:0]];rsp_valid<=1;cfg_verify<=0;
        end
        if(s_owner_valid && s_owner_ready)begin
            active<=1;owner<=s_owner_context;local_mac<=s_owner_local_mac;peer_mac<=s_owner_peer_mac;
            state<=CAPTURE;acked<=0;done_sent<=0;send_committed<=0;words<=0;send_index<=0;bytes<=0;
            timeout<=policy_timeout[in_qpn[2:0]];retries_left<=policy_retry[in_qpn[2:0]];
            rnr_left<=policy_rnr[in_qpn[2:0]];retry_kind<=0;deadline_enabled<=0;
            m_done_valid<=0;failed<=0;failure_status<=0;
        end
        if(s_axis_ip_tvalid && s_axis_ip_tready)begin
            if(!frame_shape)begin fault<=1;fault_code<=8'hd1;end
            cache_data[words]<=s_axis_ip_tdata;cache_keep[words]<=s_axis_ip_tkeep;
            words<=words+1'b1;bytes<=bytes+beat_bytes;
            if(s_axis_ip_tlast)begin send_index<=0;state<=SEND;end
        end
        // Already offered frame beats drain even after a late ACK or fault.
        if(active && state==SEND && !m_axis_ip_tvalid && (!fault || send_committed))begin
            m_axis_ip_tdata<=cache_data[send_index];m_axis_ip_tkeep<=cache_keep[send_index];
            m_axis_ip_tlast<=send_index+1==words;m_axis_ip_tvalid<=1;send_committed<=1;
        end
        if(m_axis_ip_tvalid && m_axis_ip_tready)begin
            m_axis_ip_tvalid<=0;
            if(m_axis_ip_tlast)begin state<=WAIT_MAC;send_committed<=0;attempt_count<=attempt_count+1'b1;end
            else send_index<=send_index+1'b1;
        end
        if(s_mac_valid && s_mac_ready)begin
            if(s_mac_error!=0)fail_work(s_mac_error);
            if(failed || s_mac_error!=0)state<=FAILED;
            else if(terminal_ack)begin m_done_valid<=1;state<=HOLD;end
            else begin
                state<=WAIT_TIMER;
                if(retry_kind==0)begin deadline_start<=clock_count;deadline_ticks<=ack_ticks(timeout);deadline_enabled<=timeout!=0;end
            end
        end
        if(positive_now)begin acked<=1;deadline_enabled<=0;end
        if(active && state==WAIT_TIMER && !failed)begin
            if(terminal_ack)begin m_done_valid<=1;state<=HOLD;deadline_enabled<=0;end
            else if(expired && !s_control_valid)begin
                if((retry_kind==2 ? rnr_left : retries_left)==0)fail_work(retry_kind==2 ? 8'd13 : 8'd12);
                else begin
                    if(retry_kind==2)begin if(rnr_left!=7)rnr_left<=rnr_left-1'b1;end
                    else if(retries_left!=7)retries_left<=retries_left-1'b1;
                    state<=REOWNER;deadline_enabled<=0;retry_count<=retry_count+1'b1;
                end
            end
        end
        if(m_replay_valid && m_replay_ready)begin state<=SEND;send_index<=0;retry_kind<=0;end
        if(s_control_valid && s_control_ready && !terminal_ack && !failed)begin
            if(s_control_syndrome[7:5]==1)begin
                if(retry_kind!=2)begin
                    retry_kind<=2;deadline_start<=clock_count;
                    deadline_ticks<=rnr_ticks(s_control_syndrome[4:0]);deadline_enabled<=1;rnr_count<=rnr_count+1'b1;
                    if(rnr_left==0)fail_work(8'd13);
                end
            end else if(s_control_syndrome==8'h60)begin
                retry_kind<=1;deadline_start<=clock_count;deadline_ticks<=0;deadline_enabled<=1;
            end else if(s_control_syndrome==8'h62)fail_work(8'd10);
            else if(s_control_syndrome==8'h63)fail_work(8'd11);
            else fail_work(8'd9);
        end
        if(m_done_valid && m_done_ready)begin m_done_valid<=0;done_sent<=1;end
        if(s_retire_valid)begin
            if(active && io_drained && s_retire_context===owner)begin active<=0;words<=0;done_sent<=0;acked<=0;end
            else begin fault<=1;fault_code<=8'hd2;end
        end
        if(s_positive_valid && !positive_match || s_control_valid && !control_match ||
           s_mac_valid && (!active || s_mac_context!==owner || state!=WAIT_MAC))begin fault<=1;fault_code<=8'hd3;end
    end
end
endmodule
`resetall
