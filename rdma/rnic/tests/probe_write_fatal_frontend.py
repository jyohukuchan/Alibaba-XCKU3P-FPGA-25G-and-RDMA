#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same47 real ICRC/MR/RQ/replay inputs with qualified fatal61/62 metadata.

Zero RKEY/overflow now reach the actual whole MR lookup and return1/4, not
semantic16; both still grant/replay nothing. Other45 protection and all47
raw/replay outcomes remain. Backend/HLS/MAC/native frontier modeled; not
full native fatal execution/error CQ/STOP/global drain/unpin proof.
"""
import ast
from pathlib import Path
import sys
import audit_segmented_receive as binding
import probe_write_psn_frontend as psn
import probe_segmented_write_rx_frontend as parent
sys.path.insert(0,str(parent.ROOT/'rdma/rnic/fpga'))
import derive_write_fatal_native as candidate
ROOT=parent.ROOT;once=parent.once
FATAL_MODES={6,7,8,9,10,11,12,13,14,15,19,20,21,22,23,24}
ACCESS_MODES={6,7,8,9,10,20,21}
OBSERVE=psn.OBSERVE+r'''
wire m_fatal_certified;
wire [355:0] m_fatal_context;
wire [23:0] m_fatal_received_psn,m_fatal_expected_psn;
wire [7:0] m_fatal_syndrome;
integer fatal_cycles=0,fatal_consumed=0;
reg [7:0] observed_fatal_syndrome=0;
always @(posedge clk)if(!rst)begin
 if(m_fatal_certified!==1'b0 && m_fatal_certified!==1'b1)$fatal(1,"unknown authenticated fatal certification VALID");
 if(m_fatal_certified)begin
  fatal_cycles=fatal_cycles+1;observed_fatal_syndrome=m_fatal_syndrome;
  if(!m_reject_valid || m_control_certified || m_fatal_context!==native_context ||
   m_fatal_received_psn!==m_reject_psn || m_fatal_expected_psn!==trusted_expected_psn ||
   m_reject_qpn!==trusted_qpn || crc_good_count==0 || m_packet_valid || output_valid || m_mr_valid ||
   (m_reject_error==16 ? m_fatal_syndrome!==8'h61:
    m_reject_error<1 || m_reject_error>4 || m_fatal_syndrome!==8'h62))
   $fatal(1,"fatal certificate not from actual checked semantic request or actual MR access denial");
  if(m_reject_ready)fatal_consumed=fatal_consumed+1;
 end
 if((mode==16 || mode==17 || mode==25 || mode==49) && m_fatal_certified)
  $fatal(1,"wrong peer/native PSN/format/bad ICRC gained fatal wire authority");
end
'''


def fatal_bench_patch(text):
    # Registered MR stays unchanged. These two formerly pre-MR rejects now
    # query the exact invalid key/address from their unchanged raw frames.
    text=once(text,'m_mr_key!==remote_key',"m_mr_key!==(mode==20 ? 32'd0:remote_key)")
    text=once(text,"m_mr_address!==(mr_va+64'h210+cur_offset)",
        "m_mr_address!==(mode==21 ? 64'hfffffffffffffff0:mr_va+64'h210+cur_offset)")
    text=once(text,'reject_packet(mode==16 ? 17:mode==17 ? 18:mode==18 || mode==37 ? 36:16,0);',
        'reject_packet(mode==20 ? 1:mode==21 ? 4:mode==16 ? 17:mode==17 ? 18:mode==18 || mode==37 ? 36:16,0);')
    text=once(text,'if(queries)$fatal(1,"malformed/exhausted metadata cannot query actual MR");',
        'if(queries!=(mode==20 || mode==21 ? 1:0))$fatal(1,"actual zero-key/range access denial must query once; other malformed metadata never queries");')
    return once(text,' $display("PSN_CERT_RESULT ',r'''
 $display("FATAL_CERT_RESULT {\"mode\":%0d,\"cycles\":%0d,\"consumed\":%0d,\"syndrome\":%0d}",mode,fatal_cycles,fatal_consumed,observed_fatal_syndrome);
 $display("PSN_CERT_RESULT ''')


def fatal_compare(result,run):
    old,_=binding.bindings('write-psn-front-002')
    if set(result['tests'])!=set(old['tests']):raise ValueError('all47 original cases required')
    for n,t in old['tests'].items():
        fresh=result['tests'][n]
        if fresh['replay']!=t['replay']:raise ValueError('original every raw replay/CRC outcome changed:'+n)
        if n not in ['20','21']:
            if fresh['protection']!=t['protection']:raise ValueError('original45 protection outcome changed:'+n)
        else:
            if any(v!=fresh['protection'][k]for k,v in t['protection'].items()if k!='MR_queries'):
                raise ValueError('zero-key/range access changed more than actual MR query classification:'+n)
        key=old['directory']+'/'+n+'-input.hex'
        if binding.digest(run/(n+'-input.hex'))!=old['artifact_sha256'][key]:raise ValueError('original raw input changed:'+n)


def runner_source():
    t=psn.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'def bench():','def retained_bench():')
    t=once(t,'def main():\n', 'def bench():\n    return fatal_bench_patch(retained_bench())\n\ndef main():\n')
    t=once(t,"prefix='write-psn-front-'","prefix='write-fatal-front-'")
    t=once(t,"prefix='as02-write-psn-front-'","prefix='as02-write-fatal-front-'")
    t=once(t,"    FRONT.write_text(candidate.frontend())\n    sources=[FRONT,prior.GUARD,",
        "    FRONT.write_text(candidate.frontend())\n    fatal_guard=run/(candidate.GUARD_NAME+'.v');fatal_guard.write_text(candidate.guard())\n    sources=[FRONT,fatal_guard,")
    t=once(t,'authored=sources+[Path(parent.__file__).resolve(),',
        "authored=sources+[candidate.GUARD,Path(candidate.error.__file__).resolve(),ROOT/'results/2026-10-18/rocev2-rnic-write-psn-front-002.json',Path(parent.__file__).resolve(),")
    t=once(t,"            t['certification']=certs[0]",r'''
            t['certification']=certs[0]
            fatals=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('FATAL_CERT_RESULT ')]
            if len(fatals)!=1 or fatals[0]['mode']!=mode or bool(fatals[0]['cycles'])!=(mode in FATAL_MODES)or \
               fatals[0]['consumed']!=(1 if mode in FATAL_MODES else 0)or \
               fatals[0]['syndrome']!=(0x62 if mode in ACCESS_MODES else 0x61 if mode in FATAL_MODES else 0):
                raise ValueError('actual qualified fatal certificate cardinality/class')
            t['fatal_certification']=fatals[0]''')
    t=once(t,'            elif mode==49:',r'''
            elif mode in [20,21]:
                expected=dict(MR_queries=1,grants=0,completed_packets=0,completed_messages=0,cancelled_messages=0,RQ_taken=0,fault=0,message_active=0)
                if any(s[k]!=v for k,v in expected.items()):raise ValueError('actual whole-MR access denial before all data/RQ/replay')
            elif mode==49:''')
    t=once(t,'        result.update(pass_test=True,source_unchanged=True)',
        '        fatal_compare(result,run)\n        result.update(pass_test=True,source_unchanged=True,all47_raw_inputs_and_replay_identical=True,other45_protection_identical=True,zero_key_overflow_actual_MR_classified=True)')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        candidate=candidate,parent=parent,OBSERVE=OBSERVE,fatal_bench_patch=fatal_bench_patch,fatal_compare=fatal_compare,FATAL_MODES=FATAL_MODES,ACCESS_MODES=ACCESS_MODES))
