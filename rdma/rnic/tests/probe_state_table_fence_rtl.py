#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated FOUR-STATE state-table rendezvous, not whole-core drain.

All eight entries and three ordered producer markers, normal table outputs,
late writes, missing markers, snapshot stability, full tokens/invalid inputs.
Actual normal response remains held after state OK: no CQ/drain inference.
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
reg clk=0,rst=0;always #2 clk=~clk;
reg [223:0] data[0:2];reg [2:0] valid=0;wire [2:0] ready;
wire [79:0] rxdata;wire rxvalid;reg rxready=0;
wire [127:0] txdata,qpidata;wire txvalid,qpivalid;reg txready=0,qpiready=0;
wire [335:0] fdata;wire fvalid;reg fready=0;
as02_state_fence_top dut(.ap_clk(clk),.ap_rst_n(!rst),
 .s_rx_TDATA(data[0]),.s_rx_TVALID(valid[0]),.s_rx_TREADY(ready[0]),
 .s_tx_TDATA(data[1]),.s_tx_TVALID(valid[1]),.s_tx_TREADY(ready[1]),
 .s_qpi_TDATA(data[2]),.s_qpi_TVALID(valid[2]),.s_qpi_TREADY(ready[2]),
 .m_rx_TDATA(rxdata),.m_rx_TVALID(rxvalid),.m_rx_TREADY(rxready),
 .m_tx_TDATA(txdata),.m_tx_TVALID(txvalid),.m_tx_TREADY(txready),
 .m_qpi_TDATA(qpidata),.m_qpi_TVALID(qpivalid),.m_qpi_TREADY(qpiready),
 .m_fence_TDATA(fdata),.m_fence_TVALID(fvalid),.m_fence_TREADY(fready));
integer cycle=0,queries=0,q,i,limit,stalled=0,burst_start,burst_cycles,burst_writes=0;reg [335:0] last,held;
reg [79:0] rxheld;reg [127:0] txheld,qpiheld;
reg fs=0,rs=0,ts=0,qs=0,stream_mode=0;integer n=0;
reg [335:0] replies[0:19];
reg [23:0] p,l;reg [63:0] epoch,seq;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>20000)$fatal(1,"finite state-table deadline");
 if(fs && (!fvalid || fdata!==held))$fatal(1,"fence changed under stall");
 if(rs && (!rxvalid || rxdata!==rxheld))$fatal(1,"RX response changed under stall");
 if(ts && (!txvalid || txdata!==txheld))$fatal(1,"TX response changed under stall");
 if(qs && (!qpivalid || qpidata!==qpiheld))$fatal(1,"QPI response changed under stall");
 fs=fvalid&&!fready;held=fdata;rs=rxvalid&&!rxready;rxheld=rxdata;
 ts=txvalid&&!txready;txheld=txdata;qs=qpivalid&&!qpiready;qpiheld=qpidata;
 if(fvalid&&fready)begin
  if((^fdata)===1'bx || fdata[335:321]!==0 || fdata[179:177]!==7)$fatal(1,"unknown/noncanonical fence");
  queries=queries+1;
  if(stream_mode)begin if(n>=20)$fatal(1,"duplicate readback");replies[n]=fdata;n=n+1;end
 end
end
function [223:0] request;
 input [15:0] qp;input [23:0] a,b;input [2:0] rc;input wr,rsp,marker;input [63:0] e,s;
 begin request={23'd0,3'd0,s,e,marker,rsp,wr,rc,b,a,qp};end
endfunction
function [223:0] marker;
 input [15:0] qp;input [23:0] psn;input [63:0] e,s;
 begin marker=request(qp,psn,0,0,0,0,1,e,s);end
endfunction
function integer producer;
 input integer order,step;reg [5:0] perm;
 begin
  case(order%6)
   0:perm=6'b10_01_00;1:perm=6'b01_10_00;2:perm=6'b10_00_01;
   3:perm=6'b00_10_01;4:perm=6'b01_00_10;5:perm=6'b00_01_10;
  endcase
  producer=(perm>>(2*step))&3;
 end
endfunction
task send;
 input integer source;input [223:0] word;integer deadline;
 begin
  @(negedge clk);data[source]=word;valid[source]=1;deadline=cycle+3000;
  @(posedge clk);while(!ready[source])begin if(cycle>deadline)$fatal(1,"producer deadline %0d",source);@(posedge clk);end
  @(negedge clk);valid[source]=0;
 end
endtask
task burst_tx;
 integer j,deadline;
 begin
  @(negedge clk);valid[1]=1;burst_start=cycle;deadline=cycle+3000;
  for(j=0;j<8;j=j+1)begin
   data[1]=request(2,101+j,0,0,1,0,0,0,0);
   @(posedge clk);while(!ready[1])begin if(cycle>deadline)$fatal(1,"ordinary burst deadline");@(posedge clk);end
   burst_writes=burst_writes+1;@(negedge clk);
  end
  valid[1]=0;burst_cycles=cycle-burst_start;
 end
endtask
task receive;
 input [15:0] qp;input [23:0] psn;input [63:0] e,s;input [7:0] status;integer deadline;
 begin
  deadline=cycle+3000;while(!fvalid)begin if(cycle>deadline)$fatal(1,"rendezvous response missing");@(negedge clk);end
  if(fdata[15:0]!==qp || fdata[39:16]!==psn || fdata[103:40]!==e || fdata[167:104]!==s ||
   fdata[175:168]!==status || (^fdata)===1'bx)$fatal(1,"wrong token/status %h expected%h",fdata,status);
  last=fdata;repeat(17)@(negedge clk);fready=1;@(posedge clk);@(negedge clk);fready=0;
 end
endtask
task query;
 input [15:0] qp;input [23:0] psn;input [63:0] e,s;input [7:0] status;input integer order;
 begin
  send(producer(order,0),marker(qp,psn,e,s));repeat(17)begin @(negedge clk);if(fvalid)$fatal(1,"missing second/third marker falsely certified");end
  send(producer(order,1),marker(qp,psn,e,s));repeat(17)begin @(negedge clk);if(fvalid)$fatal(1,"missing third marker falsely certified");end
  send(producer(order,2),marker(qp,psn,e,s));receive(qp,psn,e,s,status);
 end
endtask
task state;
 input [23:0] resp,old,next,unack,oldvalid;input [2:0] rc;
 begin
  if(!last[176] || last[203:180]!==resp || last[227:204]!==old || last[251:228]!==next ||
   last[275:252]!==unack || last[299:276]!==oldvalid || last[302:300]!==rc)$fatal(1,"wrong actual BRAM table state %h",last);
 end
endtask
initial begin
 for(i=0;i<3;i=i+1)data[i]=0;
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;repeat(64)@(negedge clk);
 query(7,24'hffffff,64'hffffffffffffffff,64'hffffffffffffffff,5,0);
 if(last[176] || last[302:180]!==0)$fatal(1,"uninitialized BRAM fabricated a snapshot");
 for(q=0;q<8;q=q+1)begin
  p=24'hfffffe+q;l=24'h912345+q;epoch=64'hf123456789abc001+q;seq=64'he123456789abc001+q;
  send(2,request(q,p,l,0,1,0,0,0,0));
  query(q,p,epoch,seq,0,q);state(l,l,p,p,p,7);
  send(1,request(q,p+24'd1,0,0,1,0,0,0,0));
  query(q,p,epoch,seq+64'h100,2,q+1);state(l,l,p+24'd1,p,p,7);
  send(0,request(q,p+24'd1,0,0,1,1,0,0,0));
  send(0,request(q,l+24'd1,0,q&7,1,0,0,0,0));
  query(q,p,epoch,seq+64'h200,0,q+2);state(l+24'd1,l,p+24'd1,p+24'd1,p,q&7);
 end
 // Normal reads use the actual original RX/TX/QPI outputs. Keep all three
 // responses backpressured while table-state OK is returned: NOT core drain.
 send(0,request(2,0,0,0,0,1,0,0,0));send(1,request(2,0,0,0,0,0,0,0,0));send(2,request(2,0,0,0,0,0,0,0,0));
 query(2,24'habcdef,9,10,0,2);
 if(!rxvalid || !txvalid || !qpivalid || rxdata!=={8'd0,24'd0,24'd0,24'd1} ||
  txdata!==qpidata || txdata[71:48]!==24'd1 || (^txdata)===1'bx)$fatal(1,"normal response lost/uninitialized");
 repeat(37)begin @(negedge clk);if(!rxvalid || !txvalid || !qpivalid)$fatal(1,"state OK incorrectly drained normal outputs");end
 rxready=1;txready=1;qpiready=1;@(posedge clk);@(negedge clk);rxready=0;txready=0;qpiready=0;
 // Later RX ACK cannot overtake its marker; late TX update before its OWN
 // marker must affect the snapshot. Missing TX marker withheld above.
 send(0,marker(2,24'hffffff,64'h923456789abcdef0,64'hf23456789abcdef0));
 send(0,request(2,77,0,0,1,1,0,0,0));
 send(1,request(2,77,0,0,1,0,0,0,0));send(1,marker(2,24'hffffff,64'h923456789abcdef0,64'hf23456789abcdef0));
 repeat(17)begin @(negedge clk);if(fvalid)$fatal(1,"missing QPI marker incorrectly certified");end
 send(2,marker(2,24'hffffff,64'h923456789abcdef0,64'hf23456789abcdef0));receive(2,24'hffffff,64'h923456789abcdef0,64'hf23456789abcdef0,2);
 if(last[251:228]!==24'd77 || last[275:252]!==24'd1)$fatal(1,"late producer write/later RX ordering lost");
 query(2,0,9,11,0,3);if(last[251:228]!==24'd77 || last[275:252]!==24'd77)$fatal(1,"held RX never applied");
 // Continuous VALID exercises the normal dispatch register and real BRAM
 // WAW/RAW dependencies, rather than one idle-separated request per call.
 burst_tx();send(0,request(2,108,0,0,1,1,0,0,0));query(2,6,9,20,0,4);
 if(burst_writes!=8 || last[251:228]!==24'd108 || last[275:252]!==24'd108)$fatal(1,"ordinary burst lost/reordered state writes");
 send(1,request(2,77,0,0,1,0,0,0,0));send(0,request(2,77,0,0,1,1,0,0,0));query(2,7,9,21,0,5);
 // Fill real FIFOs/output registers with20successive full tokens and confirm
 // input backpressure, stable held snapshots and lossless ordered drain.
 stream_mode=1;n=0;
 fork
  begin for(i=0;i<20;i=i+1)begin
   send(0,marker(2,24'h900000+i,64'hf234567800000001,64'he234567800000100+i));
   send(1,marker(2,24'h900000+i,64'hf234567800000001,64'he234567800000100+i));
   send(2,marker(2,24'h900000+i,64'hf234567800000001,64'he234567800000100+i));
  end end
  begin
   stalled=0;limit=cycle+3000;
   while(stalled<17)begin @(negedge clk);if(cycle>limit)$fatal(1,"input stalls not exercised");if((|(valid&~ready)))stalled=stalled+1;else stalled=0;end
   fready=1;
  end
 join
 limit=cycle+3000;while(n!=20)begin if(cycle>limit)$fatal(1,"backpressure lost replies");@(negedge clk);end
 @(negedge clk);fready=0;stream_mode=0;
 for(i=0;i<20;i=i+1)begin
  if(replies[i][15:0]!==16'd2 || replies[i][39:16]!==24'h900000+i ||
   replies[i][103:40]!==64'hf234567800000001 || replies[i][167:104]!==64'he234567800000100+i ||
   replies[i][175:168]!==0 || replies[i][251:228]!==24'd77 || replies[i][275:252]!==24'd77)$fatal(1,"lost/reordered snapshot");
 end
 query(16'hffff,0,9,12,1,4);if(last[176])$fatal(1,"out of range indexed table");
 query(16'h0102,0,9,13,1,5);if(last[176])$fatal(1,"high QPN aliased to2");
 query(2,0,0,14,3,0);query(2,0,9,0,3,1);
 send(0,marker(2,1,9,15));send(1,marker(2,1,9,64'h800000000000000f));send(2,marker(2,1,9,15));receive(2,1,9,15,4);
 if(last[304:303]!==2'd1 || last[320:305]!==16'd2)$fatal(1,"high64-bit nonce mismatch hidden");
 send(0,marker(2,2,9,16)|(224'd1<<223));send(1,marker(2,2,9,16));send(2,marker(2,2,9,16));receive(2,2,9,16,4);
 if(last[304:303]!==0 || last[320:305]!==16'd2)$fatal(1,"reserved encoding hidden");
 // Full-width ordinary table requests are checked BEFORE indexing as well.
 send(0,request(16'hffff,100,0,0,1,1,0,0,0));query(2,3,9,17,4,2);
 if(last[304:303]!==0 || last[320:305]!==16'hffff || last[251:228]!==24'd77 || last[275:252]!==24'd77)$fatal(1,"normal RX QPN range/alias");
 send(1,request(16'h0102,100,0,0,1,0,0,0,0));query(2,4,9,18,4,3);
 if(last[304:303]!==1 || last[320:305]!==16'h0102 || last[251:228]!==24'd77 || last[275:252]!==24'd77)$fatal(1,"normal TX QPN range/alias");
 send(2,request(16'hffff,100,100,0,1,0,0,0,0));query(2,5,9,19,4,4);
 if(last[304:303]!==2 || last[320:305]!==16'hffff || last[251:228]!==24'd77 || last[275:252]!==24'd77)$fatal(1,"normal QPI QPN range/alias");
 $display("STATE_FENCE_RTL {\"pass_test\":true,\"queries\":%0d,\"table_entries\":8,\"ordered_producers\":3,\"ordinary_burst_writes\":%0d,\"ordinary_burst_handshake_cycles\":%0d,\"actual_normal_outputs_held_after_state_OK\":true,\"whole_core_drain\":false,\"cycles\":%0d}",queries,burst_writes,burst_cycles,cycle);
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
    run=Path(tempfile.mkdtemp(prefix='state-fence-RTL-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(TB)
    import shutil
    shutil.copy2(Path(__file__).resolve(),run/'driver.py')
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
        if s.returncode:raise RuntimeError('actual state-table RTL failed; retain '+str(run))
        rows=[json.loads(l[len('STATE_FENCE_RTL '):])for l in s.stdout.splitlines()if l.startswith('STATE_FENCE_RTL ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual RTL result')
        assert before=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}
        assert inputs=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in inputs}
        result.update(pass_test=True,terminal_exit_status=0,summary=rows[0])
    except Exception as e:result.update(terminal_exit_status=1,error=str(e),error_type=type(e).__name__);raise
    finally:
        result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
