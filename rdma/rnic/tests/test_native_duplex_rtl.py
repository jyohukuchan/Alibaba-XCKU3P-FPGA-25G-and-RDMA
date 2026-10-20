# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual duplex RTL/derivation with explicitly controlled HLS-port models.

This tests packet/command routing and independent lifetime handshakes, not
actual HLS receipts, memory authorization, native DMA or physical operation.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import test_shared_hls_roles_rtl as old
from test_wqe_hls_sq_rtl import context,expected_sq

ROOT=old.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_duplex_transport as duplex

def stub():
    text=duplex.derive_bridge();start=text.index('module rocev2_qptx_integrity_transport #')
    head=text[start:text.index('\n);',start)+3].replace('output reg','output wire').replace('=0','')
    body=[]
    for d,w,n in re.findall(r'\b(input|output) wire (\[[^]]+\] )?(\w+)',head):
        if d=='output':body+=['reg '+(w or'')+'STUB_'+n+'=0;','assign '+n+'=STUB_'+n+';']
    return head+'\n'+'\n'.join(body)+'\nendmodule\n'

TB=old.TB.replace('rocev2_shared_hls_transport dut(.*);',
    'rocev2_shared_hls_transport #(.QP_TX_ENABLE(1),.EXTERNAL_REPLAY_ENABLE(1),'
    '.RECV_ENABLE(1),.RNR_ENABLE(1),.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1),.REQUEST_CQ_ENABLE(1)) dut(.*);')
TB=TB.replace('dut.core.','dut.qptx_core.core.')
TB=TB.replace('// BODY',r'''
dut.qptx_core.core.STUB_s_request_owner_tready=1;
dut.qptx_core.core.STUB_s_recv_owner_tready=1;
remote_operation_idle=0;
// BODY
''')

class NativeDuplexRTLTests(unittest.TestCase):
    reports={}
    def simulate(self,body):
        source=duplex.derive()
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')
            for d,w,n in old.probe.ports(source))
        tb=TB.replace('// DECLARATIONS',decl).replace('// BODY',body)
        paths=[duplex.ORIGINAL,*duplex.EXTRA,Path(duplex.__file__).resolve(),Path(__file__).resolve(),
            Path(old.__file__).resolve(),Path(duplex.bridge.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py']
        before={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in paths}
        with tempfile.TemporaryDirectory(prefix='as02-duplex-rtl-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'shared.v').write_text(source);(p/'stub.v').write_text(stub())
            cmd=['iverilog','-g2012','-s','tb','-o',str(p/'test'),str(p/'tb.v'),str(p/'shared.v'),str(p/'stub.v'),*map(str,duplex.EXTRA)]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=20);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn('"pass_test":true',r.stdout)
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(source_sha256=before,output=r.stdout+r.stderr))
    def test_remote_requests_continue_while_local_owner_is_held(self):
        self.simulate(f'owner({context()});SQ({expected_sq()});'+r'''
dut.qptx_core.core.STUB_s_axis_rx_tready=1;
s_axis_rx_tdata=128'h1234;s_axis_rx_tkeep=16'hffff;s_axis_rx_tlast=0;s_axis_rx_tvalid=1;
s_local_rx_tdata=128'habcd;s_local_rx_tkeep=16'hffff;s_local_rx_tlast=1;s_local_rx_tvalid=1;
#1;if(!s_axis_rx_tready || s_local_rx_tready || dut.h_s_axis_rx_tdata!==128'h1234)$fatal(1,"remote RX blocked by local WR");
@(posedge clk);@(negedge clk);s_axis_rx_tdata=128'h5678;s_axis_rx_tlast=1;
#1;if(!s_axis_rx_tready || s_local_rx_tready || dut.h_s_axis_rx_tdata!==128'h5678)$fatal(1,"packet interleaved");
@(posedge clk);@(negedge clk);s_axis_rx_tvalid=0;
#1;if(!s_local_rx_tready || dut.h_s_axis_rx_tdata!==128'habcd)$fatal(1,"local response starved");
@(posedge clk);@(negedge clk);s_local_rx_tvalid=0;
if(!local_hls_active || shared_hls_fault)$fatal(1,"remote RX released local ownership");
''')
    def test_real_command_tags_route_both_clients_without_role_switch(self):
        self.simulate(f'owner({context()});SQ({expected_sq()});'+r'''
m_local_write_command_ready=1;m_axis_mem_write_cmd_tready=1;
m_local_write_tready=1;m_axis_mem_write_tready=1;
@(negedge clk);
dut.qptx_core.core.STUB_m_axis_mem_write_cmd_tdata={2'd1,18'd0,28'd1,48'h1234};
dut.qptx_core.core.STUB_m_axis_mem_write_cmd_tvalid=1;
#1;if(!m_axis_mem_write_cmd_tvalid || m_local_write_command_valid || m_axis_mem_write_cmd_tdata[95:94])$fatal(1,"remote command misrouted");
@(posedge clk);@(negedge clk);
dut.qptx_core.core.STUB_m_axis_mem_write_cmd_tdata={2'd2,18'd0,28'd1,48'habcd};
#1;if(!m_local_write_command_valid || m_axis_mem_write_cmd_tvalid || m_local_write_command[95:94])$fatal(1,"local command misrouted");
@(posedge clk);@(negedge clk);dut.qptx_core.core.STUB_m_axis_mem_write_cmd_tvalid=0;
if(dut.wr_origin.count!=2)$fatal(1,"exactly two accepted command credits required");
dut.qptx_core.core.STUB_m_axis_mem_write_tdata=512'h1234;
dut.qptx_core.core.STUB_m_axis_mem_write_tkeep=1;
dut.qptx_core.core.STUB_m_axis_mem_write_tlast=1;
dut.qptx_core.core.STUB_m_axis_mem_write_tvalid=1;
#1;if(!m_axis_mem_write_tvalid || m_local_write_tvalid)$fatal(1,"remote payload misrouted");
@(posedge clk);@(negedge clk);dut.qptx_core.core.STUB_m_axis_mem_write_tdata=512'habcd;
#1;if(!m_local_write_tvalid || m_axis_mem_write_tvalid)$fatal(1,"local payload misrouted fault%h wf%h wc%h role%h cnt%h rd%h local%h keep%h",shared_hls_fault,dut.wr_fault,dut.wr_origin.fault_code,dut.role,dut.wr_origin.count,dut.wr_origin.rd,dut.wr_origin.local_data,dut.wr_origin.selected_keep);
@(posedge clk);@(negedge clk);dut.qptx_core.core.STUB_m_axis_mem_write_tvalid=0;
repeat(3)@(negedge clk);if(shared_hls_fault || !local_hls_active || dut.wr_local_busy || dut.wr_remote_busy)$fatal(1,"duplex credits/lifetime");
''')
    def test_transmit_packet_direction_preserves_all_words_under_stall(self):
        for opcode,local in [(4,True),(0x11,False),(0xc,True),(0x10,False)]:
            self.simulate(f'owner({context()});SQ({expected_sq()});'+f'''
dut.qptx_core.core.STUB_m_axis_tx_tdata=128'h45;
dut.qptx_core.core.STUB_m_axis_tx_tkeep=16'hffff;
dut.qptx_core.core.STUB_m_axis_tx_tvalid=1;
@(posedge clk);@(negedge clk);
dut.qptx_core.core.STUB_m_axis_tx_tdata=128'h{opcode<<96:032x};
@(posedge clk);@(negedge clk);dut.qptx_core.core.STUB_m_axis_tx_tdata=128'habcd;
dut.qptx_core.core.STUB_m_axis_tx_tlast=1;
repeat(13)begin @(negedge clk);if({'!m_local_tx_tvalid || m_axis_tx_tvalid || m_local_tx_tdata!==128\'h45'if local else'!m_axis_tx_tvalid || m_local_tx_tvalid || m_axis_tx_tdata!==128\'h45'})$fatal(1,"stalled packet changed direction/word");end
m_local_tx_tready=1;m_axis_tx_tready=1;
@(posedge clk);@(negedge clk);
if({'m_local_tx_tdata'if local else'm_axis_tx_tdata'}!==128'h{opcode<<96:032x})$fatal(1,"second header word changed");
@(posedge clk);@(negedge clk);
if({'m_local_tx_tdata'if local else'm_axis_tx_tdata'}!==128'habcd || !{'m_local_tx_tlast'if local else'm_axis_tx_tlast'})$fatal(1,"payload/EOF changed");
@(posedge clk);@(negedge clk);dut.qptx_core.core.STUB_m_axis_tx_tvalid=0;
repeat(3)@(negedge clk);if(shared_hls_fault || !local_hls_active)$fatal(1,"TX ownership");
''')
    def test_retiring_either_direction_does_not_cancel_the_other(self):
        recv=context(opcode=4,length=128,remote=0,rkey=0)
        for recv_first in [False,True]:
            pre=f'owner({context()});SQ({expected_sq()});'+f'''
s_recv_owner_tdata={{4'd0,24'h123456,32'd65,{recv}}};s_recv_owner_tvalid=1;
@(posedge clk);@(negedge clk);s_recv_owner_tvalid=0;
if(!dut.recv_held || !local_hls_active)$fatal(1,"two independent owners not held");
dut.qptx_core.core.STUB_m_recv_done_tdata={{8'd0,24'd1,s_recv_owner_tdata}};
dut.qptx_core.core.STUB_m_recv_done_tvalid=1;m_recv_done_tready=1;
dut.qptx_core.core.STUB_m_request_done_tdata={{12'd0,8'h0a,24'h123457,24'h123456,expected_owner}};
dut.qptx_core.core.STUB_m_request_done_tvalid=1;m_request_done_ready=1;
@(posedge clk);@(negedge clk);
dut.qptx_core.core.STUB_m_recv_done_tvalid=0;dut.qptx_core.core.STUB_m_request_done_tvalid=0;
repeat(2)@(negedge clk);remote_operation_idle=1;
'''
            local=r'''
s_local_retire_context=expected_owner;s_local_retire_valid=1;
#1;if(!s_local_retire_ready || local_core_drained)$fatal(1,"exact per-request proof cannot retire independently");
@(posedge clk);@(negedge clk);s_local_retire_valid=0;
'''
            remote=r'''
s_recv_retire_context=s_recv_owner_tdata[587:0];s_recv_retire_valid=1;
#1;if(!s_recv_retire_ready)$fatal(1,"exact per-receive proof cannot retire independently");
@(posedge clk);@(negedge clk);s_recv_retire_valid=0;
'''
            self.simulate(pre+(remote+'if(!local_hls_active)$fatal(1,"RECV retire canceled local WR");\n'+local if recv_first else
                local+'if(!dut.recv_held)$fatal(1,"local retire canceled RECV");\n'+remote)+
                'if(shared_hls_fault || local_hls_active || dut.recv_held)$fatal(1,"final independent retire");')
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_DUPLEX_RTL_REPORT'):
            result=dict(scope=__doc__,pass_test=len(cls.reports)==4 and sum(map(len,cls.reports.values()))==8,methods=len(cls.reports),
                simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                actual_HLS=False,hardware_verified=False)
            with Path(name).open('x')as f:f.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':unittest.main()
