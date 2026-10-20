#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Enabled native/same-port/local-WQE/shared MR with actual generated HLS.

Actual native AXI/control/Ethernet/MR/PTE/mux/generic PCIe/parent-guard RTL.
Physical MAC completions, host AXI/link/root/host memory and downstream local
executor lifetime are MODELS. No host-SQ/local payload executor/CQ/verbs,
Linux pins, physical board, recovery or timing-release claim is implied.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import probe_native_control as native
import probe_parent_guard_transport as parent
import shared_mr_fixture as fixture
import test_shared_mr_responder_rtl as shared
import wrkey_delivery_sim as delivery

ROOT=native.ROOT


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('fixture anchor changed: '+old)
    return text.replace(old,new)


def local_setup(instance):
    checks=[dict(local_key=8,opcode=1),dict(local_key=8,opcode=2),
            dict(local_key=0,error=1),dict(local_key=0x80000008,error=1),
            dict(local_key=10,opcode=2,error=3),dict(local_key=10,opcode=1),
            dict(local_key=8,local_address=fixture.probe.VA-1,error=4),
            dict(local_key=8,local_address=(fixture.probe.VA+0x210)&((1<<48)-1),error=4),
            dict(local_key=8,local_address=fixture.probe.VA+4095,error=4)]
    body='\n'.join(instance.local(**c)for c in checks)
    return body+'\nlocal_pd=18;'+instance.local(local_key=8,error=2)+'local_pd=17;\n'


def shared_case(instance):
    fixtures,body,cases,ordinary=native.dual.stimulus()
    record,w=instance.record(local_key=8)
    # Clear the original fixture's intentionally rejected unsafe-COMMIT error
    # at an ACTUAL stopped/drained boundary. Later unsafe-COMMIT checking must
    # not be accidentally masked by an already-sticky error.
    prefix=r'''
host_api(8,201,0,0,0,0,0,0,0,2);
if(!config_safe)$fatal(1,"initial STOP was not a real safe boundary");
write_reg(24'h401014,1,15,0,0);
if(ethernet_config_error)$fatal(1,"initial stopped clear failed");
host_api(7,202,0,0,0,0,0,0,0,0);
'''+local_setup(instance)
    before=f'''
local_allow_response=0;offer_local({record});
expiry=cycle+100;while(!lrv && cycle<expiry)@(negedge clk);
if(!lrv || !local_guard || quiet || cfg_ready || config_safe)$fatal(1,"native local MR response not owned");
repeat(9)@(negedge clk);local_allow_response=1;local_enable=0;
expiry=cycle+100;while(!local_work_valid && cycle<expiry)@(negedge clk);
if(!local_work_valid)$fatal(1,"native disable cancelled accepted WQE");
fork
 begin
'''
    after=f'''
 end
 begin
  // New incoming Ethernet/PCIe work must progress while the local result
  // retains its MR. The original allow() still waits for global quiescence.
  local_deadline=cycle+5000;while(completed!=1 && cycle<local_deadline)@(negedge clk);
  if(completed!=1 || !local_work_valid || !local_guard || quiet || cfg_ready || config_safe)$fatal(1,"native RX/local result deadlock or premature drain");
  retain_local_lease=1;
  expect_local(0,64'h{w.local_address:x},64'h210,32'd8,32'd65);
  retain_local_lease=0;
  host_stage(8,203,0,0,0,0,0,0);
  write_reg(AS02_CTL_DOORBELL,1,15,0,1);
  repeat(20)begin @(negedge clk);
   if(!control_busy || !admission_pause || quiet || config_safe || local_configuration_idle ||
     dut.datapath.responder.cfg_mr_valid || dut.datapath.responder.cfg_page_valid)$fatal(1,"native STOP bypassed downstream owner");
  end
  // Stage already differs from active MAC. With a clean initial error this
  // attempt MUST be rejected specifically while the local lease is retained.
  write_reg(24'h401010,1,15,0,0);
  read_reg(24'h40100c,host_value);
  if(host_value!==1 || !ethernet_config_error)$fatal(1,"local lease permitted unsafe route commit");
  read_reg(24'h401040,host_value);
  if(host_value!==32'hfbb97531)$fatal(1,"local lease route changed");
  release_local_lease();
  host_collect(8,203,0,0,2);
  if(!config_safe || local_input_ready || local_configuration_idle)$fatal(1,"stopped native route admitted new local WQE");
  write_reg(24'h401014,1,15,0,0);
  if(ethernet_config_error)$fatal(1,"safe clear after local STOP failed");
  host_api(7,204,0,0,0,0,0,0,0,0);
  local_enable=1;
 end
join
'''
    # Preserve all original incoming packet bytes/PSNs and all original
    # allow/deny/PCIe/sideband assertions. Only ADD local concurrency around
    # the first successful operation; no relaxed global-quiescence check.
    pattern=r'(\$display\("CASE valid_high_va_write"\);send_frame\(\d+,\d+\);\nallow\(\);)'
    matches=list(re.finditer(pattern,body))
    if len(matches)!=1:raise ValueError('first native successful operation changed')
    m=matches[0];body=body[:m.start()]+before+m[0]+after+body[m.end():]
    body=prefix+body
    body+=instance.local(local_key=8,error=1)+instance.local(local_key=16)
    body+=r'''
if(local_queries!=13 || local_results!=13 || local_leases!=1 || executor_guard || local_busy)$fatal(1,"native local namespace counts");
host_api(8,205,0,0,0,0,0,0,0,2);
if(!config_safe)$fatal(1,"final native STOP unsafe");
write_reg(24'h401014,1,15,0,0);write_reg(24'h401010,1,15,0,0);
read_reg(24'h40100c,host_value);
if(host_value!==2 || ethernet_config_error || !ethernet_enabled)$fatal(1,"final actual safe route commit");
read_reg(24'h401040,host_value);if(host_value!==32'h11223344)$fatal(1,"final active MAC");
read_reg(24'h010000,host_value);if(host_value!==32'ha55af0f0)$fatal(1,"capture aperture lost");
read_reg(0,host_value);if(host_value!==32'h524f4332)$fatal(1,"old root API lost");
if(local_input_ready || local_configuration_idle)$fatal(1,"stopped reconfigured route admitted WQE");
$display("LOCAL_RESULT {\"queries\":%0d,\"results\":%0d,\"retained_leases\":%0d,\"executor_guard\":%0d}",local_queries,local_results,local_leases,executor_guard);
'''
    return fixtures,body,cases,ordinary


def outer_fault_case(instance):
    fixtures=fixture.packet();record,w=instance.record(local_key=8)
    body=rf'''
local_allow_response=0;offer_local({record});
expiry=cycle+100;while(!lrv && cycle<expiry)@(negedge clk);
if(!lrv || !local_guard || quiet || config_safe)$fatal(1,"outer-fault test did not own MR response");
// An invalid physical-MAC completion is injected through the EXPLICIT MAC
// model queue, not internal forcing or fabricated descriptor/RAM status.
@(negedge clk);expect_fault=1;mac_cpl_tags[mac_cpl_wr%32]=16'h0001;
mac_cpl_due[mac_cpl_wr%32]=cycle+3;mac_cpl_wr=mac_cpl_wr+1;
expiry=cycle+100;while(!fault && cycle<expiry)@(negedge clk);
if(!fault || fc!==8'hf2 || local_configuration_idle || local_input_ready || quiet || !lrv)$fatal(1,"outer completion fault did not stop local admission/retain result");
local_allow_response=1;retain_local_lease=1;
expect_local(0,64'h{w.local_address:x},64'h210,32'd8,32'd65);
retain_local_lease=0;
if(!executor_guard || local_busy)$fatal(1,"outer fault lost downstream owner");
local_data={record};local_valid=1;
repeat(20)begin @(negedge clk);
 if(local_configuration_idle || local_input_ready || quiet || config_safe || cr || qr || cfg_ready ||
  !fault || fc!==8'hf2 || !executor_guard)$fatal(1,"new work or false release after outer fault");
end
if(local_results!=1 || local_queries!=1 || local_leases!=1 || commands || completed || txframes || read_tlps || write_tlps)$fatal(1,"outer fault invented native work/completion");
// Deliberately retain uncertain local ownership; ending this simulation is
// not a cancel/flush/recovery/unpin or CQ-completion proof.
$display("LOCAL_RESULT {{\"queries\":%0d,\"results\":%0d,\"retained_leases\":%0d,\"executor_guard\":%0d}}",local_queries,local_results,local_leases,executor_guard);
$display("NATIVE_FAULT_RESULT {{\"pass_test\":true,\"fault\":%0d,\"native_operations\":0,\"retained_owner\":true}}",fc);
$finish;
'''
    return fixtures,body,[],b''


def bench(fixtures,body):
    tb=native.bench()
    # Use the existing actual parent-ownership guard, not the raw fixture's
    # independent host model read/write-outstanding integers as drain proof.
    tb,count=re.subn(r'assign parent_dma_drained=.*?;',parent.GUARD,tb,count=1,flags=re.S)
    if count!=1:raise ValueError('native parent-proof layout changed')
    decl=once(fixture.DECLARATIONS,',admission_pause=0','')+'\ninteger local_deadline;\n'
    tb=once(tb,'rocev2_native_endpoint dut(',decl+'\nrocev2_native_endpoint #(.LOCAL_WQE_ENABLE(1)) dut(')
    for name,signal in re.findall(r'\.(\w+)\(([^()]*)\)',fixture.PORTS):
        if name=='cfg_admission_pause':continue
        pattern=r'\.'+name+r'\([^()]*\)'
        if len(re.findall(pattern,tb))!=1:raise ValueError('native local port not unique: '+name)
        tb=re.sub(pattern,lambda _:f'.{name}({signal})',tb)
    # Collect a doorbell already sent above, preserving the original full
    # sequence/command/cookie/slot/key/error/flags/ACK/READY assertions.
    task=tb.split('task host_finish;',1)[1].split('task host_api;',1)[0]
    task=once(task,'  write_reg(AS02_CTL_DOORBELL,1,15,0,1);\n','')
    frontend=fixture.FRONTEND+'\ntask host_collect;'+task
    frontend+=r'''
always @(posedge clk)if(!rst)begin
 if(cycle<3 || cycle%2048==0)$display("NATIVE_SHARED_PROGRESS time%0t cycle%0d local_idle%0d local_guard%0d",$time,cycle,local_configuration_idle,local_guard);
 if((local_guard || executor_guard) && (cfg_ready || config_safe))$fatal(1,"native management escaped local owner");
 if((!ethernet_enabled || ethernet_epoch==0 || admission_pause || fault) && local_input_ready)$fatal(1,"local admission ignored native route/control/fault");
end
'''
    tb=once(tb,'reg [144:0] stimulus',frontend+'\nreg [144:0] stimulus')
    includes=[ROOT/'rdma/rnic/rtl'/n for n in ['rocev2_wqe_admission.v','rocev2_mr_query_arbiter.v']]+[parent.RTL]
    return '\n'.join(f'`include "{p}"'for p in includes)+'\n'+tb.replace(
        'STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,choices=['shared-control','outer-fault'])
    parser.add_argument('--hls-build',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve earlier evidence; choose fresh report')
    selected,manifest=delivery.verify_delivery(args.hls_build)
    instance=shared.SharedMRResponderRTLTests();instance.setUpClass()
    try:fixtures,body,cases,ordinary=shared_case(instance)if args.case=='shared-control'else outer_fault_case(instance)
    finally:instance.directory.cleanup()
    tb=bench(fixtures,body)
    if 'force 'in tb:raise ValueError('internal forcing forbidden')
    sources,data=delivery.ORIGINAL_MODULES(args.hls_build)
    if sources.count(delivery.OLD_BRIDGE)!=1:raise ValueError('old bridge selection changed')
    sources.remove(delivery.OLD_BRIDGE);sources+=shared.SOURCES[:2]
    if len(sources)!=len(set(sources)):raise ValueError('duplicate compiler modules')
    pcie=native.pcie;controlled=pcie.controlled
    paths=sources+data+[
        native.RTL,native.CONFIG,native.HEADER,*native.XBAR,native.dual.TOP,native.dual.INGRESS,
        *pcie.PCIE_SOURCES,controlled.TOP,controlled.CONTROL,*controlled.registers.SOURCES,
        controlled.registers.HEADER,*controlled.integration.paged.SOURCES,
        ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',*shared.SOURCES[:4],
        shared.codec.KERNEL/'wqe.c',shared.codec.KERNEL/'wqe.h',manifest,parent.RTL,
        ROOT/'rdma/read/tests/rw_sim.py',ROOT/'rdma/host/rocev2_wire.py',
        ROOT/'rdma/read/host/read_wire.py',ROOT/'rdma/tests/test_icrc_rtl.py',Path(__file__).resolve()]
    paths += [Path(m.__file__).resolve()for m in [native,parent,native.dual,pcie,controlled,controlled.registers,
        controlled.integration,controlled.integration.paged,fixture,fixture.probe,shared,shared.codec,delivery]]
    before={str(p.relative_to(ROOT)):delivery.digest(p)for p in paths}
    run=Path(tempfile.mkdtemp(prefix='native-shared-mr-'+args.case+'-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(tb);(run/'input.hex').write_text(''.join(f'{v:x}\n'for v in fixtures))
    for item in data:shutil.copy2(item,run/item.name)
    command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sources)]
    result=dict(scope=__doc__,case=args.case,pass_test=False,terminal_exit_status=None,
        hardware_verified=False,board_integrated=False,native_host_SQ=False,local_payload_executor=False,
        native_CQ=False,standard_verbs=False,kernel_runtime=False,completion_claim=False,
        actual_C_codec=True,actual_native_same_port_control_MR_PTE_RAM_PCIe=True,
        constant_parent_proof_or_descriptor_RAM_agents=False,local_executor_lease_model=True,
        physical_MAC_host_AXI_link_root_host_memory_models=True,transport_stub=False,
        original_generated_HLS_sha256=selected['original_generated_HLS_sha256'],
        delivery_sha256=selected['delivery_sha256'],generated_files=138,delivery_files=140,
        source_sha256=before,retained_directory=str(run.relative_to(ROOT)),compiler_command=command,
        compile_timeout_seconds=90,simulation_timeout_seconds=120,
        simulation_limit_basis='Same existing bounded native gate120s: successful default003took108.36s; exact frozen default and enabled25sdiagnostics BOTH stopped at3initial time steps. Earlier70s expiry proves no functional outcome; original protocol cycle/byte/ownership gates remain unchanged.')
    started=time.monotonic()
    try:
        c=subprocess.run(command,capture_output=True,text=True,timeout=90)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compiler_returncode']=c.returncode
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        vvp=(run/'test.vvp').read_text()
        names=['rocev2_mr_table','rocev2_mr_query_arbiter','rocev2_native_endpoint','rocev2_dual_ethernet_endpoint',
               'rocev2_controlled_responder','rocev2_paged_responder','rocev2_pcie_parent_guard']
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',vvp))for n in names}
        if any(v!=1 for v in counts.values()):raise ValueError('enabled native hierarchy mismatch: '+str(counts))
        result['actual_elaborated_module_counts']=counts
        sim_started=time.monotonic()
        try:
            s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=120)
        except subprocess.TimeoutExpired as error:
            def decoded(value):return value.decode(errors='replace')if isinstance(value,bytes)else(value or '')
            (run/'simulation.log').write_text(decoded(error.stdout)+decoded(error.stderr)+'\nHARNESS_WALL_TIMEOUT_WITHOUT_FUNCTIONAL_RESULT\n')
            result.update(simulation_seconds=time.monotonic()-sim_started,observation_timeout=True)
            raise
        result['simulation_seconds']=time.monotonic()-sim_started
        (run/'simulation.log').write_text(s.stdout+s.stderr);result['simulator_returncode']=s.returncode
        print(s.stdout+s.stderr,flush=True)
        if s.returncode or 'ERROR:'in s.stdout+s.stderr:raise RuntimeError('enabled native simulation failed')
        def rows(prefix):return [json.loads(l[len(prefix)+1:])for l in s.stdout.splitlines()if l.startswith(prefix+' ')]
        local=rows('LOCAL_RESULT')
        expected=(13,13,1,0)if args.case=='shared-control'else(1,1,1,1)
        if len(local)!=1 or tuple(local[0][n]for n in ['queries','results','retained_leases','executor_guard'])!=expected:
            raise ValueError('native local ownership/count mismatch')
        result['local_summary']=local[0]
        if args.case=='shared-control':
            base=rows('RESULT');pci=rows('PCIE_RESULT');eth=rows('ETH_RESULT')
            if len(base)!=len(pci)or len(base)!=len(eth)or len(base)!=1 or not all(x[0]['pass_test']for x in [base,pci,eth]):
                raise ValueError('original actual native assertions missing')
            wire=fixture.probe.rw_sim.ethernet_frames(s.stdout)
            good=[c for c in cases if not c.get('expected_error')and not c.get('expected_integrity_drop')]
            if len(wire)!=len(good)or len(wire)!=5:raise ValueError('native response count')
            responses=[]
            for packet,case in zip(wire,good):
                if packet[:14]!=bytes.fromhex('b8830367c5d08af3fbb975310800')or fixture.probe.rocev2_wire.internet_checksum(packet[14:34]):
                    raise ValueError('native Ethernet/IPv4 checksum')
                if case['operation']=='read':
                    d=fixture.probe.read_wire.decode(packet)
                    if d['opcode']!=fixture.probe.read_wire.ONLY or d['payload']!=fixture.probe.PAYLOAD or d['syndrome']&0xe0:
                        raise ValueError('native READ payload/ACK')
                else:
                    d=fixture.probe.rocev2_wire.decode_ethernet(packet)
                    if d['opcode']!=0x11 or not d['icrc_valid']or d['aeth_syndrome']&0xe0:raise ValueError('native WRITE ACK')
                if d['psn']!=case['psn']or d['destination_qpn']!=196:raise ValueError('native wire owner')
                responses.append(dict(operation=case['operation'],PSN=case['psn'],Ethernet_hex=packet.hex(),
                    read_bytes_verified=65 if case['operation']=='read'else 0,IPv4_ICRC_QPN_PSN_AETH_checked=True))
            rx=native.dual.frames(s.stdout,'HOST_RX');tx=native.dual.frames(s.stdout,'HOST_TX')
            if len(rx)!=len(tx)or len(rx)!=1 or rx[0][0]!=ordinary or tx[0][0]!=ordinary:raise ValueError('ordinary host payload')
            if not all(u==0x0123456789abcdef012345678 for u in rx[0][1])or not all(u==0x9234<<1 for u in tx[0][1]):raise ValueError('ordinary host sidebands')
            result.update(summary=base[0],PCIe_summary=pci[0],Ethernet_summary=eth[0],responses=responses,
                write_bytes_verified=130,read_bytes_verified=195,all_ordinary_host_sidebands_checked=True,
                parent_proof_uses_host_model_counters=False,raw_MR_PTE_QP_Ethernet_config_bypass=False,
                host_replies=[l for l in s.stdout.splitlines()if l.startswith('HOST_REPLY ')])
        else:
            fault=rows('NATIVE_FAULT_RESULT')
            if len(fault)!=1 or fault[0]!=dict(pass_test=True,fault=0xf2,native_operations=0,retained_owner=True):
                raise ValueError('native outer fault proof')
            result['fault_summary']=fault[0]
        delivery.verify_delivery(args.hls_build)
        if before!={n:delivery.digest(ROOT/n)for n in before}:raise ValueError('consumed input changed')
        result.update(pass_test=True,terminal_exit_status=0,source_sha256_before_after_equal=True)
    except Exception as error:
        result.update(terminal_exit_status=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        result['artifact_sha256']={str(p.relative_to(ROOT)):delivery.digest(p)for p in run.iterdir()if p.is_file()and p.suffix!='.dat'}
        with args.report.open('x')as out:json.dump(result,out,indent=2);out.write('\n')


if __name__=='__main__':main()
