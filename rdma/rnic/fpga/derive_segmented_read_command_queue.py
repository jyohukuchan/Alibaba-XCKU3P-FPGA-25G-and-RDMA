# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bounded, owner-checked READ metadata lookahead, not extra DMA authority.

Separate command/data producer channels may need the next command accepted
before the prior payload finishes. Keep serial real child DMA/status/fences
and whole-owner/CQ retention, but queue two exact future96-bit commands. Full
authority still comes from the saved owner and genuine placement handshake.
No HLS/default/clock/capacity/original child validation changes.
"""
import derive_segmented_read_route as parent
import derive_segmented_read_memory_native as memory

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA
MUX=memory.MUX;UNPAD=memory.UNPAD;CHILD_UNPAD=memory.CHILD_UNPAD
READ=memory.READ;executor=memory.executor;ports=memory.ports


def queue_source(t):
    t=once(t,'wire retire_identity=',r'''
// Metadata is not a memory grant. Derive every queued command independently
// from the actual full saved owner; the original child validates it AGAIN
// before the existing bounded DMA command may be issued.
reg [95:0] read_commands[0:1];
reg read_cmd_wr=0,read_cmd_rd=0,read_cmd_placement=0;
reg [1:0] read_cmd_count=0;
reg [31:0] read_cmd_offset=0;
wire [31:0] read_cmd_length=saved_owner[307:276];
wire [31:0] read_cmd_bytes=read_cmd_length-read_cmd_offset>4096 ? 4096:read_cmd_length-read_cmd_offset;
wire [31:0] read_cmd_padded=(read_cmd_bytes+3)&32'hfffffffc;
wire [63:0] read_cmd_va=saved_owner[243:180]+read_cmd_offset;
wire [23:0] read_cmd_qpn=saved_owner[395:372];
wire [95:0] read_cmd_expected={2'd0,read_cmd_qpn[9:0],read_cmd_va[51:48],1'b1,1'b0,
 read_cmd_va[52],read_cmd_offset+read_cmd_bytes==read_cmd_length,read_cmd_padded[27:0],read_cmd_va[47:0]};
wire read_cmd_shape=(^s_hls_write_command)!==1'bx && read_cmd_offset<read_cmd_length &&
 s_hls_write_command==read_cmd_expected;
wire read_cmd_guard=(^downstream_queue_guard)!==1'bx && read_cmd_qpn<MAX_QPS &&
 downstream_queue_guard[read_cmd_qpn]===1'b1;
wire read_cmd_bad=large_read_path &&
 ((s_hls_write_command_valid!==1'b0 && s_hls_write_command_valid!==1'b1) ||
  (s_hls_write_command_valid && (!read_cmd_placement || !read_cmd_shape)));
wire read_cmd_ready=large_read_path && read_cmd_placement && read_cmd_guard && read_cmd_shape &&
 read_cmd_count<2 && enable===1'b1 && halt===1'b0 && !fault && !extra && !rst;
wire read_cmd_push=s_hls_write_command_valid && read_cmd_ready;
wire read_cmd_valid=large_read_path && read_cmd_count!=0;
wire read_cmd_pop=read_cmd_valid && r_s_hls_command_ready;
wire read_cmd_empty=read_cmd_count==0 && read_cmd_offset==read_cmd_length;
always @(posedge clk)begin
 if(rst)begin read_cmd_wr<=0;read_cmd_rd<=0;read_cmd_placement<=0;read_cmd_count<=0;read_cmd_offset<=0;end
 else if(s_owner_valid && s_owner_ready && read_offer)begin
  read_cmd_wr<=0;read_cmd_rd<=0;read_cmd_placement<=0;read_cmd_count<=0;read_cmd_offset<=0;
 end else begin
  if(large_read_path && s_read_response_valid && s_read_response_ready)read_cmd_placement<=1;
  if(read_cmd_push)begin
   read_commands[read_cmd_wr]<=s_hls_write_command;read_cmd_wr<=!read_cmd_wr;
   read_cmd_offset<=read_cmd_offset+read_cmd_bytes;
  end
  if(read_cmd_pop)read_cmd_rd<=!read_cmd_rd;
  case({read_cmd_push,read_cmd_pop})
   2'b10:read_cmd_count<=read_cmd_count+1'b1;
   2'b01:read_cmd_count<=read_cmd_count-1'b1;
   default:begin end
  endcase
 end
end
wire retire_identity=''')
    t=once(t,'wire extra=retire_bad ||','wire extra=read_cmd_bad || retire_bad ||')
    t=once(t,'large_read_path ? r_s_hls_command_ready:l_s_hls_write_command_ready;',
        'large_read_path ? read_cmd_ready:l_s_hls_write_command_ready;')
    t=once(t,'large_read_path ? r_s_retire_ready && !retire_bad:l_s_retire_ready);',
        'large_read_path ? r_s_retire_ready && !retire_bad && read_cmd_empty:l_s_retire_ready);')
    t=once(t,'.s_hls_command(s_hls_write_command),\n.s_hls_command_valid(large_read_path && s_hls_write_command_valid),',
        '.s_hls_command(read_commands[read_cmd_rd]),\n.s_hls_command_valid(read_cmd_valid),')
    t=once(t,".s_retire_valid(large_read_path && s_retire_valid && s_retire_offer_valid===1'b1 && retire_identity),",
        ".s_retire_valid(large_read_path && s_retire_valid && s_retire_offer_valid===1'b1 && retire_identity && read_cmd_empty),")
    return t


def derive():
    out=parent.derive();out[MUX]=queue_source(out[MUX]);return out
