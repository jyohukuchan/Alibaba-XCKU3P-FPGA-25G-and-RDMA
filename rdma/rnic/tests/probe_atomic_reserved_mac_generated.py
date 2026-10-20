#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual owned HLS/MR/Atomic/MAC with reservation BEFORE service side effects.

Seven bounded cases: earlier four cases plus finite-tag exhaustion and two
admitted-packet disable points. Production tag width13 is unchanged; this
composition uses4 to reach the boundary in15 requests. Physical host ordering,
descriptors, PHY and PTP input remain models. No native/API/timing proof.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import atomic_reserved_mac_generated_fixture as fixture
import probe_atomic_mac_generated as old
import test_atomic_mac_tx_rtl as mac

ROOT=fixture.ROOT
digest=old.digest
BASE_EXPECTED=[(2,0xfffffe,1,0x1f,0xf123456789abcdef),(2,0xfffffe,1,0x1f,0xf123456789abcdef),
    (2,0xffffff,2,0x1f,0x8123456789abcdef),(2,0,3,0x1f,0x8123456789abcdef),
    (2,1,3,0x60,None),(2,1,4,0x1f,0),(3,0x123456,1,0x1f,0),
    (2,1,4,0x1f,0),(2,2,5,0x1f,0xfedcba9876543210),(2,3,6,0x1f,0xfedcba9876543210)]
BASE_STATES=[(0xfffffe,0),(0xffffff,1),(0xffffff,1),(0,2),(1,3),(1,3),(0x123456,0),(2,4),(2,4),(3,5),(3,5)]
BASE_ADVANCES=[True,False,True,True,False,True,True,False,True,False,True]


def verify(output,case):
    core_old=old.prior.old
    packets=core_old.output_packets(output)
    expected=BASE_EXPECTED if case in (0,4)else BASE_EXPECTED[:2]if case in (5,6)else \
        [(2,0xfffffe,0,0x62,None)]if case==1 else []
    if case==4:expected=expected+[BASE_EXPECTED[-1]]*4
    if len(packets)!=len(expected):raise ValueError('missing/extra actual protected IP packets')
    for packet,(q,psn,msn,syndrome,value)in zip(packets,expected):
        size=56 if value is not None else 48
        if len(packet)!=size or packet[0]!=0x45 or int.from_bytes(packet[2:4],'big')!=size or packet[9]!=17:
            raise ValueError('actual IPv4 shape')
        if core_old.wire.internet_checksum(packet[:20])!=0 or packet[-4:]!=core_old.wire.icrc_ipv4(packet):
            raise ValueError('independent actual IPv4/ICRC')
        if packet[12:20]!=bytes([198,18,11,2,198,18,11,1])or \
            packet[20:24]!=(4791).to_bytes(2,'big')*2 or int.from_bytes(packet[24:26],'big')!=size-20:
            raise ValueError('actual trusted peer/UDP')
        body=bytes([18 if value is not None else 17,0x40])+core_old.struct.pack('!HII',0xffff,0xf12345+q,psn)
        body+=bytes([syndrome])+msn.to_bytes(3,'big')
        if value is not None:body+=core_old.struct.pack('!Q',value)
        if packet[28:-4]!=body:raise ValueError('independent Atomic wire response oracle')
    def ints(prefix):return [int(l.split()[1],16)for l in output.splitlines()if l.startswith(prefix+' ')]
    def row(prefix):
        rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith(prefix+' ')]
        if len(rows)!=1:raise ValueError('missing/duplicate '+prefix)
        return rows[0]
    summary=row('ATOMIC_GENERATED');proof=row('ATOMIC_ADMISSION_PROOF')
    if not summary['pass_test']or summary['MAC_boundary_model']or summary['positive_MAC_retirement_model']:
        raise ValueError('assertions or genuine MAC scope')
    jobs=ints('ATOMIC_JOB');receipts=ints('ATOMIC_CORE_DONE');responses=ints('ATOMIC_RESULT_WORD')
    reserved=ints('ATOMIC_MAC_RESERVED');delivered=ints('ATOMIC_HLS_RELEASED')
    owners=[l.split()[1:]for l in output.splitlines()if l.startswith('ATOMIC_OWNER ')]
    tags=[int(x[3],16)for x in owners]
    count=15 if case==4 else 11 if case==0 else 2 if case in (5,6)else 1
    completed=count if case not in (2,3)else 0
    if len(jobs)!=count or len(owners)!=count or len(reserved)!=count or len(delivered)!=count or \
        len(receipts)!=completed or len(responses)!=(0 if case==2 else count):
        raise ValueError('actual owner/reservation/service/core counts')
    if tags!=list(range(1,count+1))or proof['accepted']!=count or proof['reserved']!=count or proof['delivered']!=count:
        raise ValueError('finite nonwrapping ownership or reservation counters')
    if proof['retired']!=completed or summary['retirements']!=completed or proof['case']!=case or proof['tag_width']!=4:
        raise ValueError('actual retirement proof')
    if bool(proof['exhausted'])!=(case==4):raise ValueError('finite tag boundary not reached exactly')
    if case==4 and (not proof['checked_pending']or proof['checked_ready']):
        raise ValueError('16th post-integrity packet was not held outside admission')
    if case in (5,6)and not proof['disable_cycle']:raise ValueError('disable point not exercised')
    states=BASE_STATES+[(4,6)]*4 if case==4 else BASE_STATES if case==0 else BASE_STATES[:2]if case in (5,6)else [(0xfffffe,0)]
    advances=BASE_ADVANCES+[False]*4 if case==4 else BASE_ADVANCES if case==0 else BASE_ADVANCES[:2]if case in (5,6)else [False]
    for i,job in enumerate(jobs):
        owner=(int(owners[i][3],16)<<112)|(int(owners[i][2],16)<<88)|(int(owners[i][1],16)<<24)|int(owners[i][0],16)
        context=(0x020000000002<<280)|(0x020000000001<<232)|(0xc6120b02<<200)|(0xc6120b01<<168)|\
            ((0xf12345+(owner&0xffffff))<<144)|owner
        if job>>368!=owner or reserved[i]!=context or delivered[i]!=owner:
            raise ValueError('immutable MAC/HLS/service owner or trusted context')
        if ((job>>320)&0xffffff,(job>>344)&0xffffff)!=states[i]:
            raise ValueError('actual shared PSN/MSN before execution')
        if i<len(responses)and responses[i]>>248!=owner:raise ValueError('actual service echoed owner')
    for i,receipt in enumerate(receipts):
        job=jobs[i];psn=int.from_bytes((job&((1<<320)-1)).to_bytes(40,'little')[9:12],'big')
        epsn=(job>>320)&0xffffff;msn=(job>>344)&0xffffff;advance=advances[i];drop=case in (0,4)and i==9
        want=(job>>368)|((job&255)<<144)|(((psn+1)&0xffffff if advance else epsn)<<152)|\
            (((msn+int(advance))&0xffffff)<<176)|((7|(int(not drop)<<3)|(int(advance)<<4)|(int(drop)<<5))<<200)
        if receipt!=want:raise ValueError('independent same-table consumed core oracle')
    events=[l.split()[0]for l in output.splitlines()if l.startswith(('ATOMIC_MAC_RESERVED ','ATOMIC_HLS_RELEASED '))]
    if events!=['ATOMIC_MAC_RESERVED','ATOMIC_HLS_RELEASED']*count:raise ValueError('HLS released before real MAC reservation')
    frames=fixture.base.link.frames(output);atomic=[(t,f)for t,f in frames if t and t<8192]
    native=[(t,f)for t,f in frames if not(t and t<8192)]
    wire_tags=list(range(1,10))+[11]if case in (0,4)else list(range(1,len(packets)+1))
    if case==4:wire_tags+=list(range(12,16))
    if [t for t,_ in atomic]!=wire_tags or len(atomic)!=len(packets):
        raise ValueError('actual SFD/frame tags or no-packet drop gap')
    for (_,frame),packet in zip(atomic,packets):
        if frame!=bytes.fromhex('0200000000010200000000020800')+packet:
            raise ValueError('actual XGMII/FCS/framing differs from independent IP oracle')
    if native!=([(0x9234,fixture.base.NATIVE)]if case in (0,4)else []):raise ValueError('unrelated native frame')
    return dict(summary=summary,admission_proof=proof,actual_service_requests=[f'{x:0128x}'for x in jobs],
        actual_core_receipts=[f'{x:056x}'for x in receipts],actual_IP_UDP_ICRC_packets=[x.hex()for x in packets],
        actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],
        ordered_actual_MAC_before_HLS=True,all_bytes_FCS_ICRC_core_readback_and_owner_oracles=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,required=True,help='exact byte-identical compiler inputs only; all cases rerun')
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh-native1GiB guard')
    hls=json.loads(a.hls_report.read_text())
    if not hls.get('pass_test')or hls.get('HLS_top')!='rocev2_native_atomic_owned_top':p.error('matched owned raw HLS required')
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
    for name,sha in hls['generated_sha256'].items():
        if digest(raw/name)!=sha:raise ValueError('unchanged raw HLS')
    run=Path(tempfile.mkdtemp(prefix='atomic-owned-generated-reserved-mac-',dir=ROOT/'rdma/rnic/build'))
    obj=Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])
    words,_=old.prior.inputs();tb,bridge=fixture.bench(run,len(words))
    (run/'tb.v').write_text(tb);(run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in words))
    sources=[*sorted(raw.glob('*.v')),*fixture.base.prior.rtl.SOURCES,fixture.base.old.service.RTL,
        ROOT/'rdma/rnic/rtl/rocev2_atomic_packet_guard.v',ROOT/'rdma/rnic/rtl/rocev2_atomic_owner_reservation.v',
        *mac.SOURCES,*fixture.base.link.SOURCES,ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'rdma/rtl/rocev2_tx_padding.v',
        mac.AXIS/'axis_adapter.v',mac.AXIS/'axis_fifo.v',mac.AXIS/'axis_broadcast.v',mac.ETH/'lfsr.v',bridge]
    sources=list(dict.fromkeys(sources));data=sorted(raw.glob('*.dat'))
    for f in data:shutil.copy2(f,run/f.name)
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga'))]
    before={str(f.relative_to(ROOT)):digest(f)for f in [*sources,*data,*helpers,a.hls_report.resolve(),
        ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/rtl/rocev2_integrity_transport.v',
        ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',run/'tb.v',run/'input.hex']}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        compile_directory=str(obj),actual_generated_HLS=True,two_state=True,actual_MAC_XGMII_SFD_FCS_CDC=True,
        test_produced_MAC_receipts=False,test_driven_retirement=False,tag_width_for_bounded_test=4,default_tag_width=13,
        native_integrated=False,hardware_verified=False,simulation_limit_seconds=30,tests={})
    try:
        import atomic_reserved_generated_compile_cache as cache
        before[str(Path(cache.__file__).resolve().relative_to(ROOT))]=digest(Path(cache.__file__).resolve())
        command=[str(old.prior.old.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','8',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0','-CFLAGS','-O0',
            '--Mdir',str(obj),str(run/'tb.v'),*map(str,sources)]
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        reused=cache.compile(command,run,env,a.reuse_compiled_report.resolve())
        before.update(reused.pop('extra_source_sha256'));report.update(reused)
        shutil.copy2(obj/'Vtb',run/'Vtb')
        for case in range(7):
            start=time.monotonic()
            with(run/f'case-{case}.log').open('x')as log:
                r=subprocess.run([str(run/'Vtb'),f'+case={case}'],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=old.prior.old.no_core)
            report['tests'][case]=dict(seconds=time.monotonic()-start,exit=r.returncode)
            if r.returncode:raise RuntimeError('reserved generated case: '+str(run/f'case-{case}.log'))
            report['tests'][case].update(verify((run/f'case-{case}.log').read_text(),case))
        if before!={name:digest(ROOT/name)for name in before}:raise ValueError('source changed during build/test')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in run.iterdir()if f.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],tests={k:v['seconds']for k,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()
