#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short FOUR-STATE test of actual generated timer-state fence RTL.

All eight entries, full tokens, FIFO ordering/backpressure, real1ms timeout,
full-width range/encoding fault. Timer-state OK while timeout remains HELD
proves this is NOT whole-core drain/MR/CQ permission. No hardware/board access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
TB=chr(96)+r'''timescale 1ns/1ps
module tb;
reg clk=0,rst=1;always #2 clk=~clk;
reg [175:0] rx_data=0;reg rx_valid=0;wire rx_ready;
reg [23:0] tx_data=0;reg tx_valid=0;wire tx_ready;
wire [239:0] fence_data;wire fence_valid;reg fence_ready=0;
wire [39:0] timeout_data;wire timeout_valid;reg timeout_ready=0;
as02_timer_fence_top dut(.ap_clk(clk),.ap_rst_n(!rst),
 .s_rx_TDATA(rx_data),.s_rx_TVALID(rx_valid),.s_rx_TREADY(rx_ready),
 .s_tx_TDATA(tx_data),.s_tx_TVALID(tx_valid),.s_tx_TREADY(tx_ready),
 .m_fence_TDATA(fence_data),.m_fence_TVALID(fence_valid),.m_fence_TREADY(fence_ready),
 .m_timeout_TDATA(timeout_data),.m_timeout_TVALID(timeout_valid),.m_timeout_TREADY(timeout_ready));
integer cycle=0,queries=0,deadline,q,i,n,block_count,timeout_start,timeout_cycles,timeouts_taken=0;
reg fs=0,ts=0;reg [239:0] held_fence,last_fence;reg [39:0] held_timeout;
reg stream_mode=0;integer stream_count=0;reg [239:0] replies[0:19];
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>2000000)$fatal(1,"finite timer RTL deadline");
 if(fs && (!fence_valid || fence_data!==held_fence))$fatal(1,"fence response changed under backpressure");
 if(ts && (!timeout_valid || timeout_data!==held_timeout))$fatal(1,"timeout retracted under backpressure");
 fs=fence_valid&&!fence_ready;held_fence=fence_data;
 ts=timeout_valid&&!timeout_ready;held_timeout=timeout_data;
 if(fence_valid && fence_ready)begin
  if((^fence_data)===1'bx || fence_data[239:238]!=0)$fatal(1,"unknown/noncanonical response");
  queries=queries+1;
  if(stream_mode)begin
   if(stream_count>=20)$fatal(1,"extra response");
   replies[stream_count]=fence_data;stream_count=stream_count+1;
  end
 end
 if(timeout_valid && timeout_ready)timeouts_taken=timeouts_taken+1;
end
function [175:0] request;
 input [15:0] qp;input stop,marker;input [23:0] psn;input [63:0] epoch,seq;
 begin request={6'd0,seq,epoch,psn,marker,stop,qp};end
endfunction
task rx;
 input [175:0] word;
 integer limit;
 begin
  @(negedge clk);rx_data=word;rx_valid=1;limit=cycle+3000;
  @(posedge clk);while(!rx_ready)begin if(cycle>limit)$fatal(1,"RX FIFO deadline");@(posedge clk);end
  @(negedge clk);rx_valid=0;
 end
endtask
task tx;
 input [23:0] qp;
 integer limit;
 begin
  @(negedge clk);tx_data=qp;tx_valid=1;limit=cycle+3000;
  @(posedge clk);while(!tx_ready)begin if(cycle>limit)$fatal(1,"TX queue deadline");@(posedge clk);end
  @(negedge clk);tx_valid=0;
 end
endtask
task receive;
 input [15:0] qp;input [23:0] psn;input [63:0] epoch,seq;input [7:0] status;
 begin
  deadline=cycle+3000;while(!fence_valid)begin if(cycle>deadline)$fatal(1,"fence deadline");@(negedge clk);end
  if(fence_data[15:0]!==qp || fence_data[39:16]!==psn || fence_data[103:40]!==epoch ||
   fence_data[167:104]!==seq || fence_data[175:168]!==status || (^fence_data)===1'bx)$fatal(1,"timer readback/token/status %h expected%h",fence_data,status);
  last_fence=fence_data;repeat(17)@(negedge clk);
  fence_ready=1;@(posedge clk);@(negedge clk);fence_ready=0;
 end
endtask
task query;
 input [15:0] qp;input [23:0] psn;input [63:0] epoch,seq;input [7:0] status;
 begin rx(request(qp,0,1,psn,epoch,seq));receive(qp,psn,epoch,seq,status);end
endtask
task inactive_snapshot;
 begin if(!last_fence[176] || last_fence[177] || last_fence[209:178] || last_fence[213:210])$fatal(1,"not actual inactive zero state");end
endtask
initial begin
 repeat(8)@(negedge clk);rst=0;repeat(64)@(negedge clk);
 for(q=0;q<8;q=q+1)begin
  tx(q);repeat(16)@(negedge clk);
  query(q,(24'hfffffe+q)&24'hffffff,64'hfedcba9876543210+q,64'he123456789abc001+q,2);
  if(!last_fence[176] || !last_fence[177] || last_fence[209:178]<31200 || last_fence[209:178]>31250 || last_fence[213:210])$fatal(1,"actual eight-entry timer state");
  rx(request(q,1,0,0,0,0));
  query(q,(24'hfffffe+q)&24'hffffff,64'hfedcba9876543210+q,64'he123456789abc101+q,0);inactive_snapshot();
 end
 // Later RX stop cannot overtake this marker's active-state snapshot.
 tx(2);repeat(16)@(negedge clk);
 rx(request(2,0,1,24'h123456,9,10));rx(request(2,1,0,0,0,0));receive(2,24'h123456,9,10,2);
 query(2,24'h123457,9,11,0);inactive_snapshot();
 // Fill output/FIFO ownership. While older snapshots are held, accept a TX
 // start through the REAL generated interface. The final marker must observe
 // the active timer; a queued start must not be hidden by output stalls.
 stream_mode=1;stream_count=0;
 fork
  begin for(i=0;i<20;i=i+1)rx(request(2,0,1,24'h900000+i,64'h9123456700000001,64'hf123456700000100+i));end
  begin
   block_count=0;deadline=cycle+3000;
   while(block_count<17)begin @(negedge clk);if(cycle>deadline)$fatal(1,"FIFO backpressure not exercised");if(rx_valid&&!rx_ready)block_count=block_count+1;else block_count=0;end
   tx(2);repeat(17)@(negedge clk);fence_ready=1;
  end
 join
 deadline=cycle+3000;while(stream_count!=20)begin if(cycle>deadline)$fatal(1,"stalled output drain deadline");@(negedge clk);end
 @(negedge clk);fence_ready=0;stream_mode=0;
 for(i=0;i<20;i=i+1)begin
  if(replies[i][15:0]!==16'd2 || replies[i][39:16]!==24'h900000+i ||
   replies[i][103:40]!==64'h9123456700000001 || replies[i][167:104]!==64'hf123456700000100+i ||
   (replies[i][175:168]!=0 && replies[i][175:168]!=2))$fatal(1,"lost/reordered FIFO token");
 end
 if(replies[19][175:168]!=2 || !replies[19][177])$fatal(1,"late pending TX start hidden");
 rx(request(2,1,0,0,0,0));query(2,1,9,12,0);inactive_snapshot();
 // No shortened timer: real 250MHz/eight-entry/1ms count.
 tx(2);timeout_start=cycle;deadline=cycle+1500000;
 while(!timeout_valid)begin if(cycle>deadline)$fatal(1,"actual timeout missing");@(negedge clk);end
 timeout_cycles=cycle-timeout_start;
 if(timeout_cycles<249000 || timeout_data!==40'd2)$fatal(1,"shortened/wrong timeout %0d/%h",timeout_cycles,timeout_data);
 query(2,24'hfffffe,64'h9123456700000001,64'hf123456700000001,2);
 if(last_fence[177] || last_fence[209:178] || last_fence[213:210]!=1)$fatal(1,"real timeout retry state missing");
 rx(request(2,1,0,0,0,0));query(2,24'hffffff,64'h9123456700000001,64'hf123456700000002,0);inactive_snapshot();
 // State-readback OK with a REAL outstanding, backpressured timeout. It is
 // emphatically NOT whole-core drain or MR/QP/CQ retirement permission.
 repeat(37)begin @(negedge clk);if(!timeout_valid || timeout_data!==40'd2 || timeouts_taken)$fatal(1,"state proof discarded pending timeout");end
 timeout_ready=1;@(posedge clk);@(negedge clk);timeout_ready=0;
 repeat(31)@(negedge clk);if(timeout_valid || timeouts_taken!=1)$fatal(1,"duplicate timeout");
 query(16'hffff,24'hffffff,64'hffffffffffffffff,64'hffffffffffffffff,1);
 if(last_fence[176])$fatal(1,"invalid QPN indexed a timer");
 query(2,0,0,5,3);query(2,0,5,0,3);
 tx(24'h010002);repeat(16)@(negedge clk);query(2,1,9,13,4);
 if(last_fence[237:214]!==24'h010002 || last_fence[177])$fatal(1,"full QPN truncated/aliased");
 rx(request(2,0,1,2,9,14)|(176'd1<<175));receive(2,2,9,14,4);
 if(last_fence[237:214]!==24'd2)$fatal(1,"reserved encoding not quarantined");
 $display("TIMER_FENCE_RTL {\"pass_test\":true,\"queries\":%0d,\"timer_entries\":8,\"timeout_cycles\":%0d,\"timeout_events\":%0d,\"real_timeout_held_after_timer_state_OK\":true,\"whole_core_drain\":false,\"cycles\":%0d}",queries,timeout_cycles,timeouts_taken,cycle);
 $finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-record',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    r=json.loads(a.source_record.read_text());assert r['pass_test'] and r['HLS_constructed']
    directory=ROOT/r['retained_directory'];rtl=directory/'project/solution1/syn/verilog'
    sources=sorted(rtl.glob('*.v'));data=sorted(rtl.glob('*.dat'))
    before={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in r['generated_sha256']}
    assert before==r['generated_sha256']
    own=[Path(__file__).resolve(),a.source_record.resolve()]
    inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in own}
    run=Path(tempfile.mkdtemp(prefix='timer-fence-RTL-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(TB)
    import shutil
    for d in data:shutil.copy2(d,run/d.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_record=str(a.source_record),source_sha256={**before,**inputs},bench_sha256=hashlib.sha256(TB.encode()).hexdigest(),
        actual_generated_HLS=True,four_state_simulation=True,whole_core_drain=False,hardware_verified=False,physical_signoff=False)
    try:
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('RTL compile failed; retain '+str(run))
        started=time.monotonic()
        s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        result['simulation_seconds']=time.monotonic()-started
        (run/'simulation.log').write_text(s.stdout+s.stderr)
        if s.returncode:raise RuntimeError('actual timer RTL failed; retain '+str(run))
        rows=[json.loads(l[len('TIMER_FENCE_RTL '):])for l in s.stdout.splitlines()if l.startswith('TIMER_FENCE_RTL ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing full RTL result')
        assert before=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}
        assert inputs=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in inputs}
        result.update(pass_test=True,terminal_exit_status=0,summary=rows[0])
    except Exception as e:result.update(terminal_exit_status=1,error=str(e),error_type=type(e).__name__);raise
    finally:
        result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
