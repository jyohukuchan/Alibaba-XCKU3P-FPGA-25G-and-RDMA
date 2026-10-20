# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generated shared-HLS/actual Atomic/MR/page/RAM/ICRC composition fixture.

Trusted configuration, physical descriptors/host ordering and AXIS-to-native
MAC retirement are explicit models. No actual SQ/kernel/physical proof.
"""
import sys
from pathlib import Path
import re
import probe_atomic_shared as prior

ROOT=prior.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic_bridge as bridge


def once(t,a,b):
    if t.count(a)!=1:raise ValueError('generated Atomic fixture anchor: '+a)
    return t.replace(a,b)


def bench(directory,words):
    rtl=prior.rtl
    tb=prior.service_bench();tb=tb[:tb.index('integer fd,scanned,serial=0;')]
    generated=directory/'rocev2_atomic_integrity_transport.v';generated.write_text(bridge.derive())
    mapping=dict(clk='clk',rst='rst',m_atomic_request_tdata='x_s_hls_request',
        m_atomic_request_tvalid='x_s_hls_request_valid',m_atomic_request_tready='x_s_hls_request_ready',
        s_atomic_reply_tdata='x_m_hls_reply',s_atomic_reply_tvalid='x_m_hls_reply_valid',
        s_atomic_reply_tready='x_m_hls_reply_ready',m_atomic_owner_qpn='x_s_owner_qpn',
        m_atomic_owner_epoch='x_s_owner_epoch',m_atomic_owner_valid='x_s_owner_valid',m_atomic_owner_ready='x_s_owner_ready')
    for n in ['s_hls_request','s_hls_request_valid','s_owner_qpn','s_owner_epoch','s_owner_valid','m_hls_reply_ready']:
        tb=re.sub(r'reg (\[[^]]+\]\s+)?x_'+n+r'=0;',lambda m:'wire '+(m[1]or'')+'x_'+n+';',tb)
    tb=once(tb,'assign quiet=!x_configuration_guard',
        'assign quiet=!w_atomic_admission_guard && !x_configuration_guard')
    wrapper=rtl.instance(generated,'network','w_',mapping)
    wrapper=once(wrapper,'rocev2_atomic_integrity_transport network(',
        'rocev2_atomic_integrity_transport #(.LEGACY_QP_KEY(0),.REQUEST_CQ_ENABLE(1),.RNR_ENABLE(1),.RECV_RETIRE_ENABLE(1)) network(')
    result=tb+wrapper+NETWORK.replace('STIMULUS_LAST',str(words-1))
    if 'force 'in result:raise ValueError('no force allowed')
    return result,generated


NETWORK=r'''
reg [145:0] stimulus[0:STIMULUS_LAST];
reg [23:0] owned_qpn=0,owned_psn=0;reg [63:0] owned_epoch=0;reg [31:0] owned_tag=0,last_owned_tag=0;
reg token_held=0,reply_seen=0,wire_seen=0;reg [247:0] reply=0;
integer tx_frames=0,services=0,replies=0,retirements=0,last_services=0,last_commands=0,last_tx=0;
integer network_case=0,arg_dummy,p,b,frame_bytes=0,expiry;
reg [31:0] random_state=32'h213455a1;
reg tx_stalled=0;reg [144:0] held_tx;
always @(negedge clk)if(!rst)begin
 random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
 w_m_axis_tx_tready=random_state[2:0]!=0;
end
always @(posedge clk)if(!rst)begin
 if(a_fault || b_fault || fault || x_fault || w_atomic_admission_fault)begin
  if(network_case!=2)$fatal(1,"actual path fault a=%h b=%h p=%h x=%h guard=%d",a_fault_code,b_fault_code,fault_code,x_fault_code,w_atomic_admission_fault);
 end
 if(w_rnr_fault || w_recv_fault || w_request_fault || w_integrity_overflow_count || w_tx_integrity_drop_count)
  $fatal(1,"generated core/protected TX fault");
 if(w_m_axis_mem_write_cmd_tvalid || w_m_axis_mem_read_cmd_tvalid || w_m_axis_mem_write_tvalid)
  $fatal(1,"Atomic used an unauthorized legacy memory command");
 if(tx_stalled && (!w_m_axis_tx_tvalid || {w_m_axis_tx_tlast,w_m_axis_tx_tkeep,w_m_axis_tx_tdata}!==held_tx))
  $fatal(1,"wire packet retracted under backpressure");
 tx_stalled=w_m_axis_tx_tvalid&&!w_m_axis_tx_tready;held_tx={w_m_axis_tx_tlast,w_m_axis_tx_tkeep,w_m_axis_tx_tdata};
 if(x_s_owner_valid && x_s_owner_ready)begin
  if(token_held || w_m_atomic_owner_tag==0 || w_m_atomic_owner_tag<=last_owned_tag)$fatal(1,"packet owner/tag alias");
  owned_qpn=x_s_owner_qpn;owned_epoch=x_s_owner_epoch;owned_psn=w_m_atomic_owner_psn;
  owned_tag=w_m_atomic_owner_tag;last_owned_tag=owned_tag;token_held=1;reply_seen=0;wire_seen=0;
  $display("ATOMIC_OWNER %h %h %h %h",owned_qpn,owned_epoch,owned_psn,owned_tag);
 end
 if(x_s_hls_request_valid && x_s_hls_request_ready)begin
  services=services+1;$display("ATOMIC_JOB %092h",x_s_hls_request);
 end
 if(x_m_hls_reply_valid && x_m_hls_reply_ready)begin
  if(!token_held || x_m_hls_reply[215:192]!==owned_qpn || x_m_hls_reply[239:216]!==owned_psn)
   $fatal(1,"generated response lost real packet owner");
  reply=x_m_hls_reply;reply_seen=1;replies=replies+1;
  $display("ATOMIC_RESULT_WORD %062h",reply);
 end
 if(w_m_axis_tx_tvalid && w_m_axis_tx_tready)begin
  if(!token_held || !reply_seen || reply[247])$fatal(1,"wire before genuine matching service completion");
  $display("ATOMIC_OUT %032h %04h %d",w_m_axis_tx_tdata,w_m_axis_tx_tkeep,w_m_axis_tx_tlast);
  frame_bytes=frame_bytes+(w_m_axis_tx_tlast ? 8:16);
  if(w_m_axis_tx_tlast)begin
   tx_frames=tx_frames+1;wire_seen=1;frame_bytes=0;
  end
 end
 if(w_s_atomic_retire_valid && w_s_atomic_retire_ready)begin
  if(!token_held || !reply_seen || !wire_seen)$fatal(1,"retirement without modeled owned wire EOF");
  retirements=retirements+1;token_held=0;
 end
end
task configure_hls;
 input [23:0] q,rpsn;
 begin
  @(negedge clk);w_s_axis_qp_tdata={32'd0,48'd0,rpsn,24'h456700,q,32'd3};w_s_axis_qp_tvalid=1;
  @(posedge clk);while(!w_s_axis_qp_tready)@(posedge clk);
  @(negedge clk);w_s_axis_qp_tvalid=0;
  while(!w_m_axis_qp_apply_tvalid)@(negedge clk);
  if(w_m_axis_qp_apply_tdata[23:0]!==q || w_m_axis_qp_apply_tdata[71:48]!==rpsn || w_m_axis_qp_apply_tdata[79:72]!==1)
   $fatal(1,"actual HLS QP setup receipt");
  w_m_axis_qp_apply_tready=1;@(negedge clk);w_m_axis_qp_apply_tready=0;
  w_s_axis_conn_tdata={16'd4791,{4{32'h010b12c6}},24'hf12345+q,q[15:0]};w_s_axis_conn_tvalid=1;
  @(posedge clk);while(!w_s_axis_conn_tready)@(posedge clk);
  @(negedge clk);w_s_axis_conn_tvalid=0;repeat(30)@(negedge clk);
 end
endtask
task input_frame;
 input integer first;
 begin
  for(p=0;p<5;p=p+1)begin
   @(negedge clk);{w_s_axis_rx_tuser,w_s_axis_rx_tlast,w_s_axis_rx_tkeep,w_s_axis_rx_tdata}=stimulus[first+p];
   w_s_axis_rx_tvalid=1;@(posedge clk);while(!w_s_axis_rx_tready)@(posedge clk);
  end
  @(negedge clk);w_s_axis_rx_tvalid=0;w_s_axis_rx_tlast=0;w_s_axis_rx_tuser=0;
 end
endtask
task choose;
 input integer q;
 begin
  if(w_atomic_admission_guard || token_held || x_busy || a_busy || b_busy)$fatal(1,"trusted context changed during lease");
  @(negedge clk);w_atomic_trusted_qpn=q;
 end
endtask
task retire_wire;
 begin
  if(!reply_seen || !wire_seen || !w_atomic_admission_guard || !token_held)$fatal(1,"missing exact owned packet EOF");
  // EXPLICIT AXIS/MAC boundary MODEL, not actual physical SFD/EOF/tail proof.
  repeat(11)begin @(negedge clk);if(quiet || cfg_ready || mr_cfg_ready)$fatal(1,"release before modeled MAC handoff");end
  w_s_atomic_retire_qpn=owned_qpn;w_s_atomic_retire_epoch=owned_epoch;
  w_s_atomic_retire_psn=owned_psn;w_s_atomic_retire_tag=owned_tag;w_s_atomic_retire_valid=1;
  @(posedge clk);while(!w_s_atomic_retire_ready)@(posedge clk);
  @(negedge clk);w_s_atomic_retire_valid=0;repeat(5)@(negedge clk);
  if(!quiet || token_held || w_atomic_admission_guard)$fatal(1,"successful packet lease not handed off");
 end
endtask
task run_frame;
 input integer first,q,expected_services;
 begin
  choose(q);last_tx=tx_frames;input_frame(first);
  expiry=cycles+3000;while(tx_frames==last_tx && cycles<expiry)@(negedge clk);
  if(tx_frames!=last_tx+1 || services!=expected_services || replies!=expected_services)$fatal(1,"missing actual generated reply s=%d/r=%d/t=%d",services,replies,tx_frames);
  retire_wire();
 end
endtask
task invalid_frame;
 input integer first;
 begin
  last_services=services;last_commands=commands;last_tx=tx_frames;
  input_frame(first);repeat(220)@(negedge clk);
  if(services!=last_services || commands!=last_commands || tx_frames!=last_tx || token_held || w_atomic_admission_guard)
   $fatal(1,"unqualified packet reached actual service/DMA");
 end
endtask
initial begin
 #1 rst=1;arg_dummy=$value$plusargs("case=%d",network_case);$readmemh("input.hex",stimulus);
 for(k=0;k<16384;k=k+1)begin host[k]=(k*37)^8'h5a;posted_valid[k]=0;end
 repeat(5)@(negedge clk);rst=0;
 configure_qp(2,64'h9123456780000001,17,24'h111111);
 configure_qp(3,64'h9123456780000001,17,24'h222222);
 configure_mr(0,9,8192);configure_mr(1,1,8192);configure_mr(2,9,4091);
 configure_pages(1,0);configure_pages(2,0);configure_pages(2,1);configure_pages(2,2);configure_pages(3,0);
 w_local_ip_address={4{32'h020b12c6}};w_m_axis_ack_tready=1;w_m_axis_debug_tready=1;
 w_atomic_trusted_valid=1;w_atomic_trusted_qpn=2;w_atomic_trusted_epoch=64'h9123456780000001;
 w_atomic_trusted_local_ip=32'hc6120b02;w_atomic_trusted_peer_ip=32'hc6120b01;
 repeat(4200)@(negedge clk);configure_hls(2,24'hfffffe);configure_hls(3,24'h123456);
 enable=1;w_atomic_admission_enable=1;store64(4096,64'hf123456789abcdef);
 if(network_case==1)begin
  run_frame(70,2,1);
  if(commands || a_executed_count || physical_reads || physical_writes)$fatal(1,"MR denial performed DMA");
 end else if(network_case==2)begin
  fail_fence=5;input_frame(20);repeat(1200)@(negedge clk);
  if(!(a_fault || b_fault || fault) || services!=1 || replies || tx_frames || a_executed_count ||
    quiet || cfg_ready || mr_cfg_ready || !w_atomic_admission_guard || !a_memory_lock_request || !token_held)
   $fatal(1,"failed fence fabricated completion/unpin");
 end else begin
  invalid_frame(0);invalid_frame(5);invalid_frame(10);invalid_frame(15);
  if(w_rx_integrity_drop_count!=1 || w_atomic_admission_dropped!=3)$fatal(1,"integrity/peer/op admission counters");
  run_frame(20,2,1);run_frame(25,2,2);run_frame(30,2,3);run_frame(35,2,4);
  run_frame(40,2,5);run_frame(45,2,6);run_frame(50,3,7);run_frame(55,2,8);run_frame(60,2,9);
  if(a_executed_count!=6 || a_replay_count!=2 || load64(4096)!==64'hfedcba9876543210)$fatal(1,"real Atomic operation/replay result");
  // Last evicted duplicate generates NO packet. There is no exported actual
  // core-consumed/native-MAC retirement proof yet, so deliberately RETAIN
  // this packet lease; a quiet-time heuristic is not substituted for it.
  choose(2);input_frame(65);repeat(500)@(negedge clk);
  if(services!=10 || replies!=10 || tx_frames!=9 || !reply[247] || a_dropped_count!=1 ||
    !w_atomic_admission_guard || !token_held || quiet || cfg_ready || mr_cfg_ready)
   $fatal(1,"drop fabricated response or safe native retirement");
 end
 for(k=0;k<16384;k=k+1)if(k<4096 || k>=4104)
  if(host[k]!==(((k*37)^8'h5a)&255))$fatal(1,"Atomic clobbered neighbor byte=%d",k);
 $display("ATOMIC_GENERATED {\"pass_test\":true,\"case\":%0d,\"services\":%0d,\"replies\":%0d,\"wire_packets\":%0d,\"executed\":%0d,\"replays\":%0d,\"drops\":%0d,\"commands\":%0d,\"retirements\":%0d,\"cycles\":%0d,\"MAC_boundary_model\":true,\"drop_native_retirement_proven\":false}",network_case,services,replies,tx_frames,a_executed_count,a_replay_count,a_dropped_count,commands,retirements,cycles);
 $finish;
end
endmodule
'''
