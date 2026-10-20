// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Two actual single-staging-bank DMA clients -> original16-bit app DMA port.
// Full logical tags are translated, NEVER shortened to reserve an owner bit.
// One physical operation per client bank, both banks may run concurrently.
// Per-segment RAM tokens preserve untagged done/response ownership/order.
// Reset is NOT parent drain, MR revocation, CQ completion or host-unpin proof.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_dma_client_router #(
    parameter RAM_ADDR_WIDTH=15,
    parameter SEG_COUNT=2,
    parameter SEG_DATA_WIDTH=256,
    parameter SEG_BE_WIDTH=32,
    parameter SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-6,
    parameter DMA_LEN_WIDTH=16,
    parameter TAG_WIDTH=16,
    parameter [15:0] INITIAL_PHYSICAL_TAG=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [127:0] s_client_read_address,
    input wire [1:0] s_client_read_ram_sel,
    input wire [2*RAM_ADDR_WIDTH-1:0] s_client_read_ram_address,
    input wire [2*DMA_LEN_WIDTH-1:0] s_client_read_length,
    input wire [2*TAG_WIDTH-1:0] s_client_read_tag,
    input wire [1:0] s_client_read_valid,
    output wire [1:0] s_client_read_ready,
    output wire [2*TAG_WIDTH-1:0] m_client_read_status_tag,
    output wire [7:0] m_client_read_status_error,
    output wire [1:0] m_client_read_status_valid,
    input wire [127:0] s_client_write_address,
    input wire [1:0] s_client_write_ram_sel,
    input wire [2*RAM_ADDR_WIDTH-1:0] s_client_write_ram_address,
    input wire [63:0] s_client_write_imm,
    input wire [1:0] s_client_write_imm_en,
    input wire [2*DMA_LEN_WIDTH-1:0] s_client_write_length,
    input wire [2*TAG_WIDTH-1:0] s_client_write_tag,
    input wire [1:0] s_client_write_valid,
    output wire [1:0] s_client_write_ready,
    output wire [2*TAG_WIDTH-1:0] m_client_write_status_tag,
    output wire [7:0] m_client_write_status_error,
    output wire [1:0] m_client_write_status_valid,
    output wire [63:0] m_dma_read_address,
    output wire m_dma_read_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_read_ram_address,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_read_length,
    output wire [TAG_WIDTH-1:0] m_dma_read_tag,
    output wire m_dma_read_valid,
    input wire m_dma_read_ready,
    input wire [TAG_WIDTH-1:0] s_dma_read_status_tag,
    input wire [3:0] s_dma_read_status_error,
    input wire s_dma_read_status_valid,
    output wire [63:0] m_dma_write_address,
    output wire m_dma_write_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_write_ram_address,
    output wire [31:0] m_dma_write_imm,
    output wire m_dma_write_imm_en,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_write_length,
    output wire [TAG_WIDTH-1:0] m_dma_write_tag,
    output wire m_dma_write_valid,
    input wire m_dma_write_ready,
    input wire [TAG_WIDTH-1:0] s_dma_write_status_tag,
    input wire [3:0] s_dma_write_status_error,
    input wire s_dma_write_status_valid,
    input wire [SEG_COUNT-1:0] dma_ram_wr_cmd_sel,
    input wire [SEG_COUNT*SEG_BE_WIDTH-1:0] dma_ram_wr_cmd_be,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_wr_cmd_addr,
    input wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_wr_cmd_data,
    input wire [SEG_COUNT-1:0] dma_ram_wr_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_wr_cmd_ready,
    output wire [SEG_COUNT-1:0] dma_ram_wr_done,
    input wire [SEG_COUNT-1:0] dma_ram_rd_cmd_sel,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_rd_cmd_addr,
    input wire [SEG_COUNT-1:0] dma_ram_rd_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_rd_cmd_ready,
    output wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_rd_resp_data,
    output wire [SEG_COUNT-1:0] dma_ram_rd_resp_valid,
    input wire [SEG_COUNT-1:0] dma_ram_rd_resp_ready,
    output wire [2*SEG_COUNT-1:0] client_ram_wr_cmd_sel,
    output wire [2*SEG_COUNT*SEG_BE_WIDTH-1:0] client_ram_wr_cmd_be,
    output wire [2*SEG_COUNT*SEG_ADDR_WIDTH-1:0] client_ram_wr_cmd_addr,
    output wire [2*SEG_COUNT*SEG_DATA_WIDTH-1:0] client_ram_wr_cmd_data,
    output wire [2*SEG_COUNT-1:0] client_ram_wr_cmd_valid,
    input wire [2*SEG_COUNT-1:0] client_ram_wr_cmd_ready,
    input wire [2*SEG_COUNT-1:0] client_ram_wr_done,
    output wire [2*SEG_COUNT-1:0] client_ram_rd_cmd_sel,
    output wire [2*SEG_COUNT*SEG_ADDR_WIDTH-1:0] client_ram_rd_cmd_addr,
    output wire [2*SEG_COUNT-1:0] client_ram_rd_cmd_valid,
    input wire [2*SEG_COUNT-1:0] client_ram_rd_cmd_ready,
    input wire [2*SEG_COUNT*SEG_DATA_WIDTH-1:0] client_ram_rd_resp_data,
    input wire [2*SEG_COUNT-1:0] client_ram_rd_resp_valid,
    output wire [2*SEG_COUNT-1:0] client_ram_rd_resp_ready,
    output wire [1:0] client_busy,
    output wire drained,
    output wire tag_exhausted,
    output wire fault,
    output wire [7:0] fault_code,
    output wire [31:0] descriptor_count,
    output wire [31:0] completion_count
);
localparam [1:0] RAM_IDLE=0,RAM_SEND=1,RAM_WAIT=2,RAM_RETURN=3;
reg [1:0] active=0,issued=0,is_write=0,status_pending=0;
reg [TAG_WIDTH-1:0] physical_tag[0:1],logical_tag[0:1];
reg [3:0] status_error[0:1];
reg [RAM_ADDR_WIDTH-1:0] ram_first[0:1],read_first[0:1];
reg [RAM_ADDR_WIDTH:0] ram_end[0:1],read_end[0:1];
reg [15:0] last_tag=INITIAL_PHYSICAL_TAG;
reg [1:0] cursor=0;
reg out_valid=0,out_write=0,out_owner=0;
reg [63:0] out_address=0;
reg [RAM_ADDR_WIDTH-1:0] out_ram_address=0;
reg [DMA_LEN_WIDTH-1:0] out_length=0;
reg [TAG_WIDTH-1:0] out_tag=0;
reg [31:0] out_imm=0;
reg fault_reg=0;
reg [7:0] fault_code_reg=0;
reg [31:0] descriptors=0,completions=0;
wire [3:0] requests={s_client_write_valid,s_client_read_valid};
reg found;
reg [1:0] chosen;
integer scan,index;
always @* begin
    found=0;chosen=cursor;
    for(scan=0;scan<4;scan=scan+1)begin
        index=(cursor+scan)&3;
        if(!found && requests[index] && !active[index&1])begin found=1;chosen=index;end
    end
end
wire bank=chosen[0];
wire direction=chosen[1];
wire [63:0] candidate_address=direction ? s_client_write_address[bank*64+:64] : s_client_read_address[bank*64+:64];
wire candidate_sel=direction ? s_client_write_ram_sel[bank] : s_client_read_ram_sel[bank];
wire [RAM_ADDR_WIDTH-1:0] candidate_ram=direction ? s_client_write_ram_address[bank*RAM_ADDR_WIDTH+:RAM_ADDR_WIDTH] : s_client_read_ram_address[bank*RAM_ADDR_WIDTH+:RAM_ADDR_WIDTH];
wire [DMA_LEN_WIDTH-1:0] candidate_length=direction ? s_client_write_length[bank*DMA_LEN_WIDTH+:DMA_LEN_WIDTH] : s_client_read_length[bank*DMA_LEN_WIDTH+:DMA_LEN_WIDTH];
wire [TAG_WIDTH-1:0] candidate_tag=direction ? s_client_write_tag[bank*TAG_WIDTH+:TAG_WIDTH] : s_client_read_tag[bank*TAG_WIDTH+:TAG_WIDTH];
// Proposal capture is NOT client acceptance, physical DMA or a tag allocation.
// Full-width span arithmetic sees ONLY these registered fields. This breaks
// the actual request-arbitration ->64-bit carry -> live-fault/drain/config path.
localparam [1:0] PF_IDLE=0,PF_CHECK=1,PF_READY=2;
reg [1:0] pf_state=PF_IDLE;
reg pf_bank=0,pf_direction=0,pf_sel=0,pf_imm_en=0,pf_approved=0;
reg [63:0] pf_address=0;
reg [RAM_ADDR_WIDTH-1:0] pf_ram=0;
reg [DMA_LEN_WIDTH-1:0] pf_length=0;
reg [TAG_WIDTH-1:0] pf_tag=0;
reg [31:0] pf_imm=0;
reg [RAM_ADDR_WIDTH:0] pf_ram_end=0,pf_read_end=0;
wire [64:0] address_end={1'b0,pf_address}+pf_length;
wire [RAM_ADDR_WIDTH+1:0] candidate_end={2'b00,pf_ram}+pf_length;
wire candidate_ok=pf_sel==0 && pf_length!=0 && candidate_end<=(1<<RAM_ADDR_WIDTH) &&
    (!address_end[64] || address_end[63:0]==0) && (!pf_direction || !pf_imm_en);
reg candidate_validated,proposal_known;
always @* begin
    candidate_validated=0;proposal_known=0;
    case(^{pf_address,pf_sel,pf_ram,pf_length,pf_tag,pf_direction,pf_bank,pf_imm_en})
    1'b0,1'b1:proposal_known=1;
    default:proposal_known=0;
    endcase
    case(candidate_ok && proposal_known)1'b1:candidate_validated=1;default:candidate_validated=0;endcase
end
// Source must keep an offered request stable until the actual ready pulse.
// Check its ORIGINAL owner/direction, not whichever arbiter wins afterward.
wire [63:0] pf_live_address=pf_direction ? s_client_write_address[pf_bank*64+:64]:s_client_read_address[pf_bank*64+:64];
wire pf_live_sel=pf_direction ? s_client_write_ram_sel[pf_bank]:s_client_read_ram_sel[pf_bank];
wire [RAM_ADDR_WIDTH-1:0] pf_live_ram=pf_direction ? s_client_write_ram_address[pf_bank*RAM_ADDR_WIDTH+:RAM_ADDR_WIDTH]:s_client_read_ram_address[pf_bank*RAM_ADDR_WIDTH+:RAM_ADDR_WIDTH];
wire [DMA_LEN_WIDTH-1:0] pf_live_length=pf_direction ? s_client_write_length[pf_bank*DMA_LEN_WIDTH+:DMA_LEN_WIDTH]:s_client_read_length[pf_bank*DMA_LEN_WIDTH+:DMA_LEN_WIDTH];
wire [TAG_WIDTH-1:0] pf_live_tag=pf_direction ? s_client_write_tag[pf_bank*TAG_WIDTH+:TAG_WIDTH]:s_client_read_tag[pf_bank*TAG_WIDTH+:TAG_WIDTH];
wire pf_live_valid=pf_direction ? s_client_write_valid[pf_bank]:s_client_read_valid[pf_bank];
wire pf_live_imm_en=pf_direction ? s_client_write_imm_en[pf_bank]:1'b0;
wire proposal_changed=pf_state!=PF_IDLE &&
    ({pf_live_valid,pf_live_address,pf_live_sel,pf_live_ram,pf_live_length,pf_live_tag,pf_live_imm_en} !==
     {1'b1,pf_address,pf_sel,pf_ram,pf_length,pf_tag,pf_imm_en});
wire descriptor_bad=pf_state==PF_READY && !pf_approved;
wire proposal_state_bad=pf_state==2'b11;
wire ram_fault,status_fault;
wire live_fault=descriptor_bad || proposal_changed || proposal_state_bad || ram_fault || status_fault;
wire proposal_start=pf_state==PF_IDLE && found && enable && !out_valid &&
    !tag_exhausted && !fault_reg && !live_fault && !rst;
wire capture=pf_state==PF_READY && pf_approved && enable && !out_valid &&
    !tag_exhausted && !fault_reg && !live_fault && !rst;
assign s_client_read_ready=capture && !pf_direction ? (pf_bank ? 2'b10:2'b01) : 2'b00;
assign s_client_write_ready=capture && pf_direction ? (pf_bank ? 2'b10:2'b01) : 2'b00;
assign m_dma_read_address=out_address;
assign m_dma_write_address=out_address;
assign m_dma_read_ram_sel=out_owner;
assign m_dma_write_ram_sel=out_owner;
assign m_dma_read_ram_address=out_ram_address;
assign m_dma_write_ram_address=out_ram_address;
assign m_dma_read_length=out_length;
assign m_dma_write_length=out_length;
assign m_dma_read_tag=out_tag;
assign m_dma_write_tag=out_tag;
assign m_dma_write_imm=out_imm;
assign m_dma_write_imm_en=0;
// Accepted offers cannot disappear because another input faults/disables.
assign m_dma_read_valid=out_valid && !out_write && !rst;
assign m_dma_write_valid=out_valid && out_write && !rst;
wire out_transfer=out_valid && (out_write ? m_dma_write_ready:m_dma_read_ready) && !rst;

reg rd_match,wr_match,rd_owner,wr_owner,rd_error_known,wr_error_known;
always @* begin
    rd_match=0;wr_match=0;rd_owner=0;wr_owner=0;rd_error_known=0;wr_error_known=0;
    case(s_dma_read_status_error)
    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15:rd_error_known=1;
    default:rd_error_known=0;
    endcase
    case(s_dma_write_status_error)
    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15:wr_error_known=1;
    default:wr_error_known=0;
    endcase
    case({active[1] && issued[1] && !is_write[1] && physical_tag[1]==s_dma_read_status_tag,
          active[0] && issued[0] && !is_write[0] && physical_tag[0]==s_dma_read_status_tag})
    2'b01:begin rd_match=1;rd_owner=0;end
    2'b10:begin rd_match=1;rd_owner=1;end
    default:begin end
    endcase
    case({active[1] && issued[1] && is_write[1] && physical_tag[1]==s_dma_write_status_tag,
          active[0] && issued[0] && is_write[0] && physical_tag[0]==s_dma_write_status_tag})
    2'b01:begin wr_match=1;wr_owner=0;end
    2'b10:begin wr_match=1;wr_owner=1;end
    default:begin end
    endcase
end
assign status_fault=(s_dma_read_status_valid && (!rd_match || !rd_error_known || status_pending[rd_owner])) ||
    (s_dma_write_status_valid && (!wr_match || !wr_error_known || status_pending[wr_owner])) ||
    (s_dma_read_status_valid && s_dma_write_status_valid && rd_match && wr_match && rd_owner==wr_owner);

wire [1:0] bank_ram_busy;
wire [2*SEG_COUNT-1:0] bank_ram_busy_each;
wire [SEG_COUNT-1:0] ram_invalid,ram_owned;
genvar n,c;
generate for(n=0;n<SEG_COUNT;n=n+1)begin: segment
    reg [1:0] ws=RAM_IDLE,rs=RAM_IDLE;
    reg wo=0,ro=0;
    reg [SEG_BE_WIDTH-1:0] wbe=0;
    reg [SEG_ADDR_WIDTH-1:0] wa=0,ra=0;
    reg [SEG_DATA_WIDTH-1:0] wd=0,response=0;
    wire wsel=dma_ram_wr_cmd_sel[n],rsel=dma_ram_rd_cmd_sel[n];
    wire [RAM_ADDR_WIDTH:0] wbase={1'b0,dma_ram_wr_cmd_addr[n*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH],6'd0}+n*32;
    wire [RAM_ADDR_WIDTH:0] rbase={1'b0,dma_ram_rd_cmd_addr[n*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH],6'd0}+n*32;
    reg write_allowed,read_allowed;
    integer byte_lane;
    always @* begin
        write_allowed=0;read_allowed=0;
        if(active[wsel] && issued[wsel] && !is_write[wsel] && !status_pending[wsel] &&
            (|dma_ram_wr_cmd_be[n*SEG_BE_WIDTH+:SEG_BE_WIDTH]))begin
            write_allowed=1;
            for(byte_lane=0;byte_lane<SEG_BE_WIDTH;byte_lane=byte_lane+1)begin
                case(dma_ram_wr_cmd_be[n*SEG_BE_WIDTH+byte_lane])
                1'b0:begin end
                1'b1:case(wbase+byte_lane>=ram_first[wsel] && wbase+byte_lane<ram_end[wsel])
                    1'b1:begin end
                    default:write_allowed=0;
                endcase
                default:write_allowed=0;
                endcase
            end
        end
        if(active[rsel] && issued[rsel] && is_write[rsel] && !status_pending[rsel] &&
            rbase>=read_first[rsel] && rbase<read_end[rsel])read_allowed=1;
    end
    assign dma_ram_wr_cmd_ready[n]=ws==RAM_IDLE && write_allowed && !fault_reg && !live_fault && !rst;
    assign dma_ram_rd_cmd_ready[n]=rs==RAM_IDLE && read_allowed && !fault_reg && !live_fault && !rst;
    assign dma_ram_wr_done[n]=ws==RAM_RETURN && !rst;
    assign dma_ram_rd_resp_data[n*SEG_DATA_WIDTH+:SEG_DATA_WIDTH]=response;
    assign dma_ram_rd_resp_valid[n]=rs==RAM_RETURN && !rst;
    wire w_sent=ws==RAM_SEND && client_ram_wr_cmd_ready[wo*SEG_COUNT+n];
    wire r_sent=rs==RAM_SEND && client_ram_rd_cmd_ready[ro*SEG_COUNT+n];
    wire w_done=client_ram_wr_done[wo*SEG_COUNT+n];
    wire r_response=client_ram_rd_resp_valid[ro*SEG_COUNT+n];
    wire w_return_allowed=ws==RAM_WAIT || w_sent;
    wire r_offer_allowed=rs==RAM_WAIT || r_sent;
    // Registered command/response boundary. Actual dma_psdpram command-ready
    // depends on response-ready; including r_sent here creates a combinational
    // ready loop in the REAL composition even when behavioral agents pass.
    // A zero-latency response may be offered with command acceptance, but must
    // remain held until the registered WAIT state accepts it next cycle.
    wire r_return_allowed=rs==RAM_WAIT;
    assign ram_invalid[n]=(dma_ram_wr_cmd_valid[n] && !write_allowed) ||
        (dma_ram_rd_cmd_valid[n] && !read_allowed) ||
        (client_ram_wr_done[n] && !(wo==0 && w_return_allowed)) ||
        (client_ram_wr_done[SEG_COUNT+n] && !(wo==1 && w_return_allowed)) ||
        (client_ram_rd_resp_valid[n] && !(ro==0 && r_offer_allowed)) ||
        (client_ram_rd_resp_valid[SEG_COUNT+n] && !(ro==1 && r_offer_allowed));
    assign ram_owned[n]=ws!=RAM_IDLE || rs!=RAM_IDLE;
    for(c=0;c<2;c=c+1)begin: client
        assign client_ram_wr_cmd_sel[c*SEG_COUNT+n]=0;
        assign client_ram_rd_cmd_sel[c*SEG_COUNT+n]=0;
        assign client_ram_wr_cmd_valid[c*SEG_COUNT+n]=ws==RAM_SEND && wo==c && !rst;
        assign client_ram_wr_cmd_be[(c*SEG_COUNT+n)*SEG_BE_WIDTH+:SEG_BE_WIDTH]=wo==c ? wbe : {SEG_BE_WIDTH{1'b0}};
        assign client_ram_wr_cmd_addr[(c*SEG_COUNT+n)*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH]=wo==c ? wa : {SEG_ADDR_WIDTH{1'b0}};
        assign client_ram_wr_cmd_data[(c*SEG_COUNT+n)*SEG_DATA_WIDTH+:SEG_DATA_WIDTH]=wo==c ? wd : {SEG_DATA_WIDTH{1'b0}};
        assign client_ram_rd_cmd_valid[c*SEG_COUNT+n]=rs==RAM_SEND && ro==c && !rst;
        assign client_ram_rd_cmd_addr[(c*SEG_COUNT+n)*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH]=ro==c ? ra : {SEG_ADDR_WIDTH{1'b0}};
        // Known accepted responses keep their route under a later fault.
        assign client_ram_rd_resp_ready[c*SEG_COUNT+n]=ro==c && r_return_allowed && !rst;
        wire busy_for_client=(ws!=RAM_IDLE && wo==c) || (rs!=RAM_IDLE && ro==c) ||
            (dma_ram_wr_cmd_valid[n] && wsel==c) || (dma_ram_rd_cmd_valid[n] && rsel==c) ||
            client_ram_wr_done[c*SEG_COUNT+n] || client_ram_rd_resp_valid[c*SEG_COUNT+n];
        assign bank_ram_busy_each[c*SEG_COUNT+n]=busy_for_client;
    end
    always @(posedge clk)begin
        if(rst)begin ws<=RAM_IDLE;rs<=RAM_IDLE;wo<=0;ro<=0;wbe<=0;wa<=0;ra<=0;wd<=0;response<=0;end
        else begin
            case(ws)
            RAM_IDLE:if(dma_ram_wr_cmd_valid[n] && dma_ram_wr_cmd_ready[n])begin
                wo<=wsel;wbe<=dma_ram_wr_cmd_be[n*SEG_BE_WIDTH+:SEG_BE_WIDTH];
                wa<=dma_ram_wr_cmd_addr[n*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH];
                wd<=dma_ram_wr_cmd_data[n*SEG_DATA_WIDTH+:SEG_DATA_WIDTH];ws<=RAM_SEND;
            end
            RAM_SEND:if(w_sent)ws<=w_done ? RAM_RETURN:RAM_WAIT;
            RAM_WAIT:if(w_done)ws<=RAM_RETURN;
            RAM_RETURN:ws<=RAM_IDLE;
            endcase
            case(rs)
            RAM_IDLE:if(dma_ram_rd_cmd_valid[n] && dma_ram_rd_cmd_ready[n])begin
                ro<=rsel;ra<=dma_ram_rd_cmd_addr[n*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH];rs<=RAM_SEND;
            end
            RAM_SEND:if(r_sent)rs<=RAM_WAIT;
            RAM_WAIT:if(r_response)begin response<=client_ram_rd_resp_data[(ro*SEG_COUNT+n)*SEG_DATA_WIDTH+:SEG_DATA_WIDTH];rs<=RAM_RETURN;end
            RAM_RETURN:if(dma_ram_rd_resp_ready[n])rs<=RAM_IDLE;
            endcase
        end
    end
end endgenerate
assign ram_fault=|ram_invalid;
wire [1:0] release_status;
generate for(c=0;c<2;c=c+1)begin: completion
    assign bank_ram_busy[c]=|bank_ram_busy_each[c*SEG_COUNT+:SEG_COUNT];
    assign release_status[c]=active[c] && status_pending[c] && !bank_ram_busy[c] &&
        pf_state!=PF_CHECK && !fault_reg && !live_fault && !rst;
    assign m_client_read_status_valid[c]=release_status[c] && !is_write[c];
    assign m_client_write_status_valid[c]=release_status[c] && is_write[c];
    assign m_client_read_status_tag[c*TAG_WIDTH+:TAG_WIDTH]=m_client_read_status_valid[c] ? logical_tag[c] : {TAG_WIDTH{1'b0}};
    assign m_client_write_status_tag[c*TAG_WIDTH+:TAG_WIDTH]=m_client_write_status_valid[c] ? logical_tag[c] : {TAG_WIDTH{1'b0}};
    assign m_client_read_status_error[c*4+:4]=m_client_read_status_valid[c] ? status_error[c] : 4'd0;
    assign m_client_write_status_error[c*4+:4]=m_client_write_status_valid[c] ? status_error[c] : 4'd0;
    assign client_busy[c]=active[c] || s_client_read_valid[c] || s_client_write_valid[c] ||
        (pf_state!=PF_IDLE && pf_bank==c);
end endgenerate
assign tag_exhausted=last_tag==16'hffff;
assign fault=fault_reg;
assign fault_code=fault_code_reg;
assign descriptor_count=descriptors;
assign completion_count=completions;
assign drained=!rst && !fault_reg && !live_fault && pf_state==PF_IDLE && active==0 && !out_valid && !(|ram_owned) &&
    !(|requests) && !s_dma_read_status_valid && !s_dma_write_status_valid &&
    !(|dma_ram_wr_cmd_valid) && !(|dma_ram_rd_cmd_valid) && !(|client_ram_wr_done) && !(|client_ram_rd_resp_valid);
initial begin
    if(SEG_COUNT!=2 || SEG_DATA_WIDTH!=256 || SEG_BE_WIDTH!=32 || RAM_ADDR_WIDTH!=SEG_ADDR_WIDTH+6 ||
        RAM_ADDR_WIDTH!=15 || DMA_LEN_WIDTH!=16 || TAG_WIDTH!=16)$fatal(1,"unreviewed native DMA router geometry");
end
integer b;
always @(posedge clk)begin
    if(rst)begin
        active<=0;issued<=0;is_write<=0;status_pending<=0;last_tag<=INITIAL_PHYSICAL_TAG;cursor<=0;
        out_valid<=0;out_write<=0;out_owner<=0;out_address<=0;out_ram_address<=0;out_length<=0;out_tag<=0;out_imm<=0;
        pf_state<=PF_IDLE;pf_bank<=0;pf_direction<=0;pf_sel<=0;pf_imm_en<=0;pf_approved<=0;
        pf_address<=0;pf_ram<=0;pf_length<=0;pf_tag<=0;pf_imm<=0;pf_ram_end<=0;pf_read_end<=0;
        fault_reg<=0;fault_code_reg<=0;descriptors<=0;completions<=0;
        for(b=0;b<2;b=b+1)begin physical_tag[b]<=0;logical_tag[b]<=0;status_error[b]<=0;ram_first[b]<=0;ram_end[b]<=0;read_first[b]<=0;read_end[b]<=0;end
    end else begin
        if(live_fault && !fault_reg)begin fault_reg<=1;fault_code_reg<=descriptor_bad ? 8'h10 :
            (proposal_changed || proposal_state_bad) ? 8'h13 : status_fault ? 8'h11 : 8'h12;end
        if(out_transfer)begin out_valid<=0;issued[out_owner]<=1;descriptors<=descriptors+1'b1;end
        if(proposal_start)begin
            pf_state<=PF_CHECK;pf_bank<=bank;pf_direction<=direction;pf_sel<=candidate_sel;
            pf_address<=candidate_address;pf_ram<=candidate_ram;pf_length<=candidate_length;pf_tag<=candidate_tag;
            pf_imm_en<=direction ? s_client_write_imm_en[bank]:1'b0;
            pf_imm<=s_client_write_imm[bank*32+:32];pf_approved<=0;
        end
        if(pf_state==PF_CHECK)begin
            pf_state<=PF_READY;pf_approved<=candidate_validated;
            pf_ram_end<=candidate_end;pf_read_end<=(candidate_end+63)&~63;
        end
        if(capture)begin
            pf_state<=PF_IDLE;
            active[pf_bank]<=1;issued[pf_bank]<=0;is_write[pf_bank]<=pf_direction;status_pending[pf_bank]<=0;
            physical_tag[pf_bank]<=last_tag+1'b1;logical_tag[pf_bank]<=pf_tag;
            ram_first[pf_bank]<=pf_ram;ram_end[pf_bank]<=pf_ram_end;
            read_first[pf_bank]<=pf_ram & ~63;read_end[pf_bank]<=pf_read_end;
            out_valid<=1;out_write<=pf_direction;out_owner<=pf_bank;out_address<=pf_address;
            out_ram_address<=pf_ram;out_length<=pf_length;out_tag<=last_tag+1'b1;
            out_imm<=pf_imm;last_tag<=last_tag+1'b1;cursor<={pf_direction,pf_bank}+1'b1;
        end
        if(!fault_reg && !live_fault)begin
            if(s_dma_read_status_valid && rd_match)begin status_pending[rd_owner]<=1;status_error[rd_owner]<=s_dma_read_status_error;end
            if(s_dma_write_status_valid && wr_match)begin status_pending[wr_owner]<=1;status_error[wr_owner]<=s_dma_write_status_error;end
            for(b=0;b<2;b=b+1)if(release_status[b])begin active[b]<=0;issued[b]<=0;status_pending[b]<=0;end
            completions<=completions+release_status[0]+release_status[1];
        end
    end
end
endmodule
`resetall
