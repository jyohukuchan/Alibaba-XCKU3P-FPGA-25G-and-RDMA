# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual parser/MR/ICRC gates with BTH MigReq0/1; EXPLICIT HLS/backend MODELS.

MigReq is not TVer/reserved and cannot reconfigure a trusted peer or MR. No
actual HLS wire, path migration, native DMA/CQ/runtime claim by these units.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_protected_responder_rtl as protected

ROOT=protected.ROOT
probe=protected.probe


def fixture(kind):
    words=[];body=[];cases=[];psn=probe.PSN
    def add(name,op='write',mig=1,error=0,key=8,address=probe.VA+0x210,flags=0,change=None,bad_icrc=False):
        nonlocal psn
        args=dict(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
            source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
            destination_qpn=2,psn=psn,remote_address=address,rkey=key)
        frame=probe.rocev2_wire.write_only_frame(**args,payload=probe.PAYLOAD)if op=='write'else probe.read_wire.encode(**args,opcode=probe.read_wire.REQUEST,read_bytes=65)
        packet=bytearray(frame[14:]);packet[29]=(packet[29]&0x30)|(mig<<6)|flags
        if change:
            pos,value=change;packet[pos:pos+len(value)]=value
        packet[10:12]=b'\0\0';packet[10:12]=probe.rocev2_wire.internet_checksum(packet[:20]).to_bytes(2,'big')
        packet[-4:]=probe.rocev2_wire.icrc_ipv4(packet)
        if bad_icrc:packet[-1]^=0x40
        start=len(words);parts=probe.words(bytes(packet));words.extend(parts)
        body.append(f'$display("MIGREQ_CASE {name}");send_frame({start},{len(parts)});')
        if bad_icrc:
            body.append('''repeat(300)@(negedge clk);
if(rxbad!=1 || commands!=command_before || txframes!=tx_before || completed!=completed_before || rejected!=rejected_before || !quiet)$fatal(1,"M1invalid ICRC gained authority");''')
        elif error:body.append(f"deny(8'd{error});")
        else:body.append('allow();');psn=(psn+1)&0xffffff
        cases.append(dict(name=name,operation=op,MigReq=mig,flags=f'{packet[29]:02x}',expected_error=error,
            expected_integrity_drop=bad_icrc,psn=int.from_bytes(packet[37:40],'big'),address=f'0x{address:016x}',key=key))
    if kind=='version':
        for mig in [0,1]:
            for bit in [1,2,4,8,0x80]:add(f'M{mig}_bad_flag{bit:x}',mig=mig,flags=bit,error=16)
    elif kind=='protection':
        add('M1bad_key',key=0x80000008,error=1)
        add('M1bad_PD',key=9,error=2)
        add('M1bad_access',key=10,error=3)
        add('M1below_MR',address=probe.VA-1,error=4)
        add('M1bad_peer_QP',change=(33,(3).to_bytes(3,'big')),error=17)
        add('M1bad_peer_IP',change=(12,bytes([198,18,11,3])),error=17)
        add('M1bad_PSN',change=(37,((psn+1)&0xffffff).to_bytes(3,'big')),error=18)
        add('M1bad_PKey',change=(30,b'\0\0'),error=16)
        add('M1bad_ICRC',bad_icrc=True)
    if kind=='positive':
        add('M0WRITE',mig=0);add('M1READ',op='read');add('M1WRITE');add('M0READ',op='read',mig=0)
    else:add('M1WRITE');add('M1READ',op='read')
    tb=probe.TB.replace('STIMULUS_LAST',str(len(words)-1)).replace('// TEST_BODY','\n'.join(body))
    return tb,words,cases


class BTHMigReqTests(unittest.TestCase):
    reports={}

    def simulate(self,kind):
        tb,words,cases=fixture(kind);axis=ROOT/'external/corundum/fpga/lib/axis/rtl'
        sources=[ROOT/'rdma/rnic/rtl'/n for n in ['rocev2_protected_responder.v','rocev2_mr_table.v']]
        sources += [ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v',axis/'axis_register.v',axis/'axis_fifo.v']
        paths=sources+[Path(__file__).resolve(),Path(protected.__file__).resolve(),Path(probe.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/read/host/read_wire.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-bth-migreq-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),*map(str,sources)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[7:])for l in r.stdout.splitlines()if l.startswith('RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual(rows[0]['completed'],4 if kind=='positive'else 2)
            self.assertEqual(rows[0]['rejected'],10 if kind=='version'else 8 if kind=='protection'else 0)
            self.assertEqual(rows[0]['rx_bad'],int(kind=='protection'))
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],cases=cases,source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest())

    def test_MigReq_clear_set_READ_WRITE_remain_subject_to_actual_MR(self):self.simulate('positive')
    def test_TVers_and_current_SE_policy_rejections_preserved_for_both_M_values(self):self.simulate('version')
    def test_MigReq_never_bypasses_ICRC_peer_QP_PSN_PD_key_permissions_PKey_range(self):self.simulate('protection')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_BTH_MIGREQ_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==3,methods=len(cls.reports),tests=cls.reports,
                actual_parser_MR_integrity=True,HLS_backend_models=True,path_migration_implemented=False,
                hardware_verified=False,completion_claim=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
