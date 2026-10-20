# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C WQE + SQ-result bridge + original frontend + ONE actual MR table.

SQ-result/queue context is an EXPLICIT source model here, not DMA evidence.
Work handoff is not execution/CQ completion or a downstream lease release.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_wqe_admission_rtl as original

ROOT=original.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_sq_wqe_admission.v'


def bench(body):
    tb=original.TB
    start=tb.index('rocev2_wqe_admission dut(');end=tb.index(');',start)+2
    ports=re.findall(r'\.(\w+)\(([^()]*)\)',tb[start:end])
    # Request/response expressions with parentheses are simple boolean gates
    # in this fixture; assert exact port preservation before substitution.
    mapping=dict(ports)
    for name in list(mapping):
        if name.startswith(('s_wqe_','s_context_')):del mapping[name]
    mapping.update(s_fetch_data='wd',s_fetch_error='fe',s_fetch_qpn='cq',s_fetch_pd='cp',
        s_fetch_epoch='ce',s_fetch_sequence='cs',s_fetch_tag='ct',s_fetch_valid='wv',s_fetch_ready='wr',
        m_work_error_source='error_source',m_work_fetch_error='fetch_error',
        m_work_descriptor_available='descriptor_available',queue_guard='queue_guard')
    # Full source expressions, including the original deliberate response
    # corruption, are preserved; no table replacement or response success tie.
    instance='rocev2_sq_wqe_admission dut('+','.join(f'.{n}({v})'for n,v in mapping.items())+');'
    tb=tb[:start]+'''reg [7:0] fe=0;
wire [1:0] error_source;wire [7:0] fetch_error;wire descriptor_available;
wire [7:0] queue_guard;
'''+instance+tb[end:]
    # Correct width and all original packet fields/owner checks are retained.
    extra=r'''
always @(posedge clk)if(!rst && ov)begin
 if(error_source==1 && (authorized || descriptor_available || oid || oe!==fetch_error ||
  oop || oflags || olen || olk || ola || ooff || ora || ork))$fatal(1,"failed fetch leaked old successful authority");
 if(!descriptor_available && oid!==0)$fatal(1,"unavailable WR_ID invented identity");
 if(error_source!=1 && fetch_error!==0)$fatal(1,"admission fabricated a fetch error");
 if(!queue_guard[oq] || queue_guard!==(8'b1<<oq))$fatal(1,"work lost full-QP owner");
end
task failed_fetch;
 input [7:0] code;
 integer start_queries,start_results,deadline;
 reg [575:0] expected;
 begin
  @(negedge clk);enable=0;cfg_idle=0;fe=code;wd={512{1'bx}};
  cq=1;cp=7;ct=16'hffff;cs=64'hf123456700000001;ce=64'h9123456700000001;wv=1;ready=0;
  start_queries=queries;start_results=results;deadline=cycle+100;
  #1;if(!wr || !guard || queue_guard!==8'b10)$fatal(1,"failed fetch could not progress behind management/disable");
  @(posedge clk);@(negedge clk);wv=0;fe=0;wd=0;cq=0;cp=0;ct=0;cs=0;ce=0;
  while(!ov)begin if(cycle>deadline)$fatal(1,"failed fetch result deadline");@(negedge clk);end
  expected={64'd0,64'hf123456700000001,64'h9123456700000001,24'd1,16'd7,16'hffff,
    16'd0,16'd0,32'd0,32'd0,64'd0,64'd0,64'd0,32'd0,code};
  if(output_fields!==expected || error_source!==1 || fetch_error!==code || descriptor_available || authorized ||
   !busy || !guard || cfg_ready || queries!=start_queries)$fatal(1,"failed DMA status/context was replaced by parse/MR authority");
  repeat(9)begin @(negedge clk);
   if(!ov || output_fields!==expected || error_source!==1 || fetch_error!==code || !guard || cfg_ready)$fatal(1,"held DMA failure lost owner");
  end
  ready=1;@(posedge clk);@(negedge clk);ready=0;repeat(2)@(negedge clk);
  if(busy || guard || queue_guard || results!=start_results+1 || queries!=start_queries)$fatal(1,"failed fetch handoff/query count");
  enable=1;cfg_idle=1;checked=checked+1;
 end
endtask
'''
    tb=tb.replace('initial begin\n repeat(4)',extra+'\ninitial begin\n repeat(4)',1)
    return tb.replace('// BODY',body)


class SQWQEAdmissionRTLTests(unittest.TestCase):
    reports={}
    entry=original.WQEAdmissionRTLTests.entry

    @classmethod
    def setUpClass(cls):original.WQEAdmissionRTLTests.setUpClass.__func__(cls)

    def test_actual_C_full_namespace_context_and_capacity(self):
        c=original.codec
        cases=[self.entry(),self.entry(c.candidate(local_address=original.BASE+1,opcode=2)),
            self.entry(c.candidate(local_address=original.BASE+1,local_key=0),error=1),
            self.entry(c.candidate(local_address=original.BASE+1,local_key=original.KEY^0x80000000),error=1),
            self.entry(context=(1,8,0xf123,original.SEQ,original.EPOCH),error=2),
            self.entry(c.candidate(local_address=original.BASE+1,local_key=original.KEY+1,opcode=2),error=3),
            self.entry(c.candidate(local_address=original.BASE-1),error=4),
            self.entry(c.candidate(local_address=(original.BASE+1)&((1<<48)-1)),error=4),
            self.entry(c.candidate(local_address=original.BASE+8191),error=4),
            self.entry(context=(7,7,0xffff,original.SEQ,original.EPOCH),stalls=(3,4,7),disable=1),
            'cfg_pd=0;manage(1,3,0,64\'hf123456789abc000,8192,1,32\'h8000000b);',
            self.entry(c.candidate(local_address=original.BASE+1,local_key=original.KEY+3),
                context=(0,0,0xf123,original.SEQ,original.EPOCH))]
        self.simulate('\n'.join(cases))

    def test_all_known_DMA_errors_preserve_status_not_stale_success_authority(self):
        self.simulate(self.entry()+'\n'+'\n'.join(f'failed_fetch(8\'d{n});'for n in range(1,16)))

    def test_pending_raw_fetched_record_does_not_deadlock_MR_management(self):
        entry=self.entry(error=1)
        record=re.search(r"issue\((512'h[0-9a-f]+)",entry)[1]
        body=f'''
@(negedge clk);enable=1;cfg_idle=0;wd={record};wv=1;
repeat(9)begin @(negedge clk);if(wr || guard || busy || !cfg_ready || queue_guard)$fatal(1,"raw SQ result falsely acquired MR lease");end
// While the upstream ring still owns this raw result, MR management completes
// first. The stale descriptor must later be denied by the REAL table.
manage(2,0,32'h80000008,0,0,0,0);
@(posedge clk);while(!wr)@(posedge clk);
@(negedge clk);wv=0;wd=0;
while(!ov)@(negedge clk);
if(oe!==1 || authorized || error_source!==2 || fetch_error || !descriptor_available ||
 ola || olk || olen || !guard || cfg_ready || queue_guard!==8'b10)$fatal(1,"stale fetched record bypassed MR revoke");
ready=1;@(posedge clk);@(negedge clk);ready=0;repeat(2)@(negedge clk);
if(busy || guard || queue_guard || results!=1 || queries!=1)$fatal(1,"raw-result/MR ownership did not hand off");
checked=checked+1;
'''
        self.simulate(body)

    def test_unknown_descriptor_bytes_including_remote_key_and_WR_ID_never_query_MR(self):
        entry=self.entry(error=0x20,queries=0)
        original_record=re.search(r"512'h([0-9a-f]{128})",entry)[1]
        expected=re.search(r"576'h([0-9a-f]{144})",entry)[1]
        # Unknown bytes cannot supply a trustworthy WR_ID, even when the
        # unknown bit is elsewhere; queue/sequence shadow identity remains.
        denied=f'{int(expected,16)&((1<<512)-1):0144x}'
        for index in [127,47,31,95,15]:
            with self.subTest(hex_index=index):
                data=original_record[:index]+'x'+original_record[index+1:]
                self.simulate(entry.replace(original_record,data).replace(expected,denied))

    def test_invalid_or_unknown_trusted_context_faults_without_alias_or_completion(self):
        for mutation in ["cq=8;","cq=24'h800001;","ce=0;","cs=0;","ct=0;","cp=16'hxxx7;","fe=8'hx0;","fe=8'h80;"]:
            with self.subTest(mutation=mutation):
                self.simulate('''
@(negedge clk);enable=1;cfg_idle=1;wv=1;
'''+mutation+'''
@(posedge clk);@(negedge clk);
repeat(9)@(negedge clk);
if(!fault || fault_code!==8'h51 || !busy || !guard || queue_guard!==8'hff || wr || ov ||
 cfg_ready || queries || results)$fatal(1,"invalid trusted SQ source aliased owner or fabricated result");
checked=checked+1;
''')

    def simulate(self,body):
        tb=bench(body);self.assertNotIn('force ',tb)
        paths=[RTL,original.RTL/'rocev2_wqe_admission.v',original.RTL/'rocev2_mr_table.v',
            Path(__file__).resolve(),Path(original.__file__).resolve(),Path(original.codec.__file__).resolve(),
            original.KERNEL/'wqe.c',original.KERNEL/'wqe.h']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-sq-wqe-admission-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),
                *map(str,paths[:3])],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            m=re.search(r'WQE_ADMISSION_PASS checked=(\d+) queries=(\d+) results=(\d+) fault=(\d+) cycles=(\d+)',r.stdout)
            self.assertIsNotNone(m,r.stdout)
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(
            summary=dict(zip(['checked','queries','results','fault','cycles'],map(int,m.groups()))),
            source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_SQ_ADMISSION_UNIT_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            result=dict(scope=__doc__,pass_test=len(cls.reports)==5,methods=len(cls.reports),
                simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                actual_C_UBSan=True,actual_MR_table=True,SQ_result_source_model=True,
                actual_SQ_DMA_or_native_execution=False,hardware_verified=False,completion_claim=False)
            with p.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':unittest.main()
