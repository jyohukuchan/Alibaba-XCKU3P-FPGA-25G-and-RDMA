// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Registered contiguous-span authorization/translation primitive.
// Not yet connected to the native endpoint; no memory/DMA is performed here.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_mr_table #(
    parameter ENTRY_COUNT = 8,
    parameter INDEX_WIDTH = $clog2(ENTRY_COUNT),
    parameter [31:0] INITIAL_GENERATION = 0,
    // Legacy standalone mode defaults off; live responders MUST require it.
    parameter REQUIRE_EPOCH = 0
)(
    input wire clk,
    input wire rst,
    // Trusted management. quiescent MUST cover every outstanding memory lease,
    // not merely this lookup pipeline. Invalidation does not cancel a DMA.
    input wire cfg_quiescent,
    input wire [1:0] cfg_command,
    input wire [INDEX_WIDTH-1:0] cfg_index,
    input wire [15:0] cfg_pd,
    input wire [31:0] cfg_key,
    input wire [63:0] cfg_virtual_address,
    input wire [63:0] cfg_dma_address,
    input wire [63:0] cfg_length,
    // Bits match the basic ib_access_flags: local write, remote write,
    // remote read, remote atomic. Local read permission is implicit.
    input wire [3:0] cfg_access,
    input wire cfg_valid,
    output wire cfg_ready,
    output reg [7:0] cfg_response_error = 0,
    output reg [31:0] cfg_response_key = 0,
    output reg cfg_response_valid = 0,
    input wire cfg_response_ready,
    output reg epoch_configured = !REQUIRE_EPOCH,
    // PD must come from a validated QP/context, NEVER from the remote packet.
    input wire [15:0] s_request_pd,
    input wire [31:0] s_request_key,
    input wire [63:0] s_request_address,
    input wire [31:0] s_request_length,
    // 0 local read, 1 local write, 2 remote read, 3 remote write, 4 atomic.
    input wire [2:0] s_request_operation,
    input wire [15:0] s_request_tag,
    input wire s_request_valid,
    output wire s_request_ready,
    output reg [15:0] m_response_tag = 0,
    output reg [7:0] m_response_error = 0,
    output reg [63:0] m_response_offset = 0,
    output reg [63:0] m_response_dma_address = 0,
    output reg [31:0] m_response_length = 0,
    output wire m_response_valid,
    input wire m_response_ready
);

localparam GENERATION_WIDTH = 32-INDEX_WIDTH;
localparam [GENERATION_WIDTH-1:0] MAX_GENERATION = {GENERATION_WIDTH{1'b1}};
localparam [1:0] REGISTER=1, INVALIDATE=2, SET_EPOCH=3;
localparam [7:0] OK=0, ERR_KEY=1, ERR_PD=2, ERR_PERMISSION=3,
    ERR_RANGE=4, ERR_OPERATION=5, ERR_BUSY=6, ERR_EXHAUSTED=7,
    ERR_CONFIG=8, ERR_ALIGNMENT=9, ERR_EPOCH=10;
localparam [2:0] IDLE=0, CHECK=1, RESPONSE=2, CFG_SUM=3, CFG_APPLY=4;
reg [2:0] state=IDLE;
reg valid_table[0:ENTRY_COUNT-1];
reg [GENERATION_WIDTH-1:0] generation_table[0:ENTRY_COUNT-1];
reg [15:0] pd_table[0:ENTRY_COUNT-1];
reg [63:0] va_table[0:ENTRY_COUNT-1];
reg [63:0] dma_table[0:ENTRY_COUNT-1];
reg [63:0] length_table[0:ENTRY_COUNT-1];
reg [3:0] access_table[0:ENTRY_COUNT-1];
reg saved_valid=0;
reg [31:0] saved_key=0, request_key=0;
reg [15:0] saved_pd=0, request_pd=0, request_tag=0;
reg [63:0] saved_va=0, saved_dma=0, saved_length=0, request_address=0;
reg [31:0] request_length=0;
reg [3:0] saved_access=0;
reg [2:0] request_operation=0;
wire [INDEX_WIDTH-1:0] request_index=s_request_key[INDEX_WIDTH-1:0];
reg [1:0] management_command=0;
reg [INDEX_WIDTH-1:0] management_index=0;
reg [15:0] management_pd=0, management_saved_pd=0;
reg [31:0] management_key=0;
reg [63:0] management_va=0, management_dma=0, management_length=0;
reg [3:0] management_access=0;
reg management_saved_valid=0;
reg [GENERATION_WIDTH-1:0] management_generation=0;
reg [64:0] cfg_va_end=0, cfg_dma_end=0;
wire config_range_ok=management_length!=0 &&
    (!cfg_va_end[64] || cfg_va_end[63:0]==0) &&
    (!cfg_dma_end[64] || cfg_dma_end[63:0]==0);
wire config_access_ok=!(management_access[1] || management_access[3]) || management_access[0];
wire [GENERATION_WIDTH-1:0] next_generation=management_generation+1'b1;
wire [31:0] current_cfg_key={management_generation,management_index};
wire [63:0] offset=request_address-saved_va;
wire [64:0] requested_end={1'b0,offset}+{33'd0,request_length};
wire range_ok=request_length!=0 && request_address>=saved_va &&
    requested_end<={1'b0,saved_length};
wire [63:0] translated_address=saved_dma+offset;
reg permission_ok;
always @* begin
    case(request_operation)
        0: permission_ok=1'b1;
        1: permission_ok=saved_access[0];
        2: permission_ok=saved_access[2];
        3: permission_ok=saved_access[1];
        4: permission_ok=saved_access[3];
        default: permission_ok=1'b0;
    endcase
end

assign cfg_ready=state==IDLE && !cfg_response_valid && cfg_quiescent && !rst;
wire cfg_transfer=cfg_valid && cfg_ready;
assign s_request_ready=state==IDLE && !cfg_response_valid && !cfg_transfer && epoch_configured && !rst;
assign m_response_valid=state==RESPONSE && !rst;

integer i;
initial begin
    if(ENTRY_COUNT<2 || ENTRY_COUNT>256 || (1<<INDEX_WIDTH)!=ENTRY_COUNT ||
        INITIAL_GENERATION>MAX_GENERATION) begin
        $error("Unsupported MR table parameters");$finish;
    end
end

always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;cfg_response_valid<=0;cfg_response_error<=0;cfg_response_key<=0;
        m_response_tag<=0;m_response_error<=0;m_response_offset<=0;
        m_response_dma_address<=0;m_response_length<=0;
        saved_valid<=0;saved_key<=0;request_key<=0;saved_pd<=0;request_pd<=0;
        request_tag<=0;saved_va<=0;saved_dma<=0;saved_length<=0;
        request_address<=0;request_length<=0;saved_access<=0;request_operation<=0;
        epoch_configured<=!REQUIRE_EPOCH;
        management_command<=0;management_index<=0;management_pd<=0;management_saved_pd<=0;
        management_key<=0;management_va<=0;management_dma<=0;management_length<=0;
        management_access<=0;management_saved_valid<=0;management_generation<=0;cfg_va_end<=0;cfg_dma_end<=0;
        for(i=0;i<ENTRY_COUNT;i=i+1) begin
            valid_table[i]<=0;generation_table[i]<=INITIAL_GENERATION;
            pd_table[i]<=0;va_table[i]<=0;dma_table[i]<=0;
            length_table[i]<=0;access_table[i]<=0;
        end
    end else begin
        if(cfg_response_valid && cfg_response_ready) cfg_response_valid<=0;
        case(state)
            IDLE: if(cfg_transfer) begin
                management_command<=cfg_command;management_index<=cfg_index;
                management_pd<=cfg_pd;management_key<=cfg_key;
                management_va<=cfg_virtual_address;management_dma<=cfg_dma_address;
                management_length<=cfg_length;management_access<=cfg_access;
                management_saved_valid<=valid_table[cfg_index];
                management_saved_pd<=pd_table[cfg_index];
                management_generation<=generation_table[cfg_index];
                state<=CFG_SUM;
            end else if(s_request_valid && s_request_ready) begin
                saved_valid<=valid_table[request_index];
                saved_key<={generation_table[request_index],request_index};
                saved_pd<=pd_table[request_index];saved_va<=va_table[request_index];
                saved_dma<=dma_table[request_index];saved_length<=length_table[request_index];
                saved_access<=access_table[request_index];
                request_key<=s_request_key;request_pd<=s_request_pd;
                request_address<=s_request_address;request_length<=s_request_length;
                request_operation<=s_request_operation;request_tag<=s_request_tag;
                state<=CHECK;
            end
            CFG_SUM: begin
                cfg_va_end<={1'b0,management_va}+{1'b0,management_length};
                cfg_dma_end<={1'b0,management_dma}+{1'b0,management_length};
                state<=CFG_APPLY;
            end
            CFG_APPLY: begin
            cfg_response_valid<=1;cfg_response_error<=OK;cfg_response_key<=0;
            state<=IDLE;
            // A caller that loses external lease quiescence after admission
            // gets BUSY, never a mutation of possibly live memory metadata.
            if(!cfg_quiescent) cfg_response_error<=ERR_BUSY;
            else if(REQUIRE_EPOCH && !epoch_configured && management_command!=SET_EPOCH)
                cfg_response_error<=ERR_EPOCH;
            else case(management_command)
                REGISTER: begin
                    if(management_saved_valid) cfg_response_error<=ERR_BUSY;
                    else if(!config_range_ok || !config_access_ok || management_key!=0)
                        cfg_response_error<=ERR_CONFIG;
                    else if(management_generation==MAX_GENERATION)
                        cfg_response_error<=ERR_EXHAUSTED;
                    else begin
                        valid_table[management_index]<=1;generation_table[management_index]<=next_generation;
                        pd_table[management_index]<=management_pd;va_table[management_index]<=management_va;
                        dma_table[management_index]<=management_dma;length_table[management_index]<=management_length;
                        access_table[management_index]<=management_access;
                        cfg_response_key<={next_generation,management_index};
                    end
                end
                INVALIDATE: begin
                    if(!management_saved_valid || management_key!=current_cfg_key)
                        cfg_response_error<=ERR_KEY;
                    else if(management_pd!=management_saved_pd) cfg_response_error<=ERR_PD;
                    else begin
                        valid_table[management_index]<=0;
                        // Keep generation: a later registration MUST get a new key.
                        pd_table[management_index]<=0;va_table[management_index]<=0;
                        dma_table[management_index]<=0;length_table[management_index]<=0;
                        access_table[management_index]<=0;
                    end
                end
                SET_EPOCH: begin
                    if(!REQUIRE_EPOCH) cfg_response_error<=ERR_OPERATION;
                    else if(epoch_configured) cfg_response_error<=ERR_BUSY;
                    else if((management_key>>GENERATION_WIDTH)!=0 || management_key[GENERATION_WIDTH-1:0]==MAX_GENERATION)
                        cfg_response_error<=ERR_CONFIG;
                    else begin
                        for(i=0;i<ENTRY_COUNT;i=i+1) generation_table[i]<=management_key[GENERATION_WIDTH-1:0];
                        epoch_configured<=1;cfg_response_key<=management_key;
                    end
                end
                default: cfg_response_error<=ERR_OPERATION;
            endcase
            end
            CHECK: begin
                m_response_tag<=request_tag;m_response_error<=OK;
                // No translated addresses, extent or stale contents on denial.
                m_response_offset<=0;m_response_dma_address<=0;m_response_length<=0;
                if(!saved_valid || saved_key!=request_key) m_response_error<=ERR_KEY;
                else if(saved_pd!=request_pd) m_response_error<=ERR_PD;
                else if(request_operation>4) m_response_error<=ERR_OPERATION;
                else if(!permission_ok) m_response_error<=ERR_PERMISSION;
                else if(!range_ok) m_response_error<=ERR_RANGE;
                else if(request_operation==4 &&
                    (request_length!=8 || request_address[2:0]!=0 || translated_address[2:0]!=0))
                    m_response_error<=ERR_ALIGNMENT;
                else begin
                    m_response_offset<=offset;m_response_dma_address<=translated_address;
                    m_response_length<=request_length;
                end
                state<=RESPONSE;
            end
            RESPONSE: if(m_response_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
end
endmodule
`resetall
