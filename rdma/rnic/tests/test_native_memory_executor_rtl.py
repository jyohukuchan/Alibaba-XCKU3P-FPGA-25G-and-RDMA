# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual coherent WQE/SAME-MR -> SQ producer/executor -> shared paged PCIe.

HLS is STUBBED; raw HLS requests, authenticated READ-response admission,
physical host/link and downstream wire/CQ ownership are EXPLICIT MODELS.
The execution binding, saved memory authority and DMA/fence are actual RTL.
No real protected READ response, peer ACK, native RDMA CQ or pins is claimed.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import native_memory_fixture as memory
import test_native_sq_rtl as sq
import test_shared_mr_responder_rtl as shared
import test_wqe_memory_executor_rtl as executor
from test_wqe_hls_sq_rtl import context,expected_sq

ROOT=memory.ROOT
PRODUCER=ROOT/'rdma/rnic/rtl/rocev2_wqe_hls_sq.v'


def make_tb(words,placement):
    ctx=context(id=0xf123456789abc001,sequence=1,epoch=0x9123456700000001,qpn=2,pd=17,tag=1,
        lkey=8,address=0xfedcba9876543210,offset=0x210,remote=0xf123456789abc001,
        opcode=2 if placement else 1,flags=1,length=65)
    body=memory.sq.prefix()+f'''
enable=1;sq_command(2,1,0,0,0);
sq_deadline=cycle+3000;while(!m_hls_sq_tvalid && cycle<sq_deadline)@(negedge clk);
if(!m_hls_sq_tvalid || m_hls_sq_tdata!=={expected_sq(opcode=2 if placement else 1,qpn=2,remote=0xf123456789abc001)} ||
 e_m_memory_event_context!=={ctx} || e_owner_count!=1 || executor_queue_guard!==8'h04 ||
 e_m_memory_event_valid || read_tlps!=1 || write_tlps || local_memory_busy)$fatal(1,"actual executor owner/SQ identity");
host_stage(8,405,0,0,0,0,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(17)begin @(negedge clk);if(!control_busy || !admission_pause || quiet || config_safe)$fatal(1,"STOP passed actual executor owner");end
m_hls_sq_tready=1;@(posedge clk);@(negedge clk);m_hls_sq_tready=0;
'''
    if placement:
        body+=r'''
// The trusted protected-response controller is a MODEL here, NOT raw HLS.
e_s_read_response_context=e_m_memory_event_context;e_s_read_response_valid=1;
@(posedge clk);if(!e_s_read_response_ready)$fatal(1,"modeled protected response context");
@(negedge clk);e_s_read_response_valid=0;
'''
    select='write'if placement else'read'
    body+=f'''
e_s_hls_{select}_command={executor.raw_command(qpn=2)};e_s_hls_{select}_command_valid=1;
@(posedge clk);if(!e_s_hls_{select}_command_ready)$fatal(1,"modeled HLS raw command mismatch");
@(negedge clk);e_s_hls_{select}_command_valid=0;
if(s_local_memory_command_key!==8 || s_local_memory_command_offset!==64'h210 ||
 s_local_memory_command_length!==65 || s_local_memory_command_tag!==1 || !s_local_memory_command_valid)
 $fatal(1,"executor did not derive full saved SAME-MR authority");
// Native enable pauses the WHOLE outer DMA router, not just admissions.
// Its accepted owner must survive that pause; resume before expecting new
// physical descriptors. Executor-local admission disable is tested alone.
enable=0;repeat(17)begin @(negedge clk);if(!e_busy || executor_queue_guard!==8'h04 ||
 e_m_memory_event_valid || quiet || config_safe || router_descriptor_count!=1)$fatal(1,"paused native DMA lost lifetime or fabricated completion");end
enable=1;payload_position=0;payload_deadline=cycle+5000;
while(payload_position<65)begin
 payload_amount=65-payload_position;if(payload_amount>64)payload_amount=64;
'''
    if placement:
        body+=r'''
 e_s_axis_hls_write_tdata={512{1'bx}};e_s_axis_hls_write_tkeep=0;
 for(payload_lane=0;payload_lane<payload_amount;payload_lane=payload_lane+1)begin
  e_s_axis_hls_write_tdata[payload_lane*8+:8]=pcie_pattern(payload_position+payload_lane);e_s_axis_hls_write_tkeep[payload_lane]=1;
 end
 e_s_axis_hls_write_tlast=payload_position+payload_amount==65;e_s_axis_hls_write_tvalid=1;
 @(posedge clk);while(!e_s_axis_hls_write_tready)begin if(cycle>payload_deadline)$fatal(1,"executor placement deadline");@(posedge clk);end
 @(negedge clk);e_s_axis_hls_write_tvalid=0;
'''
    else:
        body+=r'''
 while(!e_m_axis_hls_read_tvalid)begin if(cycle>payload_deadline)$fatal(1,"executor DMA source deadline");@(negedge clk);end
 if(e_m_axis_hls_read_tlast!==(payload_position+payload_amount==65))$fatal(1,"executor source last");
 for(payload_lane=0;payload_lane<64;payload_lane=payload_lane+1)begin
  if(e_m_axis_hls_read_tkeep[payload_lane]!==(payload_lane<payload_amount) ||
   e_m_axis_hls_read_tdata[payload_lane*8+:8]!==
   (payload_lane<payload_amount ? pcie_host[4093+payload_position+payload_lane] : 8'd0))$fatal(1,"executor source host bytes/padding");
 end
 repeat(11)begin @(negedge clk);if(e_m_memory_event_valid || !e_busy || quiet || config_safe || !control_busy)$fatal(1,"executor payload stall released owner");end
 e_m_axis_hls_read_tready=1;@(posedge clk);@(negedge clk);e_m_axis_hls_read_tready=0;
'''
    body+=r'''
 payload_position=payload_position+payload_amount;
end
while(!e_m_memory_event_valid)begin if(cycle>payload_deadline)$fatal(1,"actual executor backend event deadline");@(negedge clk);end
repeat(17)begin @(negedge clk);if(e_m_memory_event_error || executor_queue_guard!==8'h04 || !e_busy ||
 !control_busy || quiet || config_safe || !e_m_memory_event_valid || !native_sq_dma_drained)$fatal(1,"memory event falsely completed RDMA/CQ");end
sq_command(3,1,35,0,0);
// Explicit downstream wire/CQ MODEL takes memory owner BEFORE its ready.
completion_queue_guard=8'h04;e_m_memory_event_ready=1;@(posedge clk);@(negedge clk);e_m_memory_event_ready=0;
repeat(11)begin @(negedge clk);if(e_busy || executor_queue_guard || quiet || config_safe || !control_busy)$fatal(1,"memory handoff lost actual downstream guard");end
completion_queue_guard=0;collect_native(8,405,0,0,2);sq_command(3,1,0,31,1);
if(!quiet || !config_safe || e_fault || sq_submission_fault || e_owner_count!=1 || e_command_count!=1 ||
 e_memory_status_count!=1 || sq_work_results!=1 || sq_fetch_count!=1 || commands || completed || txframes || local_memory_busy)
 $fatal(1,"executor native final scope/drain");
for(payload_lane=0;payload_lane<16384;payload_lane=payload_lane+1)begin
 if(pcie_posted_valid[payload_lane])$fatal(1,"executor unfenced host byte");
'''
    body+=f'''
 if({int(placement)} && payload_lane>=4093 && payload_lane<4158)begin
  if(pcie_host[payload_lane]!==pcie_pattern(payload_lane-4093))$fatal(1,"executor placed host byte");
 end else if(pcie_host[payload_lane]!==(((payload_lane*37)^8'h5a)&8'hff))$fatal(1,"executor changed host sentinel%0d",payload_lane);
end
check_ring();
$display("NATIVE_EXECUTOR_RESULT {{\\"pass_test\\":true,\\"payload_bytes_checked\\":65,\\"physical_descriptors\\":%0d,\\"read_tlps\\":%0d,\\"write_tlps\\":%0d,\\"fences\\":%0d,\\"actual_local_RDMA_completion\\":false}}",router_descriptor_count,read_tlps,write_tlps,fences);
$finish;
'''
    tb=memory.enable_memory(memory.sq.make_tb(words,body))
    tb=memory.sq.once(tb,memory.TASKS,'')
    tb=memory.sq.once(tb,'#(.LOCAL_MEMORY_ENABLE(1)) dut(','#(.LOCAL_MEMORY_ENABLE(1),.HLS_SQ_ENABLE(1)) dut(')
    # Remove ONLY the old modeled executor drivers, retaining all actual
    # work/management/ring/PCIe/host sentinel and stable-offer assertions.
    tb=memory.sq.once(tb,"  if(retain_work)executor_queue_guard<=8'h04;",'')
    tb=memory.sq.once(tb,' if(release_work)executor_queue_guard<=0;','')
    mapping=dict(clk='clk',rst='rst',enable="1'b1",halt="1'b0",
        s_owner_context='m_executor_context',s_owner_valid='m_executor_context_valid',s_owner_ready='m_executor_context_ready',
        queue_guard='executor_queue_guard',downstream_queue_guard='completion_queue_guard')
    for a,b in [('m_memory_command_write','s_local_memory_command_write'),('m_memory_command_offset','s_local_memory_command_offset'),
        ('m_memory_command_length','s_local_memory_command_length'),('m_memory_command_key','s_local_memory_command_key'),
        ('m_memory_command_tag','s_local_memory_command_tag'),('m_memory_command_valid','s_local_memory_command_valid'),
        ('m_memory_command_ready','s_local_memory_command_ready')]:mapping[a]=b
    for suffix in ['tdata','tkeep','tlast','tvalid','tready']:
        mapping['m_axis_memory_write_'+suffix]='s_axis_local_memory_write_'+suffix
        mapping['s_axis_memory_read_'+suffix]='m_axis_local_memory_read_'+suffix
    for suffix in ['tag','error','valid','ready']:mapping['s_memory_status_'+suffix]='m_local_memory_status_'+suffix
    declarations=[];connections=[];existing_driven=set()
    header=executor.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',header,re.M)
    for direction,width,name in ports:
        target=mapping.get(name,'e_'+name);connections.append(f'.{name}({target})')
        if name not in mapping:
            declarations.append(('reg 'if direction=='input'else'wire ')+(width or'')+target+('=0;'if direction=='input'else';'))
        elif direction=='output':existing_driven.add(target)
    for name in existing_driven:
        pattern=r'\breg (\[[^]]+\]\s+)?'+name+r'=0;'
        tb,count=re.subn(pattern,lambda m:'wire '+(m[1]or'')+name+';',tb)
        if count!=1:raise ValueError('existing modeled driver declaration changed '+name)
    block='\n'.join(declarations)+'\ninteger payload_position,payload_lane,payload_amount,payload_deadline;\n'+\
        'rocev2_wqe_memory_executor executor(\n'+',\n'.join(connections)+');\n'+r'''
always @(posedge clk)if(!rst)begin
 if(s_local_memory_command_valid && s_local_memory_command_ready)begin
  if(executor_queue_guard!==8'h04 || s_local_memory_command_offset!==64'h210 || s_local_memory_command_key!==8 ||
   s_local_memory_command_length!==65 || s_local_memory_command_tag!==1)$fatal(1,"production executor changed actual authorized tuple");
  pcie_current_length=s_local_memory_command_length;pcie_current_offset=s_local_memory_command_offset;
 end
 if(e_fault)$fatal(1,"actual native executor fault%h",e_fault_code);
end
'''
    tb=memory.sq.once(tb,'rocev2_native_sq_endpoint #(',block+'\nrocev2_native_sq_endpoint #(')
    return f'`include "{PRODUCER}"\n`include "{executor.RTL}"\n'+tb


class NativeMemoryExecutorTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def simulate(self,placement):
        words=memory.sq.local.fixture.packet();tb=make_tb(words,placement)
        paths=sq.input_paths(tb)+[Path(__file__).resolve(),Path(memory.__file__).resolve(),executor.RTL,
            Path(executor.__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',PRODUCER]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        records=[]
        for i in range(2):
            w=shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
                remote_key=0,opcode=2 if placement else 1,flags=1,length=65)
            data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(data,C.byref(w)),0)
            self.assertEqual(bytes(data),shared.codec.oracle(w));records.append(bytes(data))
        with tempfile.TemporaryDirectory(prefix='as02-native-executor-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(shared.protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words));(p/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),*map(str,memory.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text()
            names=['rocev2_wqe_memory_executor','rocev2_wqe_hls_sq','rocev2_native_sq_endpoint',
                'rocev2_mr_table','rocev2_mr_page_table','rocev2_memory_client_arbiter','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[23:])for l in r.stdout.splitlines()if l.startswith('NATIVE_EXECUTOR_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual(rows[0]['physical_descriptors'],4 if placement else 3)
            self.assertEqual(rows[0]['read_tlps'],2 if placement else 3)
            self.assertEqual(rows[0]['write_tlps'],2 if placement else 0);self.assertEqual(rows[0]['fences'],int(placement))
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],actual_elaborated_module_counts=counts,source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest())

    def test_actual_native_WQE_executor_reads_registered_scattered_host_pages(self):self.simulate(False)
    def test_actual_native_READ_destination_executor_requires_response_owner_and_visibility_fence(self):self.simulate(True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_MEMORY_EXECUTOR_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==2,methods=len(cls.reports),tests=cls.reports,
                actual_native_SQ_MR_executor_PTE_generic_PCIe=True,HLS_stub=True,
                authenticated_response_and_wire_CQ_models=True,actual_local_RDMA_completion=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
