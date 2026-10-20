# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual zero RQ admission/store/CQ RTL; adjacent proof producers MODELED.

Retain prior Atomic/Immediate regressions. Zero receivers require a genuine
posted owner plus matching placement, HLS receipt, MAC receipt, memory drain
and exact CQ commit/retire. This is NOT generated-HLS/full-native runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import test_zero_native_leaves as actual
import test_immediate_receive_lifetime_rtl as prior
import test_receive_ack_rtl as ack_prior
import derive_zero_rq_native as source

ROOT=source.ROOT;OUT=source.derive();digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
RUN=None


def renamed(names):
    result={source.RTL/(n+'.v'):OUT[source.RTL/(n+'.v')]for n in names}
    for p,t in result.items():
        for n in names:t=re.sub(r'\b'+n+r'\b','rocev2_atomic128_'+n.removeprefix('rocev2_'),t)
        result[p]=t
    return result


facade=SimpleNamespace(**vars(actual.admit.source))
facade.derive=lambda:renamed(['rocev2_wqe_admission','rocev2_sq_wqe_admission','rocev2_wqe_hls_sq'])
actual.admit.source=facade
facade=SimpleNamespace(**vars(actual.cq.source))
facade.cq=lambda:OUT[source.RTL/'rocev2_cq_mmio.v']
actual.cq.source=facade


class ZeroRQAdmission(actual.admit.Atomic128AdmissionTests):
    reports={}
    setUpClass=classmethod(actual.ZeroAdmission.setUpClass.__func__)
    zero_entry=actual.ZeroAdmission.zero_entry

    def test_real_zero_RECV_descriptor_passes_without_MR_query(self):
        self.simulate(self.zero_entry(4),receive_only=True)

    def test_zero_RECV_never_licenses_local_key_or_address(self):
        for offset in [16,23,36,39]:
            self.simulate(self.zero_entry(4,error=0x26,mutate=lambda b,o=offset:b.__setitem__(o,1)),receive_only=True)


def context(length=0,sequence=1):
    return actual.response.owner(4,qpn=7,pd=17,sequence=sequence,tag=sequence,
        length=length,lkey=8 if length else 0,address=0xfedcba9876543210 if length else 0,
        offset=0x210 if length else 0,remote=0,rkey=0).replace("748'h","620'h")


def proof(ctx,flags=0,immediate=0,length=0):
    return f"{{8'd0,8'd{flags},32'h{immediate:08x},24'hfedcba,4'd0,24'hfffffe,32'd{length},{ctx}}}"


def owned(ctx):
    return f'''
query_qpn=7;@(negedge clk);s_post_context={ctx};s_post_valid=1;
@(posedge clk);if(!s_post_ready)$fatal(1,"real zero-capable RQ post");
@(negedge clk);s_post_valid=0;m_head_ready=1;
@(posedge clk);if(!m_head_valid)$fatal(1,"real RQ take");
@(negedge clk);m_head_ready=0;
s_placement_context={ctx};s_placement_length=0;s_placement_psn=24'hfffffe;
'''


class ZeroRQ(prior.ImmediateReceiveLifetimeTests):
    reports={}

    def simulate(self,body):
        tb=prior.base.TB.replace('// BODY',body).replace('[587:0]','[619:0]').replace('[679:0]','[751:0]').replace('[695:0]','[767:0]')
        tb=source.once(tb,'.RECV_RETIRE_ENABLE(RETIRE_PROFILE)',
            '.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1),.IMMEDIATE_ENABLE(1)')
        run=Path(tempfile.mkdtemp(prefix=self._testMethodName+'-',dir=RUN))
        ram=Path(tempfile.mkdtemp(prefix='as02-zero-rq-unit-',dir='/dev/shm'))
        (run/'tb.v').write_text(tb);(run/'rq.v').write_text(OUT[source.RQ])
        start=time.monotonic()
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/'rq.v')],capture_output=True,text=True,timeout=20)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects' in l and 'bits' in l for l in c.stderr.splitlines()),c.stderr)
        r=subprocess.run(['vvp',str(ram/'test')],capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertNotIn('ERROR:',r.stdout+r.stderr)
        self.reports.setdefault(self._testMethodName,[]).append(dict(seconds=time.monotonic()-start,
            directory=str(run.relative_to(ROOT)),RAM_binary_sha256={str(ram/'test'):digest(ram/'test')}))

    def test_six_zero_receives_keep_owner_until_all_real_join_inputs(self):
        for length in [0,128]:
            for flags in [0,1,3]:
                ctx=context(length);imm=0x89abcdef if flags else 0;core=proof(ctx,flags,imm)
                body=owned(ctx)+f'''
s_placement_notification=32'h{imm:08x};s_placement_notification_flags={flags};s_placement_valid=1;
@(posedge clk);if(!s_placement_ready)$fatal(1,"zero placement");
@(negedge clk);s_placement_valid=0;
repeat(7)begin @(negedge clk);if(m_ticket_valid || core_proved || !active || queue_guard!==8'h80)$fatal(1,"placement invented HLS/CQ");end
s_core_data={core};s_core_valid=1;
@(posedge clk);if(!s_core_ready)$fatal(1,"exact real-consumer receipt");
@(negedge clk);s_core_valid=0;
repeat(7)begin @(negedge clk);if(m_ticket_valid || !core_proved || !active || core_msn!==24'hfedcba)$fatal(1,"core receipt invented MAC");end
s_mac_data={{16'h6001,{core}}};s_mac_valid=1;
@(posedge clk);if(!s_mac_ready)$fatal(1,"exact ACK MAC receipt");
@(negedge clk);s_mac_valid=0;
repeat(7)begin @(negedge clk);if(m_ticket_valid || !active)$fatal(1,"MAC invented memory drain");end
memory_drained=1;
repeat(7)begin @(negedge clk);if(!m_ticket_valid || m_ticket_context!=={ctx} || m_ticket_received_bytes!==0 ||
 m_ticket_notification!==32'h{imm:08x} || m_ticket_notification_flags!==8'd{flags} || !active ||
 queue_guard!==8'h80 || fault)$fatal(1,"immutable zero CQ ticket");end
m_ticket_ready=1;@(posedge clk);@(negedge clk);m_ticket_ready=0;
s_commit_context={ctx};s_commit_valid=1;
@(posedge clk);if(!s_commit_ready)$fatal(1,"exact CQ commit");
@(negedge clk);s_commit_valid=0;
repeat(7)begin @(negedge clk);if(!active || queue_guard!==8'h80 || m_head_valid)$fatal(1,"commit invented retirement");end
s_retire_context={ctx};s_retire_valid=1;
@(posedge clk);if(!s_retire_ready)$fatal(1,"exact CQ retire");
@(negedge clk);s_retire_valid=0;#1;
if(active || queue_guard || m_head_valid || fault || posted_count!=1 || taken_count!=1 || placement_count!=1 ||
 received_bytes || core_proof_count!=1)$fatal(1,"actual zero receive owner not retired exactly once");
'''
                self.simulate(body)

    def test_zero_post_never_grants_key_VA_or_offset_authority(self):
        n=int(context().split("'h")[1],16)
        for bit in [116,180,244]:
            self.simulate(f"s_post_context=620'h{n^(1<<bit):0155x};s_post_valid=1;"+r'''
repeat(7)@(negedge clk);
if(!fault || s_post_ready || posted_count || taken_count || queue_guard!==8'hff)$fatal(1,"zero posted local authority");
''')

    def test_zero_buffer_refuses_nonempty_or_mismatched_placement(self):
        for mutation in ["s_placement_length=1;", "s_placement_context[396]=~s_placement_context[396];"]:
            self.simulate(owned(context())+mutation+'s_placement_valid=1;'+self.retained(0xe8))

    def test_zero_receipt_cannot_change_actual_wire_PSN_or_notification(self):
        ctx=context();core=proof(ctx,1,0x89abcdef)
        for mutation in ["s_core_data[652]=~s_core_data[652];", "s_core_data[704]=~s_core_data[704];"]:
            body=owned(ctx)+r'''
s_placement_notification=32'h89abcdef;s_placement_notification_flags=1;s_placement_valid=1;
@(posedge clk);if(!s_placement_ready)$fatal(1,"zero placement");
@(negedge clk);s_placement_valid=0;
'''+f's_core_data={core};'+mutation+'s_core_valid=1;'+self.retained(0xea)
            self.simulate(body)


class ZeroRQCQ(actual.ZeroCQ):
    reports={}

    def test_six_empty_RECV_events_preserve_posted_owner_and_wire_notification(self):
        t=actual.cq.bench();a=t.index('notification=0;notification_flags=0;\npublish(')
        b=t.index('\n if(pub_published!=4',a);body='';seq=0
        for length in [0,128]:
            for flags in [0,1,3]:
                seq+=1;imm=0x89abcdef if flags else 0
                ctx=context(length,seq).replace("620'h","748'h")
                body+=f"notification=32'h{imm:08x};notification_flags={flags};publish({ctx},0,{seq},0);\n"
        t=t[:a]+body+t[b:]
        t=t.replace('pub_published!=4 || pub_acked!=4','pub_published!=6 || pub_acked!=6')
        self.simulate(t)


class ZeroRQACK(unittest.TestCase):
    reports={}

    def bench(self,length=0,flags=0):
        t=ack_prior.bench().replace('localparam IMMEDIATE_ENABLE=0;','localparam IMMEDIATE_ENABLE=1;')
        t=t.replace('[587:0]','[619:0]').replace('[695:0]','[767:0]')
        t=source.once(t,'.TAG_SEQUENCE_WIDTH(2)', '.TAG_SEQUENCE_WIDTH(2),.IMMEDIATE_ENABLE(1)')
        immediate=0x89abcdef if flags else 0
        t=source.once(t,"s_core_data={8'd0,msn,4'd0,psn,32'd65,owner};",
            f"s_core_data={{8'd0,8'd{flags},32'h{immediate:08x},msn,4'd0,psn,32'd0,owner}};")
        for seq in [1,2]:
            t=source.once(t,'operation('+ack_prior.context(sequence=seq)+',',
                'operation('+context(length,seq)+',')
        return t

    def simulate(self,t):
        run=Path(tempfile.mkdtemp(prefix=self._testMethodName+'-',dir=RUN))
        ram=Path(tempfile.mkdtemp(prefix='as02-zero-rq-ack-',dir='/dev/shm'))
        (run/'tb.v').write_text(t);(run/'ack.v').write_text(OUT[source.ACK])
        _,_,_,ack=ack_prior.native.case(True,True)
        for seq in [1,2]:
            packet=bytearray(ack)
            packet[37:40]=(0x987653+seq).to_bytes(3,'big');packet[41:44]=seq.to_bytes(3,'big')
            packet=ack_prior.native.qp.main.response.repair(packet)
            frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
            (run/f'ack{seq}.hex').write_text(''.join(f'{int.from_bytes(frame[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(frame),16)))
        start=time.monotonic()
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/'ack.v')],capture_output=True,text=True,timeout=20)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects' in l and 'bits' in l for l in c.stderr.splitlines()),c.stderr)
        r=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ERROR:',r.stdout+r.stderr)
        self.reports.setdefault(self._testMethodName,[]).append(dict(seconds=time.monotonic()-start,
            directory=str(run.relative_to(ROOT)),RAM_binary_sha256={str(ram/'test'):digest(ram/'test')}))

    def test_six_zero_ACK_profiles_keep_fresh_tags_actual_receipt_tail_and_CQ(self):
        # All old delayed receipt/tail, byte-exact frame, PSN/MSN, fresh tag,
        # backpressure and exact CQ retirement assertions run unchanged.
        for length in [0,128]:
            for flags in [0,1,3]:self.simulate(self.bench(length,flags))

    def test_zero_ACK_owner_cannot_grant_local_memory_authority(self):
        n=int(context().split("'h")[1],16)
        for bit in [116,180,244]:
            t=self.bench();a=t.index('operation(620\'h');b=t.index('\n $display("RECEIVE_ACK_RESULT',a)
            t=t[:a]+f"s_owner_context=620'h{n^(1<<bit):0155x};s_owner_valid=1;"+r'''
repeat(7)@(negedge clk);
if(!fault || fault_code!==8'hd2 || busy!==1'b1 || m_axis_tvalid || m_done_valid || frame_count || receipt_count ||
 queue_guard!==8'hff)$fatal(1,"noncanonical zero ACK owner acquired authority");
'''+t[b:]
            t=source.once(t,' if(fault)$fatal(1,"ACK owner fault %h",fault_code);','')
            t=t.replace('"frames\\\":2,\\\"receipts\\\":2','"frames\\\":0,\\\"receipts\\\":0')
            self.simulate(t)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    RUN=Path(tempfile.mkdtemp(prefix='zero-rq-native-units-',dir=ROOT/'rdma/rnic/build'))
    files=[*OUT,*[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]]
    before={str(f.relative_to(ROOT)):digest(f)for f in dict.fromkeys(files)}
    for f in files:
        target=RUN/'inputs'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    for f,t in OUT.items():
        target=RUN/'derived'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(t)
    classes=[ZeroRQAdmission,ZeroRQ,ZeroRQCQ,ZeroRQACK];start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)for c in classes))
    if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,directory=str(RUN.relative_to(ROOT)),four_state=True,upstream_proof_sources_modeled=True,
        generated_HLS_or_full_native_runtime=False,hardware_verified=False,
        tests={c.__name__:c.reports for c in classes},
        artifact_sha256={str(f.relative_to(ROOT)):digest(f)for f in RUN.rglob('*')if f.is_file()})
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
