#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compare actual frozen old/new C++ extent consumers, not timing proof.

Include contiguous short nonterminal beats, all65536 low16 KEEP patterns,
every receive length1..4096/final pad, single-bit holes and request edge
cases. Compare actual accept/reject AND copied-byte side effect. This is a
finite semantic regression, not a formal proof or native/physical result.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
CPP='hls/ib_transport_protocol/ib_transport_protocol.cpp'
HPP='hls/ib_transport_protocol/ib_transport_protocol.hpp'
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def helper(t,name):
    anchor='template<int WIDTH> bool as02_read_payload_extent('
    a=t.index(anchor);b=t.index('{',a);depth=1;i=b+1
    while depth:
        if t[i]=='{':depth+=1
        elif t[i]=='}':depth-=1
        i+=1
    return t[a:i].replace('as02_read_payload_extent(',name+'(',1)


BENCH=r'''
static unsigned checked=0;
static pkgShift receive(unsigned length) {
 pkgShift s(SHIFT_NONE,2);s.receive_owned=true;auto& p=s.receive;auto& n=p.owner.context;
 n=0;n(587,524)=0xf123456789abc001ULL;n(523,460)=1;n(459,396)=0x9123456700000001ULL;
 n(395,372)=2;n(371,356)=17;n(355,340)=1;n(339,324)=4;n(323,308)=1;n(307,276)=1048576;
 n(275,244)=8;n(243,180)=0xfedcba9876543210ULL;n(179,116)=1;n(19,0)=3;
 p.owner.length=length;p.owner.psn=0xfffffe;p.flags=17;p.immediate=0x89abcdef;return s;
}
static void compare(pkgShift s,net_axis<512> w,unsigned before) {
 ap_uint<32> a=before,b=before;bool old=baseline_extent<512>(s,w,a),now=candidate_extent<512>(s,w,b);checked++;
 if(old!=now || a!=b) {
  std::cout<<"EXTENT_COUNTEREXAMPLE {\"case\":"<<checked<<",\"keep_hex\":\""<<w.keep.to_string(16)
   <<"\",\"last\":"<<unsigned(w.last)<<",\"before\":"<<before<<",\"length\":"<<unsigned(s.receive.owner.length)
   <<",\"baseline_accept\":"<<old<<",\"candidate_accept\":"<<now<<",\"baseline_copied\":"<<unsigned(a)
   <<",\"candidate_copied\":"<<unsigned(b)<<"}"<<std::endl;std::exit(1);
 }
}
static ap_uint<64> prefix(unsigned n){return (ap_uint<65>(1)<<n)-1;}
int main() {
 net_axis<512> w;w.data=0;w.keep=1;w.last=0;
 compare(receive(65),w,0); // A short contiguous NONFINAL beat is legal in the old consumer.
 for(unsigned mask=0;mask<65536;mask++){w.keep=mask;compare(receive(65),w,0);}
 for(unsigned length=1;length<=4096;length++) {
  auto s=receive(length);unsigned padded=(length+3)&~3U;
  unsigned before=((padded-1)/64)*64,count=padded-before,pad=(-length)&3;
  w.data=~ap_uint<512>(0);w.keep=prefix(count);w.last=1;
  for(unsigned b=0;b<count;b++)w.data(8*b+7,8*b)=b<count-pad ? ((length+b)*37)&255:0;
  compare(s,w,before);w.last=0;compare(s,w,before);w.last=1;
  auto bad=w;bad.keep^=ap_uint<64>(1)<<(count-1);compare(s,bad,before);
  if(count<64){bad=w;bad.keep[count]=1;compare(s,bad,before);}
  if(pad){bad=w;bad.data((count-1)*8+7,(count-1)*8)=1;compare(s,bad,before);}
  compare(s,w,padded);compare(s,w,padded+1);
 }
 for(unsigned count=1;count<=64;count++)for(unsigned bit=0;bit<64;bit++) {
  w.data=0;w.keep=prefix(count)^(ap_uint<64>(1)<<bit);w.last=0;compare(receive(4096),w,0);
 }
 // Padding itself may be split across nonterminal short contiguous beats.
 for(unsigned length=1;length<=69;length++)for(unsigned before=length>2 ? length-2:0;before<=((length+3)&~3U);before++)
  for(unsigned count=0;count<=4;count++)for(bool last:{false,true})for(bool dirty:{false,true}) {
   w.data=dirty ? ~ap_uint<512>(0):ap_uint<512>(0);w.keep=prefix(count);w.last=last;compare(receive(length),w,before);
  }
 for(unsigned extent:{0U,1U,63U,64U,65U,4096U,0xffffffffU}) {
  pkgShift s(SHIFT_NONE,2);s.request_length_checked=true;s.request_owned=true;s.request_bytes=extent;
  for(unsigned before:{0U,1U,63U,64U,extent,0xfffffff0U})for(unsigned count:{0U,1U,15U,63U,64U})
   for(bool last:{false,true}){w.data=0;w.keep=prefix(count);w.last=last;compare(s,w,before);}
 }
 std::cout<<"EXTENT_CONFORMANCE {\"pass_test\":true,\"cases\":"<<checked
  <<",\"all65536_low16_KEEP_patterns\":true,\"all_receive_lengths1to4096\":true,\"short_nonfinal_preserved\":true,"
  "\"actual_accept_and_copied_compared\":true,\"timing_or_native_verified\":false}"<<std::endl;
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['baseline','source','report']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    baseline=a.baseline.resolve();source=a.source.resolve()
    for s in [baseline,source]:
        info=json.loads((s/'source.json').read_text())
        if info.get('HLS_top')!='rocev2_native_segmented_receive_top':raise ValueError('same full receive top required')
        for n,h in info['derived_sources'].items():
            if digest(s/'fns'/n)!=h:raise ValueError('changed frozen core:'+n)
    if digest(baseline/'fns'/HPP)!=digest(source/'fns'/HPP):raise ValueError('identical actual type definitions required')
    run=Path(tempfile.mkdtemp(prefix='receive-extent-conformance-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-extent-',dir='/dev/shm'))
    (run/'test.cpp').write_text('#include <iostream>\n#include <cstdlib>\n#include "ib_transport_protocol/ib_transport_protocol.hpp"\n'+
        helper((baseline/'fns'/CPP).read_text(),'baseline_extent')+'\n'+helper((source/'fns'/CPP).read_text(),'candidate_extent')+'\n'+BENCH)
    files=[*baseline.rglob('*'),*source.rglob('*'),Path(__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in files if n.is_file()}
    command=[shutil.which('g++-13'),'-std=c++17','-O2','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64',
        '-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),
        '-I/home/user/amd/2025.2/Vitis/include',str(run/'test.cpp'),'-o',str(ram/'test')]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,compile_command=command,
        runtime_limit_seconds=30,generated_HLS_or_timing_or_native=False,hardware_verified=False)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=600,env=env)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('actual extent consumers compile failed:'+str(run/'compile.log'))
        start=time.monotonic();c=subprocess.run([str(ram/'test')],capture_output=True,text=True,timeout=30)
        (run/'simulation.log').write_text(c.stdout+c.stderr);result.update(exit=c.returncode,simulation_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('actual extent consumer semantic difference:'+str(run/'simulation.log'))
        rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('EXTENT_CONFORMANCE ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual comparisons absent')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,summary=rows[0])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],simulation_seconds=result['simulation_seconds'],summary=result['summary'])))


if __name__=='__main__':main()
