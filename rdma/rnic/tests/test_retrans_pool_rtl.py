# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual2000-slot lease RAM/ring RTL, not FNS/native/core/CQ integration.

Local-reset retention is NOT FPGA reconfiguration/power-loss recovery.
Known-signal SYNTHESIS-defined simulations are NOT physical synthesis/signoff.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[3]
NAMES=['full_2000_exhaust_release_reuse','owned_leases_survive_local_reset',
 'unconsumed_offer_survives_reset','duplicate_release_fault_retained',
 'full_owner_mismatch','stale_generation_after_full_pool_reuse','full_index_range',
 'full_QPN_no_alias','both_markers_and_later_work','high64_marker_mismatch',
 'X_Z_diagnostics','generation_nonwrap']
SYN_CASES=[0,1,5,11]
EXPECTED={f'case_{n:02d}_{NAMES[n]}'for n in range(12)}|{f'synth_case_{n:02d}_{NAMES[n]}'for n in SYN_CASES}

@unittest.skipUnless(shutil.which('iverilog')and shutil.which('vvp'),'Icarus required')
class ReTxPoolTests(unittest.TestCase):
    results={}
    @classmethod
    def setUpClass(cls):
        (ROOT/'rdma/rnic/build').mkdir(exist_ok=True)
        cls.directory=Path(tempfile.mkdtemp(prefix='retrans-pool-',dir=ROOT/'rdma/rnic/build'))
        cls.inputs=cls.directory/'inputs';cls.inputs.mkdir()
        cls.files=[ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',ROOT/'rdma/rnic/tests/retrans_pool_tb.v',Path(__file__).resolve()]
        cls.source={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in cls.files}
        for f in cls.files:shutil.copy2(f,cls.inputs/f.name)
        cls.frozen={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in cls.inputs.iterdir()}
        cls.binaries={}
        try:
            for synth in [False,True]:
                for boundary in [False,True]:
                    key=('synth'if synth else'fourstate')+('-nearmax'if boundary else'')
                    binary=cls.directory/(key+'.vvp')
                    cmd=['iverilog','-g2012','-s','tb','-o',str(binary)]
                    if synth:cmd+=['-DSYNTHESIS']
                    if boundary:cmd+=["-Ptb.GENSTART=64'hfffffffffffffffe"]
                    cmd+=[str(cls.inputs/'rocev2_retrans_pool.v'),str(cls.inputs/'retrans_pool_tb.v')]
                    c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
                    (cls.directory/(key+'-compile.log')).write_text(c.stdout+c.stderr)
                    if c.returncode:raise RuntimeError('pool compile failed: '+key)
                    cls.binaries[synth,boundary]=binary
        except Exception as e:
            cls.write_report([str(e)]);raise

    def run_case(self,number,synth=False):
        key=('synth_'if synth else'')+f'case_{number:02d}_{NAMES[number]}'
        start=time.monotonic()
        s=subprocess.run(['vvp',str(self.binaries[synth,number==11]),'+CASE='+str(number)],capture_output=True,text=True,timeout=20)
        elapsed=time.monotonic()-start
        (self.directory/(key+'.log')).write_text(s.stdout+s.stderr)
        self.assertEqual(s.returncode,0,key+'; retain '+str(self.directory)+'\n'+s.stdout+s.stderr)
        rows=[json.loads(l[len('POOL_RTL '):])for l in s.stdout.splitlines()if l.startswith('POOL_RTL ')]
        self.assertEqual(len(rows),1);r=rows[0]
        self.assertTrue(r['pass_test']);self.assertEqual(r['case'],number);self.assertEqual(r['capacity'],2000)
        self.assertFalse(r['actual_FNS_process_integrated']);self.assertFalse(r['whole_core_drain'])
        if number==0:
            self.assertEqual(r['allocations'],2002);self.assertEqual(r['releases'],2002)
        self.results[key]=dict(summary=r,simulation_seconds=elapsed,SYNTHESIS_defined=synth,pass_test=True)

    @classmethod
    def write_report(cls,errors):
        current={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in cls.files}
        frozen={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in cls.inputs.iterdir()}
        if current!=cls.source:errors.append('current sources changed during test')
        if frozen!=cls.frozen:errors.append('frozen sources changed during test')
        record=dict(scope=__doc__,pass_test=not errors and set(cls.results)==EXPECTED,
            terminal_exit_status=0 if not errors and set(cls.results)==EXPECTED else 1,
            retained_directory=str(cls.directory.relative_to(ROOT)),source_sha256=cls.source,
            frozen_source_sha256=cls.frozen,expected_cases=sorted(EXPECTED),completed_cases=sorted(cls.results),
            cases=cls.results,errors=errors,actual_production_RTL=True,four_state_simulation=True,
            capacity=2000,clock_period_ns=4.0,actual_FNS_process_integrated=False,whole_core_drain=False,
            native_or_CQ_or_hardware_verified=False,physical_signoff=False,
            reset_retention_not_reconfiguration_powerloss_recovery=True,
            artifact_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in cls.directory.rglob('*')if f.is_file()})
        if name:=os.environ.get('AS02_RNIC_POOL_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            with p.open('x')as out:out.write(json.dumps(record,indent=2)+'\n')
        return record

    @classmethod
    def tearDownClass(cls):
        errors=[]
        if set(cls.results)!=EXPECTED:errors.append('missing/extra expected cases')
        for n in SYN_CASES:
            a=f'case_{n:02d}_{NAMES[n]}';b='synth_'+a
            if a in cls.results and b in cls.results and cls.results[a]['summary']!=cls.results[b]['summary']:
                errors.append('SYNTHESIS known-signal mismatch: '+a)
        r=cls.write_report(errors)
        if not r['pass_test']:raise AssertionError('pool batch incomplete/failed; retain '+str(cls.directory))

def make_test(number,synth):
    def test(self):self.run_case(number,synth)
    return test
for n in range(12):setattr(ReTxPoolTests,f'test_case_{n:02d}_{NAMES[n]}',make_test(n,False))
for n in SYN_CASES:setattr(ReTxPoolTests,f'test_synth_case_{n:02d}_{NAMES[n]}',make_test(n,True))
if __name__=='__main__':unittest.main()
