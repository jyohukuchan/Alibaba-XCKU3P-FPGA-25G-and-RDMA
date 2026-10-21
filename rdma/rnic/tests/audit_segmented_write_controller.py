#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real raw WRITE controller/visibility/PSN fanout and full classifier scope.

HLS and native-PSN endpoint are MODELS/traces; complete native placement and
actual generated-HLS payload/PCIe/CQ runtime still remain. No scope shrink.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import audit_segmented_receive as binding
import probe_segmented_write_controller as probe
import probe_native_write_classifier as route

ROOT=binding.ROOT;digest=binding.digest;leaves=probe.leaves;once=probe.once
WRAPPER='rdma/rnic/tests/probe_segmented_write_controller.py'
ROUTE='rdma/rnic/tests/probe_native_write_classifier.py'
PRE1='rdma/rnic/build/write-controller-001-preimages-yNh3Q465'
PRE2='rdma/rnic/build/write-controller-002-preimages-wZxjwwND'
ROUTEPRE='rdma/rnic/build/native-write-classifier-001-preimages-F5zGavwa'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all old reports')
    spec=[('segmented-write-controller-003',None),('segmented-write-controller-001',{WRAPPER:PRE1}),
        ('segmented-write-controller-002',{WRAPPER:PRE2}),('native-write-classifier-002',None),
        ('native-write-classifier-001',{ROUTE:ROUTEPRE}),('remote-write-memory-004',None),
        ('write-native-gateway-diagnostics-001',None)]
    rows={};ids={}
    for name,fallback in spec:rows[name],ids[name]=binding.bindings(name,fallback)
    actual=rows[spec[0][0]];bad=rows[spec[1][0]];first=rows[spec[2][0]];routing=rows[spec[3][0]];old=rows['remote-write-memory-004']
    if not actual['pass_test']or not actual['source_unchanged']or len(actual['tests'])!=14 or \
       (actual['compile_limit_seconds'],actual['runtime_limit_seconds'],actual['clock_ns'],actual['cycle_limit'])!=(10,10,4,100000):
        raise ValueError('actual full14 bounded controller modes required')
    if bad['pass_test']or not first['pass_test']or rows['native-write-classifier-001']['pass_test']:
        raise ValueError('preserve actual compile failure, success002 and classifier delta-sampling failure')
    run=ROOT/actual['directory'];frozen=Path(actual['source_sha256']and next(n for n in actual['source_sha256']if n.endswith('/runner.py')))
    if frozen.read_text()!=probe.runner_source()or (run/'tb.v').read_text()!=probe.bench(probe.prior.ack_test.candidate.derive(),probe.prior.authorization.queue.derive()):
        raise ValueError('exact consumed wrapper/bench/current derivation required')
    if 'expects'in(run/'compile.log').read_text():raise ValueError('no width coercion may qualify new controller')
    for k,t in actual['tests'].items():
        s=t['summary'];c=t['controller'];negative=int(k)>=3 and k!='5'
        if t['exit']or t['seconds']>10 or not s['pass_test']or s['fault']!=negative or not c['pass_test']:
            raise ValueError('actual expected bounded pass/quarantine result missing:'+k)
        for field,v in first['tests'][k]['summary'].items():
            if s[field]!=v:raise ValueError('old successful raw controller oracle changed:'+k+'/'+field)
        for field,v in first['tests'][k]['controller'].items():
            if c[field]!=v:raise ValueError('old raw/PSN/ACK visibility assertion changed:'+k+'/'+field)
        if not negative:
            if (s['host_bytes'],s['completed'],s['physical_writes'],s['fences'],s['nonce_commands'],s['ACK_SFDs'])!=(8193,3,5,3,3,3)or \
               (c['raw_frames'],c['replayed_frames'],c['PSN'],c['commits'],c['genuine_HLS_RQ_owners'])!=(3,3,5,3,int(k=='1'))or \
               c['replayed_bytes']!=(8348 if k=='1'else 8344)or not c['ACK_after_actual_fence']:
                raise ValueError('full raw bytes/true fence/ACK/PSN/RQ proof scope required:'+k)
            frames=probe.prior.ack_test.physical.frames((run/(k+'.log')).read_text())
            wanted=[]
            for i in range(3):
                f=b''.join(int(v,16).to_bytes(16,'little')for v in (run/f'write{i}.hex').read_text().split())[:62]
                wanted.append((0x6001+i,f))
            if frames!=wanted:raise ValueError('all actual MAC bytes/FCS/SFD/tag receipts must match')
    for k in ['10','11','12','13']:
        if actual['tests'][k]['summary']['ACK_SFDs']!=0 or actual['tests'][k]['controller']['commits']!=0:
            raise ValueError('physical-status/fence/HLS failure cannot emit a positive ACK or native commit')
    if actual['tests']['6']['controller']['commits']!=2:raise ValueError('bad LAST pad cannot advance native PSN/owner')
    trace,_=probe.prior.ack_test.traces()
    for i,v in enumerate(trace['write-rx']):
        raw_data=b''.join(int(s,16).to_bytes(64,'little')for s in (run/f'payload{i}.hex').read_text().split())[:(min(4096,8193-v['offset'])+3)&~3]
        for imm in [0,1]:
            packet=probe.raw_packet(raw_data,i,imm);lines=(run/f'raw{imm}-{i}.hex').read_text().split()
            expected=[int.from_bytes(packet[n:n+16].ljust(16,bytes(1)),'little')|(((1<<min(16,len(packet)-n))-1)<<128)|(int(n+16>=len(packet))<<144)for n in range(0,len(packet),16)]
            if list(map(lambda s:int(s,16),lines))!=expected or probe.internet_checksum(packet[:20])!=0 or probe.icrc_ipv4(packet)!=packet[-4:]:
                raise ValueError('whole real raw frame/ICRC/header/KEEP/EOF image changed')
    # Exact parent reconstruction: extra parsed Immediate is read-only and
    # no original frontend authorization/owner/replay/retire gate changes.
    front=leaves.frontend()
    front=once(front,'module '+leaves.FRONT_NAME+' #(','module rocev2_segmented_write_rx_frontend #(')
    front=once(front,'    output wire [31:0] m_packet_notification,\n','')
    front=once(front,"\nassign m_packet_notification=notify ? be32(header,40):32'd0;",'')
    if front!=leaves.FRONT.read_text():raise ValueError('qualified frontend must reconstruct byte-for-byte')
    classified=leaves.router();classified=once(classified,'module '+leaves.ROUTER_NAME+' (','module rocev2_native_atomic_rx_router (')
    classified=once(classified,',input wire force_write,',',')
    classified=once(classified,"force_write===1'b1 || (opcode>=8'h06 && opcode<=8'h09)","opcode==8'h13 || opcode==8'h14")
    if classified!=leaves.ROUTER.read_text():raise ValueError('all original classifier gates/byte path must reconstruct')
    if not routing['pass_test']or routing['summary']['frames']!=512 or routing['summary']['WRITE_frames']!=260 or routing['summary']['other_frames']!=252:
        raise ValueError('every256 opcode x2 force state byte/KEEP/EOF/stall route required')
    fixed=(ROOT/ROUTE).read_text().replace('  #1;if(configuration_guard)','  if(configuration_guard)')
    if fixed!=(ROOT/ROUTEPRE/ROUTE).read_text():raise ValueError('only post-negedge combinational observation phase changes')
    if not old['pass_test']or not rows['write-native-gateway-diagnostics-001']['audit_passed']:
        raise ValueError('retain previous actual backend/native boundary qualifications, not a new full-native pass')
    binary=next(Path(n)for n in actual['RAM_artifact_sha256']if Path(n).name=='test');vvp=binary.read_text()
    names=['rocev2_segmented_write_controller',leaves.FRONT_NAME,'rocev2_remote_write_message_guard','rocev2_remote_write_memory',
        'rocev2_mr_table','rocev2_mr_page_table','rocev2_paged_memory_backend','rocev2_memory_command_nonce',
        probe.prior.ack_test.candidate.NAME,probe.prior.authorization.queue.NAME,'axis_xgmii_tx_64','rocev2_ipv4_icrc']
    counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',vvp))for n in names}
    if any(v!=1 for v in counts.values()):raise ValueError('actual one-instance controller/MR/backend/ACK/CRC graph missing:'+str(counts))
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    lint=subprocess.run(['verilator','--lint-only','--top-module','rocev2_segmented_write_controller','-Wno-fatal',str(probe.CTRL),
        str(run/'native-front.v'),str(probe.prior.MEMORY),str(probe.prior.authorization.GUARD),
        str(ROOT/'external/corundum/fpga/lib/axis/rtl/axis_register.v')],capture_output=True,text=True,cwd=ROOT,timeout=10)
    if lint.returncode or re.search(r'%Warning-(UNOPTFLAT|LATCH|MULTIDRIVEN|UNDRIVEN|PINMISSING)',lint.stderr):
        raise ValueError('unresolved controller combinational/driver/elaboration issue:'+lint.stderr)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        protected_raw_sha256=binding.PROTECTED,controller_modes=14,classifier_frames=512,actual_elaborated_modules=counts,
        maximum_controller_seconds=max(t['seconds']for t in actual['tests'].values()),actual_whole_raw_bytes=True,
        ACK_waits_real_backend_fence_before_any_MAC_SFD=True,frontend_DONE_and_native_commit_atomic=True,
        genuine_LAST_only_full680_RQ_owner_verified=True,whole_frontend_and_classifier_parent_reconstruct_exactly=True,
        modeled_boundaries=['trusted native context/admission','actual CPP HLS trace/raw-command/RQ/whole producers','native expected-PSN commit endpoint','descriptor engine/host ordering','clock/PTP/PHY/CQ consumers'],
        actual_generated_HLS_payload_runtime=False,complete_native_controller_inserted=False,complete_native_WRITE_runtime=False,
        full_native1MiB=False,live_Linux=False,partial_message_HLS_teardown_proved=False,
        original_timing_met=False,original_estimated_ns=15.571,
        leaf_lint=dict(exit=lint.returncode,stdout=lint.stdout,stderr=lint.stderr,no_loop_latch_driver_warnings=True,not_board_timing=True),
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        remaining=['All11 original requirements retained. Insert this actual controller/classifier into the complete native graph, not another compatible-only substitute.',
            'Connect real native expectedPSN event, SAME MR/PTE/backend/global nonce, shared HLS424/456 and true680 RQ owner, ONE ACK allocator/real late-RQ/whole CQ retirement. No second namespace, fake RQ or early wire ACK.',
            'Fresh full native compile/all34 old regressions PLUS WRITE/Immediate, full1MiB/matched software/multiSGE/live Linux refs/short peer recovery/RNR/MSN/congestion.',
            'Implement real privileged partial-HLS-message teardown/unpin; no cancel/drain/reset substitute. Original4ns/default1.08ns board/physical qualification still fails/remains.',
            'No reboot needed; restore all archived RAM caches and prove authenticated exact-thread/goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,bindings=result['verified_bindings'],modes=14,classifier_frames=512,complete_native=False)),flush=True)


if __name__=='__main__':main()
