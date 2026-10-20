// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Trusted coherent DMA64 SQ rings ->64-byte fetched records/trusted contexts.
// This is a DMA CLIENT, not a PCIe engine, queue allocator, verbs provider or
// RDMA completion source. Caller owns coherent mappings and WR/MR/QP refs.
// A result/consumer advance only retires descriptor storage, NEVER an RDMA WR.
// Reset does not cancel DMA/unpin pages: require real drain + fresh host epochs.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_sq_fetch #(
    parameter MAX_QPS=8,
    parameter SEPARATE_RQ_ENABLE=0,
    parameter RECV_CANCEL_ENABLE=0,
    parameter [15:0] INITIAL_TAG=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    // Direction is trusted management metadata, never a fetched opcode/QPN bit.
    input wire cfg_receive,
    input wire [1:0] admission_available,
    input wire [MAX_QPS-1:0] receive_downstream_guard,
    output wire [MAX_QPS-1:0] receive_queue_guard,
    output wire [MAX_QPS-1:0] receive_queue_active,
    output wire [MAX_QPS-1:0] receive_queue_pending,
    output wire [MAX_QPS-1:0] receive_queue_halted,
    output wire m_result_receive,
    // Trusted, serialized management, not bytes fetched from host memory.
    //1allocate,2publish producer,3retire/cancel unfetched tail. Replies are
    // NOT CQEs/unpin proof. Software still owns every uncompleted WR reference.
    input wire [1:0] cfg_command,
    input wire [23:0] cfg_qpn,
    input wire [15:0] cfg_pd,
    input wire [63:0] cfg_epoch,
    input wire [63:0] cfg_dma_base,
    input wire [3:0] cfg_log_depth,
    input wire [63:0] cfg_producer,
    input wire cfg_valid,
    output wire cfg_ready,
    output reg [7:0] cfg_response_error=0,
    output reg [23:0] cfg_response_qpn=0,
    output reg [63:0] cfg_response_epoch=0,
    output reg [63:0] cfg_response_consumer=0,
    output reg cfg_response_valid=0,
    input wire cfg_response_ready,
    // Must be real parent descriptor/TLP/RAM drain and actual downstream work
    // ownership. Never derive either from this controller's idle flag.
    input wire parent_dma_drained,
    input wire [MAX_QPS-1:0] downstream_queue_guard,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire [MAX_QPS-1:0] queue_active,
    // Posted but not yet handed off records are separate from an MR lease.
    // Use this for route/QP lifetime exclusion, never as a completion count.
    output wire [MAX_QPS-1:0] queue_pending,
    output wire [MAX_QPS-1:0] queue_halted,
    // Connect to the actual Corundum read backend, not a CPU payload copy.
    output wire [63:0] m_command_address,
    output wire [31:0] m_command_length,
    output wire [15:0] m_command_tag,
    output wire m_command_valid,
    input wire m_command_ready,
    input wire [511:0] s_axis_read_tdata,
    input wire [63:0] s_axis_read_tkeep,
    input wire s_axis_read_tlast,
    input wire s_axis_read_tvalid,
    output wire s_axis_read_tready,
    input wire [15:0] s_status_tag,
    input wire [7:0] s_status_error,
    input wire s_status_valid,
    output wire s_status_ready,
    // On read error data is all0, queue halts, context identifies the failed
    // fetch. Route errors to trusted recovery, NEVER into WQE authorization.
    output wire [511:0] m_result_data,
    output wire [7:0] m_result_error,
    output wire [23:0] m_result_qpn,
    output wire [15:0] m_result_pd,
    output wire [63:0] m_result_epoch,
    output wire [63:0] m_result_sequence,
    output wire [15:0] m_result_tag,
    output wire m_result_valid,
    input wire m_result_ready,
    output wire busy,
    output wire tag_exhausted,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] fetch_count=0,
    output reg [31:0] result_count=0
);
localparam [2:0] IDLE=0,COMMAND=1,READ=2,RESULT=3,FAULT=4;
localparam [7:0] ERR_QPN=16,ERR_EPOCH=17,ERR_RANGE=18,ERR_BUSY=19,
    ERR_COMMAND=20,ERR_PRODUCER=21,ERR_HALTED=22,
    FAULT_DATA=64,FAULT_STATUS=65,FAULT_UNEXPECTED=66,FAULT_STATE=67;
reg [2:0] state=IDLE;
localparam SLOTS=SEPARATE_RQ_ENABLE ? 2*MAX_QPS : MAX_QPS;
localparam INDEX_WIDTH=SEPARATE_RQ_ENABLE ? 4 : 3;
reg [SLOTS-1:0] active=0,halted=0;
reg [63:0] base_table[0:SLOTS-1],epoch_table[0:SLOTS-1];
reg [63:0] producer_table[0:SLOTS-1],consumer_table[0:SLOTS-1];
reg [15:0] pd_table[0:SLOTS-1];
reg [3:0] depth_table[0:SLOTS-1];
reg [INDEX_WIDTH-1:0] cursor=0,selected=0;
reg [63:0] address=0,epoch=0,expected_sequence=0;
reg [15:0] pd=0,last_tag=INITIAL_TAG;
reg [511:0] data=0;
reg data_seen=0,status_seen=0;
reg [7:0] error=0;
reg found;
reg [INDEX_WIDTH-1:0] chosen;
integer scan,index;
always @* begin
    found=0;chosen=cursor;
    for(scan=0;scan<SLOTS;scan=scan+1)begin
        index=cursor+scan;if(index>=SLOTS)index=index-SLOTS;
        if(!found && active[index] && !halted[index] && producer_table[index]>consumer_table[index] &&
           (!SEPARATE_RQ_ENABLE || admission_available[index>=MAX_QPS]===1'b1))begin
            found=1;chosen=index;
        end
    end
end
wire cfg_qpn_ok=cfg_qpn<MAX_QPS && (!SEPARATE_RQ_ENABLE || cfg_receive===1'b0 || cfg_receive===1'b1);
// Never narrow the trusted24-bit QP before checking its complete bounds.
wire [INDEX_WIDTH-1:0] cfg_index=SEPARATE_RQ_ENABLE ? {cfg_receive,cfg_qpn[2:0]} : cfg_qpn[2:0];
wire [2*MAX_QPS-1:0] all_downstream_guard={receive_downstream_guard,downstream_queue_guard};
wire [63:0] cfg_depth=64'd1<<cfg_log_depth;
wire [64:0] cfg_end={1'b0,cfg_dma_base}+({1'b0,cfg_depth}<<6);
wire cfg_ring_ok=cfg_log_depth>=1 && cfg_log_depth<=8 && cfg_dma_base[5:0]==0 &&
    (!cfg_end[64] || cfg_end[63:0]==0);
wire cfg_selected_busy=state!=IDLE && selected==cfg_index;
wire unexpected=(s_axis_read_tvalid && (state!=READ || data_seen)) ||
    (s_status_valid && (state!=READ || status_seen));
wire cfg_owner_idle=!fault && !unexpected && !cfg_selected_busy && !all_downstream_guard[cfg_index] && parent_dma_drained;
assign cfg_ready=!cfg_response_valid && !rst;
assign tag_exhausted=last_tag==16'hffff;
wire start=state==IDLE && enable && found && !cfg_valid && !cfg_response_valid &&
    !tag_exhausted && !fault && !unexpected && !rst;
wire [63:0] ring_mask=(64'd1<<depth_table[chosen])-1'b1;
wire [63:0] ring_offset=(consumer_table[chosen]&ring_mask)<<6;
assign m_command_address=address;
assign m_command_length=64;
assign m_command_tag=last_tag;
// Do not retract an offered descriptor even when a protocol fault arrives.
assign m_command_valid=state==COMMAND && !rst;
assign s_axis_read_tready=state==READ && !data_seen && !fault && !rst;
assign s_status_ready=state==READ && !status_seen && !fault && !rst;
assign m_result_data=error==0 ? data : 512'd0;
assign m_result_error=error;
assign m_result_qpn={21'd0,selected[2:0]};
assign m_result_receive=SEPARATE_RQ_ENABLE && selected>=MAX_QPS;
assign m_result_pd=pd;
assign m_result_epoch=epoch;
assign m_result_sequence=expected_sequence;
assign m_result_tag=last_tag;
assign m_result_valid=state==RESULT && !fault && !unexpected && !rst;
assign busy=state!=IDLE || fault;
assign queue_active=active[MAX_QPS-1:0];
assign queue_halted=halted[MAX_QPS-1:0];
assign receive_queue_active=SEPARATE_RQ_ENABLE ? active>>MAX_QPS : 0;
assign receive_queue_halted=SEPARATE_RQ_ENABLE ? halted>>MAX_QPS : 0;
genvar n;
generate for(n=0;n<MAX_QPS;n=n+1)begin: guards
    assign queue_pending[n]=active[n] && producer_table[n]!=consumer_table[n];
    // Includes the selection edge and fault/held-result ownership. Caller
    // atomically extends this with downstream refs on every handoff.
    assign queue_guard[n]=(state!=IDLE && selected==n) || (start && chosen==n);
    if(SEPARATE_RQ_ENABLE)begin: receive
        assign receive_queue_pending[n]=active[MAX_QPS+n] && producer_table[MAX_QPS+n]!=consumer_table[MAX_QPS+n];
        assign receive_queue_guard[n]=(state!=IDLE && selected==MAX_QPS+n) || (start && chosen==MAX_QPS+n);
    end else begin: legacy
        assign receive_queue_pending[n]=0;assign receive_queue_guard[n]=0;
    end
end endgenerate
integer i;
initial begin
    if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed SQ QP capacity");
    if(SEPARATE_RQ_ENABLE && MAX_QPS!=8)$fatal(1,"separate SQ/RQ requires eight-QP indexing");
end
always @(posedge clk)begin
    if(rst)begin
        state<=IDLE;active<=0;halted<=0;cursor<=0;selected<=0;
        address<=0;epoch<=0;expected_sequence<=0;pd<=0;last_tag<=INITIAL_TAG;
        data<=0;data_seen<=0;status_seen<=0;error<=0;fault<=0;fault_code<=0;
        cfg_response_error<=0;cfg_response_qpn<=0;cfg_response_epoch<=0;
        cfg_response_consumer<=0;cfg_response_valid<=0;fetch_count<=0;result_count<=0;
        for(i=0;i<SLOTS;i=i+1)begin
            base_table[i]<=0;epoch_table[i]<=0;pd_table[i]<=0;depth_table[i]<=0;
            producer_table[i]<=0;consumer_table[i]<=0;
        end
    end else begin
        if(cfg_response_valid && cfg_response_ready)cfg_response_valid<=0;
        if(cfg_valid && cfg_ready)begin
            cfg_response_valid<=1;cfg_response_error<=0;
            cfg_response_qpn<=cfg_qpn;cfg_response_epoch<=cfg_epoch;cfg_response_consumer<=0;
            if(fault || unexpected)cfg_response_error<=ERR_BUSY;
            else if(!cfg_qpn_ok)cfg_response_error<=ERR_QPN;
            else begin
                cfg_response_consumer<=consumer_table[cfg_index];
                case(cfg_command)
                1: if(!cfg_owner_idle || active[cfg_index])cfg_response_error<=ERR_BUSY;
                else if(cfg_epoch==0 || cfg_epoch<=epoch_table[cfg_index])cfg_response_error<=ERR_EPOCH;
                else if(!cfg_ring_ok || cfg_producer!=0)cfg_response_error<=ERR_RANGE;
                else begin
                    active[cfg_index]<=1;halted[cfg_index]<=0;epoch_table[cfg_index]<=cfg_epoch;
                    base_table[cfg_index]<=cfg_dma_base;pd_table[cfg_index]<=cfg_pd;depth_table[cfg_index]<=cfg_log_depth;
                    producer_table[cfg_index]<=0;consumer_table[cfg_index]<=0;cfg_response_consumer<=0;
                end
                2: if(!active[cfg_index] || cfg_epoch!=epoch_table[cfg_index])cfg_response_error<=ERR_EPOCH;
                else if(halted[cfg_index])cfg_response_error<=ERR_HALTED;
                else if(cfg_producer<producer_table[cfg_index] ||
                    cfg_producer-consumer_table[cfg_index]>(64'd1<<depth_table[cfg_index]))cfg_response_error<=ERR_PRODUCER;
                else producer_table[cfg_index]<=cfg_producer;
                3: if(!active[cfg_index] || cfg_epoch!=epoch_table[cfg_index])cfg_response_error<=ERR_EPOCH;
                else if(!cfg_owner_idle)cfg_response_error<=ERR_BUSY;
                else begin
                    // Cancel only unfetched ring storage. This is NOT a CQE,
                    // driver MR-ref release or proof that downstream work died.
                    active[cfg_index]<=0;halted[cfg_index]<=0;base_table[cfg_index]<=0;
                    pd_table[cfg_index]<=0;depth_table[cfg_index]<=0;
                    producer_table[cfg_index]<=0;consumer_table[cfg_index]<=0;
                    // Keep epoch watermark: retirement never permits reuse.
                end
                0: if(!RECV_CANCEL_ENABLE || !SEPARATE_RQ_ENABLE || cfg_receive!==1'b1)cfg_response_error<=ERR_COMMAND;
                else if(!active[cfg_index] || cfg_epoch!=epoch_table[cfg_index] || cfg_pd!=pd_table[cfg_index])cfg_response_error<=ERR_EPOCH;
                else if(cfg_dma_base!=base_table[cfg_index] || cfg_log_depth!=depth_table[cfg_index] ||
                    cfg_producer!=producer_table[cfg_index])cfg_response_error<=ERR_PRODUCER;
                else if(!cfg_owner_idle)cfg_response_error<=ERR_BUSY;
                else begin
                    // RQC1 has already reclaimed every never-taken posted
                    // owner. Actual downstream/parent drain is rechecked here.
                    // Return the exact cancelled final producer, not the fetch
                    // consumer, and retire the unfetched tail atomically.
                    cfg_response_consumer<=producer_table[cfg_index];
                    active[cfg_index]<=0;halted[cfg_index]<=0;base_table[cfg_index]<=0;
                    pd_table[cfg_index]<=0;depth_table[cfg_index]<=0;
                    producer_table[cfg_index]<=0;consumer_table[cfg_index]<=0;
                end
                default:cfg_response_error<=ERR_COMMAND;
                endcase
            end
        end
        // Data/status offers are owned only after actual descriptor acceptance.
        // A valid result/data/status must not be silently dropped/reassigned.
        if(unexpected)begin
            fault<=1;fault_code<=FAULT_UNEXPECTED;
            if(state!=COMMAND)state<=FAULT;
        end
        case(state)
        IDLE:if(start)begin
            selected<=chosen;address<=base_table[chosen]+ring_offset;
            pd<=pd_table[chosen];epoch<=epoch_table[chosen];expected_sequence<=consumer_table[chosen]+1'b1;
            last_tag<=last_tag+1'b1;data<=0;data_seen<=0;status_seen<=0;error<=0;state<=COMMAND;
        end
        COMMAND:if(m_command_valid && m_command_ready)begin
            fetch_count<=fetch_count+1'b1;
            state<=fault || s_axis_read_tvalid || s_status_valid ? FAULT : READ;
        end
        READ:if(!unexpected)begin
            if(s_axis_read_tvalid && s_axis_read_tready)begin
                case(s_axis_read_tkeep==64'hffffffffffffffff && s_axis_read_tlast)
                1'b1:begin data<=s_axis_read_tdata;data_seen<=1;end
                default:begin fault<=1;fault_code<=FAULT_DATA;state<=FAULT;end
                endcase
            end
            if(s_status_valid && s_status_ready)begin
                case(s_status_tag==last_tag)
                1'b1:case(s_status_error)
                    // Backend forwards the actual4-bit Corundum DMA status,
                    // including10(PCIe UR); NEVER relabel it as local code6.
                    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15:begin status_seen<=1;error<=s_status_error;if(s_status_error!=0)halted[selected]<=1;end
                    default:begin fault<=1;fault_code<=FAULT_STATUS;state<=FAULT;end
                endcase
                default:begin fault<=1;fault_code<=FAULT_STATUS;state<=FAULT;end
                endcase
            end
            // Registered ownership only; never combinational data->result.
            if(data_seen && status_seen && !fault)state<=RESULT;
        end
        RESULT:if(m_result_valid && m_result_ready)begin
            consumer_table[selected]<=expected_sequence;result_count<=result_count+1'b1;
            cursor<=selected+1>=SLOTS ? 0 : selected+1'b1;state<=IDLE;
        end
        FAULT:state<=FAULT;
        default:begin fault<=1;fault_code<=FAULT_STATE;state<=FAULT;end
        endcase
    end
end
endmodule
`resetall
