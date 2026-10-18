#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""READ-response ingress guards, host coexistence, and queued-run isolation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / 'rdma/tests'))
sys.path.insert(0,str(ROOT / 'rdma/read/host'))
import test_ethernet_rtl as legacy
import read_wire

RTL=ROOT / 'rdma/read/rtl/rocev2_rw_ethernet_rx.v'
TB=legacy.RX_TB.replace('reg enable=0;','reg enable=0,read_mode=0;reg [31:0] run_id=0;wire [31:0] stales;')
TB=TB.replace('rocev2_ethernet_rx dut (','rocev2_rw_ethernet_rx dut (')
TB=TB.replace('.enable(enable),','.enable(enable),.read_mode(read_mode),.run_id(run_id),')
TB=TB.replace('.overflow_count(overflows))','.overflow_count(overflows),.stale_frame_count(stales))')
TB=TB.replace('reg [266:0] inputs','reg [299:0] inputs')
TB=TB.replace('{qpn,enable,su,sl,sk,sd}=inputs[index]','{run_id,read_mode,qpn,enable,su,sl,sk,sd}=inputs[index]')
TB=TB.replace('if(quiet==50) begin','if(quiet==50) begin\n  if(stales!=STALE_FRAMES) $fatal(1,"stale frame count differs");')


class RWIngressRTLTests(unittest.TestCase):
    reports={}

    def simulate(self,vectors,expected_stale=0):
        inputs,hosts,roces=[],[],[]
        counts=dict(HOST_FRAMES=0,ROCE_FRAMES=0,DROP_FRAMES=0,OVERFLOW_FRAMES=0,STALE_FRAMES=expected_stale)
        for frame,route,options in vectors:
            packed=legacy.pack_words(frame,options.get('user',0),options.get('error'),options.get('hole'))
            for index,value in enumerate(packed):
                change=options.get('change_midframe',False) and index>0
                enable=options.get('enabled',True) and not change
                qpn=7 if change else options.get('qpn',2)
                mode=options.get('read_mode',True) and not change
                epoch=options.get('run_id',1)
                inputs.append(value | int(enable)<<242 | qpn<<243 | int(mode)<<267 | epoch<<268)
            counts[('ROCE' if route=='STALE' else route)+'_FRAMES']+=1
            if route=='HOST':hosts.extend(packed)
            elif route=='ROCE':roces.extend(legacy.pack_words(frame[14:]))
            if len(packed)>1024:counts['OVERFLOW_FRAMES']+=1
        constants=dict(N_INPUT=len(inputs),N_HOST=len(hosts),N_ROCE=len(roces),**counts)
        tb=TB
        for name,value in sorted(constants.items(),key=lambda item:-len(item[0])):tb=tb.replace(name,str(value))
        with tempfile.TemporaryDirectory(prefix='as02-rw-ingress-') as directory:
            path=Path(directory)
            (path / 'tb.v').write_text(tb)
            for name,values in [('inputs',inputs),('host',hosts),('roce',roces)]:
                (path / (name+'.hex')).write_text(''.join(f'{v:x}\n' for v in values))
            sources=[RTL,ROOT / 'external/corundum/fpga/lib/eth/rtl/eth_axis_rx.v',
                     ROOT / 'external/corundum/fpga/lib/axis/rtl/axis_fifo.v']
            compiled=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path / 'test.vvp'),
                                     str(path / 'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=30)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            sim=subprocess.run(['vvp',str(path / 'test.vvp')],cwd=path,capture_output=True,text=True,timeout=60)
            self.assertEqual(sim.returncode,0,sim.stdout+sim.stderr)
            rows=[json.loads(line[7:]) for line in sim.stdout.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(len(rows),1,sim.stdout)
            self.reports[self._testMethodName]=dict(rows[0],pass_test=True,stale_frames=expected_stale,
                icrc_validation='downstream integrity block; classifier test only')

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_RW_INGRESS_REPORT'):
            deps=[RTL,Path(__file__),Path(legacy.__file__),Path(read_wire.__file__)]
            report=dict(scope='RW Ethernet classifier/framer RTL, not ICRC validation, HLS or hardware',
                        hardware_verified=False,complete=len(cls.reports)==2,tests=cls.reports,
                        source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in deps})
            with Path(target).open('x') as out:out.write(json.dumps(report,indent=2)+'\n')

    @staticmethod
    def responses(size):
        return read_wire.responses(bytes((i*179 ^ i>>7 ^ 0xD3)&255 for i in range(size)),
            initial_psn=0xFFFFFE,source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=2)

    def test_read_opcodes_mode_snapshot_peer_guards_and_host_preservation(self):
        vectors=[]
        for i in range(50):
            frame=bytes(range(12))+b'\x08\x06'+bytes([i])*46
            vectors.append((frame,'HOST',dict(user=(0x123456780000000000000000+i)<<1,error=1 if i%4==0 else None)))
        frames=self.responses(65)+self.responses(8193)
        for frame in frames:
            vectors.append((frame,'ROCE',dict(change_midframe=True)))
            vectors.append((frame,'DROP',dict(read_mode=False)))
        for mode in (False,True):vectors.append((legacy.ack(),'ROCE',dict(read_mode=mode)))
        good=frames[0]
        for offset in (0,6,26,30,47,48,49):
            changed=bytearray(good);changed[offset]^=1
            vectors.append((bytes(changed),'DROP',{}));vectors.append((good,'ROCE',{}))
        for opcode in (0x00,0x02,0x06,0x0A,0x0C):
            changed=bytearray(good);changed[42]=opcode
            vectors.append((bytes(changed),'DROP',{}))
        for error,hole in ((0,None),(3,None),(None,1),(None,3)):
            vectors.append((good,'DROP',dict(error=error,hole=hole)))
        vectors.append((good[:48],'DROP',{}))
        vectors.append((good,'HOST',dict(enabled=False,user=0x123456789<<1)))
        changed=bytearray(good);changed[37]=1;vectors.append((bytes(changed),'HOST',{}))
        for length in (9215,16400):
            vectors.append((good.ljust(length,b'\0'),'DROP',{}));vectors.append((good,'ROCE',{}))
        self.simulate(vectors)

    def test_old_run_response_behind_stalled_host_is_discarded(self):
        host=bytes(range(12))+b'\x08\x06'+bytes(range(46))
        good=self.responses(65)[0]
        # Epoch2 is visible while the first host frame blocks epoch1's
        # queued response. Only that old response is discarded, not host data.
        vectors=[(host,'HOST',dict(run_id=1)),(good,'STALE',dict(run_id=1))]
        vectors += [(host,'HOST',dict(run_id=2,user=(i+1)<<1)) for i in range(50)]
        vectors.append((good,'ROCE',dict(run_id=2)))
        self.simulate(vectors,expected_stale=1)


if __name__=='__main__':unittest.main()
