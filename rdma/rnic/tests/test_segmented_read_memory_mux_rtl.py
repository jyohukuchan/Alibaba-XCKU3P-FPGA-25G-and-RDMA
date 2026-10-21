#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""New native READ memory selection + real old/source/READ/common-nonce RTL.

Keep all11 prior same-instance/READ/Atomic/zero/source/replay tests. Add real
READ unpad bypass/child/physical-nonce paths. Protected MR/token grants,
backend/fences/visibility and CQ remain MODELS; no native admission/runtime,
HLS/protocol/MSN/Linux/physical/timing qualification.
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
import test_segmented_executor_mux_rtl as old
import test_segmented_read_executor_rtl as read

ROOT=old.ROOT;digest=old.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_memory_native as source


def read_fixture(mux,unpad):
    mapping=dict(halt='parent_fault || up_fault',s_read_response_valid='token_take',s_read_response_ready='executor_token_ready',
        s_hls_write_command='up_command',s_hls_write_command_valid='up_command_valid',s_hls_write_command_ready='up_command_ready')
    for n in ['tdata','tkeep','tlast','tvalid','tready']:
        mapping['s_axis_hls_write_'+n]='up_'+n
        mapping['m_axis_memory_write_'+n]='m_axis_memory_'+n
    for n in ['write','offset','length','key','tag','valid','ready']:mapping['m_memory_command_'+n]='mx_command_'+n
    for n in ['tag','error','valid','ready']:mapping['s_memory_status_'+n]='mx_status_'+n
    decl=old.helper.instance(mux,'dut','',mapping)
    decl+='\nreg parent_fault=0;reg s_read_response_valid=0;wire s_read_response_ready=executor_token_ready && unpad_token_ready;wire token_take=s_read_response_valid && s_read_response_ready;wire executor_token_ready,unpad_token_ready;\n'
    decl+='wire [95:0] up_command;wire up_command_valid,up_command_ready;wire [511:0] up_tdata;wire [63:0] up_tkeep;wire up_tlast,up_tvalid,up_tready;\n'
    decl+='reg [95:0] s_hls_command=0;reg s_hls_command_valid=0;wire s_hls_command_ready;reg [511:0] s_axis_hls_tdata=0;reg [63:0] s_axis_hls_tkeep=0;reg s_axis_hls_tlast=0,s_axis_hls_tvalid=0;wire s_axis_hls_tready;\n'
    decl+='wire [511:0] m_axis_memory_tdata;wire [63:0] m_axis_memory_tkeep;wire m_axis_memory_tlast,m_axis_memory_tvalid;reg m_axis_memory_tready=0;\n'
    decl+='wire up_fault,up_busy;wire [7:0] up_fault_code;wire [MAX_QPS-1:0] up_guard;\n'
    um=dict(clk='clk',rst='rst',enable='enable',bypass='large_read_path',s_context='s_read_response_context',s_context_valid='token_take',s_context_ready='unpad_token_ready',downstream_queue_guard='downstream_queue_guard',
        s_command='s_hls_command',s_command_valid='s_hls_command_valid',s_command_ready='s_hls_command_ready',m_command='up_command',m_command_valid='up_command_valid',m_command_ready='up_command_ready',
        s_axis_tdata='s_axis_hls_tdata',s_axis_tkeep='s_axis_hls_tkeep',s_axis_tlast='s_axis_hls_tlast',s_axis_tvalid='s_axis_hls_tvalid',s_axis_tready='s_axis_hls_tready',
        m_axis_tdata='up_tdata',m_axis_tkeep='up_tkeep',m_axis_tlast='up_tlast',m_axis_tvalid='up_tvalid',m_axis_tready='up_tready',
        fault='up_fault',fault_code='up_fault_code',queue_guard='up_guard',busy='up_busy')
    decl+=old.helper.instance(unpad,'outer_unpad','u_',um)
    nonce=source.RTL/'rocev2_memory_command_nonce.v';nm=dict(clk='clk',rst='rst',enable='enable',parent_fault='fault || up_fault')
    for d,w,n in source.ports(nonce.read_text()):
        if n.startswith('s_command_'):nm[n]='mx_command_'+n.removeprefix('s_command_')
        elif n.startswith('m_command_'):nm[n]='m_memory_command_'+n.removeprefix('m_command_')
        elif n.startswith('s_status_'):nm[n]='s_memory_status_'+n.removeprefix('s_status_')
        elif n.startswith('m_status_'):nm[n]='mx_status_'+n.removeprefix('m_status_')
    decl+=old.helper.instance(nonce,'physical_nonce','n_',nm)
    for d,w,n in source.ports(mux.read_text()):
        if n.startswith('m_memory_command_')or n.startswith('s_memory_status_'):
            sig=mapping[n];decl+='wire '+(w+' 'if w else'')+sig+';\n'
    # Mapping suppresses generic declarations for these real backend pins.
    for d,w,n in source.ports(nonce.read_text()):
        if n.startswith('m_command_')or n.startswith('s_status_'):
            sig=nm[n];decl+=('wire 'if d=='output'else'reg ')+(w+' 'if w else'')+sig+(';'if d=='output'else'=0;')+'\n'
    decl+='wire [31:0] fragment_count=dut.read_fragments.fragment_count;wire [31:0] retired_count=dut.read_fragments.retired_count;wire [31:0] discarded_padding_bytes=dut.read_fragments.discarded_padding_bytes;\n'
    t=read.TB.replace('// DECLARATIONS',decl).replace("748'hOWNER",f"748'h{read.owner(4097):0187x}")
    t=source.once(t,'s_retire_context=expected;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)',
        's_retire_context=expected;s_retire_offer_valid=1;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)')
    t=source.once(t,'@(negedge clk);s_retire_valid=0;#1;',
        '@(negedge clk);s_retire_valid=0;s_retire_offer_valid=0;repeat(3)@(negedge clk);#1;')
    # Only retained READ adds this extra CQ consumer. Legacy memory handoff
    # still relies on its unchanged outer TX/lifetime CQ owner, not this mux.
    if t.count('m_memory_event_valid || s_retire_ready')!=2:raise ValueError('both data-before-status assertions required')
    t=t.replace('m_memory_event_valid || s_retire_ready','m_memory_event_valid || (large_read_path && s_retire_ready)')
    return t


class ReadMemory(old.Mux):
    reports={};runs=[]

    def simulate(self,body,read_case=False):
        run=Path(tempfile.mkdtemp(prefix='segmented-read-memory-mux-',dir=ROOT/'rdma/rnic/build'))
        ram=Path(tempfile.mkdtemp(prefix='as02-read-memory-mux-',dir='/dev/shm'))
        out=source.derive();paths=[]
        for p in [source.MUX,source.UNPAD,source.CHILD_UNPAD,source.executor.MUX,source.executor.CHILD,
                  source.RTL/'rocev2_wqe_memory_executor.v',source.RTL/'rocev2_wqe_read_unpad.v']:
            target=run/p.name;target.write_text(out[p]);paths.append(target)
        if read_case:t=read_fixture(run/source.MUX.name,run/source.UNPAD.name)
        else:
            t=old.fixture(run/source.MUX.name)
            t=source.once(t,'rocev2_segmented_executor_mux dut(','rocev2_segmented_read_executor_mux dut(')
            t=t.replace('dut.segmented.','dut.source_and_legacy.segmented.')
        (run/'tb.v').write_text(t.replace('// BODY',body));self.runs.append(run)
        sources=[*paths,source.READ,source.RTL/'rocev2_segmented_source_executor.v',source.RTL/'rocev2_memory_command_nonce.v']
        item=dict(directory=str(run.relative_to(ROOT)),pass_test=False,READ_route_test=read_case,runtime_limit_seconds=10)
        self.reports.setdefault(self._testMethodName,[]).append(item)
        try:
            cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),*map(str,sources)]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(run/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
            start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
            item.update(seconds=time.monotonic()-start,exit=r.returncode);(run/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);item['pass_test']=True
        finally:
            item['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
            item['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}

    def test_large_READ_actual_external_unpad_bypass_and_common_physical_nonce(self):
        self.simulate(r'''
bind_owner();if(!large_read_path)$fatal(1,"new retained READ role not selected");placement();
s_retire_context=expected;s_retire_offer_valid=1;stall_memory_once=1;
fragment(0,4096,1);if(m_memory_event_valid || s_retire_ready)$fatal(1,"partial READ completion");
fragment(4096,1,2);finish_success();
if(command_count!=2 || memory_status_count!=2 || n_command_count!=2 || n_retired_count!=2 || n_fault || up_fault ||
 u_context_count || u_discarded_padding_bytes || discarded_padding_bytes!=3)$fatal(1,"READ duplicated external pad/token or bypassed common nonce");
''',True)

    def test_short_READ_uses_original_unpad_and_executor_role(self):
        self.simulate(r'''
expected[307:276]=8;bind_owner();if(large_read_path)$fatal(1,"small READ changed role");placement();
raw_command(0);backend_command(0,8,1);payload(0,8);status(1);
if(!m_memory_event_valid || m_memory_event_context!==expected || u_context_count!=1 || discarded_padding_bytes)$fatal(1,"legacy READ unpad changed");
m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;repeat(4)@(negedge clk);
if(busy || queue_guard || up_fault || fault || n_fault || n_retired_count!=1 || retired_count)$fatal(1,"legacy READ memory handoff failed");
''',True)

    def test_large_READ_wrong_direction_and_nonatomic_CQ_never_alias_legacy(self):
        for offer in ["s_hls_read_command_valid=1;","s_retire_context=expected;s_retire_offer_valid=0;s_retire_valid=1;",
                      "s_retire_context=expected^1;s_retire_offer_valid=1;"]:
            self.simulate('bind_owner();placement();'+offer+'quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"READ aliased foreign command/CQ");',True)

    def test_unknown_unpad_route_quarantines_without_memory_or_release(self):
        self.simulate(r'''
bind_owner();placement();force large_read_path=1'bx;repeat(10)@(negedge clk);
if(up_fault!==1'b1 || busy!==1'b1 || (queue_guard|up_guard)!==255 || m_memory_command_valid!==1'b0 || m_memory_event_valid!==1'b0 || s_retire_ready!==1'b0)$fatal(1,"unknown route granted DMA/CQ");
''',True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    inputs=[*list((ROOT/'rdma/rnic/fpga').glob('*.py')),*list((ROOT/'rdma/rnic/rtl').glob('*.v')),
        Path(__file__).resolve(),Path(old.__file__).resolve(),Path(old.previous.__file__).resolve(),Path(read.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs};start=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ReadMemory);methods=suite.countTestCases();r=unittest.TextTestRunner(verbosity=2).run(suite)
    same=all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=methods,cases=sum(map(len,ReadMemory.reports.values())),seconds=time.monotonic()-start,
        source_unchanged=same,source_sha256=before,tests=ReadMemory.reports,all11_original_mux_cases_retained=True,
        actual_common_physical_command_nonce=True,MR_grant_RX_backend_CQ_visibility_modeled=True,
        native_runtime=False,large_READ_admission_open=False,hardware_verified=False,default_graph_changed=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['pass_test']else 1)
