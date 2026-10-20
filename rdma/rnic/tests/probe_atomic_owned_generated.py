#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated owned Atomic core/service/guard/MR/page/RAM/IP/ICRC.

Actual224-bit consumed SAME-table readback receipts retain packet nonce.
Drop retires through that receipt then a new valid operation succeeds.
Trusted configuration/physical descriptors/host ordering and positive MAC
SFD/EOF/tail boundary remain MODELS, not native/SQ/kernel/board/timing proof.
Each functional runtime <=30seconds; no hardware actions or traffic.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic_owned_generated_fixture as fixture
import probe_atomic_generated as old

ROOT=fixture.ROOT;digest=fixture.prior.digest


def inputs():
    words,frames=old.inputs();frame=old.packet(20,2,3,1);frames.append(frame)
    for off in range(0,72,16):
        p=frame[off:off+16];words.append(int.from_bytes(p.ljust(16,b'\0'),'little')|
            (((1<<len(p))-1)<<128)|(int(off+16>=72)<<144))
    return words,frames


def verify(output,case):
    packets=old.output_packets(output)
    expected=[(2,0xfffffe,1,0x1f,0xf123456789abcdef),(2,0xfffffe,1,0x1f,0xf123456789abcdef),
        (2,0xffffff,2,0x1f,0x8123456789abcdef),(2,0,3,0x1f,0x8123456789abcdef),
        (2,1,3,0x60,None),(2,1,4,0x1f,0),(3,0x123456,1,0x1f,0),(2,1,4,0x1f,0),
        (2,2,5,0x1f,0xfedcba9876543210),(2,3,6,0x1f,0xfedcba9876543210)]if case==0 else \
        [(2,0xfffffe,0,0x62,None)]if case==1 else []
    if len(packets)!=len(expected):raise ValueError(('missing actual packets',len(packets),len(expected)))
    for p,(q,psn,msn,syndrome,value)in zip(packets,expected):
        size=56 if value is not None else 48
        if len(p)!=size or p[0]!=0x45 or int.from_bytes(p[2:4],'big')!=size or p[9]!=17:
            raise ValueError('actual IPv4 shape')
        if old.wire.internet_checksum(p[:20])!=0 or p[-4:]!=old.wire.icrc_ipv4(p):raise ValueError('actual checksum/ICRC')
        if p[12:20]!=bytes([198,18,11,2,198,18,11,1])or int.from_bytes(p[22:24],'big')!=4791 or \
            int.from_bytes(p[24:26],'big')!=size-20:raise ValueError('trusted IP/UDP shape')
        bth=bytes([18 if value is not None else 17,0x40])+old.struct.pack('!HII',0xffff,0xf12345+q,psn)
        body=bth+bytes([syndrome])+msn.to_bytes(3,'big')
        if value is not None:body+=old.struct.pack('!Q',value)
        if p[28:-4]!=body:raise ValueError(('independent wire oracle',p.hex(),body.hex()))
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ATOMIC_GENERATED ')]
    if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing generated assertions')
    jobs=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('ATOMIC_JOB ')]
    receipts=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('ATOMIC_CORE_DONE ')]
    owners=[l.split()[1:]for l in output.splitlines()if l.startswith('ATOMIC_OWNER ')]
    tags=[int(x[-1],16)for x in owners]
    if len(set(tags))!=len(tags)or any(t==0 for t in tags):raise ValueError('aliased immutable owner')
    if len(receipts)!=(11 if case==0 else 1 if case==1 else 0):raise ValueError('missing/false core receipts')
    states=[(0xfffffe,0),(0xffffff,1),(0xffffff,1),(0,2),(1,3),(1,3),(0x123456,0),(2,4),(2,4),(3,5),(3,5)]
    advances=[True,False,True,True,False,True,True,False,True,False,True]
    for i,job in enumerate(jobs):
        if job>>368!=(int(owners[i][3],16)<<112)|(int(owners[i][2],16)<<88)|\
            (int(owners[i][1],16)<<24)|int(owners[i][0],16):raise ValueError('HLS immutable owner changed')
        if case==0 and (((job>>320)&0xffffff,(job>>344)&0xffffff)!=states[i]):
            raise ValueError('actual shared HLS request PSN/MSN')
    for i,d in enumerate(receipts):
        j=jobs[i];op=j&255;psn=int.from_bytes((j&((1<<320)-1)).to_bytes(40,'little')[9:12],'big')
        epsn=(j>>320)&0xffffff;msn=(j>>344)&0xffffff
        advance=advances[i]if case==0 else False;drop=case==0 and i==9
        expected_done=(j>>368)|(op<<144)|(((psn+1)&0xffffff if advance else epsn)<<152)|\
            (((msn+int(advance))&0xffffff)<<176)|((7|(int(not drop)<<3)|(int(advance)<<4)|(int(drop)<<5))<<200)
        if d!=expected_done:raise ValueError(('independent current-state/owner done oracle',f'{d:056x}',f'{expected_done:056x}'))
    return dict(summary=rows[0],actual_IP_UDP_ICRC_packets=[p.hex()for p in packets],
        actual_service_requests=[f'{x:0128x}'for x in jobs],actual_core_receipts=[f'{x:056x}'for x in receipts],
        unique_real_packet_tags=tags,independent_wire_and_current_state_readback_oracle=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,help='fresh RTL translation, only exact identical compiler inputs reused')
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh-native1GiB guard')
    info=json.loads(a.hls_report.read_text())
    if not info.get('pass_test')or info.get('HLS_top')!='rocev2_native_atomic_owned_top':p.error('matched complete owned core required')
    raw=ROOT/info['directory']/'project/solution1/syn/verilog'
    for n,h in info['generated_sha256'].items():
        if digest(raw/n)!=h:raise ValueError('raw generated HLS changed')
    run=Path(tempfile.mkdtemp(prefix='atomic-owned-generated-',dir=ROOT/'rdma/rnic/build'))
    obj=(Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])if a.reuse_compiled_report else
        Path(tempfile.mkdtemp(prefix='as02-atomic-owned-generated-obj-',dir='/dev/shm')))
    words,frames=inputs();tb,bridge=fixture.bench(run,len(words));(run/'tb.v').write_text(tb)
    (run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in words))
    axis=ROOT/'external/corundum/fpga/lib/axis/rtl';eth=ROOT/'external/corundum/fpga/lib/eth/rtl'
    sources=[*sorted(raw.glob('*.v')),*fixture.prior.rtl.SOURCES,fixture.service.RTL,
        ROOT/'rdma/rnic/rtl/rocev2_atomic_packet_guard.v',ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',
        ROOT/'rdma/rtl/rocev2_tx_padding.v',axis/'axis_adapter.v',axis/'axis_fifo.v',eth/'lfsr.v',bridge]
    sources=list(dict.fromkeys(sources));data=sorted(raw.glob('*.dat'))
    for item in data:shutil.copy2(item,run/item.name)
    modules=[fixture,fixture.service,fixture.base,fixture.prior,fixture.prior.rtl,fixture.prior.rtl.paged,
        fixture.bridge,fixture.bridge.base,fixture.bridge.base.base,
        fixture.bridge.base.base.parent,fixture.bridge.base.base.parent.bridge,
        fixture.bridge.base.base.parent.bridge.legacy,old]
    own=[Path(m.__file__).resolve()for m in modules]+[Path(__file__).resolve(),a.hls_report.resolve(),
        ROOT/'rdma/rtl/rocev2_integrity_transport.v',ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',
        ROOT/'rdma/host/rocev2_wire.py',run/'tb.v',run/'input.hex']
    before={str(x.relative_to(ROOT)):digest(x)for x in [*sources,*data,*own]}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        compile_directory=str(obj),actual_generated_HLS=True,actual_MR_PTE_paged_RAM_IP_UDP_ICRC=True,
        native_integrated=False,hardware_verified=False,two_state=True,simulation_limit_seconds=30,
        physical_host_ordering_and_positive_MAC_boundary_models=True,tests={})
    try:
        command=[str(old.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','8',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0',
            '-CFLAGS','-O0','--Mdir',str(obj),str(run/'tb.v'),*map(str,sources)]
        report['compile_command']=command
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5';start=time.monotonic()
        if a.reuse_compiled_report:
            import atomic_owned_generated_compile_cache as cache
            before[str(Path(cache.__file__).resolve().relative_to(ROOT))]=digest(Path(cache.__file__).resolve())
            reused=cache.compile(command,run,env,a.reuse_compiled_report.resolve())
            before.update(reused.pop('extra_source_sha256'));report.update(reused)
        else:
            with(run/'compile.log').open('x')as log:
                c=subprocess.run(command,cwd=run,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1200)
            report['compile_seconds']=time.monotonic()-start
            if c.returncode:raise RuntimeError('actual generated composition compile: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',run/'Vtb')
        for case in range(4):
            start=time.monotonic()
            with(run/f'case-{case}.log').open('x')as log:
                c=subprocess.run([str(run/'Vtb'),f'+case={case}'],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=old.no_core)
            report['tests'][case]=dict(seconds=time.monotonic()-start,exit=c.returncode)
            if c.returncode:raise RuntimeError('generated owned case: '+str(run/f'case-{case}.log'))
            report['tests'][case].update(verify((run/f'case-{case}.log').read_text(),case))
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','tests']}),flush=True)


if __name__=='__main__':main()
