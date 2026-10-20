#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual dispatcher/legacy/large child/common nonce, backend/CQ are MODELS.

Exercise same-instance legacy -> large+replays -> legacy, real unchanged READ/
Atomic placement, zero work, and fail-closed foreign interfaces. Not native
large admission, peer/MAC/CQ or physical qualification.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
import probe_atomic_responder as helper
import test_segmented_source_executor_rtl as previous

ROOT=helper.ROOT;digest=helper.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_executor as source


def fixture(mux):
    ports=source.parent.helpers.module_ports(mux)
    aliases=dict(halt='parent_fault',s_hls_read_command='s_hls_command',s_hls_read_command_valid='s_hls_command_valid',
        s_hls_read_command_ready='s_hls_command_ready')
    for field in ['tdata','tkeep','tlast','tvalid','tready']:
        aliases['m_axis_hls_read_'+field]='m_axis_hls_'+field
        aliases['s_axis_memory_read_'+field]='s_axis_memory_'+field
    for field in ['write','offset','length','key','tag','valid','ready']:
        aliases['m_memory_command_'+field]='mx_command_'+field
    for field in ['tag','error','valid','ready']:aliases['s_memory_status_'+field]='mx_status_'+field
    names={};connections=[]
    for direction,width,port in ports:
        sig=aliases.get(port,port);connections.append('.'+port+'('+sig+')')
        shared=sig.startswith(('mx_command_','mx_status_'))
        names[sig]=('wire'if shared or direction=='output'else'reg',width)
    declarations='\n'.join(kind+' '+(width+' 'if width else'')+n+('=0;'if kind=='reg'else';')for n,(kind,width)in names.items())
    declarations+='\nrocev2_segmented_executor_mux dut('+','.join(connections)+');\n'
    nonce=ROOT/'rdma/rnic/rtl/rocev2_memory_command_nonce.v';mapping=dict(clk='clk',rst='rst',enable='enable',parent_fault='fault',
        busy='nonce_busy',configuration_guard='nonce_guard',fault='nonce_fault',fault_code='nonce_fault_code',
        exhausted='nonce_exhausted',command_count='nonce_commands',status_count='nonce_statuses',retired_count='nonce_retired')
    for field in ['write','offset','length','key','tag','valid','ready']:
        mapping['s_command_'+field]='mx_command_'+field;mapping['m_command_'+field]='m_memory_command_'+field
    for field in ['tag','error','valid','ready']:
        mapping['s_status_'+field]='s_memory_status_'+field;mapping['m_status_'+field]='mx_status_'+field
    for direction,width,port in source.parent.helpers.module_ports(nonce):
        sig=mapping[port]
        if sig not in names and sig not in ['clk','rst','enable','fault']:
            declarations+=('reg 'if direction=='input'else'wire ')+(width+' 'if width else'')+sig+('=0;'if direction=='input'else';')+'\n'
            names[sig]=('reg'if direction=='input'else'wire',width)
    declarations+=source.parent.helpers.instance(nonce,'physical_nonce',mapping)
    declarations+='\nwire [31:0] fragment_count=dut.segmented.fragment_count;\n'
    declarations+='wire [31:0] replay_count=dut.segmented.replay_count;wire [31:0] retired_count=dut.segmented.retired_count;\n'
    declarations+=f"localparam [747:0] LARGE_OWNER=748'h{previous.owner():0187x};\n"
    t=previous.TB.replace('// DECLARATIONS',declarations).replace("748'hOWNER",f"748'h{previous.owner():0187x}")
    t=t.replace('rst=0;enable=1;m_axis_hls_tready=1;','rst=0;enable=1;m_axis_hls_tready=1;downstream_queue_guard=4;')
    t=t.replace('task quarantine;',r'''
task legacy_read_source;input [15:0] physical;
 begin
  @(negedge clk);s_hls_command={2'd0,10'd2,4'hc,1'b1,1'b0,1'b1,1'b1,28'd8,48'hba9876543210};s_hls_command_valid=1;
  @(posedge clk);while(!s_hls_command_ready)@(posedge clk);
  @(negedge clk);s_hls_command_valid=0;
  backend_command(0,8,physical);backend_data(0,8);status(physical);
 end
endtask
task legacy_placement;input [15:0] physical;
 begin
  @(negedge clk);s_read_response_context=expected;s_read_response_valid=1;
  @(posedge clk);while(!s_read_response_ready)@(posedge clk);
  @(negedge clk);s_read_response_valid=0;
  s_hls_write_command={2'd0,10'd2,4'hc,1'b1,1'b0,1'b1,1'b1,28'd8,48'hba9876543210};s_hls_write_command_valid=1;
  @(posedge clk);while(!s_hls_write_command_ready)@(posedge clk);
  @(negedge clk);s_hls_write_command_valid=0;
  deadline=cycle+100;while(!m_memory_command_valid)begin @(negedge clk);if(cycle>deadline)$fatal(1,"placement command timeout");end
  if(!m_memory_command_write || m_memory_command_tag!==physical || m_memory_command_length!==8 ||
   m_memory_command_offset!==64'h210 || m_memory_command_key!==8)$fatal(1,"legacy placement tuple/physical nonce");
  m_memory_command_ready=1;@(posedge clk);@(negedge clk);m_memory_command_ready=0;
  s_axis_hls_write_tdata=512'h0123456789abcdef;s_axis_hls_write_tkeep=255;s_axis_hls_write_tlast=1;s_axis_hls_write_tvalid=1;
  @(posedge clk);while(!s_axis_hls_write_tready)@(posedge clk);
  @(negedge clk);s_axis_hls_write_tvalid=0;
  while(!m_axis_memory_write_tvalid)@(negedge clk);
  if(m_axis_memory_write_tdata!==512'h0123456789abcdef || m_axis_memory_write_tkeep!==255 || !m_axis_memory_write_tlast)$fatal(1,"legacy actual result bytes");
  m_axis_memory_write_tready=1;@(posedge clk);@(negedge clk);m_axis_memory_write_tready=0;status(physical);
 end
endtask
task consume_event;
 begin
  if(!m_memory_event_valid || m_memory_event_context!==expected || m_memory_event_error)$fatal(1,"legacy whole event identity");
  m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
  repeat(3)@(negedge clk);if(busy || queue_guard || fault || nonce_fault)$fatal(1,"legacy event ownership not handed off");
 end
endtask
task quarantine;''')
    return t


class Mux(unittest.TestCase):
    reports={};runs=[]
    def simulate(self,body):
        run=Path(tempfile.mkdtemp(prefix='segmented-executor-mux-',dir=ROOT/'rdma/rnic/build'))
        ram=Path(tempfile.mkdtemp(prefix='as02-segmented-mux-',dir='/dev/shm'))
        out=source.derive();paths=[]
        for original in [source.MUX,source.CHILD,source.RTL/'rocev2_wqe_memory_executor.v']:
            p=run/original.name;p.write_text(out[original]);paths.append(p)
        (run/'tb.v').write_text(fixture(run/source.MUX.name).replace('// BODY',body));self.runs.append(run)
        sources=[*paths,source.RTL/'rocev2_segmented_source_executor.v',source.RTL/'rocev2_memory_command_nonce.v']
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.reports.setdefault(self._testMethodName,[]).append(dict(directory=str(run.relative_to(ROOT)),
            seconds=time.monotonic()-start,RAM_binary_sha256=digest(ram/'test')))

    def test_same_instance_legacy_large_replays_legacy_and_global_nonce(self):
        self.simulate(r'''
expected=LARGE_OWNER;expected[307:276]=8;expected[339:324]=2;bind_owner();legacy_placement(1);consume_event();
expected=LARGE_OWNER;expected[523:460]=8;bind_owner();
fragment(0,4096,2);fragment(0,4096,3);fragment(4096,4096,4);fragment(8192,1,5);
if(!m_memory_event_valid || !busy || queue_guard!==4)$fatal(1,"large source event lost owner");
m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
fragment(8192,1,6);
if(m_memory_event_valid || fragment_count!=3 || replay_count!=2 || !busy || events!=2)$fatal(1,"large post-event replay/one-event semantics");
s_retire_context=expected;s_retire_offer_valid=1;s_retire_valid=0;
repeat(20)begin @(negedge clk);if(!busy || queue_guard!==4 || retired_count)$fatal(1,"source released before other genuine CQ consumer ready");end
s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"large CQ retirement readiness");
@(negedge clk);s_retire_valid=0;s_retire_offer_valid=0;repeat(3)@(negedge clk);
expected=LARGE_OWNER;expected[523:460]=9;expected[307:276]=8;expected[339:324]=7;bind_owner();legacy_placement(7);consume_event();
if(owner_count!=3 || command_count!=7 || memory_status_count!=7 || nonce_commands!=7 || nonce_statuses!=7 || nonce_retired!=7 || retired_count!=1)$fatal(1,"mixed real dispatcher/global nonce counts");
''')

    def test_legacy_READ_and_Atomic_actual_result_placement(self):
        for op in [2,7]:
            self.simulate(r'''
expected=LARGE_OWNER;expected[307:276]=8;expected[339:324]=OP;
bind_owner();legacy_placement(1);consume_event();
if(command_count!=1 || memory_status_count!=1 || nonce_commands!=1 || nonce_fault)$fatal(1,"legacy placement dispatch changed");
'''.replace('=OP;','='+str(op)+';'))

    def test_zero_SEND_keeps_no_memory_authority_on_legacy_path(self):
        self.simulate(r'''
expected=LARGE_OWNER;expected[339:324]=3;expected[307:276]=0;expected[275:20]=0;
bind_owner();repeat(5)@(negedge clk);consume_event();
if(command_count || memory_status_count || nonce_commands)$fatal(1,"legacy zero invented DMA");
''')

    def test_ordinary_small_WRITE_SEND_uses_retained_source_and_global_nonce(self):
        for op in [1,3]:
            self.simulate(r'''
expected=LARGE_OWNER;expected[307:276]=8;expected[339:324]=OP;
if(OP==3)expected[115:20]=0;
bind_owner();fragment(0,8,1);
if(!m_memory_event_valid || !busy || queue_guard!==4)$fatal(1,"small source dispatch lost lease");
m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
fragment(0,8,2);
if(m_memory_event_valid || fragment_count!=1 || replay_count!=1 || !busy || events!=1)$fatal(1,"small source post-event replay lost");
s_retire_context=expected;s_retire_offer_valid=1;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"small source CQ fanout not ready");
@(negedge clk);s_retire_valid=0;s_retire_offer_valid=0;repeat(3)@(negedge clk);
if(busy || queue_guard || fault || nonce_fault || nonce_commands!=2 || nonce_retired!=2 || retired_count!=1)$fatal(1,"small source physical nonce/CQ lifetime");
'''.replace('OP',str(op)))

    def test_large_mode_rejects_unowned_placement_or_write_interfaces(self):
        for offered in ['s_read_response_valid=1;','s_hls_write_command_valid=1;','s_axis_hls_write_tvalid=1;',
                        's_retire_context=expected^1;s_retire_offer_valid=1;s_retire_valid=0;',
                        's_retire_context=expected;s_retire_offer_valid=0;s_retire_valid=1;']:
            self.simulate('bind_owner();'+offered+'quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"large mode silently aliased foreign interface");')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    paths=[Path(__file__).resolve(),Path(source.__file__).resolve(),Path(previous.__file__).resolve(),
        source.RTL/'rocev2_segmented_source_executor.v',source.RTL/'rocev2_memory_command_nonce.v',Path(helper.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in paths};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Mux))
    assert all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=Mux.reports,four_state=True,actual_legacy_source_child_and_common_nonce=True,
        backend_CQ_and_trusted_MR_grant_modeled=True,native_large_or_hardware_runtime=False,
        artifact_sha256={str(n.relative_to(ROOT)):digest(n)for run in Mux.runs for n in run.iterdir()if n.is_file()})
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
