# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real128-byte PCIe fetch -> one MR table -> immutable owner/SQ RTL.

Only trusted configuration, physical host/root and downstream owner/HLS sinks
are models. Sink release is staging qualification, NEVER a WR completion or
unpin proof. No test-produced WQE/MR reply or SQ word drives the DUT.
"""
import re
import probe_atomic128_sq_dma as fetch
import test_atomic128_admission_rtl as admission

ROOT=fetch.ROOT;source=admission.source;once=source.once


def instance(text,name,mapping,parameters=''):
    header=text.split('\n);',1)[0]
    module=re.search(r'\bmodule\s+(\w+)',header)[1]
    ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?',header)
    declared=[];connections=[]
    if set(mapping)-{n for _,_,n in ports}:raise ValueError('unknown connected port '+name)
    for direction,width,port in ports:
        if port not in mapping and direction=='input':raise ValueError('missing real input '+name+'.'+port)
        signal=mapping.get(port,name+'_'+port)
        if port not in mapping:declared.append('wire '+(width or '')+signal+';')
        connections.append('.'+port+'('+signal+')')
    return '\n'.join(declared)+'\n'+module+(' #('+parameters+')'if parameters else'')+' '+name+'('+','.join(connections)+');\n'


def connections():
    derived=source.derive()
    a=dict(clk='clk',rst='rst',enable="1'b1",configuration_idle='mr_bootstrap_done && !mr_cfg_valid && !mr_cfg_pending && !mr_cfg_response_valid',
        s_fetch_data='m_result_data',s_fetch_error='m_result_error',s_fetch_qpn='m_result_qpn',s_fetch_pd='m_result_pd',
        s_fetch_epoch='m_result_epoch',s_fetch_sequence='m_result_sequence',s_fetch_tag='m_result_tag',
        s_fetch_valid='m_result_valid && m_result_ready',s_fetch_ready='pipeline_input_ready',m_work_ready='stage_s_work_ready',
        m_mr_request_ready='mr_s_request_ready',s_mr_response_tag='mr_m_response_tag',s_mr_response_error='mr_m_response_error',
        s_mr_response_offset='mr_m_response_offset',s_mr_response_length='mr_m_response_length',s_mr_response_valid='mr_m_response_valid')
    txt=instance(derived[source.SQ],'admit',a,'.SEND_ENABLE(1),.IMMEDIATE_ENABLE(1)')
    context='{'+','.join('admit_m_work_'+n for n in ['swap_add','compare','immediate','wr_id','sequence','epoch','qpn','pd','tag',
        'opcode','flags','length','local_key','local_address','local_offset','remote_address','remote_key','error',
        'error_source','fetch_error','descriptor_available','authorized'])+'}'
    h=dict(clk='clk',rst='rst',enable="1'b1",halt="1'b0",s_work_context=context,s_work_valid='admit_m_work_valid',
        s_work_ready='stage_s_work_ready',m_owner_ready='modeled_owner_ready',downstream_queue_guard='modeled_owner_guard',
        m_axis_sq_tready='modeled_HLS_ready')
    txt+='wire stage_s_work_ready;\n'+instance(derived[source.HLS],'stage',h,'.IMMEDIATE_ENABLE(1)')
    m=dict(clk='clk',rst='rst',cfg_quiescent='!admit_configuration_guard && !stage_configuration_guard && !(|modeled_owner_guard)',
        cfg_command='mr_cfg_command',cfg_index='mr_cfg_index',cfg_pd='mr_cfg_pd',cfg_key='mr_cfg_key',
        cfg_virtual_address="64'hf123456789abc000",cfg_dma_address="64'd0",cfg_length="64'd8192",cfg_access="4'd1",
        cfg_valid='mr_cfg_valid',cfg_ready='mr_cfg_ready',cfg_response_ready="1'b1",cfg_response_valid='mr_cfg_response_valid',
        cfg_response_key='mr_cfg_result',cfg_response_error='mr_cfg_error',
        m_response_ready='admit_s_mr_response_ready')
    for n in ['pd','key','address','length','operation','tag','valid']:m['s_request_'+n]='admit_m_mr_request_'+n
    txt+=instance((source.RTL/'rocev2_mr_table.v').read_text(),'mr',m,'.REQUIRE_EPOCH(1)')
    return txt


MODELS=r'''
wire pipeline_input_ready,pipeline_raw_ready;
assign pipeline_raw_ready=m_result_ready && pipeline_input_ready;
reg mr_bootstrap_done=0,mr_cfg_valid=0,mr_cfg_pending=0;
reg [1:0] mr_cfg_command=0;reg [2:0] mr_cfg_index=0;reg [15:0] mr_cfg_pd=0;
reg [31:0] mr_cfg_key=0;wire mr_cfg_ready,mr_cfg_response_valid;wire [31:0] mr_cfg_result;wire [7:0] mr_cfg_error;
reg [7:0] modeled_owner_guard=0;reg modeled_have_owner=0,modeled_SQ_seen=0;
reg [747:0] modeled_owner=0;integer modeled_owner_deadline=0;
wire modeled_owner_ready=(|modeled_owner_guard) && !modeled_have_owner;
wire modeled_HLS_ready=rng[15:13]!=0;
wire [7:0] pipeline_queue_guard=admit_queue_guard | stage_queue_guard | modeled_owner_guard;
integer actual_work_count=0,actual_owner_count=0,actual_SQ_count=0;
always @(posedge clk)begin
 if(rst)begin mr_cfg_pending<=0;modeled_owner_guard<=0;modeled_have_owner<=0;modeled_SQ_seen<=0;end
 else begin
  if(mr_cfg_valid && mr_cfg_ready)mr_cfg_pending<=1;
  if(mr_cfg_response_valid)mr_cfg_pending<=0;
  if(admit_fault || stage_fault)$fatal(1,"actual pipeline admission/owner protocol fault");
  if(m_result_valid && pipeline_raw_ready)$display("PIPE_RAW %0d %0d %016h %0d %0d %0d %0256h",
   m_result_qpn,m_result_pd,m_result_epoch,m_result_sequence,m_result_tag,m_result_error,m_result_data);
  if(admit_m_work_valid && stage_s_work_ready)begin
   actual_work_count=actual_work_count+1;$display("PIPE_WORK %0187h",stage.s_work_context);
  end
  // Explicit downstream model. Its guard is registered BEFORE actual owner
  // handshake; actual staging cannot use its OWN queue_guard as this proof.
  if(!modeled_have_owner && !(|modeled_owner_guard) && stage_m_owner_valid)
   modeled_owner_guard<=8'b1<<stage_m_owner_context[395:372];
  if(stage_m_owner_valid && modeled_owner_ready)begin
   modeled_have_owner<=1;modeled_owner<=stage_m_owner_context;modeled_SQ_seen<=0;modeled_owner_deadline<=cycle+16;
   actual_owner_count=actual_owner_count+1;$display("PIPE_OWNER %0187h",stage_m_owner_context);
  end
  if(stage_m_axis_sq_tvalid && modeled_HLS_ready)begin
   if(!modeled_have_owner || !modeled_owner[0] || stage_m_owner_context!==modeled_owner || modeled_SQ_seen)
    $fatal(1,"actual SQ without its full immutable guarded owner");
   modeled_SQ_seen<=1;actual_SQ_count=actual_SQ_count+1;$display("PIPE_HLS %0102h",stage_m_axis_sq_tdata);
  end
  if(modeled_have_owner && (!modeled_owner[0] || modeled_SQ_seen) && cycle>=modeled_owner_deadline)begin
   modeled_have_owner<=0;modeled_owner_guard<=0;
  end
  if((|pipeline_queue_guard) && mr_cfg_ready)$fatal(1,"MR management escaped actual frontend/staging/model-owner guard");
 end
end
task mr_setup;
 input [1:0] command;input [2:0] index;input [15:0] pd;input [31:0] key,expected_key;
 integer deadline;
 begin
  @(negedge clk);mr_cfg_command=command;mr_cfg_index=index;mr_cfg_pd=pd;mr_cfg_key=key;mr_cfg_valid=1;
  deadline=cycle+100;@(posedge clk);while(!mr_cfg_ready)begin if(cycle>deadline)$fatal(1,"MR config request deadline");@(posedge clk);end
  @(negedge clk);mr_cfg_valid=0;while(!mr_cfg_response_valid)begin if(cycle>deadline)$fatal(1,"MR config reply deadline");@(negedge clk);end
  if(mr_cfg_error || mr_cfg_result!==expected_key)$fatal(1,"actual MR configuration result");
  @(negedge clk);
 end
endtask
initial begin
 @(negedge rst);
 mr_setup(3,0,0,32'h10000000,32'h10000000);
 mr_setup(1,0,16'hf123,0,32'h80000008);mr_setup(1,1,16'habcd,0,32'h80000009);
 mr_bootstrap_done=1;
end
'''


def bench(error):
    t=fetch.bench(error)
    t=once(t,'module tb;','module tb;\nlocalparam MAX_QPS=8;\n'+MODELS+connections())
    t=once(t,'rocev2_atomic128_sq_dma_fetch dut(.*);',
        'rocev2_atomic128_sq_dma_fetch dut(.m_result_ready(pipeline_raw_ready),'
        '.downstream_queue_guard(downstream_queue_guard | pipeline_queue_guard),.*);')
    t=once(t,'if(m_result_valid&&m_result_ready)observed_results=observed_results+1;',
        'if(m_result_valid&&pipeline_raw_ready)observed_results=observed_results+1;')
    t=once(t,'m_result_ready=1;@(posedge clk);@(negedge clk);m_result_ready=0;',
        'm_result_ready=1;@(posedge clk);while(!pipeline_raw_ready)@(posedge clk);@(negedge clk);m_result_ready=0;')
    t=once(t,' if(!parent_dma_drained || !dma_drained || busy || fault || backend_fence_count ||',
        ' while((|pipeline_queue_guard) || admit_busy || stage_busy)@(negedge clk);\n'
        ' if(actual_work_count!==(ERROR_CASE ? 4:6) || actual_owner_count!==actual_work_count ||\n'
        '   actual_SQ_count!==(ERROR_CASE ? 3:6))$fatal(1,"pipeline missing work/owner/SQ handoffs");\n'
        ' if(!parent_dma_drained || !dma_drained || busy || fault || backend_fence_count ||')
    return t
