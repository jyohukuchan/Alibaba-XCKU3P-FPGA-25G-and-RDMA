# SPDX-License-Identifier: BSD-2-Clause-Views
"""Native tool offline models/cross-language oracles; never map PCI or open QPs."""
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / 'rdma/read/host'))
import fpga_rw_client as client

old=client.common
NONCE=bytes(range(32))
CFG=client.ReadConfig('198.18.10.2','198.18.10.1',0x8AF3FBB97531,0xB8830367C5D0,
    size=65,count=3,local_psn=0xFFFFFE,device_timeout_cycles=10000,host_timeout_seconds=0.02)
IDLE=old.CORE_RESET|old.QUIET|old.HALT
ACTIVE=(5<<8)|old.BUSY|0x80
DONE=(7<<8)|IDLE|old.DONE|0x80
ERROR=(8<<8)|IDLE|old.FAILED|0x80


def endpoint(cfg=CFG,nonce=NONCE,resources=1):
    return client.ReadEndpoint(0xABCDEF,0x987654,0xFEDCBA98,0xFEDCBA9876543210,cfg.size,cfg.count,
                              old.gid_for_ip(cfg.peer_ip),nonce,resources)


class Registers:
    def __init__(self,cfg=CFG,mode='good'):
        self.cfg=cfg;self.mode=mode;self.writes=[];self.bar_reads=set();self.wait=3;self.interrupted=False
        self.values={old.ID:0x524F4332,old.VERSION:0x20000,client.CAPACITY_REG:client.CAPACITY,
            client.RAM_BASE_REG:client.RAM_BASE,old.STATUS:IDLE,client.MODE:0,client.RUN_ID:9,0xC0:11,0xC4:11}

    def check_identity(self):client.PciBar2V2.check_identity(self)

    def read32(self,address):
        if address==old.STATUS and self.values[address]==ACTIVE:
            if self.mode=='interrupt' and not self.interrupted:
                self.interrupted=True;raise KeyboardInterrupt()
            if self.mode not in ('timeout','interrupt','abort_stuck'):
                self.wait-=1
                if self.wait==0:self.finish()
        if address>=client.RAM_BASE:self.bar_reads.add(address)
        value=self.values.get(address,0)
        if self.mode=='readback' and address==0x68:return value^1
        if self.mode=='mode_readback' and address==client.MODE:return value^1
        return value

    def write32(self,address,value):
        self.writes.append((address,value))
        if address==old.COMMAND:
            if value==1:
                self.values[old.STATUS]=ACTIVE;self.values[client.RUN_ID]+=1
            elif value==4 and self.mode!='abort_stuck':
                self.values[old.STATUS]=ERROR;self.values[old.ERROR]=5
            elif value==2:self.values[old.STATUS]=IDLE|(0x80 if self.values.get(client.MODE) else 0)
        else:self.values[address]=value

    def finish(self):
        c=self.cfg;total=c.size*c.count
        nonce=NONCE if self.mode!='stale' else bytes([NONCE[0]^1])+NONCE[1:]
        payload=client.source_data(nonce,c.size,c.count)
        expected,_=client.capture_vectors(c,payload)
        if self.mode!='unwritten':
            for address in range(0,len(expected),4):self.values[client.RAM_BASE+address]=int.from_bytes(expected[address:address+4],'little')
        if self.mode in ('tail_corruption','sentinel_corruption'):
            offset=(c.count-1)*c.stride+c.size-1 if self.mode=='tail_corruption' else c.allocation
            address=client.RAM_BASE+(offset&~3);self.values[address]^=1<<((offset&3)*8)
        self.values.update({old.STATUS:DONE,old.ERROR:0,old.ISSUED:c.count,old.ACKED:c.count,old.TOTAL:total,
            old.ELAPSED:10000,old.READ_COMMANDS:0,old.READ_BYTES:0,0xC0:11+c.count,0xC4:11+c.count,
            client.COMMITTED:c.count,client.CAPTURE_BYTES:total,client.AUTHORIZED:c.count,
            client.PADDING:((-c.size)&3)*c.count,client.CHUNKS:((c.size+4095)//4096)*c.count,
            client.CAPTURE_ERROR:0,client.LEASE:c.allocation,client.CAPTURE_STATE:6})
        faults={'partial_count':(client.COMMITTED,c.count-1),'partial_bytes':(client.CAPTURE_BYTES,total-1),
            'no_authorization':(client.AUTHORIZED,0),'bad_chunks':(client.CHUNKS,0),'bad_padding':(client.PADDING,123),
            'capture_fault':(client.CAPTURE_ERROR,2),'wrong_lease':(client.LEASE,c.allocation+64),
            'pending_capture':(client.CAPTURE_STATE,4),'missing_cpl':(0xC4,11),'tx_fault':(0xAC,1),
            'guard_fault':(0xCC,1<<16),'source_command':(old.READ_COMMANDS,1),'failed':(old.STATUS,ERROR)}
        if self.mode in faults:
            address,value=faults[self.mode];self.values[address]=value


class PeerSocket:
    def __init__(self,registers,packet=None,ready=b'R',verdict=b'P'):
        self.registers=registers;self.incoming=bytearray((packet or endpoint(registers.cfg).encode())+ready+verdict)
        self.sent=[];self.receives=0

    def recv(self,count):
        self.receives+=1;part=bytes(self.incoming[:min(7,count)]);del self.incoming[:len(part)];return part

    def sendall(self,data):
        if data in (b'D',b'A') and not old.safe_terminal(self.registers.values[old.STATUS]):
            raise AssertionError('peer MR release before FPGA quiescence')
        if data==b'D':
            extent=min(client.CAPACITY,self.registers.cfg.allocation+64)
            if self.registers.bar_reads!=set(range(client.RAM_BASE,client.RAM_BASE+extent,4)):
                raise AssertionError('peer MR released before full host BAR readback')
        self.sent.append(bytes(data))


class RWClientTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        built=subprocess.run(['make','-C',str(ROOT / 'rdma/read/host'),'all'],capture_output=True,text=True,timeout=30)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_RW_CLIENT_REPORT'):
            files=[Path(__file__),Path(client.__file__),Path(old.__file__),ROOT / 'rdma/read/host/rc_read_peer.c',
                   ROOT / 'rdma/read/host/Makefile',ROOT / 'rdma/read/build/rc_read_peer']
            report=dict(scope='Native-tool protocol/MMIO models and C/Python oracle, not hardware',
                hardware_verified=False,complete=len(cls.reports)==13,tests=cls.reports,
                source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            with Path(target).open('x') as out:out.write(json.dumps(report,indent=2)+'\n')

    def test_c_python_nonce_payload_exactly_match(self):
        result=subprocess.run([str(ROOT / 'rdma/read/build/rc_read_peer'),'--self-test'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        row=json.loads(result.stdout)
        expected=hashlib.shake_256(NONCE+struct.pack('!II',65,3)).digest(195)
        self.assertEqual(bytes.fromhex(row['payload_hex']),expected)
        self.assertEqual(row['sha256'],hashlib.sha256(expected).hexdigest())
        self.assertTrue(row['pass']);self.assertFalse(row['hardware_access'])
        self.reports[self._testMethodName]=dict(pass_test=True,all_reference_bytes_compared=195,protocol_negative_controls=4)

    def test_full_width_read_and_all_bar_bytes_compared(self):
        rows=[]
        for size,count in ((1,3),(65,3),(4097,3),(65536,4)):
            cfg=dataclasses.replace(CFG,size=size,count=count)
            registers=Registers(cfg);peer=PeerSocket(registers)
            result=client.run_read(registers,cfg,peer)
            self.assertTrue(result['success'] and result['host_bar_verified'] and result['source_verified_unchanged'])
            self.assertFalse(result['source_payload_transferred_over_tcp'])
            self.assertEqual(result['payload_bytes_compared'],size*count)
            self.assertEqual(result['mismatches'],0);self.assertEqual(peer.sent[1:],[b'R',b'D'])
            self.assertEqual(len(peer.sent[0]),256)
            self.assertEqual(registers.values[0x70],0x76543210);self.assertEqual(registers.values[0x74],0xFEDCBA98)
            rows.append(dict(size=size,count=count,payload_bytes=size*count,bar_bytes=result['bar_bytes_compared']))
        self.reports[self._testMethodName]=dict(pass_test=True,cases=rows)

    def test_endpoint_malformed_or_mismatched_rejected_before_mmio_writes(self):
        packet=endpoint().encode();line=packet.split(b'\0')[0]
        mutations=[(b'AS02RD2',b'AS02RC1'),(b'abcdef',b'1000000'),(b'abcdef',b'-1'),
            (b'987654',b'1000000'),(b'fedcba98 ',b'1fedcba98 '),
            (b'fedcba9876543210',b'ffffffffffffff80'),(b'65 3 ',b'64 3 '),(b'65 3 ',b'65 +3 '),
            (b'c6120a01',b'c6120a03'),(NONCE.hex().encode(),b'a'*63),(b' 1\n',b' 0\n'),(b' 1\n',b' 33\n')]
        variants=[line.replace(a,b).ljust(256,b'\0') for a,b in mutations]
        variants += [packet[:-1]+b'X',b'x'*256,packet[:-1]]
        for bad in variants:
            registers=Registers();peer=PeerSocket(registers,packet=bad)
            with self.subTest(packet=bad[:40]),self.assertRaises(client.ClientError):client.run_read(registers,CFG,peer)
            self.assertEqual(registers.writes,[])
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=len(variants))

    def test_config_bounds_and_peer_read_resource_limit(self):
        invalid=[dict(size=0),dict(size=65537),dict(count=0),dict(count=4097),dict(size=65536,count=5),
            dict(size=1,count=4097),dict(local_qpn=8),dict(local_qpn=1),dict(local_psn=1<<24),
            dict(read_window=0),dict(read_window=33),dict(host_timeout_seconds=0),dict(local_mac=0)]
        for values in invalid:
            with self.subTest(values=values),self.assertRaises(client.ClientError):dataclasses.replace(CFG,**values).validate()
        cfg=dataclasses.replace(CFG,read_window=2);registers=Registers(cfg);peer=PeerSocket(registers)
        with self.assertRaises(client.ClientError):client.run_read(registers,cfg,peer)
        self.assertEqual(registers.writes,[])
        self.reports[self._testMethodName]=dict(pass_test=True,rejected_configurations=len(invalid),peer_resource_limit_checked=True)

    def test_completion_does_not_replace_real_ram_commit_counters(self):
        modes=['partial_count','partial_bytes','no_authorization','bad_chunks','bad_padding','capture_fault',
            'wrong_lease','pending_capture','missing_cpl','tx_fault','guard_fault','source_command','failed']
        for mode in modes:
            registers=Registers(mode=mode);peer=PeerSocket(registers)
            with self.subTest(mode=mode),self.assertRaises(client.ClientError) as caught:client.run_read(registers,CFG,peer)
            self.assertFalse(caught.exception.evidence['success']);self.assertNotIn(b'D',peer.sent)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=len(modes))

    def test_unwritten_stale_tail_and_sentinel_corruption_rejected(self):
        modes=['unwritten','stale','tail_corruption','sentinel_corruption']
        for mode in modes:
            registers=Registers(mode=mode);peer=PeerSocket(registers)
            with self.subTest(mode=mode),self.assertRaises(client.ClientError) as caught:client.run_read(registers,CFG,peer)
            evidence=caught.exception.evidence
            self.assertGreater(evidence['mismatches'],0);self.assertEqual(evidence['bar_bytes_compared'],448)
            self.assertNotIn(b'D',peer.sent);self.assertIn(b'A',peer.sent)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=4,all_bar_bytes_compared_on_failure=True)

    def test_timeout_and_interrupt_abort_before_source_release(self):
        for mode in ('timeout','interrupt'):
            registers=Registers(mode=mode);peer=PeerSocket(registers)
            with self.subTest(mode=mode),self.assertRaises(client.ClientError) as caught:client.run_read(registers,CFG,peer)
            self.assertTrue(caught.exception.evidence['tx_quiescence_verified'])
            self.assertIn((old.COMMAND,4),registers.writes);self.assertEqual(peer.sent[-1],b'A');self.assertNotIn(b'D',peer.sent)
        self.reports[self._testMethodName]=dict(pass_test=True,aborts=2)

    def test_unproven_abort_never_claims_or_requests_mr_release(self):
        registers=Registers(mode='abort_stuck');peer=PeerSocket(registers)
        with mock.patch.object(old,'abort_owned',return_value=False),self.assertRaises(client.ClientError) as caught:
            client.run_read(registers,CFG,peer)
        self.assertFalse(caught.exception.evidence['tx_quiescence_verified'])
        self.assertNotIn(b'A',peer.sent);self.assertNotIn(b'D',peer.sent)
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_unknown_version_or_existing_owner_refused_without_mutation(self):
        for key,value in ((old.VERSION,0x10000),(old.ID,0),(client.CAPACITY_REG,65536),(old.STATUS,ACTIVE)):
            registers=Registers();registers.values[key]=value;peer=PeerSocket(registers)
            with self.subTest(key=key),self.assertRaises(client.ClientError):client.run_read(registers,CFG,peer)
            self.assertEqual(registers.writes,[]);self.assertEqual(peer.receives,0)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=4)

    def test_configuration_readback_failure_cannot_start(self):
        for mode in ('readback','mode_readback'):
            registers=Registers(mode=mode);peer=PeerSocket(registers)
            with self.subTest(mode=mode),self.assertRaises(client.ClientError):client.run_read(registers,CFG,peer)
            self.assertNotIn((old.COMMAND,1),registers.writes);self.assertNotIn(b'R',peer.sent)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=2)

    def test_memory_mapping_bounds_and_old_client_version_refusal(self):
        registers=client.PciBar2V2.__new__(client.PciBar2V2);registers.mapping=bytearray(client.MMIO_BYTES)
        for address,value in ((old.ID,0x524F4332),(old.VERSION,0x20000),(client.CAPACITY_REG,client.CAPACITY),
                              (client.RAM_BASE_REG,client.RAM_BASE)):
            struct.pack_into('<I',registers.mapping,address,value)
        registers.check_identity();registers.write32(client.MMIO_BYTES-4,0xDEADBEEF)
        self.assertEqual(registers.read32(client.MMIO_BYTES-4),0xDEADBEEF)
        for address in (-4,1,client.MMIO_BYTES):
            with self.subTest(address=address),self.assertRaises(client.ClientError):registers.read32(address)
            with self.assertRaises(client.ClientError):registers.write32(address,0)
        with self.assertRaises(client.ClientError):old.PciBar2.check_identity(registers)
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_peer_readiness_or_source_verdict_cannot_be_skipped(self):
        registers=Registers();peer=PeerSocket(registers,ready=b'F')
        with self.assertRaises(client.ClientError):client.run_read(registers,CFG,peer)
        self.assertEqual(registers.writes,[])
        registers=Registers();peer=PeerSocket(registers,verdict=b'F')
        with self.assertRaises(client.ClientError) as caught:client.run_read(registers,CFG,peer)
        self.assertTrue(caught.exception.evidence['host_bar_verified']);self.assertFalse(caught.exception.evidence['success'])
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_live_native_peer_requires_explicit_authorization(self):
        command=[str(ROOT / 'rdma/read/build/rc_read_peer'),'mlx5_0','3','198.18.10.1','65','3','18516','0xfffffe']
        result=subprocess.run(command,env={},capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,2);self.assertIn('authorization required',result.stderr)
        self.reports[self._testMethodName]=dict(pass_test=True)


if __name__=='__main__':unittest.main()
