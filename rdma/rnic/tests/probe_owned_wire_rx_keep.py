#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short actual keep-helper / length arithmetic differential against retained048.

C++ evidence only: not RTL, native admission, payload DMA, or physical signoff.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('wire_rx',ROOT/'rdma/rnic/hls/owned_wire_rx_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def sha(q):return hashlib.sha256(Path(q).read_bytes()).hexdigest()
TEST=r"""
#include <cassert>
#include <iostream>
int main() {
 unsigned patterns=0,arithmetic=0,opcodes=0,decoded_beats=0,frame_check_beats=0,query_vectors=0;
 for(unsigned k=0;k<256;k++) {
  net_axis<64> w;w.keep=k;
  // Literal original048 width/validity/popcount semantics.
  ap_uint<9> keep=w.keep;ap_uint<9> next=keep+1;
  unsigned bytes=0;
  for(unsigned b=0;b<8;b++)if(w.keep[b])bytes++;
  bool canonical=keep!=0 && (keep & next)==0;
  ap_uint<4> actual=as02_rx_wire_keep_bytes(w.keep);
  assert((actual!=0)==canonical);
  if(canonical)assert(actual==bytes);
  for(unsigned last=0;last<2;last++) {
   bool old_valid=canonical && (last || keep==255);
   bool new_valid=actual!=0 && (last || w.keep==255);
   assert(old_valid==new_valid);
  }
  patterns++;
 }
 const unsigned masks[8]={1,3,7,15,31,63,127,255};
 for(unsigned c=0;c<65536;c++)for(unsigned m=0;m<8;m++) {
  ap_uint<17> count=c;
  ap_uint<4> bytes=as02_rx_wire_keep_bytes(ap_uint<8>(masks[m]));
  ap_uint<17> actual=count+ap_uint<17>(bytes);
  ap_uint<17> original=count+unsigned(m+1);
  assert(actual==original && actual.to_uint()==c+m+1);
  for(unsigned last=0;last<2;last++) {
   // Whole uint16 lengths, endpoints, and exact/full/overrun TLAST behavior.
   for(unsigned sample=0;sample<5;sample++) {
    unsigned length=sample==0?12:(sample==1?65535:(sample==2?c:((c+m+sample-1)&65535)));
    bool a=actual>length || actual>65535 || (!last && actual==length) || (last && actual!=length);
    bool o=original>length || original>65535 || (!last && original==length) || (last && original!=length);
    assert(a==o);
   }
  }
  arithmetic++;
 }
 for(unsigned n=0;n<256;n++) {
  ibOpCode op=static_cast<ibOpCode>(n);
  unsigned original=12+(checkIfAethHeader(op)?4:(checkIfRethHeader(op)?16:0));
  ap_uint<5> actual=checkIfAethHeader(op)?16:(checkIfRethHeader(op)?28:12);
  assert(actual==original);opcodes++;
 }
 // Exercise the ACTUAL new dataflow decoder for every keep/opcode pair.
 // Software streams do not prove RTL backpressure or native authorization.
 stream<ap_uint<80>> packets("keep_test_packets");stream<ap_uint<96>> decoded("keep_test_decoded");
 for(unsigned k=0;k<256;k++)for(unsigned n=0;n<256;n++) {
  ap_uint<80> raw=ap_uint<80>(0xfedcba9876543210ULL);
  raw(7,0)=n;raw(71,64)=k;raw(79,72)=(k^n)&255;
  packets.write(raw);as02_rx_wire_decode(packets,decoded);
  assert(!decoded.empty());ap_uint<96> d=decoded.read();
  assert(d(79,0)==raw && d(95,90)==0 && d[89]==(n>RC_ACK));
  assert(d(83,80)==as02_rx_wire_keep_bytes(ap_uint<8>(k)));
  ibOpCode op=static_cast<ibOpCode>(n);
  unsigned old_minimum=12+(checkIfAethHeader(op)?4:(checkIfRethHeader(op)?16:0));
  assert(d(88,84)==old_minimum && packets.empty() && decoded.empty());
  decoded_beats++;
 }
 // ACTUAL II1 frame-check task, independent original guard oracle. These
 // annotated component stimuli are not native admission/end-to-end frames.
 stream<ap_uint<320>> begins("guard_begins"),checked_begins("guard_checked_begins");
 stream<ap_uint<128>> annotated("guard_annotated"),checked("guard_checked");
 for(unsigned c=0;c<65536;c++)for(unsigned m=0;m<8;m++) {
  unsigned length=12+((c*13+m*11)%65524),total=c+m+1;
  ap_uint<320> descriptor=0;descriptor(23,0)=2;descriptor(87,24)=1;
  descriptor(103,88)=length;descriptor[104]=1;descriptor(289,274)=65535;
  begins.write(descriptor);as02_rx_wire_frame_check(begins,annotated,checked_begins,checked);
  assert(!checked_begins.empty() && checked_begins.read()==descriptor);
  for(unsigned last=0;last<2;last++) {
   ap_uint<80> raw=0;raw(7,0)=17;raw(71,64)=masks[m];raw[72]=last;
   packets.write(raw);as02_rx_wire_decode(packets,decoded);ap_uint<96> d=decoded.read();
   ap_uint<128> a=0;a(95,0)=d;a(112,96)=total;a[113]=c==0;
   annotated.write(a);as02_rx_wire_frame_check(begins,annotated,checked_begins,checked);
   for(unsigned tick=0;checked.empty();tick++) {
    assert(tick<8);as02_rx_wire_frame_check(begins,annotated,checked_begins,checked);
   }
   ap_uint<128> actual=checked.read();
   bool old_bad=(!last && masks[m]!=255) || total>length || total>65535 ||
       (!last && total==length) || (last && total!=length) || (c==0 && length<16);
   assert(actual(113,0)==a(113,0) && actual[114]==old_bad && actual(127,115)==0);
   assert(annotated.empty() && checked.empty());frame_check_beats++;
  }
 }
 stream<ap_uint<320>> query_in("full_query_in");stream<as02RxLookupQuery> query_out("full_query_out");
 auto test_query=[&](ap_uint<320> raw) {
  query_in.write(raw);
  for(unsigned tick=0;query_out.empty();tick++) {
   assert(tick<8);as02_rx_lookup_decode(query_in,query_out);
  }
  as02RxLookupQuery q=query_out.read();
  assert(q.qpn==raw(23,0) && q.psn==raw(47,24) && q.opcode==raw(55,48) && q.epoch==raw(119,56));
  assert(q.syndrome==raw(127,120) && q.has_aeth==bool(raw[128]) && q.marker==bool(raw[129]));
  assert(q.owner==raw(297,130) && q.bad==(raw(319,298)!=0));
  assert(query_in.empty() && query_out.empty());query_vectors++;
 };
 test_query(0);test_query(~ap_uint<320>(0));
 for(unsigned bit=0;bit<320;bit++) {
  ap_uint<320> one=0;one[bit]=1;test_query(one);
  ap_uint<320> cold=~ap_uint<320>(0);cold[bit]=0;test_query(cold);
 }
 unsigned long long random_state=0xfedcba9876543210ULL;
 for(unsigned sample=0;sample<512;sample++) {
  ap_uint<320> raw=0;
  for(unsigned lane=0;lane<5;lane++) {
   random_state^=random_state<<13;random_state^=random_state>>7;random_state^=random_state<<17;
   raw(lane*64+63,lane*64)=random_state;
  }
  test_query(raw);
 }
 std::cout<<"WIRE_RX_KEEP_DIFF {\"pass_test\":true,\"keep_patterns\":"<<patterns
  <<",\"uint16_count_valid_keep_pairs\":"<<arithmetic<<",\"opcode_minimums\":"<<opcodes
  <<",\"actual_decoded_beats\":"<<decoded_beats
  <<",\"actual_frame_check_beats\":"<<frame_check_beats
  <<",\"actual_full320_query_vectors\":"<<query_vectors
  <<",\"all_uint16_counts\":true,\"RTL_tested\":false}"<<std::endl;
}
"""
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--vitis-include',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
 a=ap.parse_args()
 if a.report.exists():ap.error('preserve earlier evidence')
 old_record=ROOT/'results/2026-10-18/rocev2-rnic-owned-wire-rx-hls-001.json'
 prior=json.loads(old_record.read_text());old=ROOT/prior['retained_directory']/'inputs'
 assert sha(old/'profile/owned_wire_rx_profile.py')==prior['frozen_source_sha256']['profile/owned_wire_rx_profile.py']
 old_header=old/'fns/hls/ib_transport_protocol/owned_wire_rx.hpp'
 assert sha(old_header)==prior['frozen_source_sha256']['fns/hls/ib_transport_protocol/owned_wire_rx.hpp']
 legacy=old_header.read_text()
 for text in ['ap_uint<9> keep=w.keep;ap_uint<9> next=keep+1;','unsigned bytes=0;',
              'if(w.keep[b])bytes++;','ap_uint<17> total=count+bytes;',
              'unsigned minimum=12+(checkIfAethHeader(op)?4:(checkIfRethHeader(op)?16:0));']:
  assert text in legacy,text
 run=Path(tempfile.mkdtemp(prefix='owned-wire-rx-keep-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
 own=[Path(__file__).resolve(),Path(p.__file__).resolve(),p.CPP,p.HPP,old_record,old_header,old/'profile/owned_wire_rx_profile.py']
 before={str(q.relative_to(ROOT)):sha(q)for q in own}
 for q in own:
  dest=inp/q.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,dest)
 (run/'owned_wire_rx.hpp').write_text(p.wire_header(p.CPP.read_text(),p.HPP.read_text()))
 (run/'keep.cpp').write_text('#include "owned_wire_rx.hpp"\n'+p.derive_query_decoder()+'\n'+TEST)
 result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
  source_sha256=before,legacy_source_record=str(old_record.relative_to(ROOT)),simulation_wall_bound_seconds=30,
  hardware_verified=False,RTL_tested=False,physical_signoff=False)
 def current():
  for n,h in before.items():assert sha(ROOT/n)==h,n
 try:
  current();compiler=shutil.which('g++-13')or shutil.which('g++')
  cmd=[compiler,'-std=c++17','-O2','-pthread','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8',
       '-D__VITIS_HLS__','-I'+str(old/'adapter'),'-I'+str(old/'fns/hls'),
       '-I'+str(old/'fns/hls/ib_transport_protocol'),'-I'+str(a.vitis_include.resolve()),
       str(run/'keep.cpp'),'-o',str(run/'keep')]
  (run/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
  t=time.monotonic()
  with(run/'compile.log').open('x')as out:c=subprocess.run(cmd,cwd=run,stdout=out,stderr=subprocess.STDOUT,timeout=120)
  result['compile_seconds']=time.monotonic()-t
  if c.returncode:raise RuntimeError('C++ compile failed')
  t=time.monotonic()
  c=subprocess.run([str(run/'keep')],cwd=run,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
  result['simulation_seconds']=time.monotonic()-t
  (run/'run.stdout.log').write_text(c.stdout)
  if c.returncode:raise RuntimeError('C++ differential failed')
  prefix='WIRE_RX_KEEP_DIFF '
  rows=[json.loads(line[len(prefix):])for line in c.stdout.splitlines()if line.startswith(prefix)]
  assert len(rows)==1 and rows[0]['pass_test']and rows[0]['keep_patterns']==256 and rows[0]['uint16_count_valid_keep_pairs']==524288 and rows[0]['actual_decoded_beats']==65536 and rows[0]['actual_frame_check_beats']==1048576 and rows[0]['actual_full320_query_vectors']==1154
  current();result.update(pass_test=True,terminal_exit_status=0,summary=rows[0]);print(json.dumps(result['summary']),flush=True)
 except Exception as e:result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
 finally:
  result['frozen_source_sha256']={str(q.relative_to(inp)):sha(q)for q in inp.rglob('*')if q.is_file()}
  result['artifact_sha256']={str(q.relative_to(ROOT)):sha(q)for q in run.iterdir()if q.is_file()}
  with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
