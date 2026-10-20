#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""128-byte CAS/FADD/normal WQEs through actual SQ/RAM/mux/PCIe DMA RTL.

Trusted config and physical host/root/link remain models. Uses real extended
C codec, all128 fetched bytes/operands and trusted QP/PD/epoch/sequence checked.
No descriptor/status/RAM substitute, no host writes/fences, no WQE MR admission,
native requester/standard verbs/CQ completion, hardware or timing qualification.
"""
import argparse
import ctypes as C
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import probe_sq_dma_fetch as old
import test_atomic_wqe as codec

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_fetch as source


def bench(error):
    # The historical probe predates the eight explicit separate-RQ ports.
    # Review the CURRENT exact interface, not a permissive port-count waiver.
    ports=old.pcie.ports(old.TOP)
    extension=[entry for entry in ports if entry[2]in ['cfg_receive','admission_available',
        'receive_downstream_guard','receive_queue_guard','receive_queue_active',
        'receive_queue_pending','receive_queue_halted','m_result_receive']]
    expected=[('input','','cfg_receive'),('input','1:0','admission_available'),
        ('input','MAX_QPS-1:0','receive_downstream_guard'),
        *[('output','MAX_QPS-1:0',n)for n in ['receive_queue_guard','receive_queue_active','receive_queue_pending','receive_queue_halted']],
        ('output','','m_result_receive')]
    if extension!=expected:raise ValueError('unreviewed trusted SQ/RQ controls')
    code=source.once(inspect.getsource(old.bench),'if len(ports)!=79:','if len(ports)!=87:')
    namespace=dict(vars(old));exec(compile(code,'<checked-current-SQ-interface-fixture>','exec'),namespace)
    t=namespace['bench'](error)
    t=source.once(t,'rocev2_sq_dma_fetch dut(','rocev2_atomic128_sq_dma_fetch dut(')
    t=source.once(t,'wire [511:0] m_result_data;','wire [1023:0] m_result_data;')
    t=source.once(t,'reg [511:0] records[0:6];reg [7:0] host[0:255];',
        'reg [1023:0] records[0:6];reg [7:0] host[0:511];')
    if t.count('[703:0]')!=2:raise ValueError('exact full result/stalled context widths')
    t=t.replace('[703:0]','[1215:0]')
    for a,b in [('m_dma_read_length!==64','m_dma_read_length!==128'),
        ("address<64'h8123456789abc080","address<64'h8123456789abc100"),
        ("address<64'hfedcba9876543080","address<64'hfedcba9876543100"),
        ("host_index=128+address-64'hfedcba9876543000","host_index=256+address-64'hfedcba9876543000"),
        ('for(b=0;b<64;b=b+1)host[slot*64+b]','for(b=0;b<128;b=b+1)host[slot*128+b]'),
        ("error_code ? 512'd0 : records[record_index]","error_code ? 1024'd0 : records[record_index]"),
        ("h[105:96]!==16 || h[71:64]!==8'hff || h[5:0]!=0","h[105:96]!==32 || h[71:64]!==8'hff || h[6:0]!=0"),
        ("cpl[105:96]=16;","cpl[105:96]=32;"),('cpl[75:64]=64;','cpl[75:64]=128;'),
        ('bytes_count=64;','bytes_count=128;')]:t=source.once(t,a,b)
    # Byte counts in the inherited result summary are parsed separately here;
    # no assertion is replaced by a different successful-result label.
    return t


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--error',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if shutil.disk_usage(ROOT).free<256*1024**2:raise RuntimeError('component compile256MiB guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('RAM1GiB artifact guard')
    run=Path(tempfile.mkdtemp(prefix='atomic128-sq-dma-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic128-fetch-artifacts-',dir='/dev/shm'))
    generated={}
    for original,text in source.derive().items():
        path=run/('rocev2_atomic128_'+original.name.removeprefix('rocev2_'));path.write_text(text);generated[original]=path
    sources=[generated.get(path,path)for path in old.SOURCES]
    records=[];cls=codec.AtomicWQETests;cls.setUpClass()
    try:
        for i,(seq,epoch)in enumerate([(1,0x8000000000000001),(2,0x8000000000000001),
            (1,0x9000000000000001),(2,0x9000000000000001),(3,0x8000000000000001),
            (4,0x8000000000000001),(1,0x8000000000000002)]):
            op=[7,8,1,5,7,8,7][i]
            if op in [7,8]:w=codec.candidate(op,compare=(0xfedcba9876543210+i)if op==7 else 0,swap_add=0x8123456789abcdef+i,
                sequence=seq,epoch=epoch,wr_id=0xf123456700000000+i)
            else:w=codec.AtomicWQE(codec.base.candidate(opcode=op,sequence=seq,epoch=epoch,
                wr_id=0xf123456700000000+i,remote_address=0 if op==5 else 0xe23456789abcd008,
                remote_key=0 if op==5 else 0x81234567,immediate=0x89abcdef if op==5 else 0),0,0)
            out=(C.c_uint8*128)()
            if cls.lib.as02_atomic_wqe_encode(out,C.byref(w)) or bytes(out)!=codec.oracle(w):raise ValueError('actual extended C codec mismatch')
            records.append(bytes(out))
    finally:cls.tearDownClass()
    (run/'records.hex').write_text(''.join(f'{int.from_bytes(record,"little"):0256x}\n'for record in records))
    (run/'tb.v').write_text(bench(a.error))
    own=[*sources,source.FETCH,source.DMA,Path(source.__file__).resolve(),Path(__file__).resolve(),
        Path(old.__file__).resolve(),Path(old.sq.__file__).resolve(),Path(codec.__file__).resolve(),
        Path(codec.base.__file__).resolve(),*[codec.KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h']],run/'tb.v',run/'records.hex']
    before={str(path.relative_to(ROOT)):old.hashlib.sha256(path.read_bytes()).hexdigest()for path in own}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,error_case=a.error,
        actual_PCIe_engine=True,actual_backend_segmented_RAM_and_clients=True,actual_native_shape_muxes=True,
        descriptor_bytes=128,actual_C_codec=True,hardware_verified=False,native_requester_integrated=False,
        local_WQE_MR_authorization_connected=False,standard_API_runtime=False,RDMA_completion_claim=False,
        simulation_timeout_seconds=30)
    try:
        started=time.monotonic();command=['iverilog','-g2012','-s','tb','-o',str(ram/'test.vvp'),str(run/'tb.v'),*map(str,sources)]
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        report.update(compile_seconds=time.monotonic()-started,compiler_command=command)
        if c.returncode:raise RuntimeError('actual128-byte SQ/PCIe compile '+str(run/'compile.log'))
        started=time.monotonic();r=subprocess.run(['vvp',str(ram/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        (run/'simulation.log').write_text(r.stdout+r.stderr);report.update(simulation_seconds=time.monotonic()-started,simulator_exit=r.returncode)
        if r.returncode or 'ERROR:'in r.stdout+r.stderr:raise RuntimeError('actual128-byte SQ/PCIe run '+str(run/'simulation.log'))
        summaries=[json.loads(line.split(' ',1)[1])for line in r.stdout.splitlines()if line.startswith('SQ_PCIE_RESULT ')]
        actual=[line.split()[1:]for line in r.stdout.splitlines()if line.startswith('SQ_RECORD ')]
        expected=[(0,1,10,0),(7,1,0,2),(7,2,0,3),(0,1,0,6)]if a.error else [(0,1,0,0),(7,1,0,2),(0,2,0,1),(7,2,0,3),(0,3,0,4),(0,4,0,5)]
        if len(summaries)!=1 or not summaries[0]['pass_test']or len(actual)!=len(expected):raise ValueError('full128-byte result count')
        for row,(q,seq,error,index)in zip(actual,expected):
            if list(map(int,row[:3]))!=[q,seq,error]or int(row[3],16)!=(0 if error else int.from_bytes(records[index],'little')):
                raise ValueError('independent128-byte actual DMA operand/header oracle')
        if before!={n:old.hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}:raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True,summary=summaries[0],all_128_record_bytes_and_operands_verified=True,
            record_bytes_verified=128*len(actual),zeroed_error_bytes_verified=128 if a.error else 0,no_host_writes_or_fences=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(path.relative_to(ROOT)):old.hashlib.sha256(path.read_bytes()).hexdigest()for path in run.iterdir()if path.is_file()}
        report['RAM_artifact_sha256']={str(path):old.hashlib.sha256(path.read_bytes()).hexdigest()for path in ram.iterdir()if path.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,simulation_seconds=report['simulation_seconds'],summary=report['summary'])),flush=True)


if __name__=='__main__':main()
