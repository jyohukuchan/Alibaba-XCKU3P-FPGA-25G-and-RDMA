#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C WQE bytes -> hardware owner/SQ staging -> unchanged per-WR HLS/IP.

One request, no peer completion. MR authorization, physical source memory and
downstream executor/WR/CQ lifetime are EXPLICIT MODELS. Native coherent SQ/
MR is tested separately; this leaf does not prove native DMA/execution/CQ.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import tempfile

import probe_wrkey_wire as wire
import test_shared_mr_responder_rtl as shared
import test_wqe_hls_sq_rtl as unit

ROOT=wire.ROOT
LOCAL=0xfedcba9876543210
REMOTE=0xf123456789abc001


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('leaf fixture anchor changed: '+old)
    return text.replace(old,new)


def bench(write):
    tb=wire.TB.replace('WRITE_VALUE',str(int(write)))
    tb=once(tb,'reg rst=0,qv=0,cv=0,sqv=0,mr=0;','reg rst=0,qv=0,cv=0,mr=0;wire sqv;')
    tb=once(tb,'reg [239:0] sq=0;\nreg [31:0] key=0;',r'''
wire [247:0] keyed_work_sq;wire [239:0] sq=keyed_work_sq[239:0];wire [31:0] key=keyed_work_sq[239:208];
reg [587:0] contexts[0:0];reg wvalid=0,work_taken=0,owner_taken=0,owner_ready=0;
wire wready,owner_valid,stage_fault,stage_busy;wire [587:0] owner_context;
wire [7:0] stage_guard,stage_fault_code;reg [7:0] executor_guard=0;
wire [31:0] owners,SQ_handoffs;
rocev2_wqe_hls_sq stage(
 .clk(clk),.rst(rst),.enable(1'b1),.halt(1'b0),.s_work_context(contexts[0]),.s_work_valid(wvalid),.s_work_ready(wready),
 .m_owner_context(owner_context),.m_owner_valid(owner_valid),.m_owner_ready(owner_ready),.downstream_queue_guard(executor_guard),
 .m_axis_sq_tdata(keyed_work_sq),.m_axis_sq_tvalid(sqv),.m_axis_sq_tready(sqr),
 .queue_guard(stage_guard),.configuration_guard(),.busy(stage_busy),.fault(stage_fault),.fault_code(stage_fault_code),
 .owner_handoff_count(owners),.HLS_SQ_handoff_count(SQ_handoffs));
''')
    tb=once(tb,'reg [239:0] requests[0:3];reg [31:0] keys[0:3];','')
    tb=once(tb,' $readmemh("sq.hex",requests);$readmemh("keys.hex",keys);',' $readmemh("context.hex",contexts);')
    tb=once(tb,r'''
 if(!sqv && issued<4 && qdone && cdone && cycle>2200) begin
  sq=requests[issued];key=keys[issued];sqv=1;
 end''',r'''
 wvalid=!work_taken && qdone && cdone && cycle>2200;
 owner_ready=owner_valid && !owner_taken;
 // This explicit executor MODEL retains ownership UNTIL TEST END. A packet
 // generated without peer ACK is NOT an RDMA completion or lifetime release.
 if(owner_ready)executor_guard=8'h04;''')
    tb=once(tb,' if(sqv&&sqr)begin issued=issued+1;sqv<=0;end',r'''
 if(wvalid&&wready)work_taken<=1;
 if(owner_valid&&owner_ready)begin
  if(owner_context!==contexts[0] || executor_guard!==8'h04 || sqv)$fatal(1,"owner-before-SQ/full context");
  owner_taken<=1;
 end
 if(sqv&&sqr)begin
  if(dut.keyed_sq_data!==keyed_work_sq || !keyed_work_sq[240] || keyed_work_sq[247:241]!=0 || !owner_taken)
   $fatal(1,"actual raw HLS248-bit ABI/key-valid/owner changed");
  issued=issued+1;
 end
 if(stage_fault)$fatal(1,"actual staging fault%h",stage_fault_code);''')
    expected=(2<<84)|(((LOCAL>>48)&15)<<80)|(1<<79)|(((LOCAL>>52)&1)<<77)|(1<<76)|(65<<48)|(LOCAL&((1<<48)-1))
    tb=once(tb,r'''  if(!WRITE || active || commands>=4 || rc[47:0]!==48'h4000+commands*256 ||
     rc[75:48]!==28'd65 || rc[93:84]!==10'd2 || rc[79]!==((commands&1)!=0))''',
        f"  if(!WRITE || active || commands>=1 || rc!==96'h{expected:024x})")
    tb=once(tb,' if(issued==4 && frames==4 && txgood==4 && commands==WRITE*4 && read_frames==WRITE*4 && !active)',
        ' if(issued==1 && frames==1 && txgood==1 && commands==WRITE && read_frames==WRITE && !active)')
    tb=once(tb,'  if(!network_stalls)$fatal',r'''
  if(stage_busy || stage_guard || owners!=1 || SQ_handoffs!=1 || executor_guard!==8'h04 || owner_valid || stage_fault)
   $fatal(1,"packet generation incorrectly completed/released actual modeled WR owner");
  if(!network_stalls)$fatal''')
    return f'`include "{unit.RTL}"\n'+tb


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operation',choices=['read','write'],required=True)
    p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.report.exists():p.error('preserve prior evidence; choose fresh report')
    paths=[Path(__file__).resolve(),Path(wire.__file__).resolve(),Path(unit.__file__).resolve(),unit.RTL,
        Path(shared.__file__).resolve(),Path(shared.codec.__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_admission_rtl.py',
        shared.codec.KERNEL/'wqe.c',shared.codec.KERNEL/'wqe.h',shared.codec.KERNEL/'mr_contract.h',
        ROOT/'rdma/host/rocev2_wire.py']
    before={str(q.relative_to(ROOT)):wire.delivery.digest(q)for q in paths}
    write=args.operation=='write';instance=shared.SharedMRResponderRTLTests();instance.setUpClass()
    try:
        w=shared.codec.candidate(wr_id=0xf123456789abc001,sequence=1,epoch=0x9123456700000001,
            local_address=LOCAL,local_key=8,remote_address=REMOTE,remote_key=0,
            opcode=1 if write else 2,flags=1,length=65)
        data=(C.c_uint8*64)();result=instance.lib.as02_wqe_encode(data,C.byref(w))
        if result or bytes(data)!=shared.codec.oracle(w):raise ValueError('actual C/independent WQE bytes')
        record=bytes(data)
    finally:instance.directory.cleanup()
    # Context authorization and queue identity are explicit models here.
    def le(start,n):return int.from_bytes(record[start:start+n],'little')
    ctx=unit.context(id=le(0,8),sequence=le(8,8),epoch=le(56,8),qpn=2,pd=17,tag=1,
        opcode=le(44,2),flags=le(46,2),length=le(32,4),lkey=le(36,4),address=le(16,8),offset=0x210,
        remote=le(24,8),rkey=le(40,4))
    value=int(ctx.split("'h")[1],16);tb=bench(write)
    run=Path(tempfile.mkdtemp(prefix='wqe-hls-wire-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,operation=args.operation,
        actual_C_UBSan_WQE_record_hex=record.hex(),source_sha256=before,retained_directory=str(run.relative_to(ROOT)),
        actual_MR_native_coherent_SQ=False,executor_source_memory_and_WR_CQ_owner_models=True,
        actual_local_RDMA_completion=False,hardware_verified=False,board_integrated=False,standard_verbs=False)
    previous=wire.delivery.bounded.tempfile
    class ExistingRun:
        @staticmethod
        def mkdtemp(**kwargs):return str(run)
    try:
        wire.delivery.bounded.tempfile=ExistingRun
        output,identity=wire.delivery.simulate(tb,{'context.hex':[value]},args.hls_build)
        identity.update(original_testbench_assertions_preserved=False,
            supplied_NEW_single_WR_bench_not_rewritten_by_runner=True)
        report['actual_HLS_identity']=identity
        vvp=(run/'test.vvp').read_text()
        names=['rocev2_wqe_hls_sq','rocev2_top','rocev2_integrity_transport','rocev2_wrkey_sq_adapter']
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
        if not all(v==1 for v in counts.values()):raise ValueError('actual HLS/owner/SQ hierarchy '+str(counts))
        report['actual_elaborated_module_counts']=counts
        actual=wire.packets(output)
        if len(actual)!=1:raise ValueError('one actual IP packet required')
        packet=actual[0];pad=3 if write else 0;opcode=10 if write else 12
        payload=bytes(((i*131)^(i>>8)^0x5a)&255 for i in range(65))if write else b''
        if(len(packet)!=(128 if write else 60)or packet[0]!=0x45 or packet[9]!=17 or
            int.from_bytes(packet[2:4],'big')!=len(packet)or int.from_bytes(packet[6:8],'big')&0x3fff or
            packet[12:16]!=bytes([198,18,11,2])or packet[16:20]!=bytes([198,18,11,1])or
            int.from_bytes(packet[22:24],'big')!=4791 or int.from_bytes(packet[24:26],'big')!=len(packet)-20 or
            packet[26:28]!=b'\0\0'or packet[28]!=opcode or (packet[29]>>4)&3!=pad or (packet[29]&0xcf)!=0x40 or
            packet[30:32]!=b'\xff\xff'or packet[32]&0x3f or packet[36]&0x7f or
            int.from_bytes(packet[33:36],'big')!=196 or int.from_bytes(packet[37:40],'big')!=0xfffffe or
            int.from_bytes(packet[40:48],'big')!=REMOTE or int.from_bytes(packet[48:52],'big')!=0 or
            int.from_bytes(packet[52:56],'big')!=65 or packet[56:-4]!=payload+b'\0'*pad or
            wire.internet_checksum(packet[:20])or packet[-4:]!=wire.icrc_ipv4(packet)):
            raise ValueError('actual hardware-derived key0/VA64/PSN/payload/pad/checksum packet')
        rows=[json.loads(l[7:])for l in output.splitlines()if l.startswith('RESULT ')]
        if len(rows)!=1 or rows[0]['requests']!=1 or rows[0]['IP_packets']!=1:raise ValueError('actual HLS bounded summary')
        if before!={n:wire.delivery.digest(ROOT/n)for n in before}:raise ValueError('input changed during probe')
        report.update(pass_test=True,terminal_exit_status=0,summary=rows[0],packet_hex=packet.hex(),
            zero_remote_key_not_QP_fallback=True,full_remote_VA64_and_PSN_checked=True,
            payload_bytes_checked=65 if write else 0,IPv4_ICRC_checked=True,
            source_sha256_before_after_equal=True,four_state_simulation=True,
            simulation_seconds=identity['simulation_seconds'],simulation_timeout_seconds=120,
            original_multi_WR_bench_not_modified=True,new_finite_single_WR_owner_retained_case=True)
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error),terminal_exit_status=1);raise
    finally:
        wire.delivery.bounded.tempfile=previous
        report['artifact_sha256']={str(q.relative_to(ROOT)):wire.delivery.digest(q)for q in run.iterdir()if q.is_file()}
        with args.report.open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()
