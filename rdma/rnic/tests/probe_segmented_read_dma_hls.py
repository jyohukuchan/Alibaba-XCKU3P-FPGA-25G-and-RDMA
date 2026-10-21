#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual READ C++ output snapshots -> actual origin router/unpad/executor RTL.

Instrument a copy of the unchanged passing fixture, not the HLS body or its
assertions. Record genuine full748 owner/96-bit memCmd/padded payload, then
consume unchanged snapshots in four-state RTL. This is separate executions,
NOT cycle-coupled HLS/generated-RTL/native MR/PTE/DMA/visibility/CQ/Linux or
physical qualification. Placement, backend status/fence and CQ are MODELS.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import probe_segmented_read_hls as hls
import test_segmented_read_executor_rtl as unit

ROOT=hls.ROOT;digest=hls.digest;once=hls.once
ROUTER=ROOT/'rdma/rnic/rtl/rocev2_memory_origin_router.v'

TRACE=r'''
        ap_uint<96> trace_raw=0;
        trace_raw(47,0)=c.addr;trace_raw(75,48)=c.len;trace_raw[76]=c.ctl;
        trace_raw[77]=c.strm;trace_raw[78]=c.sync;trace_raw[79]=c.host;
        trace_raw(83,80)=c.tdst;trace_raw(89,84)=c.pid;trace_raw(93,90)=c.vfid;trace_raw(95,94)=c.origin;
        std::cout<<std::dec<<"READ_DMA_TRACE "<<owner.to_string(16)<<" "<<offset<<" "<<trace_raw.to_string(16)<<std::endl;
'''

DRIVER=r'''
reg [747:0] trace_owner[0:3];reg [95:0] trace_command[0:277];
reg [576:0] trace_data[0:WORDS_MINUS_ONE];
integer wi,pi=0,di=0,words=0,wait_limit;
reg [576:0] trace_word;
task trace_raw_command;
 begin
  @(negedge clk);s_hls_command=trace_command[pi];s_hls_command_valid=1;wait_limit=cycle+100;
  @(posedge clk);while(!s_hls_command_ready)begin @(posedge clk);if(cycle>wait_limit)$fatal(1,"actual C++ raw command rejected %h %h",fault_code,r_fault_code);end
  @(negedge clk);s_hls_command_valid=0;
 end
endtask
task trace_payload;input integer offset;input integer bytes;
 integer limit;
 begin
  fragment_base=offset;fragment_bytes=bytes;fragment_written=0;trace_word=0;
  while(!trace_word[576])begin
   trace_word=trace_data[di];di=di+1;
   @(negedge clk);s_axis_hls_tdata=trace_word[511:0];s_axis_hls_tkeep=trace_word[575:512];s_axis_hls_tlast=trace_word[576];s_axis_hls_tvalid=1;limit=cycle+200;
   @(posedge clk);while(!s_axis_hls_tready)begin @(posedge clk);if(cycle>limit)$fatal(1,"actual C++ payload rejected %h %h",fault_code,r_fault_code);end
   @(negedge clk);s_axis_hls_tvalid=0;
  end
  limit=cycle+100;while(fragment_written!=bytes)begin @(negedge clk);if(cycle>limit)$fatal(1,"actual C++ bytes not placed");end
  repeat(5)begin @(negedge clk);if(m_memory_event_valid || s_retire_ready)$fatal(1,"data without real modeled status completed READ");end
 end
endtask
'''

BODY=r'''
$readmemh("owners.hex",trace_owner);$readmemh("commands.hex",trace_command);$readmemh("data.hex",trace_data);
if($test$plusargs("BAD_ORIGIN") || $test$plusargs("BAD_ROUTED_COMMAND"))begin
 expected=trace_owner[0];bind_owner();placement();
 s_hls_command=trace_command[0];
 if($test$plusargs("BAD_ORIGIN"))s_hls_command[95:94]=0;else s_hls_command[0]=~s_hls_command[0];
 s_hls_command_valid=1;quarantine();
 if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"corrupt copy of real command authorized DMA");
 $display("READ_DMA_SNAPSHOT_NEGATIVE");
end else begin
 for(wi=0;wi<4;wi=wi+1)begin
  expected=trace_owner[wi];total_written=0;events=0;bind_owner();placement();
  s_retire_context=expected;s_retire_valid=1;
  for(off=0;off<expected[307:276];off=off+4096)begin
   count=expected[307:276]-off>4096 ? 4096:expected[307:276]-off;
   trace_raw_command();backend_command(off,count,16'ha001+pi);trace_payload(off,count);status(16'ha001+pi);pi=pi+1;
   if(off+count<expected[307:276] && m_memory_event_valid)$fatal(1,"actual C++ partial message completed whole WR");
  end
  if(!m_memory_event_valid || total_written!=expected[307:276] || events || s_retire_ready || retired_count!=wi)$fatal(1,"whole snapshot memory/CQ lifetime mismatch");
  repeat(10)@(negedge clk);m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
  if(!busy || queue_guard!==4 || events!=1 || retired_count!=wi)$fatal(1,"snapshot memory event released before CQ");
  @(posedge clk);if(!s_retire_ready)$fatal(1,"identical full snapshot CQ refused");
  @(negedge clk);s_retire_valid=0;#1;if(busy || queue_guard || fault || r_busy || r_fault || retired_count!=wi+1)$fatal(1,"snapshot CQ release mismatch");
 end
 if(pi!=278 || di!=WORDS || fragment_count!=278 || owner_count!=4 || retired_count!=4 || discarded_padding_bytes!=9)$fatal(1,"all genuine snapshots/counters required");
 $display("READ_DMA_SNAPSHOT {\"pass_test\":true,\"whole_WRs\":4,\"fragments\":278,\"placed_bytes\":1126403,\"padding\":9,\"actual_origin_router_unpad_executor\":true}");
end
'''


def snapshot(output):
    hls.verify_read(output)
    commands=[];payload=[];owners=[]
    for line in output.splitlines():
        if line.startswith('READ_DMA_TRACE '):
            _,owner,offset,command=line.split();owner,offset,command=int(owner,16),int(offset),int(command,16)
            if offset==0:owners.append(owner)
            commands.append((owner,offset,command))
        elif line.startswith('SEGMENTED_READ_DATA '):
            _,length,offset,data=line.split();payload.append((int(length),int(offset),bytes.fromhex(data)))
    if len(commands)!=278 or len(owners)!=4 or len(payload)!=278:raise ValueError('all actual READ commands/data required')
    words=[];total=0
    for (owner,offset,command),(length,data_offset,data)in zip(commands,payload):
        if ((owner>>276)&0xffffffff)!=length or offset!=data_offset or command>>94!=2 or ((command>>48)&0xfffffff)!=len(data):
            raise ValueError('actual owner/command/payload tuple mismatch')
        total+=min(4096,length-offset)
        for p in range(0,len(data),64):
            b=data[p:p+64];words.append(int.from_bytes(b,'little')|(((1<<len(b))-1)<<512)|(int(p+64>=len(data))<<576))
    if total!=1126403:raise ValueError('all actual destination payload extents required')
    return owners,commands,words


def bench(words):
    mapping=dict(parent_fault='r_fault',s_hls_command='route_command',s_hls_command_valid='route_command_valid',s_hls_command_ready='route_command_ready',
        s_axis_hls_tdata='route_data',s_axis_hls_tkeep='route_keep',s_axis_hls_tlast='route_last',s_axis_hls_tvalid='route_valid',s_axis_hls_tready='route_ready')
    decl=unit.helper.instance(unit.RTL,'dut','',mapping)
    decl+='\nwire [95:0] route_command;wire route_command_valid,route_command_ready;wire [511:0] route_data;wire [63:0] route_keep;wire route_last,route_valid,route_ready;\n'
    decl+='reg [95:0] s_hls_command=0;reg s_hls_command_valid=0;wire s_hls_command_ready;reg [511:0] s_axis_hls_tdata=0;reg [63:0] s_axis_hls_tkeep=0;reg s_axis_hls_tlast=0,s_axis_hls_tvalid=0;wire s_axis_hls_tready;\n'
    route=dict(clk='clk',rst='rst',local_owned='busy && !fault',remote_owned="1'b0",
        s_command='s_hls_command',s_command_valid='s_hls_command_valid',s_command_ready='s_hls_command_ready',
        m_local_command='route_command',m_local_command_valid='route_command_valid',m_local_command_ready='route_command_ready',
        s_data='s_axis_hls_tdata',s_keep='s_axis_hls_tkeep',s_last='s_axis_hls_tlast',s_valid='s_axis_hls_tvalid',s_ready='s_axis_hls_tready',
        m_local_data='route_data',m_local_keep='route_keep',m_local_last='route_last',m_local_valid='route_valid',m_local_ready='route_ready')
    decl+=unit.helper.instance(ROUTER,'router','r_',route)
    text=unit.TB.replace('// DECLARATIONS',decl+DRIVER).replace("748'hOWNER","748'd0")
    text=once(text,"m_memory_command_offset!==64'h1234567800000210+offset","m_memory_command_offset!==expected[179:116]+offset")
    text=text.replace('WORDS_MINUS_ONE',str(words-1)).replace('WORDS',str(words))
    return text.replace('// BODY',BODY.replace('WORDS',str(words)))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cpp-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    old=json.loads(a.cpp_report.read_text());source=ROOT/'rdma/rnic/build/native-segmented-read-transport-003'
    if not all(old.get(n)for n in ['pass_test','source_unchanged','full_top_CPP_compiled'])or len(old.get('tests',{}))!=11:raise ValueError('full new-core C++ regressions required')
    before={};frozen_old=ROOT/old['directory']
    for key in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:
        for n,h in old[key].items():
            q=Path(n);q=q if q.is_absolute()else ROOT/q
            if digest(q)!=h:raise ValueError('changed prior C++ evidence:'+n)
            if not q.is_relative_to(Path('/dev/shm')):before[str(q.relative_to(ROOT))]=h
    for n in [Path(__file__).resolve(),Path(hls.__file__).resolve(),Path(unit.__file__).resolve(),Path(unit.source.__file__).resolve(),unit.RTL,ROUTER,a.cpp_report.resolve()]:before[str(n.relative_to(ROOT))]=digest(n)
    run=Path(tempfile.mkdtemp(prefix='segmented-read-DMA-HLS-',dir=ROOT/'rdma/rnic/build'));ram=Path(tempfile.mkdtemp(prefix='as02-read-DMA-HLS-',dir='/dev/shm'))
    for n in frozen_old.iterdir():
        if n.suffix in ['.cpp','.hpp']:shutil.copy2(n,run/n.name)
    t=(run/'test.cpp').read_text();t=once(t,'        std::vector<unsigned char> actual;bool eof=false;',TRACE+'\n        std::vector<unsigned char> actual;bool eof=false;');(run/'test.cpp').write_text(t)
    command=[str(run/'test.cpp')if x==str(frozen_old/'test.cpp')else '-I'+str(run)if x=='-I'+str(frozen_old)else str(ram/'cpp')if x==old['compile_command'][-1]else x for x in old['compile_command']]
    result=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),compile_command=command,
        runtime_limit_seconds=30,tests={},actual_CPP_then_RTL_snapshots=True,cycle_coupled=False,actual_generated_HLS_RTL=False,
        native_integration=False,hardware_verified=False,protected_RX_and_backend_CQ_visibility_modeled=True)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=600,env=env)
        result['CPP_compile_seconds']=time.monotonic()-start;(run/'cpp-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('instrumented copy of actual C++ fixture compile failed')
        start=time.monotonic();r=subprocess.run([str(ram/'cpp'),'read'],capture_output=True,text=True,timeout=30,preexec_fn=hls.old.no_core)
        result['CPP_seconds']=time.monotonic()-start;(run/'cpp.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise ValueError('actual unchanged READ consumers failed')
        owners,commands,words=snapshot(r.stdout)
        (run/'owners.hex').write_text(''.join(f'{n:0187x}\n'for n in owners));(run/'commands.hex').write_text(''.join(f'{n:024x}\n'for o,off,n in commands));(run/'data.hex').write_text(''.join(f'{n:0145x}\n'for n in words))
        (run/'child.v').write_text(unit.source.child_source());(run/'unpad.v').write_text(unit.source.unpad_source());(run/'tb.v').write_text(bench(len(words)))
        snapshots={str((run/n).relative_to(ROOT)):digest(run/n)for n in ['owners.hex','commands.hex','data.hex']};result['unaltered_CPP_snapshot_sha256']=snapshots
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'rtl'),str(run/'tb.v'),str(unit.RTL),str(ROUTER),str(run/'child.v'),str(run/'unpad.v')]
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(run/'rtl-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('actual router/controller/children compile failed')
        if any(re.search(r'(?i)port .*expects .*bits',l)for l in c.stderr.splitlines()):raise ValueError('actual port width mismatch')
        for mode in ['positive','BAD_ORIGIN','BAD_ROUTED_COMMAND']:
            start=time.monotonic();r=subprocess.run(['vvp',str(ram/'rtl'),*(['+'+mode]if mode!='positive'else[])],cwd=run,capture_output=True,text=True,timeout=30)
            (run/(mode+'.log')).write_text(r.stdout+r.stderr);result['tests'][mode]=dict(seconds=time.monotonic()-start,exit=r.returncode)
            if r.returncode:raise ValueError('actual C++-snapshot RTL consumer failed:'+mode)
            marker='READ_DMA_SNAPSHOT 'if mode=='positive'else'READ_DMA_SNAPSHOT_NEGATIVE'
            if marker not in r.stdout:raise ValueError('actual snapshot consumer assertions missing')
        if any(digest(ROOT/n)!=h for n,h in {**before,**snapshots}.items()):raise ValueError('consumed source/actual snapshots changed')
        result.update(pass_test=True,source_unchanged=True,full748_owners=4,commands=278,actual_payload_bytes=1126403,padding_bytes_removed=9,
            actual_origin_router=True,actual_bounded_unpad_executor=True,whole_owner_CQ_releases=4)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,CPP_compile_seconds=result['CPP_compile_seconds'],CPP_seconds=result['CPP_seconds'],tests=result['tests'])))


if __name__=='__main__':main()
