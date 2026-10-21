#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Every actual CRC mask equals the unchanged vendor function result.

The original LFSR function and every output XOR are retained. The helper
memoizes that same function's index-independent prefix and selects all
indices at compile time. Compare EVERY state/data output mask for the four
exact production CRC widths, not sampled payloads or a Python CRC model.
Identical masks plus identical XORs retain all four-state input behavior.
This host simulation acceleration does not change any hardware source,
cycle/clock/timeout/assertion, polynomial, parameter, port or checksum gate.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import probe_segmented_write_rx_frontend as frontend

ROOT=frontend.ROOT;digest=frontend.digest
TB=r'''
module tb;
parameter DATA_WIDTH=32;
localparam MASK_WIDTH=32+DATA_WIDTH;
integer index=0;
wire [31:0] state_out;wire [DATA_WIDTH-1:0] data_out;
reg [MASK_WIDTH-1:0] original;
lfsr #(.LFSR_WIDTH(32),.LFSR_POLY(32'h04c11db7),.LFSR_CONFIG("GALOIS"),
 .LFSR_FEED_FORWARD(0),.REVERSE(1),.DATA_WIDTH(DATA_WIDTH),.STYLE("REDUCTION")) dut(
 .state_in(32'd0),.data_in({DATA_WIDTH{1'b0}}),.state_out(state_out),.data_out(data_out));
initial begin
 if(!$value$plusargs("INDEX=%d",index) || index<0 || index>=MASK_WIDTH)$fatal(1,"all exact mask indices required");
 original=dut.lfsr_mask(index);
 if(original!==dut.constant_masks[index*MASK_WIDTH+:MASK_WIDTH])$fatal(1,"original complete vendor mask mismatch");
 $display("CONSTANT_MASK_RESULT {\"pass_test\":true,\"data_width\":%0d,\"index\":%0d,\"mask_bits\":%0d}",DATA_WIDTH,index,MASK_WIDTH);
 $finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    run=Path(tempfile.mkdtemp(prefix='CRC-constant-mask-proof-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-CRC-constant-mask-proof-',dir='/dev/shm'))
    original=frontend.LFSR.read_text();derived=frontend.compiletime_lfsr()
    start=original.index('function [LFSR_WIDTH+DATA_WIDTH-1:0] lfsr_mask(')
    end=original.index('endfunction',start)+len('endfunction')
    if derived.count(original[start:end])!=1:raise ValueError('unchanged complete vendor reference function required')
    before={str(n.relative_to(ROOT)):digest(n)for n in [Path(__file__).resolve(),Path(frontend.__file__).resolve(),frontend.LFSR]}
    (run/'lfsr.v').write_text(derived);(run/'tb.v').write_text(TB)
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        tests={},compile_limit_seconds=10,case_limit_seconds=10,exact_data_widths=[32,64,96,128],
        unchanged_vendor_function_is_actual_reference=True,all_state_and_data_output_masks_checked=True,
        parameters=dict(LFSR_WIDTH=32,LFSR_POLY='04c11db7',LFSR_CONFIG='GALOIS',LFSR_FEED_FORWARD=0,REVERSE=1,STYLE='REDUCTION'),
        production_or_vendor_sources_changed=False,hardware_verified=False)
    try:
        result['compile_commands']=[]
        for width in result['exact_data_widths']:
            binary=ram/str(width);command=['iverilog','-g2012','-s','tb','-Ptb.DATA_WIDTH='+str(width),'-o',str(binary),str(run/'tb.v'),str(run/'lfsr.v')]
            result['compile_commands'].append(command)
            c=subprocess.run(command,capture_output=True,text=True,timeout=10)
            (run/(str(width)+'-compile.log')).write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError('constant mask proof compile failed')
            for index in range(32+width):
                key=str(width)+'-'+str(index);start=time.monotonic()
                c=subprocess.run(['vvp',str(binary),'+INDEX='+str(index)],capture_output=True,text=True,timeout=10)
                (run/(key+'.log')).write_text(c.stdout+c.stderr)
                t=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][key]=t
                if c.returncode:raise ValueError('actual unchanged vendor mask differs:'+key)
                rows=[json.loads(l.split(' ',1)[1])for l in c.stdout.splitlines()if l.startswith('CONSTANT_MASK_RESULT ')]
                if rows!=[dict(pass_test=True,data_width=width,index=index,mask_bits=32+width)]:raise ValueError('exact complete mask result missing')
                t['summary']=rows[0]
        if len(result['tests'])!=448 or any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('all448 exact masks and unchanged input required')
        result.update(pass_test=True,source_unchanged=True,coefficients_compared=sum((32+w)**2 for w in [32,64,96,128]))
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,masks=448,coefficient_bits=result['coefficients_compared'],maximum_seconds=max(t['seconds']for t in result['tests'].values()),hardware_sources_changed=False)),flush=True)


if __name__=='__main__':main()
