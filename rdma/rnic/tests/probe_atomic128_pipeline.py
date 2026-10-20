#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual PCIe128-byte SQ -> one real MR table ->748 owner/408 SQ RTL.

Physical host/root/trusted config and downstream owner/HLS sinks are models.
No modeled descriptor/status/RAM/MR response or HLS SQ word drives the DUT.
This is NOT actual HLS Atomic execution/ACK/result/CQ/kernel/physical proof.
Both positive and PCIe UR runs are short bounded cases <=30sec.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic128_pipeline_fixture as fixture
import test_atomic_wqe as codec

ROOT=fixture.ROOT;source=fixture.source


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def records():
    result=[];cls=codec.AtomicWQETests;cls.setUpClass()
    try:
        for i,(seq,epoch)in enumerate([(1,0x8000000000000001),(2,0x8000000000000001),
            (1,0x9000000000000001),(2,0x9000000000000001),(3,0x8000000000000001),
            (4,0x8000000000000001),(1,0x8000000000000002)]):
            op=[7,8,1,5,7,8,7][i]
            fields=dict(opcode=op,sequence=seq,epoch=epoch,wr_id=0xf123456700000000+i,
                length=8 if op in [7,8]else 65,local_key=0x80000009 if i in [2,3]else 0x80000008,
                local_address=0xf123456789abc001,remote_address=0 if op==5 else 0xe23456789abcd008,
                remote_key=0 if op==5 else 0x81234567,immediate=0x89abcdef if op==5 else 0)
            w=codec.AtomicWQE(codec.base.candidate(**fields),0xfedcba9876543210+i if op==7 else 0,
                0x8123456789abcdef+i if op in [7,8]else 0)
            out=(C.c_uint8*128)()
            if cls.lib.as02_atomic_wqe_encode(out,C.byref(w)) or bytes(out)!=codec.oracle(w):raise ValueError('actual128-byte C encoder/oracle')
            result.append(bytes(out))
    finally:cls.tearDownClass()
    return result


def pack(values):
    result=0
    for width,value in values:result=(result<<width)|value
    return result


def verify(output,data,error):
    expected=[(0,1,10,0),(7,1,0,2),(7,2,0,3),(0,1,0,6)]if error else \
        [(0,1,0,0),(7,1,0,2),(0,2,0,1),(7,2,0,3),(0,3,0,4),(0,4,0,5)]
    raw=[line.split()[1:]for line in output.splitlines()if line.startswith('PIPE_RAW ')]
    works=[int(line.split()[1],16)for line in output.splitlines()if line.startswith('PIPE_WORK ')]
    owners=[int(line.split()[1],16)for line in output.splitlines()if line.startswith('PIPE_OWNER ')]
    sq=[int(line.split()[1],16)for line in output.splitlines()if line.startswith('PIPE_HLS ')]
    wanted_context=[];wanted_sq=[]
    if len(raw)!=len(expected):raise ValueError('actual fetched context count')
    for tag,(row,(q,seq,status,index))in enumerate(zip(raw,expected),1):
        r=data[index];pd=0xabcd if q==7 else 0xf123;epoch=int.from_bytes(r[56:64],'little')
        if [int(row[0]),int(row[1]),int(row[2],16),int(row[3]),int(row[4]),int(row[5])]!=[q,pd,epoch,seq,tag,status] or \
            int(row[6],16)!=(0 if status else int.from_bytes(r,'little')):raise ValueError('actual full128-byte DMA/context/operand mismatch')
        def get(off,n):return int.from_bytes(r[off:off+n],'little')if not status else 0
        wid=get(0,8);local=get(16,8);remote=get(24,8);length=get(32,4);lkey=get(36,4);rkey=get(40,4)
        op=get(44,2);flags=get(46,2);imm=get(48,4);compare=get(64,8);operand=get(72,8)
        lower=pack([(64,wid),(64,seq),(64,epoch),(24,q),(16,pd),(16,tag),(16,op),(16,flags),
            (32,length),(32,lkey),(64,local),(64,local-0xf123456789abc000 if not status else 0),
            (64,remote),(32,rkey),(8,status),(2,1 if status else 0),(8,status),(1,int(not status)),(1,int(not status))])
        wanted_context.append(lower|(imm<<588)|(compare<<620)|(operand<<684))
        if not status:
            wire_op={1:10,2:12,3:4,5:5,6:11,7:19,8:20}[op]
            wanted_sq.append((operand<<344)|(compare<<280)|(imm<<241)|(1<<240)|(rkey<<208)|(length<<176)|
                (remote<<112)|(local<<48)|(1<<43)|(1<<42)|(q<<32)|wire_op)
    if works!=wanted_context or owners!=wanted_context or sq!=wanted_sq:raise ValueError('independent full748-bit owner/408-bit SQ oracle')
    summaries=[json.loads(line.split(' ',1)[1])for line in output.splitlines()if line.startswith('SQ_PCIE_RESULT ')]
    if len(summaries)!=1 or not summaries[0]['pass_test']:raise ValueError('original PCIe/fetch assertions missing')
    return dict(summary=summaries[0],actual_work_contexts=[f'{n:0187x}'for n in works],
        actual_owner_contexts=[f'{n:0187x}'for n in owners],actual_SQ_words=[f'{n:0102x}'for n in sq],
        actual_PCIe_to_same_MR_to_guarded_owner_SQ=True,all_header_operand_and_context_bits_verified=True,
        no_CPU_payload_copy_or_MR_authorization_substitute=True,downstream_owner_and_HLS_models=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--error',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if shutil.disk_usage(ROOT).free<256*1024**2:raise RuntimeError('component256MiB guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('RAM1GiB artifact headroom')
    run=Path(tempfile.mkdtemp(prefix='atomic128-request-pipeline-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic128-pipeline-artifacts-',dir='/dev/shm'))
    data=records();(run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0256x}\n'for r in data))
    (run/'tb.v').write_text(fixture.bench(a.error))
    generated={}
    for original,text in {**source.fetch.derive(),**source.derive()}.items():
        path=run/('rocev2_atomic128_'+original.name.removeprefix('rocev2_'));path.write_text(text);generated[original]=path
    sources=[generated.get(path,path)for path in fixture.fetch.old.SOURCES]
    sources += [generated[source.WQE],generated[source.SQ],generated[source.HLS],source.RTL/'rocev2_mr_table.v']
    helpers=[Path(m.__file__).resolve()for m in [fixture,fixture.fetch,fixture.fetch.old,fixture.admission,source,source.fetch,codec,codec.base]]
    own=[*sources,*generated,Path(__file__).resolve(),*helpers,*[codec.KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h','mr_contract.h']],run/'tb.v',run/'records.hex']
    before={str(path.relative_to(ROOT)):digest(path)for path in own}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,error_case=a.error,
        actual_PCIe_DMA_RAM_and_muxes=True,actual_single_MR_table=True,actual_C_UBSan=True,
        actual_owner_and_SQ_staging=True,HLS_endpoint_model=True,executor_endpoint_model=True,
        native_requester_integrated=False,hardware_verified=False,standard_API_runtime=False,WR_completion_claim=False,simulation_limit_seconds=30)
    try:
        started=time.monotonic();cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test.vvp'),str(run/'tb.v'),*map(str,sources)]
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        report.update(compile_seconds=time.monotonic()-started,compiler_command=cmd)
        if c.returncode:raise RuntimeError('pipeline actual RTL compile '+str(run/'compile.log'))
        started=time.monotonic();r=subprocess.run(['vvp',str(ram/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        (run/'simulation.log').write_text(r.stdout+r.stderr);report.update(simulation_seconds=time.monotonic()-started,simulation_exit=r.returncode)
        if r.returncode or 'ERROR:'in r.stdout+r.stderr:raise RuntimeError('pipeline actual RTL run '+str(run/'simulation.log'))
        report.update(verify(r.stdout,data,a.error))
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('pipeline source changed '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(path.relative_to(ROOT)):digest(path)for path in run.iterdir()if path.is_file()}
        report['RAM_artifact_sha256']={str(path):digest(path)for path in ram.iterdir()if path.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,simulation_seconds=report['simulation_seconds'],summary=report['summary'])),flush=True)


if __name__=='__main__':main()
