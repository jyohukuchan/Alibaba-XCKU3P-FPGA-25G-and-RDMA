# SPDX-License-Identifier: BSD-2-Clause-Views
"""One unchanged wire/backend fixture plus actual local WQE/single shared MR.

The downstream local lease is explicitly a test model, NOT a native DMA/WQ.
Use either the explicit transport stub or actual generated HLS, never confuse
the two scopes. Descriptor bytes are supplied by the actual C codec in tests.
"""
import probe_protected_responder as probe

DECLARATIONS=r'''
reg local_enable=1,local_valid=0,local_ready=0,local_allow_response=1,admission_pause=0;
reg [511:0] local_data=0;
reg [15:0] local_pd=17;
wire local_configuration_idle,local_input_ready,local_busy,local_guard,local_fault;
wire [7:0] local_fault_code;
wire [15:0] lqpd,lqt,lrt;
wire [31:0] lqkey,lqlen,lrlen;
wire [63:0] lqa,lroff;
wire [2:0] lqop;
wire lqv,lqr,lrv,lrr;
wire [7:0] lre;
wire [63:0] local_id,local_seq,local_epoch,local_address,local_offset,remote_address;
wire [31:0] local_length,local_key,remote_key;
wire [23:0] local_qpn;
wire [15:0] work_pd,work_tag,local_op,local_flags;
wire [7:0] local_error;
wire local_work_valid,local_authorized;
reg executor_guard=0,lease_release=0,retain_local_lease=0;
integer local_results=0,local_queries=0,local_leases=0;
wire [575:0] local_fields={local_id,local_seq,local_epoch,local_qpn,work_pd,work_tag,
 local_op,local_flags,local_length,local_key,local_address,local_offset,remote_address,remote_key,local_error};
reg local_stalled=0;reg [575:0] held_local;
always @(posedge clk)begin
 if(rst)begin executor_guard<=0;local_stalled<=0;end
 else begin
  if(local_stalled && (!local_work_valid || local_fields!==held_local))$fatal(1,"local result changed under stall");
  local_stalled<=local_work_valid&&!local_ready;held_local<=local_fields;
  if(lqv&&lqr)local_queries=local_queries+1;
  if(local_fault)$fatal(1,"unexpected local MR protocol fault %h",local_fault_code);
  if(local_work_valid&&local_ready)begin
   local_results=local_results+1;
   if(local_authorized&&retain_local_lease)begin executor_guard<=1;local_leases=local_leases+1;end
  end
  if(lease_release)executor_guard<=0;
  if((local_guard || executor_guard) && (quiet || cr || qr))$fatal(1,"configuration escaped local memory owner");
 end
end
'''

PORTS=r'''
 .cfg_admission_pause(admission_pause),
 .local_work_guard(local_guard || executor_guard),.local_configuration_idle(local_configuration_idle),
 .s_local_mr_request_pd(lqpd),.s_local_mr_request_key(lqkey),.s_local_mr_request_address(lqa),
 .s_local_mr_request_length(lqlen),.s_local_mr_request_operation(lqop),.s_local_mr_request_tag(lqt),
 .s_local_mr_request_valid(lqv),.s_local_mr_request_ready(lqr),
 .m_local_mr_response_tag(lrt),.m_local_mr_response_error(lre),.m_local_mr_response_offset(lroff),
 .m_local_mr_response_length(lrlen),.m_local_mr_response_valid(lrv),
 .m_local_mr_response_ready(lrr && local_allow_response),
'''

FRONTEND=r'''
rocev2_wqe_admission local_admission(
 .clk(clk),.rst(rst),.enable(local_enable),.configuration_idle(local_configuration_idle),
 .s_wqe_data(local_data),.s_wqe_keep(64'hffffffffffffffff),.s_wqe_last(1'b1),.s_wqe_valid(local_valid),
 .s_wqe_ready(local_input_ready),.s_context_valid(1'b1),.s_context_qpn(24'd2),.s_context_pd(local_pd),
 .s_context_tag(16'hf123),.s_context_sequence(64'hf123456700000001),.s_context_epoch(64'h9123456700000001),
 .m_mr_request_pd(lqpd),.m_mr_request_key(lqkey),.m_mr_request_address(lqa),.m_mr_request_length(lqlen),
 .m_mr_request_operation(lqop),.m_mr_request_tag(lqt),.m_mr_request_valid(lqv),.m_mr_request_ready(lqr),
 .s_mr_response_tag(lrt),.s_mr_response_error(lre),.s_mr_response_offset(lroff),.s_mr_response_length(lrlen),
 .s_mr_response_valid(lrv && local_allow_response),.s_mr_response_ready(lrr),
 .m_work_wr_id(local_id),.m_work_sequence(local_seq),.m_work_epoch(local_epoch),.m_work_qpn(local_qpn),
 .m_work_pd(work_pd),.m_work_tag(work_tag),.m_work_opcode(local_op),.m_work_flags(local_flags),
 .m_work_length(local_length),.m_work_local_key(local_key),.m_work_local_address(local_address),
 .m_work_local_offset(local_offset),.m_work_remote_address(remote_address),.m_work_remote_key(remote_key),
 .m_work_error(local_error),.m_work_authorized(local_authorized),.m_work_valid(local_work_valid),
 .m_work_ready(local_ready),.busy(local_busy),.configuration_guard(local_guard),.fault(local_fault),.fault_code(local_fault_code));
task offer_local;
 input [511:0] data;
 integer deadline;
 begin
  @(negedge clk);local_data=data;local_valid=1;deadline=cycle+100;
  @(posedge clk);while(local_input_ready!==1)begin if(cycle>deadline)$fatal(1,"local WQE offer deadline");@(posedge clk);end
  @(negedge clk);local_valid=0;local_data=0;
 end
endtask
task expect_local;
 input [7:0] error_code;input [63:0] address,offset;input [31:0] key_value,length;
 integer deadline;
 begin
  deadline=cycle+300;while(local_work_valid!==1)begin if(cycle>deadline)$fatal(1,"local result deadline");@(negedge clk);end
  if(local_error!==error_code || local_authorized!==(error_code==0) || work_pd!==local_pd ||
    work_tag!==16'hf123 || local_qpn!==2 || local_seq!==64'hf123456700000001 || local_epoch!==64'h9123456700000001)
   $fatal(1,"local result mixed trusted context err=%d expected=%d",local_error,error_code);
  if(error_code==0)begin
   if(local_address!==address || local_offset!==offset || local_key!==key_value || local_length!==length ||
      remote_key!==0 || remote_address!==64'hf123456789abc001)$fatal(1,"local full-width tuple/key0 corrupted");
  end else if(local_address!==0 || local_offset!==0 || local_key!==0 || local_length!==0 ||
    remote_address!==0 || remote_key!==0 || local_op!==0 || local_flags!==0)$fatal(1,"denied WQE leaked authority");
  repeat(7)begin @(negedge clk);if(cr || qr || quiet || !local_guard)$fatal(1,"held WQE result released MR");end
  local_ready=1;@(posedge clk);@(negedge clk);local_ready=0;#1;
 end
endtask
task release_local_lease;
 begin
  if(!executor_guard || local_busy)$fatal(1,"did not retain a real modeled handoff owner");
  repeat(9)begin @(negedge clk);if(cr || qr || quiet)$fatal(1,"MR changed during downstream ownership");end
  lease_release=1;@(posedge clk);@(negedge clk);lease_release=0;#1;
 end
endtask
'''


def make_tb(fixtures,body):
    tb=probe.TB
    old='rocev2_protected_responder dut('
    if tb.count(old)!=1:raise ValueError('protected fixture instance changed')
    tb=tb.replace(old,DECLARATIONS+'\nrocev2_protected_responder #(.EXTERNAL_ADMISSION_CONTROL(1),.LOCAL_WQE_ENABLE(1)) dut(')
    old=' .m_memory_command_write(mw)'
    if tb.count(old)!=1:raise ValueError('protected fixture memory port changed')
    tb=tb.replace(old,PORTS+old)
    old='reg [144:0] stimulus'
    if tb.count(old)!=1:raise ValueError('protected fixture stimulus declaration changed')
    tb=tb.replace(old,FRONTEND+'\n'+old)
    old=' if(deferred==0'
    if tb.count(old)!=1:raise ValueError('protected fixture final summary changed')
    tb=tb.replace(old,r''' $display("LOCAL_RESULT {\"queries\":%0d,\"results\":%0d,\"retained_leases\":%0d,\"executor_guard\":%0d}",local_queries,local_results,local_leases,executor_guard);
'''+old)
    tb=tb.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)
    return tb


def packet(operation='write',psn=probe.PSN,key=8):
    args=dict(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
              source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
              destination_qpn=2,psn=psn,remote_address=probe.VA+0x210,rkey=key)
    if operation=='write':frame=probe.rocev2_wire.write_only_frame(**args,payload=probe.PAYLOAD)
    else:frame=probe.read_wire.encode(**args,opcode=probe.read_wire.REQUEST,read_bytes=65)
    return probe.words(frame[14:])
