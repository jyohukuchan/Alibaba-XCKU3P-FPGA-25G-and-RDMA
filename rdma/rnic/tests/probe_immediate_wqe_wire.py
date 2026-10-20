#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C/verbs adapter -> SQ-result/MR -> typed staging -> generated HLS.

Checks real padding/IPv4/ICRC and actual ACK-consuming request retirement.
Fetched SQ result, payload memory, executor lifetime and peer are MODELS;
NOT coherent SQ DMA, native memory/MAC/CQ, real post_send/provider or hardware.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import test_wqe_codec as codec
import test_kernel_queue_lifecycle as kernel_test

ROOT=codec.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_immediate_bridge as bridge
sys.path.insert(0,str(ROOT/'rdma/host'))
from rocev2_wire import internet_checksum,icrc_ipv4

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(values,base):
    for n,h in values.items():
        if digest(base/n)!=h:raise ValueError('consumed source changed: '+str(base/n))

def acknowledgment():
    ip=bytearray(struct.pack('!BBHHHBBH4s4s',0x45,0,48,100,0,64,17,0,
        bytes([198,18,11,1]),bytes([198,18,11,2])))
    ip[10:12]=internet_checksum(ip).to_bytes(2,'big')
    bth=b'\x11\0\xff\xff\0'+(2).to_bytes(3,'big')+b'\0'+(0xfffffe).to_bytes(3,'big')
    p=bytes(ip)+struct.pack('!HHHH',4791,4791,28,0)+bth+b'\0\0\0\1'+bytes(4)
    return p[:-4]+icrc_ipv4(p)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-report',type=Path,required=True)
    p.add_argument('--simulator',choices=['verilator','iverilog'],default='verilator')
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    hls=json.loads(a.hls_report.read_text())
    if not hls.get('pass_test')or hls.get('HLS_top')!='rocev2_native_immediate_top':raise ValueError('actual matched Immediate HLS required')
    verify(hls['source_sha256'],ROOT)
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog';verify(hls['generated_sha256'],raw)
    rtl=ROOT/'rdma/rnic/rtl';axis=ROOT/'external/corundum/fpga/lib/axis/rtl'
    static=[rtl/n for n in ['rocev2_wqe_admission.v','rocev2_sq_wqe_admission.v','rocev2_wqe_hls_sq.v','rocev2_mr_table.v']]
    static += [ROOT/'rdma/rtl'/n for n in ['rocev2_ipv4_icrc.v','rocev2_tx_padding.v']]
    static += [axis/n for n in ['axis_adapter.v','axis_fifo.v','axis_register.v']]+[ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']
    tests=ROOT/'rdma/rnic/tests';kernel=ROOT/'rdma/rnic/kernel';bench=tests/'immediate_wqe_wire_tb.v'
    sources=[*static,*raw.glob('*.v'),*raw.glob('*.dat'),a.hls_report.resolve(),bench,Path(__file__).resolve(),
        Path(codec.__file__).resolve(),tests/'test_immediate_wqe.py',tests/'kernel_immediate_wqe.c',
        tests/'kernel_queue_model.h',Path(kernel_test.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',
        *[kernel/n for n in ['wqe.c','wqe.h','mr_contract.h','verbs_wqe.c']],
        Path(bridge.__file__).resolve(),Path(bridge.parent.__file__).resolve(),Path(bridge.parent.bridge.__file__).resolve(),
        Path(bridge.parent.bridge.legacy.__file__).resolve(),bridge.parent.bridge.legacy.BRIDGE]
    before={str(x.relative_to(ROOT)):digest(x)for x in sources}
    run=Path(tempfile.mkdtemp(prefix='immediate-wqe-wire-',dir=ROOT/'rdma/rnic/build'))
    (run/'bridge.v').write_text(bridge.derive());shutil.copy2(bench,run/'tb.v')
    for x in raw.glob('*.dat'):shutil.copy2(x,run/x.name)
    result=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        actual_generated_HLS=True,actual_MR_table=True,hardware_verified=False,native_integration=False,
        simulation_limit_seconds_per_case=30,simulation_cases=8,models=['fetched SQ result','payload memory','executor lifetime','peer ACK'],
        real_post_send_or_provider=False,native_DMA_MAC_or_CQ=False,tests={})
    result.update(simulator=a.simulator,two_state_simulation=a.simulator=='verilator',four_state_simulation=a.simulator=='iverilog')
    print(json.dumps(dict(directory=str(run),actual_generated_HLS=True,per_case_seconds_max=30,hardware_untouched=True)),flush=True)
    try:
        c=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-fsanitize=undefined',
            '-fno-sanitize-recover=undefined','-I',str(kernel),str(kernel/'wqe.c'),'-o',str(run/'codec.so')],capture_output=True,text=True,timeout=30)
        (run/'codec-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('codec compile failed')
        lib=C.CDLL(str(run/'codec.so'));lib.as02_wqe_encode_profile.argtypes=[C.POINTER(C.c_uint8),C.POINTER(codec.WQE),C.c_uint32]
        records=[];work=[]
        for op in [5,6]:
            for imm in [0,0x01234567,0x80000000,0xffffffff]:
                index=len(records);w=codec.candidate(wr_id=0xf123456789abc001+index,sequence=index+1,
                    local_address=0xfedcba9876543210,local_key=0x80000008,opcode=op,immediate=imm,
                    remote_address=0 if op==5 else 0xe23456789abcdef0,remote_key=0 if op==5 else imm^0x81234567)
                data=(C.c_uint8*64)()
                if lib.as02_wqe_encode_profile(data,C.byref(w),1)or bytes(data)!=codec.oracle(w):raise ValueError('actual C/independent Immediate descriptor oracle')
                records.append(bytes(data));work.append(w)
        (run/'records.hex').write_text(''.join(f'{int.from_bytes(x,"little"):0128x}\n'for x in records))
        ack=acknowledgment();words=[(int(j==2)<<144)|(65535<<128)|int.from_bytes(ack[j*16:j*16+16],'little')for j in range(3)]
        (run/'acks.hex').write_text(''.join(f'{v:037x}\n'for _ in range(8)for v in words))
        # Execute actual Linux-WR adapter with explicit primitive/type models.
        includes=run/'include'
        for name in kernel_test.HEADERS:
            target=includes/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('#include "kernel_queue_model.h"\n')
        command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(includes),'-I',str(tests),'-I',str(kernel),
            '-include',str(tests/'kernel_queue_model.h'),str(kernel/'wqe.c'),str(kernel/'verbs_wqe.c'),
            str(tests/'kernel_immediate_wqe.c'),'-o',str(run/'verbs-test')]
        c=subprocess.run(command,capture_output=True,text=True,timeout=30);(run/'verbs-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual verbs adapter compile failed: '+str(run/'verbs-compile.log'))
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        r=subprocess.run([str(run/'verbs-test')],capture_output=True,text=True,timeout=10,env=env)
        (run/'verbs.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('actual verbs adapter failed: '+str(run/'verbs.log'))
        result['actual_C_verbs_profile_cases']=8;result['default_legacy_posting_profile_still_refuses']=True
        all_rtl=[run/'tb.v',run/'bridge.v',*static,*sorted(raw.glob('*.v'))]
        if a.simulator=='iverilog':
            command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),*map(str,all_rtl)];compile_limit=60
        else:
            obj=Path(tempfile.mkdtemp(prefix='as02-immediate-obj-',dir='/dev/shm'))
            result['compile_directory']=str(obj)
            command=['/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator','--binary','--timing',
                '--top-module','tb','-Wno-fatal','-j','4','--output-split','20000','--output-split-cfuncs','0',
                '-CFLAGS','-O0','--Mdir',str(obj),*map(str,all_rtl)];compile_limit=1200
        env_compile=os.environ.copy();env_compile['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=compile_limit,env=env_compile)
        result['compile_seconds']=time.monotonic()-start;result['compile_command']=command
        (run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual Immediate pipeline compile failed: '+str(run/'compile.log'))
        for index,w in enumerate(work):
            runtime=['vvp',str(run/'test.vvp')]if a.simulator=='iverilog'else[str(obj/'Vtb')]
            start=time.monotonic()
            try:r=subprocess.run([*runtime,'+CASE='+str(index)],cwd=run,capture_output=True,text=True,timeout=30)
            except subprocess.TimeoutExpired as e:
                (run/f'case{index}.log').write_text((e.stdout or b'').decode(errors='replace')+(e.stderr or b'').decode(errors='replace'))
                raise
            elapsed=time.monotonic()-start;(run/f'case{index}.log').write_text(r.stdout+r.stderr)
            if r.returncode:raise RuntimeError('actual Immediate pipeline failed: '+str(run/f'case{index}.log'))
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('IMMEDIATE_WQE_WIRE ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual pipeline assertions')
            packets=[];current=bytearray()
            for line in r.stdout.splitlines():
                if not line.startswith('IMMEDIATE_IP '):continue
                _,data,keep,last=line.split();beat=int(data,16).to_bytes(16,'little')
                current.extend(beat[j]for j in range(16)if int(keep,16)&(1<<j))
                if last=='1':packets.append(bytes(current));current.clear()
            if len(packets)!=1 or current:raise ValueError('exactly one complete actual IP request required')
            packet=packets[0];header=(struct.pack('!QII',w.remote_address,w.remote_key,w.length)if w.opcode==6 else b'')+struct.pack('!I',w.immediate)
            payload=bytes((j*131^0x5a)&255 for j in range(65))
            if len(packet)!=116+(16 if w.opcode==6 else 0)or packet[0]!=0x45 or packet[9]!=17 or internet_checksum(packet[:20])or \
                packet[12:20]!=bytes([198,18,11,2,198,18,11,1])or packet[20:24]!=struct.pack('!HH',4791,4791)or \
                int.from_bytes(packet[2:4],'big')!=len(packet)or int.from_bytes(packet[24:26],'big')!=len(packet)-20 or \
                packet[28]!=(5 if w.opcode==5 else 11)or (packet[29]>>4)&3!=3 or packet[29]&0xcf!=0x40 or \
                packet[30:32]!=b'\xff\xff'or int.from_bytes(packet[33:36],'big')!=196 or \
                int.from_bytes(packet[37:40],'big')!=0xfffffe or packet[40:-4]!=header+payload+bytes(3)or packet[-4:]!=icrc_ipv4(packet):
                raise ValueError('Immediate/key/VA/payload/padding/IP/UDP/BTH/ICRC mismatch in actual packet')
            result['tests'][str(index)]=dict(summary=rows[0],simulation_seconds=elapsed,opcode=w.opcode,immediate=w.immediate,
                remote_key=w.remote_key,remote_address=w.remote_address,packet_hex=packet.hex(),actual_wire_and_ICRC_match=True)
            print(json.dumps(dict(case=index,pass_test=True,opcode=w.opcode,simulation_seconds=elapsed)),flush=True)
        verify(before,ROOT);verify(hls['generated_sha256'],raw)
        result.update(pass_test=True,source_unchanged=True,matched_generated_HLS_unchanged=True,
            generated_fixture_sha256={n:digest(run/n)for n in ['bridge.v','tb.v','records.hex','acks.hex']})
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),directory=str(run.relative_to(ROOT)))))

if __name__=='__main__':main()
