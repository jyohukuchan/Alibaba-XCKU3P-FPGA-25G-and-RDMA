#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual message RQ + ACK lifetime + CQC publisher and host-ACK guard handoff.

Reuses ALL three actual ACK/EOF/receipt/tail and retained-RQ checks, then
connects real commit/retire to the actual CQ publisher (not manual success).
HLS/placement/MR/backend/PHY pins remain producer models; AXI host is modeled.
This is not live generated-HLS/native/PCIe/kernel/provider/physical proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import probe_receive_message_ack as base
import test_cq_path_rtl as host

ROOT=base.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_receive as graph
CQ=graph.RTL/'rocev2_cq_mmio.v';once=graph.once
AXI=[host.AXI/(n+'.v')for n in ['axil_reg_if','axil_reg_if_rd','axil_reg_if_wr']]
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def bench(ack):
    t=base.bench(ack)
    for width,n in [('', 'm_ticket_ready'),('[619:0] ', 's_commit_context'),('', 's_commit_valid'),
                    ('[619:0] ', 's_retire_context'),('', 's_retire_valid')]:
        t=once(t,'reg '+width+n+'=0;','wire '+width+n+';')
    t=once(t,'assign parent_fault=a_fault;','assign parent_fault=a_fault || c_fault;')
    declarations=r'''
reg allow_cq=0,allow_commit=0,allow_retire=0;
wire [747:0] c_commit_context,c_retire_context;
wire [7:0] c_commit_error,c_guard,c_fault_code;
wire c_commit_valid,c_retire_valid,c_ticket_ready,c_busy,c_fault;
wire [31:0] c_published,c_acked;
reg [11:0] host_awaddr=0,host_araddr=0;reg [2:0] host_awprot=0,host_arprot=0;
reg host_awvalid=0,host_wvalid=0,host_bready=0,host_arvalid=0,host_rready=0;
reg [31:0] host_wdata=0;reg [3:0] host_wstrb=0;
wire host_awready,host_wready,host_bvalid,host_arready,host_rvalid;
wire [1:0] host_bresp,host_rresp;wire [31:0] host_rdata;
assign m_ticket_ready=c_ticket_ready && allow_cq;
assign s_commit_context=c_commit_context[619:0];assign s_commit_valid=c_commit_valid && allow_commit;
assign s_retire_context=c_retire_context[619:0];assign s_retire_valid=c_retire_valid && allow_retire;
rocev2_cq_mmio #(.MESSAGE_ENABLE(1),.IMMEDIATE_ENABLE(1)) publisher(
 .clk(clk),.rst(rst),.parent_fault(fault || a_fault),
 .s_ticket_context({128'd0,m_ticket_context}),.s_ticket_valid(m_ticket_valid && allow_cq),.s_ticket_ready(c_ticket_ready),
 .s_ticket_received_bytes(m_ticket_received_bytes),.s_ticket_notification(m_ticket_notification),.s_ticket_notification_flags(m_ticket_notification_flags),
 .s_owner_cookie(64'd1),.s_owner_epoch(64'h9123456700000001),.s_owner_pd(16'd17),.s_owner_valid(1'b1),
 .m_commit_context(c_commit_context),.m_commit_error(c_commit_error),.m_commit_valid(c_commit_valid),.m_commit_ready(s_commit_ready && allow_commit),
 .m_retire_context(c_retire_context),.m_retire_valid(c_retire_valid),.m_retire_ready(s_retire_ready && allow_retire),
 .queue_guard(c_guard),.busy(c_busy),.fault(c_fault),.fault_code(c_fault_code),.published_count(c_published),.acknowledged_count(c_acked),
 .s_axil_awaddr(host_awaddr),.s_axil_awprot(host_awprot),.s_axil_awvalid(host_awvalid),.s_axil_awready(host_awready),
 .s_axil_wdata(host_wdata),.s_axil_wstrb(host_wstrb),.s_axil_wvalid(host_wvalid),.s_axil_wready(host_wready),
 .s_axil_bresp(host_bresp),.s_axil_bvalid(host_bvalid),.s_axil_bready(host_bready),
 .s_axil_araddr(host_araddr),.s_axil_arprot(host_arprot),.s_axil_arvalid(host_arvalid),.s_axil_arready(host_arready),
 .s_axil_rdata(host_rdata),.s_axil_rresp(host_rresp),.s_axil_rvalid(host_rvalid),.s_axil_rready(host_rready));
always @(posedge clk)if(!rst && c_fault)$fatal(1,"actual CQ publisher fault %h",c_fault_code);
'''
    tasks=host.HOST[host.HOST.index('integer host_deadline'):host.HOST.index('task cq_snapshot;')]
    t=once(t,'initial begin\n rst=1;',declarations+tasks+'initial begin\n rst=1;')
    start=t.index(' m_ticket_ready=1;tick;m_ticket_ready=0;s_commit_context=owner;s_commit_valid=1;')
    end=t.index(' $display("MESSAGE_ACK_RESULT ',start)
    t=t[:start]+r'''
 allow_cq=1;tick;allow_cq=0;
 cq_read(12'h00c,host_value);if(host_value!=2 || !c_commit_valid || c_retire_valid || c_published || !active ||
 c_commit_context!=={128'd0,owner} || c_commit_error || c_guard!==8'h80)$fatal(1,"actual CQ commit owner/backpressure");
 cq_read(12'h038,host_value);if(host_value)$fatal(1,"CQ bytes visible before commit");
 allow_commit=1;@(posedge clk);if(!s_commit_ready || !c_commit_valid)$fatal(1,"actual CQ/RQ commit handshake");
 @(negedge clk);allow_commit=0;
 repeat(7)begin tick;if(!active || queue_guard!==8'h80 || !c_retire_valid || c_retire_context!=={128'd0,owner} || c_published)$fatal(1,"CQ retire stall/full RQ owner");end
 cq_read(12'h01c,host_value);if(host_value)$fatal(1,"CQ proof before genuine RQ retire");
 allow_retire=1;@(posedge clk);if(!s_retire_ready || !c_retire_valid)$fatal(1,"actual CQ/RQ retire handshake");
 @(negedge clk);allow_retire=0;#1;
 if(active || queue_guard || a_busy || !c_busy || c_guard!==8'h80 || c_published!=1 || c_acked)$fatal(1,"RQ-to-CQ guard handoff until host ACK");
 cq_read(12'h008,host_value);if(host_value!=255)$fatal(1,"exact new CQC cohort ABI");
 cq_read(12'h00c,host_value);if(host_value!=3)$fatal(1,"real CQ visible after commit/retire");
 cq_read(12'h018,host_value);if(host_value!=1)$fatal(1,"one nonwrapping event sequence");
 cq_read(12'h01c,host_value);if(host_value!=15)$fatal(1,"actual CQ proof fields");
 cq_read(12'h038,host_value);if(host_value!=8193)$fatal(1,"actual bytes not posted capacity");
 cq_read(12'h03c,host_value);if(host_value!=1)$fatal(1,"CQ immediate flags");
 cq_read(12'h090,host_value);if(host_value!=32'h89abcdef)$fatal(1,"wire Immediate preserved");
 host_fd=$fopen("event.hex","w");
 for(host_i=0;host_i<20;host_i=host_i+1)begin
  cq_read(12'h040+host_i*4,host_value);
  if(host_value!==(({20'd0,owner}>>(host_i*32))&32'hffffffff))$fatal(1,"entire posted owner/capacity changed in CQ");
  $fdisplay(host_fd,"%08h",host_value);
 end
 for(host_i=0;host_i<4;host_i=host_i+1)begin
  cq_read(12'h0a0+host_i*4,host_value);if(host_value)$fatal(1,"unexpected Atomic extension in RECV CQ");
  $fdisplay(host_fd,"%08h",host_value);
 end
 $fclose(host_fd);
 repeat(17)begin tick;if(c_acked || c_published!=1 || c_guard!==8'h80 || !c_busy)$fatal(1,"host delay released CQ owner");end
 cq_ack(1);cq_read(12'h014,host_value);
 if(host_value!=1 || c_acked!=1 || c_published!=1 || c_guard || c_busy || active || queue_guard)$fatal(1,"exact host ACK guard release");
'''+t[end:]
    t=once(t,'MESSAGE_ACK_RESULT ','MESSAGE_CQ_ACK_RESULT ')
    return t


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    ack=base.candidate.derive();cq=graph.derive()[CQ]
    run=Path(tempfile.mkdtemp(prefix='receive-message-cq-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-message-cq-',dir='/dev/shm'))
    inputs=[base.QUEUE,base.ACK,CQ,*AXI,Path(__file__).resolve(),Path(base.__file__).resolve(),Path(host.__file__).resolve(),
        Path(base.native.__file__).resolve(),*list((ROOT/'rdma/rnic/fpga').glob('derive_*.py'))]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    shutil.copy2(base.QUEUE,run/base.QUEUE.name);(run/base.ACK.name).write_text(ack);(run/CQ.name).write_text(cq)
    (run/'tb.v').write_text(bench(ack))
    _,_,_,packet=base.native.case(True,True)
    for k in range(3):
        b=bytearray(packet);b[37:40]=((0xfffffe+k)&0xffffff).to_bytes(3,'big');b[41:44]=(1 if k==2 else 0).to_bytes(3,'big')
        b=base.native.qp.main.response.repair(b);frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+b
        (run/f'ack{k}.hex').write_text(''.join(f'{int.from_bytes(frame[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(frame),16)))
    command=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/base.QUEUE.name),str(run/base.ACK.name),str(run/CQ.name),*map(str,AXI)]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,compile_command=command,
        runtime_limit_seconds=10,four_state=True,actual_RQ_ACK_CQ_and_AXI_register_RTL=True,
        HLS_MR_DMA_upstream_PHY_and_host_boundaries_modeled=True,full_native_or_physical=False,hardware_verified=False)
    try:
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('actual RQ/ACK/CQ compile failed:'+str(run/'compile.log'))
        start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(c.stdout+c.stderr);result.update(exit=c.returncode,simulation_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('actual RQ/ACK/CQ failed:'+str(run/'simulation.log'))
        rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('MESSAGE_CQ_ACK_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual full coupled assertions missing')
        # Independently reconstruct EVERY immutable posted-owner bit in the
        # actual AXI reads. No observed record is rewritten or normalized.
        words=[int(s,16)for s in (run/'event.hex').read_text().splitlines()]
        expected=(0xf123456789abc001<<524)|(1<<460)|(0x9123456700000001<<396)|(7<<372)|(17<<356)|(1<<340)|(4<<324)|(1<<308)|(1048576<<276)|(0xf1234567<<244)|(0xfedcba9876543210<<180)|(0x210<<116)|3
        if len(words)!=24 or sum(v<<(32*i)for i,v in enumerate(words))!=expected:raise ValueError('full actual CQ context/capacity oracle')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during test')
        result.update(pass_test=True,source_unchanged=True,summary=rows[0],full_CQ_AXI_snapshot=True,
            actual_published_events=1,actual_host_ACKs=1,posted_capacity=1048576,actual_received_bytes=8193)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],simulation_seconds=result['simulation_seconds'],
        actual_published_events=1,host_ACKs=1,full_owner_snapshot=True)))


if __name__=='__main__':main()
