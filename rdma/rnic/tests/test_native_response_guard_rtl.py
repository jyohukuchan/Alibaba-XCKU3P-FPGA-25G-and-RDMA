# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native coherent READ WQE/MR -> protected wire response -> executor DMA.

Actual packet integrity/peer/QP/PSN/length gate generates the placement token;
not a copied authorized context. HLS extraction/commands, expected issued PSN/
connection, physical host/link and final wire/CQ remain EXPLICIT MODELS.
No actual HLS READ/peer completion/kernel pins/board/standard verbs is proven.
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

import test_native_memory_executor_rtl as native
import test_wqe_response_guard_rtl as response

ROOT=native.ROOT


def make_tb(words):
    tb=native.make_tb(words,True)
    start=tb.index('// The trusted protected-response controller is a MODEL here, NOT raw HLS.')
    end=tb.index('\ne_s_hls_write_command=96\'h',start)
    tb=tb[:start]+r'''
// Issued PSN/connection values are MODELS; the actual response protection and
// whole-packet integrity, original WQE identity and token are production RTL.
rg_s_expect_valid=1;@(posedge clk);if(!rg_s_expect_ready)$fatal(1,"native protected expectation");
@(negedge clk);rg_s_expect_valid=0;
response_send(0);
payload_deadline=cycle+5000;while(!rg_m_reject_valid)begin if(cycle>payload_deadline)$fatal(1,"native wrong-peer/QP rejection deadline");@(negedge clk);end
repeat(13)begin @(negedge clk);if(rg_m_reject_error!=8'h92 || response_tokens || response_words || rg_accepted_count ||
 s_local_memory_command_valid || local_memory_busy || e_m_memory_event_valid || router_descriptor_count!=1 || !control_busy || quiet || config_safe)
 $fatal(1,"bad protected response reached HLS/DMA or released native owner");end
rg_m_reject_ready=1;@(posedge clk);@(negedge clk);rg_m_reject_ready=0;
response_send(8);
payload_deadline=cycle+5000;while(!rg_m_axis_hls_rx_tvalid)begin if(cycle>payload_deadline)$fatal(1,"native protected replay deadline");@(negedge clk);end
repeat(11)begin @(negedge clk);if(response_tokens!=1 || response_words || s_local_memory_command_valid || !e_busy || !rg_busy ||
 !control_busy || quiet || config_safe || e_m_memory_event_valid)$fatal(1,"protected token/replay stall owner");end
response_allow_frame=1;
while(!rg_m_response_event_valid)begin if(cycle>payload_deadline)$fatal(1,"native validated response event deadline");@(negedge clk);end
if(response_words!=8 || response_tokens!=1 || rg_accepted_count!=1 || rg_rejected_count!=1 || rg_integrity_drop_count ||
 rg_m_response_event_context!==e_m_memory_event_context || rg_m_response_event_opcode!=8'h10 || rg_m_response_event_psn!=24'hfffffe)
 $fatal(1,"actual native protected response context/frame");
'''+tb[end:]
    tb=native.memory.sq.once(tb,'completion_queue_guard=0;collect_native(8,405,0,0,2);',r'''
// Native memory event is not a CQ. The real response guard continues holding
// its wire owner until the separately held downstream CQ MODEL takes it.
if(wire_queue_guard!==8'h04 || !rg_m_response_event_valid || !rg_busy)$fatal(1,"response wire owner vanished at memory status");
rg_m_response_event_ready=1;@(posedge clk);@(negedge clk);rg_m_response_event_ready=0;
repeat(3)@(negedge clk);
if(rg_busy || wire_queue_guard || rg_fault || quiet || !control_busy)$fatal(1,"response event falsely completed downstream CQ owner");
completion_queue_guard=0;collect_native(8,405,0,0,2);''')
    # The real packet validator, NOT a copied-context model, drives the actual
    # executor's private placement input and native wire guard.
    for name in ['e_s_read_response_context','e_s_read_response_valid','wire_queue_guard']:
        tb,count=re.subn(r'\breg (\[[^]]+\]\s+)?'+name+r'=0;',lambda m:'wire '+(m[1]or'')+name+';',tb)
        if count!=1:raise ValueError('modeled response declaration changed '+name)
        if re.search(r'\b'+name+r'\s*(?:<=|=(?!=))',tb):raise ValueError('modeled response authority driver survived '+name)
    mapping=dict(clk='clk',rst='rst',enable="1'b1",halt="1'b0",s_expect_context='e_m_memory_event_context',
        s_expect_local_ip="32'hc6120b02",s_expect_peer_ip="32'hc6120b01",s_expect_psn="24'hfffffe",
        m_read_response_context='e_s_read_response_context',m_read_response_valid='e_s_read_response_valid',
        m_read_response_ready='e_s_read_response_ready',downstream_queue_guard='executor_queue_guard | completion_queue_guard',
        queue_guard='wire_queue_guard',m_axis_hls_rx_tready='response_ready')
    h=response.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h,re.M)
    declarations=[];connections=[]
    for direction,width,name in ports:
        target=mapping.get(name,'rg_'+name);connections.append(f'.{name}({target})')
        if name not in mapping:declarations.append(('reg 'if direction=='input'else'wire ')+(width or'')+target+('=0;'if direction=='input'else';'))
    block='\n'.join(declarations)+'\n'+r'''
reg response_allow_frame=0,response_ready=0;reg [127:0] response_frames[0:15];
integer response_position,response_deadline,response_tokens=0,response_words=0;
reg response_stall=0;reg [144:0] held_response;
initial $readmemh("response.hex",response_frames);
// Sample ready on the opposite edge, not a recomputed expression after the
// original fixture's blocking posedge cycle counter has already advanced.
always @(negedge clk)response_ready=!rst && response_allow_frame && cycle%11>2;
task response_send;
 input integer start;
 begin
  response_deadline=cycle+5000;
  for(response_position=0;response_position<116;response_position=response_position+16)begin
   @(negedge clk);rg_s_axis_rx_tdata=response_frames[start+response_position/16];
   rg_s_axis_rx_tkeep=response_position==112 ? 16'hf : 16'hffff;rg_s_axis_rx_tlast=response_position==112;rg_s_axis_rx_tvalid=1;
   @(posedge clk);while(!rg_s_axis_rx_tready)begin if(cycle>response_deadline)$fatal(1,"native protected response input deadline");@(posedge clk);end
  end
  @(negedge clk);rg_s_axis_rx_tvalid=0;
 end
endtask
always @(posedge clk)if(!rst)begin
 if(e_s_read_response_valid && e_s_read_response_ready)begin
  if(e_s_read_response_context!==e_m_memory_event_context || executor_queue_guard!==8'h04 || rg_m_axis_hls_rx_tvalid)
   $fatal(1,"actual protected placement token/native owner ordering");
  response_tokens=response_tokens+1;
 end
 if(response_stall && (!rg_m_axis_hls_rx_tvalid || {rg_m_axis_hls_rx_tlast,rg_m_axis_hls_rx_tkeep,rg_m_axis_hls_rx_tdata}!==held_response))$fatal(1,"native protected replay changed under stall");
 response_stall=rg_m_axis_hls_rx_tvalid&&!response_ready;
 held_response={rg_m_axis_hls_rx_tlast,rg_m_axis_hls_rx_tkeep,rg_m_axis_hls_rx_tdata};
 if(rg_m_axis_hls_rx_tvalid && response_ready)begin
  if(response_words>=8 || rg_m_axis_hls_rx_tdata!==response_frames[8+response_words] ||
   rg_m_axis_hls_rx_tkeep!==(response_words==7 ? 16'hf : 16'hffff) || rg_m_axis_hls_rx_tlast!==(response_words==7) || response_tokens!=1)
   $fatal(1,"native protected actual response bytes/context word%0d got%h expected%h keep%h last%b tokens%0d",response_words,rg_m_axis_hls_rx_tdata,response_frames[8+response_words],rg_m_axis_hls_rx_tkeep,rg_m_axis_hls_rx_tlast,response_tokens);
  response_words=response_words+1;
 end
 if(rg_fault)$fatal(1,"native response protection fault%h",rg_fault_code);
end
'''
    block+='\nrocev2_wqe_response_guard response_guard('+',\n'.join(connections)+');\n'
    tb=native.memory.sq.once(tb,'rocev2_wqe_memory_executor executor(',block+'\nrocev2_wqe_memory_executor executor(')
    return f'`include "{response.RTL}"\n'+tb


class NativeResponseGuardTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):native.shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def test_actual_response_rejection_then_full_context_placement_scattered_DMA_and_fence(self):
        words=native.memory.sq.local.fixture.packet();tb=make_tb(words)
        paths=native.sq.input_paths(tb)+[Path(__file__).resolve(),Path(native.__file__).resolve(),Path(native.memory.__file__).resolve(),
            native.executor.RTL,Path(native.executor.__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',native.PRODUCER,
            response.RTL,Path(response.__file__).resolve(),Path(response.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        records=[]
        for i in range(2):
            w=native.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
                remote_key=0,opcode=2,flags=1,length=65)
            data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(data,C.byref(w)),0)
            self.assertEqual(bytes(data),native.shared.codec.oracle(w));records.append(bytes(data))
        good=bytearray(response.packet(mig=1));good[35]=2;good=response.repair(good)
        bad=bytearray(good);bad[35]=3;bad=response.repair(bad)
        frames=[int.from_bytes(p[n:n+16].ljust(16,b'\0'),'little')for p in [bad,good]for n in range(0,len(p),16)]
        with tempfile.TemporaryDirectory(prefix='as02-native-response-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(native.shared.protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words));(p/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
            (p/'response.hex').write_text(''.join(f'{v:032x}\n'for v in frames))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),*map(str,native.memory.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text();names=['rocev2_wqe_response_guard','rocev2_wqe_memory_executor','rocev2_wqe_hls_sq',
                'rocev2_mr_table','rocev2_mr_page_table','rocev2_memory_client_arbiter','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[23:])for l in r.stdout.splitlines()if l.startswith('NATIVE_EXECUTOR_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual(rows[0]['physical_descriptors'],4);self.assertEqual(rows[0]['read_tlps'],2)
            self.assertEqual(rows[0]['write_tlps'],2);self.assertEqual(rows[0]['fences'],1)
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],actual_elaborated_module_counts=counts,source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),wrong_QPN_rejected_without_memory_side_effect=True,
            actual_protected_READ_token=True,actual_HLS_extraction=False)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_RESPONSE_GUARD_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==1,methods=len(cls.reports),tests=cls.reports,
                actual_native_SQ_MR_RX_integrity_response_guard_executor_PTE_generic_PCIe_fence=True,
                HLS_extraction_expected_issued_context_physical_host_link_and_CQ_models=True,
                actual_HLS_READ_response=False,actual_WR_completion=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
