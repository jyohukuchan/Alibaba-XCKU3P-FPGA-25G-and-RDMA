#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only generated-RTL monitors, not a passing functional proof."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import probe_timer_state_fence_rtl as probe

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-record',type=Path,required=True)
    p.add_argument('--reset-edge',action='store_true')
    a=p.parse_args();r=json.loads(a.source_record.read_text())
    rtl=probe.ROOT/r['retained_directory']/'project/solution1/syn/verilog'
    before={n:hashlib.sha256((probe.ROOT/n).read_bytes()).hexdigest()for n in r['generated_sha256']}
    assert before==r['generated_sha256']
    run=Path(tempfile.mkdtemp(prefix='timer-fence-diagnosis-',dir=probe.ROOT/'rdma/rnic/build'))
    monitor='''
always @(negedge clk)if(cycle>=60 && cycle<145)begin
 $display("DIAG c=%0d rx=%b/%b update=%b/%b/%b tx=%b/%b pending=%b readback=%b/%b/%b out=%b/%b reset=%b fifo=%b/%b/%b/%h clk=%b",
 cycle,rx_valid,rx_ready,dut.timer_fence_decode_U0_updates_write,dut.updates_empty_n,
 dut.as02_timer_state_fence_consumer_42_U0_updates_read,tx_valid,tx_ready,
 dut.as02_timer_state_fence_consumer_42_U0.fence_pending,
 dut.as02_timer_state_fence_consumer_42_U0_readbacks_write,dut.readbacks_empty_n,
 dut.timer_fence_encode_U0_readbacks_read,fence_valid,fence_ready,dut.ap_rst_n_inv,
 dut.updates_U.push,dut.updates_U.pop,dut.updates_U.empty_n,dut.updates_U.mOutPtr,dut.updates_U.clk);
end
'''
    bench=probe.TB.replace('initial begin\n repeat(8)',monitor+'\ninitial begin\n repeat(8)')
    if a.reset_edge:
        bench=bench.replace('reg clk=0,rst=1;','reg clk=0,rst=0;').replace('initial begin\n repeat(8)','initial begin\n @(negedge clk);rst=1;repeat(8)')
    assert bench!=probe.TB
    (run/'tb.v').write_text(bench)
    compile_cmd=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sorted(rtl.glob('*.v'))) ]
    c=subprocess.run(compile_cmd,capture_output=True,text=True,timeout=30)
    (run/'compile.log').write_text(c.stdout+c.stderr)
    if c.returncode:raise RuntimeError(c.stderr)
    s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
    (run/'simulation.log').write_text(s.stdout+s.stderr)
    assert before=={n:hashlib.sha256((probe.ROOT/n).read_bytes()).hexdigest()for n in before}
    print(json.dumps(dict(scope=__doc__,directory=str(run),diagnostic_exit=s.returncode,not_a_passing_test=True)))
    print(s.stdout+s.stderr)

if __name__=='__main__':main()
