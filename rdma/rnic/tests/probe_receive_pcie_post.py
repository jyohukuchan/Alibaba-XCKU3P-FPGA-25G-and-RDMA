#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C128/coherent RQ PCIe DMA -> real full-range MR -> real message RQ.

Use the actual new source graph's fetch/admission bodies and original
Corundum backend/RAM/mux/generic PCIe engine, not descriptor/status/RAM/MR
agents. Physical host/root/link and privileged queue/MR configuration remain
models. No payload placement/HLS/MAC/CQ/installed Linux/physical/timing claim.
Error work is consumed by an explicit error sink, NOT a CQ or unpin proof.
This additional connection test does not replace any previous regression.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import probe_atomic128_sq_dma as fetch
import atomic128_pipeline_fixture as fixture
import test_segmented_receive_wqe as codec

ROOT=fetch.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_receive as graph
once=graph.once
BASE=0xf123456789abc000
EPOCHS={0:0x8000000000000001,7:0x9000000000000001}
PDS={0:0xf123,7:0xabcd}


def digest(p):
    with Path(p).open('rb')as f:return __import__('hashlib').file_digest(f,'sha256').hexdigest()


def records(case):
    result=[];codec.SegmentedReceiveWQE.setUpClass()
    try:
        for index,(q,seq,length)in enumerate([(0,1,8193),(0,2,1048576),(7,1,65537),(7,2,4097)]):
            key=0x80000008+(q==7);address=BASE+1
            if case==1:
                if index==0:key=0x8000000a
                elif index==1:address=BASE+8193
                elif index==2:key^=0x80000000
            w=codec.SegmentedReceiveWQE.receive(length,local_address=address,local_key=key,
                sequence=seq,epoch=EPOCHS[q],wr_id=0xf123456700000000+index)
            raw=(C.c_uint8*128)()
            if codec.SegmentedReceiveWQE.lib.as02_segmented_receive_wqe_encode(raw,C.byref(w)):
                raise ValueError('actual RECV codec refused canonical input')
            canonical=codec.old.old.old.old.old.oracle(w)
            if bytes(raw)!=canonical:raise ValueError('independent complete128-byte codec oracle')
            b=bytearray(raw)
            if case==2:
                if index==0:b[8:16]=(seq+1).to_bytes(8,'little')
                elif index==1:b[56:64]=(EPOCHS[q]+1).to_bytes(8,'little')
                elif index==2:b[80]=1
                else:b[24]=1
            result.append(bytes(b))
    finally:codec.SegmentedReceiveWQE.directory.cleanup()
    return result


def contexts(data,case):
    result=[]
    for index,b in enumerate(data):
        q=0 if index<2 else 7;seq=index%2+1
        error=([3,4,1,0][index]if case==1 else [0x23,0x22,0x20,0x20][index]if case==2 else 10 if case==3 and index==0 else 0)
        failed_fetch=case==3 and index==0
        def get(off,size):return int.from_bytes(b[off:off+size],'little')
        def auth(off,size):return get(off,size)if not error else 0
        context=0
        # Tag is filled independently below from actual deterministic fetch order.
        tag=([1,3,2,4]if case!=3 else [1,0,2,3])[index]
        fields=[(32,0),(64,0 if failed_fetch else get(0,8)),(64,seq),(64,EPOCHS[q]),
            (24,q),(16,PDS[q]),(16,tag),(16,auth(44,2)),(16,auth(46,2)),(32,auth(32,4)),
            (32,auth(36,4)),(64,auth(16,8)),(64,get(16,8)-BASE if not error else 0),
            (64,0),(32,0),(8,error),(2,1 if failed_fetch else 2 if error else 0),
            (8,10 if failed_fetch else 0),(1,int(not failed_fetch)),(1,int(not error))]
        for width,value in fields:context=(context<<width)|value
        result.append((context,error))
    return result


def connections(generated):
    amap=dict(clk='clk',rst='rst',enable="1'b1",configuration_idle='mr_bootstrap_done && !mr_cfg_pending && !mr_cfg_valid && !mr_cfg_response_valid',
        s_fetch_data='m_result_data',s_fetch_error='m_result_error',s_fetch_qpn='m_result_qpn',s_fetch_pd='m_result_pd',
        s_fetch_epoch='m_result_epoch',s_fetch_sequence='m_result_sequence',s_fetch_tag='m_result_tag',
        s_fetch_valid='m_result_valid && m_result_ready && m_result_receive',s_fetch_ready='pipeline_input_ready',
        m_work_ready='work_ready',m_mr_request_ready='mr_s_request_ready',s_mr_response_tag='mr_m_response_tag',
        s_mr_response_error='mr_m_response_error',s_mr_response_offset='mr_m_response_offset',
        s_mr_response_length='mr_m_response_length',s_mr_response_valid='mr_m_response_valid')
    text=fixture.instance(generated[graph.RTL/'rocev2_sq_wqe_admission.v'],'admit',amap,
        '.SEND_ENABLE(1),.IMMEDIATE_ENABLE(1),.RECV_ENABLE(1),.RECV_ONLY(1)')
    fields=['immediate','wr_id','sequence','epoch','qpn','pd','tag','opcode','flags','length',
        'local_key','local_address','local_offset','remote_address','remote_key','error','error_source',
        'fetch_error','descriptor_available','authorized']
    text+='wire [619:0] posted_context={'+','.join('admit_m_work_'+n for n in fields)+'};\n'
    rmap=dict(clk='clk',rst='rst',parent_fault='admit_fault || fault',s_post_context='posted_context',
        s_post_valid='admit_m_work_valid && admit_m_work_authorized && allow_work',query_qpn='rq_query',
        m_head_ready='rq_take',memory_drained='parent_dma_drained && dma_drained')
    header=graph.RTL/'rocev2_receive_message_queue.v'
    for direction,width,n in re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',header.read_text().split('\n);',1)[0]):
        if direction=='input'and n not in rmap:rmap[n]="'0"
    text+=fixture.instance(header.read_text(),'rq',rmap)
    mmap=dict(clk='clk',rst='rst',cfg_quiescent='!admit_configuration_guard && !(|rq_queue_guard)',
        cfg_command='mr_cfg_command',cfg_index='mr_cfg_index',cfg_pd='mr_cfg_pd',cfg_key='mr_cfg_key',
        cfg_virtual_address="64'hf123456789abc000",cfg_dma_address="64'd0",cfg_length="64'd1056768",
        cfg_access='mr_cfg_access',cfg_valid='mr_cfg_valid',cfg_ready='mr_cfg_ready',cfg_response_ready="1'b1",
        cfg_response_valid='mr_cfg_response_valid',cfg_response_key='mr_cfg_result',cfg_response_error='mr_cfg_error',
        m_response_ready='admit_s_mr_response_ready')
    for n in ['pd','key','address','length','operation','tag','valid']:mmap['s_request_'+n]='admit_m_mr_request_'+n
    return text+fixture.instance((graph.RTL/'rocev2_mr_table.v').read_text(),'mr',mmap,'.REQUIRE_EPOCH(1)')


MODELS=r'''
localparam MAX_QPS=8;
wire pipeline_input_ready,pipeline_raw_ready,work_ready;
assign pipeline_raw_ready=m_result_ready && pipeline_input_ready;
reg allow_work=1;reg [23:0] rq_query=0;reg rq_take=0;
assign work_ready=allow_work && (admit_m_work_authorized ? rq_s_post_ready:1'b1);
wire [7:0] pipeline_guard=admit_queue_guard | rq_queue_guard;
reg mr_bootstrap_done=0,mr_cfg_valid=0,mr_cfg_pending=0;
reg [1:0] mr_cfg_command=0;reg [2:0] mr_cfg_index=0;reg [15:0] mr_cfg_pd=0;
reg [31:0] mr_cfg_key=0;reg [3:0] mr_cfg_access=1;
wire mr_cfg_ready,mr_cfg_response_valid;wire [31:0] mr_cfg_result;wire [7:0] mr_cfg_error;
integer actual_queries=0,actual_works=0,actual_posts=0;
reg [619:0] expected_contexts[0:3];reg [7:0] expected_errors[0:3];integer idx_work,idx_query;
reg work_stalled=0;reg [619:0] held_work;
always @(posedge clk)if(!rst)begin
 if(mr_cfg_valid && mr_cfg_ready)mr_cfg_pending<=1;
 if(mr_cfg_response_valid)mr_cfg_pending<=0;
 if(admit_fault || rq_fault)$fatal(1,"real MR/admission/RQ fault");
 if(m_result_valid && !m_result_receive)$fatal(1,"trusted receive result became SQ work");
 if(work_stalled && (!admit_m_work_valid || posted_context!==held_work))$fatal(1,"work changed under downstream stall");
 work_stalled=admit_m_work_valid && !work_ready;held_work=posted_context;
 if(m_result_valid && pipeline_raw_ready)$display("RECV_PCIE_RAW %0d %0d %016h %0d %0d %0d %0256h",
  m_result_qpn,m_result_pd,m_result_epoch,m_result_sequence,m_result_tag,m_result_error,m_result_data);
 if(admit_m_mr_request_valid && mr_s_request_ready)begin
  idx_query=admit_m_mr_request_pd==16'hf123 ? admit_m_mr_request_tag==1 ? 0:1:
    admit_m_mr_request_tag==2 ? 2:3;
  if(admit_m_mr_request_pd!==(idx_query<2 ? 16'hf123:16'habcd) ||
     admit_m_mr_request_key!==records[idx_query][319:288] ||
     admit_m_mr_request_address!==records[idx_query][191:128] ||
     admit_m_mr_request_length!==records[idx_query][287:256] || admit_m_mr_request_operation!==1)
   $fatal(1,"actual MR query lost FULL posted capacity/key/VA/local-write permission");
  actual_queries=actual_queries+1;
  $display("RECV_PCIE_MR %0d %08h %016h %0d %0d",admit_m_mr_request_pd,admit_m_mr_request_key,
   admit_m_mr_request_address,admit_m_mr_request_length,admit_m_mr_request_tag);
 end
 if(admit_m_work_valid && work_ready)begin
  idx_work=admit_m_work_qpn==0 ? admit_m_work_sequence-1:admit_m_work_sequence+1;
  if(idx_work<0 || idx_work>3 || posted_context!==expected_contexts[idx_work] ||
     admit_m_work_error!==expected_errors[idx_work] || admit_m_work_compare || admit_m_work_swap_add)
   $fatal(1,"independent full620 actual PCIe/MR work owner/error mismatch index%d actual%h expected%h",idx_work,posted_context,expected_contexts[idx_work]);
  actual_works=actual_works+1;$display("RECV_PCIE_WORK %0155h",posted_context);
 end
 if(rq.s_post_valid && rq_s_post_ready)begin
  actual_posts=actual_posts+1;$display("RECV_PCIE_POSTED %0155h",rq.s_post_context);
 end
 if((|rq_queue_guard) && mr_cfg_ready)$fatal(1,"posted RQ released MR management exclusion");
 if(rq_m_ticket_valid || rq_m_packet_retire_valid || rq_placement_count || rq_packet_retired_count ||
    rq_core_proof_count || rq_received_bytes)$fatal(1,"descriptor acquisition fabricated data execution or completion");
end
'''


def bench(case,data,expected):
    t=fetch.bench(case==3)
    t=once(t,'rocev2_atomic128_sq_dma_fetch dut(.*);',
        "rocev2_sq_dma_fetch #(.SEPARATE_RQ_ENABLE(1),.RECV_CANCEL_ENABLE(1)) dut("
        '.m_result_ready(pipeline_raw_ready),.receive_downstream_guard(pipeline_guard),.*);')
    t=once(t,'if(m_result_valid&&m_result_ready)observed_results=observed_results+1;',
        'if(m_result_valid&&pipeline_raw_ready)observed_results=observed_results+1;')
    t=once(t,'result_stalled=m_result_valid&&!m_result_ready;', 'result_stalled=m_result_valid&&!pipeline_raw_ready;')
    t=once(t,'m_result_tag!==tag_value || !queue_guard[q]', 'm_result_tag!==tag_value || !receive_queue_guard[q]')
    t=once(t,'if(!m_result_valid || !queue_guard[q])', 'if(!m_result_valid || !receive_queue_guard[q])')
    t=once(t,'m_result_ready=1;@(posedge clk);@(negedge clk);m_result_ready=0;',
        'm_result_ready=1;@(posedge clk);while(!pipeline_raw_ready)@(posedge clk);@(negedge clk);m_result_ready=0;')
    begin=t.index('initial begin\n rst=0;repeat(2)@(negedge clk);rst=1;')
    t=t[:begin]+BODY+'\nendmodule\n'
    expected_setup='\n'.join(f"expected_contexts[{i}]=620'h{ctx:0155x};expected_errors[{i}]=8'd{error};"for i,(ctx,error)in enumerate(expected))
    posts=4 if case==0 else 1 if case==1 else 0 if case==2 else 2
    query=4 if case in [0,1]else 0 if case==2 else 2
    total=3 if case==3 else 4
    body=t.replace('// EXPECTED',expected_setup).replace('CASE_VALUE',str(case)).replace('POST_COUNT',str(posts)).replace('QUERY_COUNT',str(query)).replace('RESULT_COUNT',str(total))
    generated=graph.derive()
    models=MODELS+fixture.MODELS[fixture.MODELS.index('task mr_setup;'):fixture.MODELS.index('initial begin\n @(negedge rst);')]
    return once(body,'module tb;','module tb;\n'+models+connections(generated))


BODY=r'''
initial begin
 rst=0;repeat(2)@(negedge clk);rst=1;
 $readmemh("records.hex",records);load_slot(0,0);load_slot(1,1);load_slot(2,2);load_slot(3,3);
 // EXPECTED
 repeat(8)@(negedge clk);rst=0;cfg_receive=1;admission_available=3;
 mr_setup(3,0,0,32'h10000000,32'h10000000);
 mr_setup(1,0,16'hf123,0,32'h80000008);mr_setup(1,1,16'habcd,0,32'h80000009);
 mr_cfg_access=0;mr_setup(1,2,16'hf123,0,32'h8000000a);mr_cfg_access=1;mr_bootstrap_done=1;
 configure(1,0,16'hf123,64'h8000000000000001,64'h8123456789abc000,0,1,0);
 configure(1,7,16'habcd,64'h9000000000000001,64'hfedcba9876543000,0,1,0);
 configure(2,0,0,64'h8000000000000001,0,2,0,0);configure(2,7,0,64'h9000000000000001,0,2,0,0);
 allow_work=0;enable=1;while(!tlp_tx_rd_req_tlp_valid)@(negedge clk);enable=0;
 configure(3,7,0,64'h9000000000000001,0,0,0,19);
 take_result(0,CASE_VALUE==3 ? 10:0,0,16'hf123,64'h8000000000000001,1,1);
 while(!admit_m_work_valid)@(negedge clk);
 repeat(17)begin @(negedge clk);
  if(!admit_m_work_valid || admit_queue_guard!==1 || rq_posted_count || mr_cfg_ready)
   $fatal(1,"held admitted owner lost MR/queue guard before actual RQ handoff");
 end
 allow_work=1;
 if(CASE_VALUE==3)begin
  repeat(40)begin @(negedge clk);
   if(dma_drained || !busy || backend_command_count!=1 || descriptors!=1 || dut.memory.idle)
    $fatal(1,"PCIe error bypassed actual withheld parent drain");
  end
  if(!actual_parent_dma_drained)$fatal(1,"generic PCIe engine did not drain after UR");
  configure(3,0,0,64'h8000000000000001,0,0,0,19);allow_parent_drain=1;
 end
 enable=1;
 take_result(2,0,7,16'habcd,64'h9000000000000001,1,2);
 if(CASE_VALUE!=3)take_result(1,0,0,16'hf123,64'h8000000000000001,2,3);
 take_result(3,0,7,16'habcd,64'h9000000000000001,2,CASE_VALUE==3 ? 3:4);
 enable=0;repeat(50)@(negedge clk);
 if(!parent_dma_drained || !dma_drained || busy || fault || admit_busy || rq_fault ||
    descriptors!=RESULT_COUNT || read_tlps!=RESULT_COUNT || read_completions!=RESULT_COUNT ||
    observed_results!=RESULT_COUNT || fetch_count!=RESULT_COUNT || result_count!=RESULT_COUNT ||
    actual_works!=RESULT_COUNT || actual_queries!=QUERY_COUNT || actual_posts!=POST_COUNT || rq_posted_count!=POST_COUNT ||
    generic_error_seen!=(CASE_VALUE==3) || receive_queue_halted!==(CASE_VALUE==3 ? 1:0) || queue_active)
  $fatal(1,"actual RQ PCIe/MR/posted ownership coverage/count mismatch works%d queries%d posts%d",actual_works,actual_queries,actual_posts);
 if(POST_COUNT!=0)begin
  rq_query=CASE_VALUE==0 ? 0:7;#1;
  if(!rq_m_head_valid || rq_m_head_context!==expected_contexts[CASE_VALUE==0 ? 0:CASE_VALUE==1 ? 3:2])
   $fatal(1,"actual posted full620 owner changed before take");
  rq_take=1;@(posedge clk);@(negedge clk);rq_take=0;#1;
  if(!rq_active || rq_taken_count!=1 || rq_held_context!==expected_contexts[CASE_VALUE==0 ? 0:CASE_VALUE==1 ? 3:2])
   $fatal(1,"actual retained receive owner changed on take");
  configure(3,7,0,64'h9000000000000001,0,0,0,19);
  mr_cfg_command=2;mr_cfg_index=1;mr_cfg_key=32'h80000009;mr_cfg_valid=1;
  repeat(17)begin @(negedge clk);if(mr_cfg_ready || mr_cfg_response_valid || !rq_active || !rq_queue_guard[7])
   $fatal(1,"held posted receive allowed real MR revoke");end
  mr_cfg_valid=0;
 end
 // A SAME-QPN SQ bank is independent from all retained receive owners.
 cfg_receive=0;configure(1,0,16'h1234,64'ha000000000000001,64'h8123456789abc000,0,1,0);
 if(queue_active!==1 || receive_queue_active!==8'h81)$fatal(1,"same-QPN trusted SQ/RQ bank alias");
 configure(3,0,0,64'ha000000000000001,0,0,0,0);
 for(i=0;i<512;i=i+1)if(host[i]!==records[i/128][(i%128)*8+:8])$fatal(1,"coherent ring was modified");
 $display("RECV_PCIE_RESULT {\"pass_test\":true,\"case\":%0d,\"fetches\":%0d,\"MR_queries\":%0d,\"posted\":%0d,\"held\":%0d,\"cycles\":%0d}",CASE_VALUE,descriptors,actual_queries,actual_posts,rq_active,cycle);
 $finish;
end
'''


def verify(output,data,case,expected):
    order=[0,2,3]if case==3 else [0,2,1,3]
    raw=[l.split()[1:]for l in output.splitlines()if l.startswith('RECV_PCIE_RAW ')]
    work=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('RECV_PCIE_WORK ')]
    posted=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('RECV_PCIE_POSTED ')]
    if len(raw)!=len(order):raise ValueError('actual coherent RQ raw count')
    for tag,(row,index)in enumerate(zip(raw,order),1):
        q=0 if index<2 else 7;error=10 if case==3 and index==0 else 0
        if [int(row[0]),int(row[1]),int(row[2],16),int(row[3]),int(row[4]),int(row[5])]!=[q,PDS[q],EPOCHS[q],index%2+1,tag,error]or \
           int(row[6],16)!=(0 if error else int.from_bytes(data[index],'little')):
            raise ValueError('independent actual128-byte PCIe/RQ trusted-context oracle')
    if work!=[expected[i][0]for i in order]or posted!=[expected[i][0]for i in order if expected[i][1]==0]:
        raise ValueError('independent full620 work/real RQ posting oracle')
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('RECV_PCIE_RESULT ')]
    if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual bounded connection assertions missing')
    return dict(summary=rows[0],all128_descriptor_bytes_and_full620_owners_verified=True,
        raw_bytes=len(raw)*128,actual_posted_contexts=[f'{v:0155x}'for v in posted])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if shutil.disk_usage(ROOT).free<256*1024**2:raise RuntimeError('original component256MiB guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('original RAM1GiB guard')
    run=Path(tempfile.mkdtemp(prefix='receive-pcie-post-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-pcie-post-',dir='/dev/shm'))
    derived=graph.derive();leaves={}
    for n in ['rocev2_sq_fetch.v','rocev2_sq_dma_fetch.v','rocev2_sq_wqe_admission.v','rocev2_wqe_admission.v']:
        path=graph.RTL/n;target=run/n;target.write_text(derived[path]);leaves[path]=target
    sources=[leaves.get(s,s)for s in fetch.old.SOURCES]
    sources += [leaves[graph.RTL/'rocev2_sq_wqe_admission.v'],leaves[graph.RTL/'rocev2_wqe_admission.v'],
        graph.RTL/'rocev2_mr_table.v',graph.RTL/'rocev2_receive_message_queue.v']
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma')]
    inputs=[*sources,*leaves,Path(__file__).resolve(),*helpers,*[codec.KERNEL/n for n in codec.SOURCES],*codec.KERNEL.glob('wqe*.h')]
    before={str(n.relative_to(ROOT)):digest(n)for n in dict.fromkeys(inputs)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},
        actual_C128_Corundum_PCIe_RAM_MR_and_message_RQ=True,physical_host_root_link_and_privileged_config_modeled=True,
        descriptor_status_RAM_or_MR_substitute=False,HLS_payload_MAC_CQ_or_installed_API=False,hardware_verified=False,
        four_state=True,runtime_limit_seconds=10,compile_limit_seconds=60)
    try:
        for case in range(4):
            folder=run/str(case);folder.mkdir();data=records(case);expected=contexts(data,case)
            (folder/'records.hex').write_text(''.join(f'{int.from_bytes(b,"little"):0256x}\n'for b in data))
            tb=folder/'tb.v';tb.write_text(bench(case,data,expected))
            command=['iverilog','-g2012','-s','tb','-o',str(ram/str(case)),str(tb),*map(str,sources)]
            start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=60)
            (folder/'compile.log').write_text(c.stdout+c.stderr)
            item=dict(compile_seconds=time.monotonic()-start,compile_exit=c.returncode,command=command);report['tests'][str(case)]=item
            if c.returncode:raise ValueError('actual PCIe/MR/message-RQ compile failed:'+str(folder/'compile.log'))
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/str(case))],cwd=folder,capture_output=True,text=True,timeout=10)
            (folder/'simulation.log').write_text(c.stdout+c.stderr);item.update(seconds=time.monotonic()-start,exit=c.returncode)
            if c.returncode or 'ERROR:'in c.stdout+c.stderr:raise ValueError('actual PCIe/MR/message-RQ failed:'+str(folder/'simulation.log'))
            item.update(verify(c.stdout,data,case,expected))
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.rglob('*')if n.is_file()}
        report['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=4,maximum_case_seconds=max(t['seconds']for t in report['tests'].values()))),flush=True)


if __name__=='__main__':main()
