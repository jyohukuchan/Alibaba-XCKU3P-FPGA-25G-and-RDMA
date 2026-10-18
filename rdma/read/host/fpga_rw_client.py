#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite version2 FPGA READ/WRITE client. No programming or host DMA.

READ reference bytes are derived independently from a32-byte peer nonce;
TCP never carries the source payload. Returned data is read from real BAR RAM.
Live access keeps the original audited PCI identity and exclusive device lock.
"""
import argparse
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import mmap
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / 'rdma/host'))
import fpga_write_client as common

CAPACITY=262144
RAM_BASE=0x10000
MMIO_BYTES=RAM_BASE+CAPACITY
MODE,READ_WINDOW,CAPACITY_REG,RAM_BASE_REG=0x100,0x104,0x108,0x10C
COMMITTED,CAPTURE_BYTES,PADDING,CHUNKS,CAPTURE_ERROR,AUTHORIZED,LEASE,CAPTURE_STATE,RUN_ID=range(0x110,0x134,4)
require=common.require
ClientError=common.ClientError


def source_data(nonce,size,count):
    require(len(nonce)==32 and 1<=size<=65536 and 1<=count<=4096 and size*count<=CAPACITY,
            'invalid synthetic source extent/nonce')
    return hashlib.shake_256(nonce+struct.pack('!II',size,count)).digest(size*count)


@dataclass(frozen=True)
class ReadConfig:
    local_ip:str
    peer_ip:str
    local_mac:int
    peer_mac:int
    size:int=65
    count:int=1
    local_qpn:int=2
    local_psn:int=0x123456
    device_timeout_cycles:int=common.CLOCK_HZ//10
    host_timeout_seconds:float=2.0
    read_window:int=1

    @property
    def stride(self):return (self.size+63)&~63

    @property
    def allocation(self):return self.stride*self.count

    def validate(self):
        common.ipv4(self.local_ip);common.ipv4(self.peer_ip)
        require(self.local_ip!=self.peer_ip,'local/peer IP must differ')
        require(1<=self.size<=65536 and 1<=self.count<=4096 and self.allocation<=CAPACITY,
                'READ requires1..65536bytes,1..4096operations within256KiB aligned capture')
        require(2<=self.local_qpn<8 and 0<=self.local_psn<=0xFFFFFF,'QP/PSN outside compiled width')
        require(1<=self.read_window<=32,'READ resource window must be1..32')
        require(all(0<m<(1<<48) and not m&(1<<40) for m in (self.local_mac,self.peer_mac)),
                'unicast nonzero MACs required')
        require(10000<=self.device_timeout_cycles<=4*common.CLOCK_HZ and
                self.device_timeout_cycles/common.CLOCK_HZ<self.host_timeout_seconds<=8,
                'device/host deadlines must fit before peer teardown')


@dataclass(frozen=True)
class ReadEndpoint:
    qpn:int
    psn:int
    rkey:int
    address:int
    size:int
    count:int
    gid:bytes
    nonce:bytes
    resources:int

    def encode(self):
        text=(f'AS02RD2 {self.qpn:x} {self.psn:x} {self.rkey:x} {self.address:x} '
              f'{self.size} {self.count} {self.gid.hex()} {self.nonce.hex()} {self.resources}\n').encode('ascii')
        require(len(text)<common.CONTROL_BYTES,'endpoint record too long')
        return text.ljust(common.CONTROL_BYTES,b'\0')


def decode_endpoint(packet,config):
    require(len(packet)==common.CONTROL_BYTES,'truncated READ endpoint')
    prefix,nul,padding=packet.partition(b'\0')
    require(nul==b'\0' and not padding.strip(b'\0') and prefix.endswith(b'\n'),'bad endpoint padding/framing')
    try:fields=prefix[:-1].decode('ascii').split(' ')
    except UnicodeDecodeError as error:raise ClientError('non-ASCII READ endpoint') from error
    require(len(fields)==10 and fields[0]=='AS02RD2','bad READ endpoint fields/version')
    for value,width in zip(fields[1:5],(6,6,8,16)):
        require(re.fullmatch(r'[0-9a-fA-F]{1,'+str(width)+r'}',value) is not None,'bad endpoint hex width')
    require(all(re.fullmatch(r'[0-9]{1,5}',v) for v in fields[5:7]) and
        re.fullmatch(r'[0-9a-fA-F]{32}',fields[7]) is not None and
        re.fullmatch(r'[0-9a-fA-F]{64}',fields[8]) is not None and
        re.fullmatch(r'[0-9]{1,2}',fields[9]) is not None,'bad endpoint size/nonce/resources')
    peer=ReadEndpoint(*(int(v,16) for v in fields[1:5]),int(fields[5]),int(fields[6]),
                      bytes.fromhex(fields[7]),bytes.fromhex(fields[8]),int(fields[9]))
    require(2<=peer.qpn<=0xFFFFFF and peer.size==config.size and peer.count==config.count,
            'peer QP/extent differs from requested READ')
    require(peer.gid==common.gid_for_ip(config.peer_ip),'peer GID differs from explicit IPv4')
    require(peer.address!=0 and peer.address+peer.size*peer.count<=0xFFFFFFFFFFFFFFFF,
            'peer source MR overflows64bits')
    require(1<=peer.resources<=32 and config.read_window<=peer.resources,'peer has insufficient READ resources')
    return peer


class PciBar2V2(common.PciBar2):
    def __init__(self,bdf):
        # Retain the original explicit opt-in, BDF/subsystem/driver checks,
        # x86_64 UC mapping and the SAME exclusive lock used by old clients.
        super().__init__(bdf)
        try:
            require(os.fstat(self.fd).st_size>=MMIO_BYTES,'BAR2 cannot cover the protected capture window')
            self.mapping.close();self.mapping=None
            self.mapping=mmap.mmap(self.fd,MMIO_BYTES,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE)
            self.check_identity()
        except BaseException:
            self.close();raise

    def check_identity(self):
        require(self.read32(common.ID)==0x524F4332 and self.read32(common.VERSION)==0x00020000,
                'BAR2 is not the supported version2 READ/WRITE app')
        require(self.read32(CAPACITY_REG)==CAPACITY and self.read32(RAM_BASE_REG)==RAM_BASE,
                'unexpected version2 capture RAM layout')

    def read32(self,address):
        require(0<=address<MMIO_BYTES and address%4==0 and address+4<=len(self.mapping),'invalid version2 MMIO read')
        return struct.unpack_from('<I',self.mapping,address)[0]

    def write32(self,address,value):
        require(0<=address<MMIO_BYTES and address%4==0 and address+4<=len(self.mapping) and
                0<=value<=0xFFFFFFFF,'invalid version2 MMIO write')
        struct.pack_into('<I',self.mapping,address,value)
        require(self.read32(common.ID)==0x524F4332,'device disappeared during MMIO write')


def snapshot(registers):
    result=common.snapshot(registers)
    result.update(operation_mode=registers.read32(MODE),run_id=registers.read32(RUN_ID),
        committed=registers.read32(COMMITTED),capture_bytes=registers.read32(CAPTURE_BYTES),
        padding_bytes=registers.read32(PADDING),response_chunks=registers.read32(CHUNKS),
        capture_error=registers.read32(CAPTURE_ERROR),authorized=registers.read32(AUTHORIZED),
        capture_lease=registers.read32(LEASE),capture_state=registers.read32(CAPTURE_STATE))
    return result


def capture_vectors(config,payload):
    extent=min(CAPACITY,config.allocation+64)
    expected=bytearray(b'\xa5'*extent);prefill=bytearray(expected)
    for index in range(config.count):
        part=payload[index*config.size:(index+1)*config.size];start=index*config.stride
        expected[start:start+config.size]=part
        prefill[start:start+config.size]=bytes(b^255 for b in part)
    return expected,prefill


def readback(registers,config,payload,evidence):
    expected,_=capture_vectors(config,payload)
    observed=bytearray(len(expected))
    for address in range(0,len(expected),4):
        observed[address:address+4]=registers.read32(RAM_BASE+address).to_bytes(4,'little')
    mismatches=sum(a!=b for a,b in zip(expected,observed))
    first_bad=next((i for i,(a,b) in enumerate(zip(expected,observed)) if a!=b),None)
    actual=b''.join(observed[i*config.stride:i*config.stride+config.size] for i in range(config.count))
    evidence.update(bar_bytes_compared=len(expected),payload_bytes_compared=len(payload),mismatches=mismatches,
        first_bad_capture_offset=first_bad,actual_payload_sha256=hashlib.sha256(actual).hexdigest(),
        sentinel_bytes_compared=len(expected)-len(payload))
    require(mismatches==0,'BAR capture payload/sentinel byte mismatch')


def run_config_error_probe(registers,config,evidence):
    """Reject a one-byte-short advertised source range before any READ SQ.

    Caller owns the BAR and keeps the peer MR/readiness lease throughout this
    prelude and the following valid READ. CLEAR is app-local, not a NIC/global
    reset. Saved terminal diagnostics are cleared by START even when the core
    is never released, so cumulative TX counters are compared in IDLE instead.
    """
    before=snapshot(registers)
    require(common.safe_terminal(before['status']) and common.state(before['status'])==0 and
            before['operation_mode']==1,'configuration probe requires owned READ IDLE')
    require(before['run_id']<=0xFFFFFFFD,'configuration probe and recovery need two fresh generations')
    probe=dict(success=False,before=before,advertised_remote_bytes=config.size*config.count-1,
        required_remote_bytes=config.size*config.count,expected_error_code=1,
        application_commands=[],global_reset_requested=False,peer_mr_lease_retained=True)
    evidence['configuration_error_probe']=probe
    registers.write32(0x78,probe['advertised_remote_bytes'])
    registers.write32(0x7C,0)
    require(registers.read32(0x78)==probe['advertised_remote_bytes'] and registers.read32(0x7C)==0,
            'one-byte-short source range did not read back')
    rejects=registers.read32(common.REJECTS)
    # Record ownership before the posted START/flush, including an interrupted
    # MMIO write. run_read then performs bounded abort/quiescence on any failure.
    probe['application_commands'].append(1)
    registers.write32(common.COMMAND,1)
    deadline=time.monotonic()+config.host_timeout_seconds
    while True:
        status=registers.read32(common.STATUS)
        if status&(common.DONE|common.FAILED):break
        require(time.monotonic()<deadline,'configuration error probe deadline exceeded')
        time.sleep(0.001)
    failed=snapshot(registers);probe['error_terminal']=failed
    require(common.safe_terminal(failed['status']) and common.state(failed['status'])==8 and
        failed['status']&common.FAILED and not failed['status']&common.DONE and failed['error_code']==1 and
        failed['status']&0x80 and failed['operation_mode']==1 and failed['run_id']==before['run_id']+1,
        'invalid READ range did not enter quiescent ERR_CONFIG')
    require(all(failed[key]==0 for key in ('issued','acknowledged','committed','capture_bytes','authorized',
        'response_chunks','padding_bytes','capture_error','read_commands','read_bytes')) and
        failed['capture_state']==6 and all(value==0 for value in failed['diagnostics'].values()),
        'invalid READ range reached SQ/payload/transport or capture fault')
    require(registers.read32(common.REJECTS)==rejects,'probe START was rejected instead of range-validated')
    probe['application_commands'].append(2)
    common.prepare(registers)
    cleared=snapshot(registers);probe['cleared_idle']=cleared
    require(cleared['run_id']==failed['run_id'] and cleared['operation_mode']==1 and
        all(cleared['diagnostics'][key]==before['diagnostics'][key] for key in ('0xc0','0xc4')) and
        registers.read32(common.REJECTS)==rejects,
        'CLEAR changed generation or invalid range emitted actual RoCE TX/completions')
    probe.update(success=True,no_read_sq_issued=True,no_roce_tx_or_completion=True,
        clear_without_global_reset=True)


def run_read(registers,config,sock,*,probe_config_error=False):
    config.validate();common.prepare(registers)
    started=False;released=False
    evidence=dict(event='fpga_read_test',success=False,source_verified_unchanged=False,host_bar_verified=False,
        message_bytes=config.size,messages=config.count,read_window=config.read_window,
        config_error_probe_requested=probe_config_error,config_error_recovery_verified=False,
        control_only_tcp=True,software_roce_in_this_client=False,fpga_payload_destination='protected_local_capture_ram')
    wall_start=time.monotonic()
    try:
        peer=decode_endpoint(common.receive(sock,common.CONTROL_BYTES),config)
        reference=source_data(peer.nonce,config.size,config.count)
        evidence.update(nonce=peer.nonce.hex(),expected_payload_sha256=hashlib.sha256(reference).hexdigest(),
            local_qpn=config.local_qpn,local_psn=config.local_psn,peer_qpn=peer.qpn,peer_psn=peer.psn,
            peer_rkey=f'0x{peer.rkey:08x}',peer_address=f'0x{peer.address:016x}',peer_read_resources=peer.resources)
        local=ReadEndpoint(config.local_qpn,config.local_psn,0,0,config.size,config.count,
            common.gid_for_ip(config.local_ip),peer.nonce,config.read_window)
        sock.sendall(local.encode())
        require(common.receive(sock,1)==b'R','peer READ responder was not ready')
        common.configure(registers,config,peer)
        rejected=registers.read32(common.REJECTS)
        registers.write32(MODE,1);registers.write32(READ_WINDOW,config.read_window)
        require(registers.read32(MODE)==1 and registers.read32(READ_WINDOW)==config.read_window,
                'READ mode/resource readback differs')
        _,prefill=capture_vectors(config,reference)
        for address in range(0,len(prefill),4):
            registers.write32(RAM_BASE+address,int.from_bytes(prefill[address:address+4],'little'))
        require(registers.read32(common.REJECTS)==rejected,'FPGA rejected configuration or RAM prefill')
        run_before=registers.read32(RUN_ID)
        require(run_before<=(0xFFFFFFFD if probe_config_error else 0xFFFFFFFE),
                'insufficient fresh run generations; no silent wrap permitted')
        sock.sendall(b'R')
        started=True
        if probe_config_error:
            run_config_error_probe(registers,config,evidence)
            common.configure(registers,config,peer)
            require(registers.read32(MODE)==1 and registers.read32(READ_WINDOW)==config.read_window,
                    'READ ownership/configuration changed after error CLEAR')
            run_before=registers.read32(RUN_ID)
        baseline_tx=registers.read32(0xC0);baseline_cpl=registers.read32(0xC4)
        registers.write32(common.COMMAND,1)
        deadline=time.monotonic()+config.host_timeout_seconds
        while True:
            status=registers.read32(common.STATUS)
            if status&(common.DONE|common.FAILED):break
            require(time.monotonic()<deadline,'FPGA READ completion deadline exceeded')
            time.sleep(0.001)
        result=snapshot(registers);evidence.update(result)
        require(common.safe_terminal(result['status']),'terminal state does not prove TX/core quiescence')
        require(common.state(result['status'])==7 and result['status']&common.DONE and
                not result['status']&common.FAILED and result['error_code']==0,'FPGA READ failed')
        require(result['status']&0x80 and result['operation_mode']==1 and result['run_id']==run_before+1,
                'READ operation/generation mismatch')
        total=config.size*config.count;chunks=((config.size+4095)//4096)*config.count
        require(result['issued']==config.count and result['acknowledged']==config.count and
                result['total_bytes']==total and result['elapsed_cycles']>0,'missing READ completions')
        require(result['committed']==config.count and result['capture_bytes']==total and result['authorized']==config.count and
                result['response_chunks']==chunks and result['padding_bytes']==((-config.size)&3)*config.count and
                result['capture_error']==0 and result['capture_lease']==config.allocation and
                result['capture_state']==6,'READ data was not fully committed to idle protected RAM')
        diag=result['diagnostics']
        require(diag['0xcc']==0 and diag['0xac']==0 and diag['0xb0']==0,'TX guard/integrity/overflow fault')
        require(((diag['0xc0']-baseline_tx)&0xFFFFFFFF)>=config.count and
                ((diag['0xc4']-baseline_cpl)&0xFFFFFFFF)>=config.count and
                result['read_commands']==0 and result['read_bytes']==0,'not the actual READ request/capture path')
        readback(registers,config,reference,evidence)
        require(registers.read32(RUN_ID)==result['run_id'] and registers.read32(common.STATUS)==result['status'] and
                registers.read32(COMMITTED)==config.count and registers.read32(CAPTURE_BYTES)==total,
                'capture ownership/state changed during BAR readback')
        evidence['host_bar_verified']=True
        sock.sendall(b'D');released=True
        require(common.receive(sock,1)==b'P','native peer source memory changed or MR verification failed')
        evidence.update(success=True,source_verified_unchanged=True,tx_quiescence_verified=True,
            config_error_recovery_verified=probe_config_error,
            expected_payload_complement_prefilled=True,source_payload_transferred_over_tcp=False,
            seconds_from_hw_counter=result['elapsed_cycles']/common.CLOCK_HZ,
            includes_initialization_and_drain=True,benchmark_claim=False,
            total_control_wall_seconds=time.monotonic()-wall_start,remote_provider_identity_verified=False)
        return evidence
    except BaseException as error:
        evidence.update(error=str(error) or type(error).__name__,start_attempted=started)
        if started:
            try:
                evidence['tx_quiescence_verified']=common.abort_owned(registers)
                evidence['final_status']=registers.read32(common.STATUS)
                if evidence['tx_quiescence_verified'] and not released:
                    sock.sendall(b'A');released=True
                    evidence['abort_source_lease_release_acknowledged']=common.receive(sock,1)==b'P'
            except BaseException as cleanup_error:
                evidence['cleanup_error']=str(cleanup_error) or type(cleanup_error).__name__
                evidence.setdefault('tx_quiescence_verified',False)
        raise ClientError(str(error) or type(error).__name__,evidence) from error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation',choices=('read','write'),required=True)
    parser.add_argument('--bdf',required=True)
    parser.add_argument('--local-ip',required=True,type=common.ipv4)
    parser.add_argument('--peer-ip',required=True,type=common.ipv4)
    parser.add_argument('--local-mac',required=True,type=common.mac_number)
    parser.add_argument('--peer-mac',required=True,type=common.mac_number)
    parser.add_argument('--message-bytes',type=int,default=65)
    parser.add_argument('--count',type=int,default=1)
    parser.add_argument('--read-window',type=int,default=1)
    parser.add_argument('--probe-config-error',action='store_true',
        help='READ only: reject a one-byte-short advertised source range, CLEAR, then perform the valid READ')
    parser.add_argument('--qpn',type=int,default=2)
    parser.add_argument('--psn',type=lambda s:int(s,0))
    parser.add_argument('--port',type=int,default=18516)
    parser.add_argument('--device-timeout-cycles',type=int,default=common.CLOCK_HZ//10)
    parser.add_argument('--host-timeout-seconds',type=float,default=2.0)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    require(not args.probe_config_error or args.operation=='read','configuration error probe is READ only')
    require(1<=args.port<=65535,'invalid control port')
    if args.report:require(not args.report.exists(),'refusing to replace a prior test result')
    cls=ReadConfig if args.operation=='read' else common.Config
    keywords=dict(size=args.message_bytes,count=args.count,local_qpn=args.qpn,
        local_psn=args.psn if args.psn is not None else secrets.randbelow(1<<24),
        device_timeout_cycles=args.device_timeout_cycles,host_timeout_seconds=args.host_timeout_seconds)
    if args.operation=='read':keywords['read_window']=args.read_window
    config=cls(args.local_ip,args.peer_ip,args.local_mac,args.peer_mac,**keywords);config.validate()
    def interrupted(signum,_):raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        with PciBar2V2(args.bdf) as registers:
            with socket.create_connection((config.peer_ip,args.port),timeout=5,source_address=(config.local_ip,0)) as control:
                control.settimeout(5)
                if args.operation=='read':result=run_read(registers,config,control,probe_config_error=args.probe_config_error)
                else:
                    common.prepare(registers);registers.write32(MODE,0)
                    require(registers.read32(MODE)==0,'cannot select exclusive WRITE mode')
                    result=common.run_transfer(registers,config,control)
        result.update(operation=args.operation,bdf=args.bdf,hardware_access=True,application_version=0x20000)
        code=0
    except ClientError as error:
        result=dict(error.evidence,success=False,error=str(error),operation=args.operation,bdf=args.bdf)
        code=1
    print(json.dumps(result,indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
    return code


if __name__=='__main__':
    try:sys.exit(main())
    except (ClientError,OSError,ValueError) as error:
        print('refused/failed: '+str(error),file=sys.stderr);sys.exit(1)
