// SPDX-License-Identifier: BSD-2-Clause-Views
// Real2000-slot allocator candidate. Not yet connected to FNS process/MR/CQ.
// Packed lease RAM and generation survive LOCAL reset; FPGA configuration /
// power loss still require external persistent-generation/ownership recovery.
module rocev2_retrans_pool #(
    parameter [63:0] GENERATION_START=64'd1
)(
    input wire clk,input wire rst,
    // owner={sequence64,epoch64,PSN24,QPN16}; marker168, reserved191:169=0
    input wire [191:0] s_alloc_data,input wire s_alloc_valid,output reg s_alloc_ready,
    // {reserved7,marker,owner168,generation64,index16}
    input wire [255:0] s_release_data,input wire s_release_valid,output reg s_release_ready,
    // {status8,owner168,generation64,index16};0success; not a CQE
    output reg [255:0] m_alloc_data=0,output reg m_alloc_valid=0,input wire m_alloc_ready,
    output reg [255:0] m_release_data=0,output reg m_release_valid=0,input wire m_release_ready,
    // {reserved11,snapshot_valid,status8,free12,global_active12,owner_active12,owner168}
    output reg [223:0] m_fence_data=0,output reg m_fence_valid=0,input wire m_fence_ready,
    output reg pool_fault=0,output wire initialized,
    output wire [11:0] free_slots,output wire [11:0] active_slots
);
localparam CAP=2000;
localparam INIT_R=0,INIT_W=1,IDLE=2,ALLOC_R=3,ALLOC_S=4,ALLOC_CHECK=5,
    ALLOC_COMMIT=6,ALLOC_OFFER=7,REL_R=8,REL_CHECK=9,REL_CTX=10,
    REL_COMMIT=11,REL_OFFER=12,FENCE_R=13,FENCE_W=14,FENCE_REPLY=15,FENCE_OFFER=16;
localparam FREE=2'b00,OFFERED=2'b01,OWNED=2'b10;
reg [4:0] state=INIT_R;
// Atomic packed record: {state2,generation64,sequence64,epoch64,PSN24,QPN16}.
// NEVER clear these in rst. Rebuilding from actual records preserves leases.
(* ram_style="block" *) reg [233:0] leases[0:CAP-1];
(* ram_style="block" *) reg [15:0] free_ring[0:CAP-1];
integer init_idx;
initial begin
    for(init_idx=0;init_idx<CAP;init_idx=init_idx+1)leases[init_idx]=234'd0;
end
reg [63:0] next_generation=GENERATION_START; // deliberately NOT reset by rst
reg [11:0] free_count=0,active_count=0;
reg [15:0] head=0,tail=0,scan_idx=0;
reg [1:0] seen=0;
reg [167:0] fence_owner=0,alloc_owner=0;
reg [247:0] release_lease=0;
reg [15:0] alloc_idx=0;
reg offer_has_lease=0;
reg [11:0] scan_owner_count=0,scan_global_count=0;
reg [233:0] slot_q=0,release_record=0;
reg [15:0] ring_q=0;
reg slot_ren,slot_we,ring_ren,ring_we;
reg [15:0] slot_ra,slot_wa,ring_ra,ring_wa;
reg [233:0] slot_wd;
reg [15:0] ring_wd;
wire slot_active=(slot_q[233:232]===OFFERED)||(slot_q[233:232]===OWNED);
wire slot_free=(slot_q[233:232]===FREE);
wire slot_owner_matches=slot_q[167:104]===fence_owner[167:104] &&
    slot_q[103:40]===fence_owner[103:40] && slot_q[15:0]===fence_owner[15:0];
wire fence_owner_valid=(fence_owner[15:0]<8 && fence_owner[103:40]!=0 && fence_owner[167:104]!=0);
assign free_slots=free_count;assign active_slots=active_count;
assign initialized=state!=INIT_R && state!=INIT_W;
function [15:0] advance;
    input [15:0] value;
    begin advance=value==CAP-1?16'd0:value+16'd1;end
endfunction
// X/Z checks are simulation diagnostics, not an analog CDC/ECC detector.
// Explicit synthesis branches prevent X literals becoming synthesis don't-cares.
function unknown_alloc;
    input [191:0] value;
    begin
`ifdef SYNTHESIS
        unknown_alloc=1'b0;
`else
        unknown_alloc=(^value)===1'bx;
`endif
    end
endfunction
function unknown_release;
    input [255:0] value;
    begin
`ifdef SYNTHESIS
        unknown_release=1'b0;
`else
        unknown_release=(^value)===1'bx;
`endif
    end
endfunction
function unknown_slot;
    input [233:0] value;
    begin
`ifdef SYNTHESIS
        unknown_slot=1'b0;
`else
        unknown_slot=(^value)===1'bx;
`endif
    end
endfunction

// One logical synchronous read/write port per packed RAM. Common write
// enable/address makes owner/state/generation one atomic record transaction.
always @(posedge clk) begin
    if(!rst)begin
        if(slot_ren)slot_q<=leases[slot_ra];
        if(slot_we)leases[slot_wa]<=slot_wd;
        if(ring_ren)ring_q<=free_ring[ring_ra];
        if(ring_we)free_ring[ring_wa]<=ring_wd;
    end
end

always @* begin
    s_alloc_ready=0;s_release_ready=0;
    slot_ren=0;slot_we=0;ring_ren=0;ring_we=0;
    slot_ra=0;slot_wa=0;slot_wd=0;ring_ra=0;ring_wa=0;ring_wd=0;
    if(!rst)case(state)
        INIT_R,FENCE_R:begin slot_ren=1;slot_ra=scan_idx;end
        INIT_W:if(slot_free)begin ring_we=1;ring_wa=tail;ring_wd=scan_idx;end
        IDLE:begin
            // Return priority follows the existing free-list behavior.
            // A blocked allocation cannot hide releases needed for progress.
            s_release_ready=!seen[1];
            if(!(s_release_valid===1'b1 && !seen[1]))
                s_alloc_ready=!seen[0] && (s_alloc_data[168]===1'b1 || free_count!=0 || pool_fault);
        end
        ALLOC_R:begin ring_ren=1;ring_ra=head;end
        ALLOC_S:if(ring_q<CAP)begin slot_ren=1;slot_ra=ring_q;end
        ALLOC_COMMIT:begin
            slot_we=1;slot_wa=alloc_idx;slot_wd={OFFERED,next_generation,alloc_owner};
        end
        ALLOC_OFFER:if(m_alloc_valid && m_alloc_ready && offer_has_lease)begin
            // Reply wire order is owner/gen/index; RAM order is gen/owner.
            slot_we=1;slot_wa=m_alloc_data[15:0];
            slot_wd={OWNED,m_alloc_data[79:16],m_alloc_data[247:80]};
        end
        REL_R:begin slot_ren=1;slot_ra=release_lease[15:0];end
        REL_COMMIT:begin
            slot_we=1;slot_wa=release_lease[15:0];slot_wd={FREE,release_record[231:0]};
            ring_we=1;ring_wa=tail;ring_wd=release_lease[15:0];
        end
    endcase
end

// Both real producer queues carry their own ordered marker. No separate
// idle/quiet input grants a fence, and PSN is echoed but not the WR identity
// match: one WR may legitimately own multiple metadata PSNs.
task mark;
    input source;input [167:0] owner;input bad;
    begin
        seen[source]<=1'b1;
        if(seen==0)fence_owner<=owner;
        else if(fence_owner!==owner)pool_fault<=1'b1;
        if(bad)pool_fault<=1'b1;
    end
endtask
task alloc_error;
    input [7:0] status;input [167:0] owner;
    begin
        m_alloc_data<={status,owner,80'd0};m_alloc_valid<=1;
        offer_has_lease<=0;pool_fault<=1;state<=ALLOC_OFFER;
    end
endtask
task release_error;
    input [7:0] status;
    begin
        m_release_data<={status,release_lease};m_release_valid<=1;
        pool_fault<=1;state<=REL_OFFER;
    end
endtask

always @(posedge clk) begin
    if(rst)begin
        state<=INIT_R;scan_idx<=0;head<=0;tail<=0;free_count<=0;active_count<=0;
        seen<=0;fence_owner<=0;alloc_owner<=0;release_lease<=0;alloc_idx<=0;offer_has_lease<=0;
        scan_owner_count<=0;scan_global_count<=0;
        m_alloc_valid<=0;m_release_valid<=0;m_fence_valid<=0;
        m_alloc_data<=0;m_release_data<=0;m_fence_data<=0;
        // pool_fault/next_generation/lease RAM deliberately retain state.
    end else begin
        if(m_alloc_valid && m_alloc_ready)m_alloc_valid<=0;
        if(m_release_valid && m_release_ready)m_release_valid<=0;
        if(m_fence_valid && m_fence_ready)m_fence_valid<=0;
        case(state)
            INIT_R:state<=INIT_W;
            INIT_W:begin
                if(slot_free)begin free_count<=free_count+1'b1;tail<=advance(tail);end
                else begin
                    active_count<=active_count+1'b1;
                    if(!slot_active || unknown_slot(slot_q) || slot_q[231:168]==0 || slot_q[15:0]>=8 ||
                        slot_q[103:40]==0 || slot_q[167:104]==0)pool_fault<=1;
                end
                if(scan_idx==CAP-1)begin state<=IDLE;scan_idx<=0;end
                else begin scan_idx<=scan_idx+1'b1;state<=INIT_R;end
            end
            IDLE:begin
                if(seen==3)begin
                    scan_idx<=0;scan_owner_count<=0;scan_global_count<=0;state<=FENCE_R;
                end else if(s_release_valid===1'b1 && s_release_ready)begin
                    if(unknown_release(s_release_data))begin
                        release_lease<=0;m_release_data<={8'd3,248'd0};m_release_valid<=1;
                        pool_fault<=1;state<=REL_OFFER;
                    end else if(s_release_data[248])begin
                        mark(1'b1,s_release_data[247:80],s_release_data[255:249]!=0 || s_release_data[79:0]!=0);
                    end else if(s_release_data[255:249]!=0)begin
                        release_lease<=s_release_data[247:0];m_release_data<={8'd3,s_release_data[247:0]};
                        m_release_valid<=1;pool_fault<=1;state<=REL_OFFER;
                    end else if(s_release_data[15:0]>=CAP)begin
                        release_lease<=s_release_data[247:0];m_release_data<={8'd1,s_release_data[247:0]};
                        m_release_valid<=1;pool_fault<=1;state<=REL_OFFER;
                    end else begin release_lease<=s_release_data[247:0];state<=REL_R;end
                end else if(s_alloc_valid===1'b1 && s_alloc_ready)begin
                    if(unknown_alloc(s_alloc_data))alloc_error(8'd3,168'd0);
                    else if(s_alloc_data[168])mark(1'b0,s_alloc_data[167:0],s_alloc_data[191:169]!=0);
                    else if(s_alloc_data[191:169]!=0)alloc_error(8'd3,s_alloc_data[167:0]);
                    else if(pool_fault)alloc_error(8'd4,s_alloc_data[167:0]);
                    else if(s_alloc_data[15:0]>=8)alloc_error(8'd1,s_alloc_data[167:0]);
                    else if(s_alloc_data[103:40]==0 || s_alloc_data[167:104]==0)alloc_error(8'd3,s_alloc_data[167:0]);
                    else begin alloc_owner<=s_alloc_data[167:0];state<=ALLOC_R;end
                end
            end
            ALLOC_R:state<=ALLOC_S;
            ALLOC_S:begin
                if(ring_q>=CAP)alloc_error(8'd9,alloc_owner);
                else begin alloc_idx<=ring_q;state<=ALLOC_CHECK;end
            end
            ALLOC_CHECK:begin
                if(!slot_free || free_count==0 || active_count>=CAP)alloc_error(8'd9,alloc_owner);
                else if(next_generation==0 || next_generation==64'hffffffffffffffff)alloc_error(8'd8,alloc_owner);
                else state<=ALLOC_COMMIT;
            end
            ALLOC_COMMIT:begin
                m_alloc_data<={8'd0,alloc_owner,next_generation,alloc_idx};m_alloc_valid<=1;offer_has_lease<=1;
                next_generation<=next_generation+1'b1;head<=advance(head);
                free_count<=free_count-1'b1;active_count<=active_count+1'b1;state<=ALLOC_OFFER;
            end
            ALLOC_OFFER:if(m_alloc_valid && m_alloc_ready)begin offer_has_lease<=0;state<=IDLE;end
            REL_R:state<=REL_CHECK;
            REL_CHECK:begin
                release_record<=slot_q;
                if(slot_q[233:232]!==OWNED)begin
                    if(slot_free)release_error(8'd5);else release_error(8'd8);
                end else if(slot_q[231:168]!==release_lease[79:16])release_error(8'd6);
                else state<=REL_CTX;
            end
            REL_CTX:begin
                if(release_record[167:0]!==release_lease[247:80])release_error(8'd7);
                else if(free_count>=CAP || active_count==0)release_error(8'd9);
                else state<=REL_COMMIT;
            end
            REL_COMMIT:begin
                tail<=advance(tail);free_count<=free_count+1'b1;active_count<=active_count-1'b1;
                m_release_data<={8'd0,release_lease};m_release_valid<=1;state<=REL_OFFER;
            end
            REL_OFFER:if(m_release_valid && m_release_ready)state<=IDLE;
            FENCE_R:state<=FENCE_W;
            FENCE_W:begin
                if(!slot_free)begin
                    scan_global_count<=scan_global_count+1'b1;
                    if(slot_active && slot_owner_matches)scan_owner_count<=scan_owner_count+1'b1;
                    if(!slot_active || unknown_slot(slot_q) || slot_q[231:168]==0 || slot_q[15:0]>=8 ||
                        slot_q[103:40]==0 || slot_q[167:104]==0)pool_fault<=1;
                end
                if(scan_idx==CAP-1)state<=FENCE_REPLY;
                else begin scan_idx<=scan_idx+1'b1;state<=FENCE_R;end
            end
            FENCE_REPLY:begin
                m_fence_data<=0;m_fence_data[167:0]<=fence_owner;
                m_fence_data[179:168]<=scan_owner_count;m_fence_data[191:180]<=active_count;
                m_fence_data[203:192]<=free_count;m_fence_valid<=1;
                if(pool_fault || scan_global_count!=active_count || {1'b0,free_count}+{1'b0,active_count}!=CAP)begin
                    m_fence_data[211:204]<=8'd4;pool_fault<=1;
                end else if(!fence_owner_valid)m_fence_data[211:204]<=8'd3;
                else begin
                    m_fence_data[212]<=1;
                    m_fence_data[211:204]<=scan_owner_count==0?8'd0:8'd2;
                end
                state<=FENCE_OFFER;
            end
            FENCE_OFFER:if(m_fence_valid && m_fence_ready)begin seen<=0;state<=IDLE;end
            default:begin pool_fault<=1;state<=INIT_R;scan_idx<=0;head<=0;tail<=0;free_count<=0;active_count<=0;end
        endcase
    end
end
endmodule
