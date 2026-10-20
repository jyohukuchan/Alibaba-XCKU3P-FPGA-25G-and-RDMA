# SPDX-License-Identifier: BSD-2-Clause-Views
"""Enabled local WQE -> actual paged/controlled responder -> ONE shared MR.

Actual C codec, MR/PTE/control/segmented RAM are exercised. The default short
unit run explicitly stubs HLS; AS02_RNIC_SHARED_PAGED_HLS_BUILD selects actual
generated HLS. PCIe/host visibility and downstream local work lifetime are
MODELS, not host SQ fetch, local payload execution, CQ, verbs or board proof.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

import probe_controlled_responder as controlled
import probe_protected_paged_dma as paged
import shared_mr_fixture as fixture
import test_paged_responder_rtl as paged_unit
import test_shared_mr_responder_rtl as shared
import wrkey_delivery_sim as delivery

ROOT=fixture.probe.ROOT


def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError(f'fixture anchor changed: {old}')
    return text.replace(old,new)


def bench(layer,fixtures,body):
    top='rocev2_'+('controlled' if layer=='controlled' else 'paged')+'_responder'
    tb=controlled.bench() if layer=='controlled' else paged.composite_bench()
    declarations=replace_once(fixture.DECLARATIONS,',admission_pause=0','')
    tb=replace_once(tb,top+' dut(',declarations+'\n'+top+' #(.LOCAL_WQE_ENABLE(1)) dut(')
    # Replace only the optional client's explicit OFF tie-offs. No private
    # datapath state/configuration is forced or driven through hierarchy.
    for name,signal in re.findall(r'\.(\w+)\(([^()]*)\)',fixture.PORTS):
        if name=='cfg_admission_pause':continue
        pattern=r'\.'+name+r'\([^()]*\)'
        if len(re.findall(pattern,tb))!=1:raise ValueError('local port changed: '+name)
        tb=re.sub(pattern,lambda _:f'.{name}({signal})',tb)
    monitor=r'''
always @(posedge clk) if(!rst && (local_guard || executor_guard)) begin
 if(cfg_ready) $fatal(1,"PTE mutation escaped local WQE/downstream lease");
end
'''
    tb=replace_once(tb,'reg [144:0] stimulus',fixture.FRONTEND+monitor+'\nreg [144:0] stimulus')
    # These finite cases each execute ONE real incoming 65B WRITE through
    # actual page splitting/RAM/fence, not the original five-operation suite.
    begin=tb.index(' if(deferred==0');end=tb.index('$fatal(',begin)
    tb=tb[:begin]+''' if(deferred==0 || statuses!=1 || commands!=1 || completed!=1 || fault ||
 command_count!=1 || fence_count!=1 || completion_count!=1 || pcie_physical_reads!=1 || pcie_physical_writes!=2) '''+tb[end:]
    tb=replace_once(tb,' if(deferred==0',r''' $display("LOCAL_RESULT {\"queries\":%0d,\"results\":%0d,\"retained_leases\":%0d,\"executor_guard\":%0d}",local_queries,local_results,local_leases,executor_guard);
 if(deferred==0''')
    if layer=='controlled':
        tb=replace_once(tb,'if(op==5 && completed!=3)','if(op==5 && completed!=1)')
    extras=[ROOT/'rdma/rnic/rtl'/n for n in ['rocev2_wqe_admission.v','rocev2_mr_query_arbiter.v']]
    return '\n'.join(f'`include "{p}"'for p in extras)+'\n'+tb.replace(
        'STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)


class SharedMRPagedRTLTests(unittest.TestCase):
    reports={}
    record=shared.SharedMRResponderRTLTests.record
    local=shared.SharedMRResponderRTLTests.local

    @classmethod
    def setUpClass(cls):
        # Executes the SAME actual C/UBSan codec and independent byte oracle.
        shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def namespace_case(self):
        fixtures=fixture.packet()
        body=f'send_frame(0,{len(fixtures)});allow();\n'
        cases=[dict(local_key=8,opcode=1),dict(local_key=8,opcode=2),
               dict(local_key=0,error=1),dict(local_key=0x80000008,error=1),
               dict(local_key=10,opcode=2,error=3),dict(local_key=10,opcode=1),
               dict(local_key=8,local_address=fixture.probe.VA-1,error=4),
               dict(local_key=8,local_address=(fixture.probe.VA+0x210)&((1<<48)-1),error=4),
               dict(local_key=8,local_address=fixture.probe.VA+4095,error=4)]
        body+='\n'.join(self.local(**c)for c in cases)
        body+='\nlocal_pd=18;'+self.local(local_key=8,error=2)+'local_pd=17;\n'
        body+='''
admission_pause=1;
@(negedge clk);ci=0;cp=17;cc=2;ck=8;cv=1;car=0;
@(posedge clk);while(!cr)@(posedge clk);
@(negedge clk);cv=0;while(!cav)@(negedge clk);
if(ce!==0 || cak!==0)$fatal(1,"namespace MR revoke");
car=1;@(negedge clk);car=0;
page_management(4,0,8,0);configure_mr(0,17,7,16);publish_pages(0,16);admission_pause=0;
'''
        body+=self.local(local_key=8,error=1)+self.local(local_key=16)
        body+='if(local_results!=12 || local_queries!=12 || local_leases)$fatal(1,"namespace counts");'
        return 'paged',fixtures,body

    def page_lease_case(self):
        fixtures=fixture.packet();record,w=self.record(local_key=8)
        body=f'''
send_frame(0,{len(fixtures)});allow();
admission_pause=1;configure_mr(3,17,7,11);
// A raw PTE offer owns management BEFORE capture, even when pause is missing.
@(negedge clk);pc=1;pi=3;pk=11;pp=0;pa=pcie_dma_page(0);pv=1;par=0;
admission_pause=0;local_data={record};local_valid=1;
repeat(7)begin @(negedge clk);if(local_input_ready || local_guard || cfg_ready)$fatal(1,"PTE offer lost priority");end
admission_pause=1;
@(posedge clk);while(!cfg_ready)@(posedge clk);
@(negedge clk);pv=0;
while(!cfg_response_valid)@(negedge clk);
if(cfg_response_error || cfg_response_key!==11)$fatal(1,"PTE BEGIN failed");
// Remove the raw offer/pause to isolate accepted PTE response ownership.
admission_pause=0;
repeat(9)begin @(negedge clk);if(local_input_ready || local_guard || local_configuration_idle)$fatal(1,"held PTE response admitted WQE");end
admission_pause=1;par=1;@(posedge clk);@(negedge clk);par=0;
page_management(2,3,11,0);page_management(2,3,11,1);page_management(3,3,11,0);
retain_local_lease=1;admission_pause=0;
@(posedge clk);while(!local_input_ready)@(posedge clk);
@(negedge clk);local_valid=0;local_data=0;
expect_local(0,64'h{w.local_address:x},64'h210,32'd8,32'd65);
retain_local_lease=0;
if(local_busy || !executor_guard || quiet)$fatal(1,"handoff released lifetime");
// Both MR and PTE mutations must wait beyond lookup AND WQE-result handoff.
@(negedge clk);admission_pause=1;ci=0;cp=17;cc=2;ck=8;cv=1;car=0;
pc=4;pi=0;pk=8;pv=1;par=0;
repeat(12)begin @(negedge clk);if(cr || cav || cfg_ready || cfg_response_valid || quiet)$fatal(1,"revoke escaped downstream owner");end
release_local_lease();
@(posedge clk);while(!cr)@(posedge clk);
if(cfg_ready)$fatal(1,"PTE preempted MR revoke");
@(negedge clk);cv=0;while(!cav)begin @(negedge clk);if(cfg_ready)$fatal(1,"PTE entered MR pipeline");end
if(ce!==0 || cak!==0)$fatal(1,"deferred MR revoke");
repeat(7)begin @(negedge clk);if(cfg_ready)$fatal(1,"PTE bypassed held MR response");end
car=1;@(posedge clk);@(negedge clk);car=0;
@(posedge clk);while(!cfg_ready)@(posedge clk);
@(negedge clk);pv=0;while(!cfg_response_valid)@(negedge clk);
if(cfg_response_error || cfg_response_key!==8)$fatal(1,"deferred PTE revoke");
par=1;@(posedge clk);@(negedge clk);par=0;
configure_mr(0,17,7,16);publish_pages(0,16);admission_pause=0;
{self.local(local_key=8,error=1)}
{self.local(local_key=16)}
if(local_results!=3 || local_queries!=3 || local_leases!=1 || executor_guard)$fatal(1,"PTE lease counts");
'''
        return 'paged',fixtures,body

    def overlap_case(self,layer):
        fixtures=fixture.packet();record,w=self.record(local_key=8)
        body=f'''
local_allow_response=0;offer_local({record});
expiry=cycle+100;while(!lrv && cycle<expiry)@(negedge clk);
if(!lrv || !local_busy || quiet || cfg_ready)$fatal(1,"local MR response not owned");
repeat(9)@(negedge clk);
local_allow_response=1;local_enable=0;
expiry=cycle+100;while(!local_work_valid && cycle<expiry)@(negedge clk);
if(!local_work_valid)$fatal(1,"disable cancelled accepted local WQE");
// Start a FRESH packet while the local result still owns the MR lifetime.
// Using backend/PTE cfg_ready as admission would deadlock precisely here.
send_frame(0,{len(fixtures)});
expiry=cycle+3000;while(completed==0 && cycle<expiry)@(negedge clk);
if(completed!=1 || commands!=1 || !local_work_valid || quiet || cfg_ready || cr)$fatal(1,"fresh RX deadlocked behind local result");
retain_local_lease=1;
expect_local(0,64'h{w.local_address:x},64'h210,32'd8,32'd65);
retain_local_lease=0;
'''
        if layer=='controlled':
            body+='''
// The actual AXI controller must wait for the modeled downstream lease.
host_stage(5,OWNER0,0,8,0,0,0,0);
write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(20)begin @(negedge clk);
 if(!control_busy || !admission_pause || dut.cfg_mr_valid || dut.cfg_page_valid || quiet)$fatal(1,"controller fabricated local drain");
end
release_local_lease();
host_limit=cycle+5000;host_value=0;
while(!(host_value & AS02_ST_REPLY) && cycle<host_limit)read_reg(AS02_CTL_STATUS,host_value);
if(!(host_value & AS02_ST_REPLY))$fatal(1,"deferred controller invalidate deadline");
for(host_i=0;host_i<8;host_i=host_i+1)read_reg(AS02_CTL_REPLY_SEQ+host_i*4,host_reply[host_i]);
if(host_reply[0]!==host_pending_sequence || host_reply[1]!==5 || {host_reply[3],host_reply[2]}!==OWNER0 ||
 host_reply[4]!==0 || host_reply[5]!==8 || host_reply[6]!==0 || host_reply[7]!==3)$fatal(1,"deferred invalidate full proof");
write_reg(AS02_CTL_REPLY_ACK,host_pending_sequence,15,1,0);
host_value=0;while(!(host_value & AS02_ST_READY))read_reg(AS02_CTL_STATUS,host_value);
host_api(2,OWNER0+3,0,0,17,7,0,0,16,0);host_pages(OWNER0+3,0,16);
local_enable=1;
'''
            body+=self.local(local_key=8,error=1)+self.local(local_key=16)
            body+='if(local_results!=3 || local_queries!=3)$fatal(1,"controlled local results");'
        else:
            body+='release_local_lease();local_enable=1;'
            body+='if(local_results!=1 || local_queries!=1)$fatal(1,"paged local results");'
        body+='repeat(4)@(negedge clk);if(!quiet || executor_guard || local_busy || !local_configuration_idle)$fatal(1,"enabled layer not idle");'
        return layer,fixtures,body

    def simulate(self,case):
        layer,fixtures,body=case;tb=bench(layer,fixtures,body)
        self.assertNotIn('force ',tb)
        paths=[*shared.SOURCES,*paged.paged.SOURCES,controlled.TOP,controlled.CONTROL,
               *controlled.registers.SOURCES,controlled.registers.HEADER,
               ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',
               ROOT/'rdma/rnic/kernel/wqe.c',ROOT/'rdma/rnic/kernel/wqe.h',
               ROOT/'rdma/rtl/rocev2_integrity_transport.v']
        paths += [Path(m.__file__).resolve()for m in [paged,controlled,fixture,shared,paged_unit,
                  shared.codec,shared.protected,fixture.probe,controlled.registers,paged.paged]]+[Path(__file__).resolve()]
        paths += [ROOT/n for n in ['rdma/host/rocev2_wire.py','rdma/read/host/read_wire.py','rdma/tests/test_icrc_rtl.py']]
        hls=os.environ.get('AS02_RNIC_SHARED_PAGED_HLS_BUILD')
        identity={};retained=None;wire_checks=[]
        if hls:
            build=Path(hls);selected,manifest=delivery.verify_delivery(build)
            sources,data=delivery.ORIGINAL_MODULES(build)
            self.assertEqual(sources.count(delivery.OLD_BRIDGE),1)
            sources.remove(delivery.OLD_BRIDGE)
            sources+=shared.SOURCES[:2]
            self.assertEqual(len(sources),len(set(sources)))
            paths += sources+data+[manifest,Path(delivery.__file__).resolve(),ROOT/'rdma/read/tests/rw_sim.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        if hls:
            # Preserve the exact enabled fixture and actual compiler/simulator
            # outputs; select the verified explicit241/248-bit SQ derivative,
            # never silently pad the old240-bit bridge into per-WR HLS.
            p=Path(tempfile.mkdtemp(prefix='shared-mr-paged-hls-',dir=ROOT/'rdma/rnic/build'))
            retained=str(p.relative_to(ROOT))
            (p/'tb.v').write_text(tb);(p/'input.hex').write_text(''.join(f'{v:x}\n'for v in fixtures))
            for item in data:shutil.copy2(item,p/item.name)
            command=['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,sources)]
            c=subprocess.run(command,capture_output=True,text=True,timeout=90)
            (p/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            started=time.monotonic()
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=55)
            seconds=time.monotonic()-started
            (p/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertNotIn('ERROR:',r.stdout+r.stderr);output=r.stdout
            frames=fixture.probe.rw_sim.ethernet_frames(output);self.assertEqual(len(frames),1,output)
            packet=frames[0];self.assertEqual(fixture.probe.rocev2_wire.internet_checksum(packet[:20]),0)
            decoded=fixture.probe.rocev2_wire.decode_ethernet(bytes.fromhex('b8830367c5d08af3fbb975310800')+packet)
            self.assertEqual(decoded['opcode'],0x11);self.assertTrue(decoded['icrc_valid'])
            self.assertEqual(decoded['aeth_syndrome']&0xe0,0)
            self.assertEqual(decoded['psn'],fixture.probe.PSN);self.assertEqual(decoded['destination_qpn'],196)
            wire_checks=[dict(IPv4_hex=packet.hex(),IPv4_checksum=True,ICRC=True,PSN=True,QPN=True,AETH_ACK=True)]
            delivery.verify_delivery(build)
            identity=dict(original_generated_HLS_sha256=selected['original_generated_HLS_sha256'],
                delivery_sha256=selected['delivery_sha256'],generated_files=138,delivery_files=140,
                compiler_command=command,compiler_exit_status=c.returncode,simulator_exit_status=r.returncode,
                simulation_seconds=seconds,simulation_timeout_seconds=55,
                original_bridge_excluded_exactly_once=True,explicit_SQ_adapter=True,
                fixture_sha256={n:delivery.digest(p/n)for n in ['tb.v','input.hex','compile.log','simulation.log','test.vvp']})
        else:
            # Backend files are included by the real composite fixture. Only
            # the transport is an explicit stub; no descriptor/RAM bypass.
            sources=[p for p in shared.SOURCES if p.name not in ['rocev2_wqe_admission.v','rocev2_mr_query_arbiter.v']]
            with tempfile.TemporaryDirectory(prefix='as02-shared-paged-unit-')as directory:
                p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(paged_unit.transport_stub())
                (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in fixtures))
                c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),
                                  *map(str,sources)],capture_output=True,text=True,timeout=30)
                self.assertEqual(c.returncode,0,c.stdout+c.stderr)
                r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr);output=r.stdout
        rows=[json.loads(line[7:])for line in output.splitlines()if line.startswith('RESULT ')]
        locals_=[json.loads(line[13:])for line in output.splitlines()if line.startswith('LOCAL_RESULT ')]
        self.assertEqual(len(rows),1,output);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(len(locals_),1,output);self.assertEqual(locals_[0]['executor_guard'],0)
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(layer=layer,summary=rows[0],local_summary=locals_[0],
            actual_hls=bool(hls),hls_identity=identity,retained_directory=retained,
            wire_checks=wire_checks,source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            stimulus_sha256=hashlib.sha256(''.join(f'{v:x}\n'for v in fixtures).encode()).hexdigest())

    def test_full_local_namespace_and_rekey_through_paged_layer(self):self.simulate(self.namespace_case())
    def test_pte_priority_and_mr_pte_revoke_wait_for_downstream_lease(self):self.simulate(self.page_lease_case())
    def test_fresh_rx_progresses_while_paged_local_result_is_held(self):self.simulate(self.overlap_case('paged'))
    def test_actual_axi_controller_revoke_waits_for_same_local_owner(self):self.simulate(self.overlap_case('controlled'))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_SHARED_PAGED_UNIT_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            result=dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,
                actual_C_codec=True,actual_same_MR=True,actual_paged_backend_and_RAM=True,
                local_executor_lease_model=True,pcie_descriptor_and_host_visibility_model=True,
                native_host_SQ=False,local_payload_execution=False,native_CQ=False,
                kernel_runtime=False,hardware_verified=False,board_integrated=False,completion_claim=False)
            with target.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':unittest.main()
