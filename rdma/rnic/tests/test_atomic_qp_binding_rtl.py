# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQC/mailbox/fetch owner arrays -> Atomic privileged route binding.

Network configuration source, downstream lease assertion and physical DMA
backend are models. No force/internal table writes or invented lookup reply.
Not full native Atomic admission/MAC/API or host-unpin qualification.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_sq_control_regs_rtl as legacy
import probe_atomic_responder as ports

ROOT=legacy.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic_owner_lookup as lookup
RTL=ROOT/'rdma/rnic/rtl/rocev2_atomic_qp_binding.v'

TASKS=r'''
task route;
 input [23:0] q;input [15:0] pd;input txonly;
 begin
  @(negedge clk);p_cfg_qpn=q;p_cfg_pd=pd;p_cfg_tx_only=txonly;
  p_cfg_peer_qpn=24'hf1234c;p_cfg_local_ip=32'hc6120b02;p_cfg_peer_ip=32'hc6120b01;p_cfg_valid=1;
  #1;if(!p_cfg_binding_ready)$fatal(1,"actual owner route not ready");
  p_cfg_fire=1;@(posedge clk);@(negedge clk);p_cfg_fire=0;p_cfg_valid=0;p_cfg_tx_only=0;#1;
 end
endtask
task bound;
 input [63:0] epoch,cookie;
 begin
  #1;if(!p_bound_valid || !p_admission_valid || p_bound_qpn!==7 || p_bound_pd!==17 ||
    p_bound_epoch!==epoch || p_bound_cookie!==cookie || p_bound_peer_qpn!==24'hf1234c ||
    p_bound_local_ip!==32'hc6120b02 || p_bound_peer_ip!==32'hc6120b01 || p_fault)
   $fatal(1,"actual SQC epoch/cookie/PD/route binding lost or stale");
 end
endtask
task close_queue;
 begin
  defaults(3,0,64'h8123456789abcdef);stage_words();bell();reply(0,31);ack();
  if(owner_active || fetch_active || atomic_query_valid || p_admission_valid)
   $fatal(1,"closed SQC authority still admits Atomic");
 end
endtask
'''
INITIAL=r'''
initial begin
 scenario=0;subcase=0;rst=0;repeat(2)@(negedge clk);rst=1;parent_dma_drained=1;
 repeat(8)@(negedge clk);rst=0;
 // BODY
 // Deliberately asserted parent fault is expected to quarantine the SQC.
 // Every other case must still reject any unexpected SQC fatal status.
 if((fatal && !endpoint_fault) || mmio_error || fetch_fault || fetches || results)$fatal(1,"unexpected actual SQC/DMA mutation or fault");
 $display("ATOMIC_QP_BINDING_RESULT {\"pass_test\":true,\"configs\":%0d,\"fetches\":%0d,\"bound_epoch\":\"%016h\",\"binding_fault\":%0d}",configs,fetches,p_bound_epoch,p_fault);
 $finish;
end
endmodule
'''


class AtomicQPBindingTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        authored=[RTL,lookup.SOURCE,Path(lookup.__file__).resolve(),Path(__file__).resolve(),
            Path(ports.__file__).resolve(),Path(legacy.__file__).resolve(),legacy.HEADER,*legacy.SOURCES]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in authored}
        with tempfile.TemporaryDirectory(prefix='as02-atomic-qp-binding-')as temporary:
            p=Path(temporary);sq=p/'rocev2_sq_control_regs.v';sq.write_text(lookup.derive())
            io=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(?:\[([^]]+)\]\s+)?(\w+)',sq.read_text().split('\n);',1)[0])
            driven={'cfg_ready','cfg_response_error','cfg_response_qpn','cfg_response_epoch','cfg_response_consumer',
                'cfg_response_valid','fetch_queue_guard','wire_queue_guard','atomic_query_qpn'}
            decl='\n'.join(legacy.pcie.declaration(n,legacy.pcie.width(e,dict(ADDR_WIDTH=12,MAX_QPS=8)),
                'reg'if d=='input'and n not in driven else'wire')for d,e,n in io)
            macros='\n'.join('localparam '+n+'='+re.sub(r'([0-9a-fA-F]+)U$',r'\1',v).replace('0x',"32'h")+';'
                for n,v in re.findall(r'^#define (AS02_SQC_\w+) (\w+)',legacy.HEADER.read_text(),re.M))
            instance=ports.instance(RTL,'binding','p_',dict(clk='clk',rst='rst',parent_fault='fatal || endpoint_fault',
                m_query_qpn='atomic_query_qpn',s_query_cookie='atomic_query_cookie',s_query_epoch='atomic_query_epoch',
                s_query_pd='atomic_query_pd',s_query_valid='atomic_query_valid'))
            tb=legacy.TB[:legacy.TB.index('initial begin\n scenario=0;')]
            tb=tb.replace('// ABI',macros).replace('// DECLARATIONS',decl+'\n'+instance+
                '\nassign wire_queue_guard=p_queue_guard;\n').replace('INITIAL_SEQUENCE_VALUE','0')
            tb+=TASKS+INITIAL.replace('// BODY',body)
            if 'force 'in tb:raise ValueError('no internal table override')
            (p/'tb.v').write_text(tb)
            sources=[sq,RTL,*legacy.SOURCES[1:]]
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,sources)],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            s=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            if s.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic-qp-binding-failure-',dir=ROOT/'rdma/rnic/build'))
                for name in ['tb.v','test.vvp','rocev2_sq_control_regs.v']:shutil.copy2(p/name,diag/name)
                (diag/'simulation.log').write_text(s.stdout+s.stderr)
                print('Preserved failed fixture/binary/log: '+str(diag),flush=True)
            self.assertEqual(s.returncode,0,s.stdout+s.stderr);self.assertNotIn('ERROR:',s.stdout+s.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in s.stdout.splitlines()if l.startswith('ATOMIC_QP_BINDING_RESULT ')]
            self.assertEqual(len(rows),1,s.stdout);self.assertTrue(rows[0]['pass_test'])
            self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],
                source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
                derived_SQC_sha256=hashlib.sha256(sq.read_bytes()).hexdigest()))
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})

    def test_actual_owner_epoch_cookie_PD_and_route_snapshot(self):
        self.simulate(r'''
allocate();route(7,17,0);bound(64'h9123456700000001,64'hfedcba9889abcdef);
p_cfg_qpn=6;p_cfg_pd=19;p_cfg_peer_qpn=1;p_cfg_local_ip=1;p_cfg_peer_ip=2;
repeat(10)@(negedge clk);bound(64'h9123456700000001,64'hfedcba9889abcdef);
''')

    def test_full_width_unknown_unowned_or_wrong_PD_configuration_never_binds(self):
        for field in ["p_cfg_qpn=24'h800007;","p_cfg_qpn=24'hxxxx07;","p_cfg_qpn=6;","p_cfg_pd=18;"]:
            with self.subTest(field=field):self.simulate(r'''
allocate();@(negedge clk);p_cfg_qpn=7;p_cfg_pd=17;p_cfg_valid=1;p_cfg_local_ip=1;p_cfg_peer_ip=2;
'''+field+r'''
repeat(10)@(negedge clk);
if(p_cfg_binding_ready || p_bound_valid || p_admission_valid || p_fault || atomic_query_pd!=0 && p_cfg_pd==17)
 $fatal(1,"invalid lookup/cfg acquired RX binding");
''')

    def test_same_QPN_recreated_epoch_does_not_reauthorize_old_network_route(self):
        self.simulate(r'''
allocate();route(7,17,0);bound(64'h9123456700000001,64'hfedcba9889abcdef);
close_queue();
defaults(1,0,0);words[4]=2;words[6]=32'h89abcdf0;stage_words();bell();reply(0,7);ack();
if(!atomic_query_valid || atomic_query_epoch!==64'h9123456700000002 || p_admission_valid ||
 p_bound_epoch!==64'h9123456700000001 || p_bound_cookie!==64'hfedcba9889abcdef)
 $fatal(1,"recreated SQC owner revived old RX route");
route(7,17,0);bound(64'h9123456700000002,64'hfedcba9889abcdf0);
''')

    def test_actual_lease_guard_blocks_SQC_retirement_and_route_reconfiguration(self):
        self.simulate(r'''
allocate();route(7,17,0);p_lease_guard=1;#1;
if(!p_configuration_guard || wire_queue_guard!==128)$fatal(1,"Atomic lease absent from SQC protection");
defaults(3,0,64'h8123456789abcdef);stage_words();bell();reply(35,0);ack();
if(configs!=1 || owner_active!==128 || fetch_active!==128 || p_fault)$fatal(1,"held Atomic lease allowed SQC retirement");
p_cfg_valid=1;p_cfg_pd=0;repeat(10)@(negedge clk);
if(p_cfg_binding_ready || !p_bound_valid || p_bound_epoch!==64'h9123456700000001)$fatal(1,"held lease allowed tombstone");
p_cfg_valid=0;p_lease_guard=0;route(7,0,0);
if(p_bound_valid || p_admission_valid || p_bound_epoch || p_bound_cookie)$fatal(1,"tombstone retained RX authority");
close_queue();
''')

    def test_lookup_busy_during_legal_producer_update_does_not_abort_owned_Atomic(self):
        self.simulate(r'''
allocate();route(7,17,0);p_lease_guard=1;
defaults(2,1,0);stage_words();bell();reply(0,0);
if(atomic_query_valid || p_admission_valid || p_fault || p_bound_epoch!==64'h9123456700000001 ||
 !p_configuration_guard || wire_queue_guard!==128)$fatal(1,"busy lookup canceled owned Atomic or enabled new admission");
ack();bound(64'h9123456700000001,64'hfedcba9889abcdef);
if(!fetch_queue_guard[7] || !p_configuration_guard || wire_queue_guard!==128)
 $fatal(1,"producer update released actual fetch/Atomic owner");
// Offered fetch and Atomic lease remain held. This is NOT a drain/unpin test.
''')

    def test_TX_only_configuration_does_not_replace_active_RX_binding(self):
        self.simulate(r'''
allocate();route(7,17,0);route(6,19,1);bound(64'h9123456700000001,64'hfedcba9889abcdef);
route(7,0,0);
if(p_bound_valid || p_admission_valid || p_bound_epoch || p_bound_qpn || p_bound_pd)$fatal(1,"tombstone did not revoke");
''')

    def test_illegal_acceptance_unknown_lease_or_parent_fault_fail_closed(self):
        for change in ["p_cfg_valid=1;p_cfg_qpn=6;p_cfg_pd=17;p_cfg_fire=1;",
                       "p_lease_guard=1'bx;","p_cfg_fire=1'bx;","endpoint_fault=1;"]:
            with self.subTest(change=change):self.simulate(r'''
allocate();route(7,17,0);
'''+change+r'''
repeat(10)@(negedge clk);
if(!p_fault || p_admission_valid || !p_configuration_guard || wire_queue_guard!==255 ||
 p_bound_epoch!==64'h9123456700000001)$fatal(1,"invalid acceptance/fault released bound owner");
''')

    @classmethod
    def tearDownClass(cls):
        name=os.environ.get('AS02_ATOMIC_QP_BINDING_REPORT')
        if name:
            report=dict(scope=__doc__,pass_test=len(cls.reports)==7 and sum(map(len,cls.reports.values()))==13,
                methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                actual_SQC_mailbox_fetch_owner_arrays=True,actual_same_namespace_read_only_lookup=True,
                physical_DMA_and_network_configuration_and_lease_source_models=True,
                native_integrated=False,hardware_verified=False)
            with (ROOT/name).open('x')as f:f.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
