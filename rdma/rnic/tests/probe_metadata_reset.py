#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite actual generated metadata-table RTL reset/storage/backpressure test.

All2000entries/allfields are checked through real FIFO ports. No internal
forcing, table replacement or RTL repair. This does NOT prove complete
transport/native/physical timing or authorize an image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]

TB = r'''
always #2 ap_clk=~ap_clk;
integer cycles=0, responses=0, expected_responses=0, checks=0;
integer i, j, start_cycle=0, expected_initial_delay=SEQUENTIAL;
integer reset_checks=0, zero_checks=0, data_checks=0, append_checks=0;
reg [319:0] expected_entry=0;
reg [31:0] rng=32'h750032ba;
reg [319:0] value;
reg [447:0] request;
always @(negedge ap_clk) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 rt_metaRspFifo_full_n=rng[2:0]!=0;
end
always @(posedge ap_clk) if(!ap_rst) begin
 cycles=cycles+1;
 if(cycles>250000) $fatal(1,"metadata total-cycle deadline");
 if(rt_metaRspFifo_write) begin
  if(!rt_metaRspFifo_full_n || responses>=expected_responses) $fatal(1,"unsolicited/blocked metadata response");
  if(rt_metaRspFifo_din!==expected_entry) $fatal(1,"metadata payload mismatch expected=%h actual=%h",expected_entry,rt_metaRspFifo_din);
  responses=responses+1;checks=checks+1;
 end
end
function [319:0] entry;
 input integer index;
 reg [319:0] v;
 begin
  v=0;v[23:0]=24'hfedcba^index;v[47:32]=(index*17)^16'hcafe;
  v[95:64]=32'h89876543^index;v[191:128]=64'hfedcba9876543210^(index*64'h123456789);
  v[255:192]=64'h8102030405060708^(index*64'hfedcba987);
  v[287:256]=32'hfdb97531^index;v[288]=index&1;v[299:296]=index&15;
  v[304]=(index>>1)&1;v[312]=1;entry=v;
 end
endfunction
task reset_table;
 input integer clocks;
 begin
  @(negedge ap_clk);ap_rst=1;ap_start=0;rt_metaReqFifo_empty_n=0;
  repeat(clocks)@(negedge ap_clk);
  ap_rst=0;ap_start=1;start_cycle=cycles;reset_checks=reset_checks+1;
 end
endtask
task send;
 input [447:0] req;
 integer deadline;
 begin
  @(negedge ap_clk);rt_metaReqFifo_dout=req;rt_metaReqFifo_empty_n=1;
  deadline=cycles+12000;
  @(posedge ap_clk);
  while(rt_metaReqFifo_read!==1) begin
   if(cycles>=deadline)$fatal(1,"metadata request deadline");
   @(posedge ap_clk);
  end
  if(expected_initial_delay && cycles-start_cycle<2000) $fatal(1,"request consumed before full metadata initialization");
  expected_initial_delay=0;
  @(negedge ap_clk);rt_metaReqFifo_empty_n=0;
 end
endtask
task write_entry;
 input integer index;
 input [319:0] v;
 reg [447:0] r;
 begin
  r=0;r[15:0]=index;r[383:64]=v;r[384]=1;send(r);
  // Separate transactions, preserving real generated pipeline retirement.
  repeat(6)@(negedge ap_clk);
 end
endtask
task read_entry;
 input integer index;
 input [319:0] v;
 reg [447:0] r;
 integer deadline;
 begin
  expected_entry=v;expected_responses=expected_responses+1;
  r=0;r[15:0]=index;send(r);deadline=cycles+12000;
  while(responses<expected_responses) begin
   if(cycles>=deadline)$fatal(1,"metadata response deadline");
   @(negedge ap_clk);
  end
  @(negedge ap_clk);
 end
endtask
task append_entry;
 input integer index,next_index;
 reg [447:0] r;
 begin
  r=0;r[15:0]=index;r[111:96]=next_index;r[392]=1;send(r);
  repeat(6)@(negedge ap_clk);
 end
endtask
initial begin
 ap_start=0;ap_continue=1;rt_metaReqFifo_fifo_cap=2;rt_metaReqFifo_num_data_valid=1;
 rt_metaRspFifo_fifo_cap=2;rt_metaRspFifo_num_data_valid=0;
 reset_table(1);
 // Queue the LAST entry immediately: no stale/unknown data may escape.
 read_entry(1999,0);zero_checks=zero_checks+1;
 for(i=0;i<2000;i=i+1)begin read_entry(i,0);zero_checks=zero_checks+1;end
 for(i=0;i<2000;i=i+1)begin write_entry(i,entry(i));end
 for(i=0;i<2000;i=i+1)begin read_entry(i,entry(i));data_checks=data_checks+1;end
 for(i=0;i<2000;i=i+1)begin
  append_entry(i,(i*31+7)%2000);value=entry(i);value[47:32]=(i*31+7)%2000;value[312]=0;
  read_entry(i,value);append_checks=append_checks+1;
 end
 expected_initial_delay=SEQUENTIAL;reset_table(8);
 read_entry(1999,0);zero_checks=zero_checks+1;
 for(i=0;i<2000;i=i+1)begin read_entry(i,0);zero_checks=zero_checks+1;end
 // An append to a never-written entry preserves zero for every other field.
 append_entry(999,1999);value=0;value[47:32]=1999;read_entry(999,value);append_checks=append_checks+1;
 for(j=0;j<7;j=j+1)begin
  write_entry(1999,entry(1999));
  reset_table(1);
  case(j)0:i=0;1:i=1;2:i=7;3:i=1998;4:i=1999;5:i=2000;default:i=2001;endcase
  repeat(i)@(negedge ap_clk);
  expected_initial_delay=SEQUENTIAL;reset_table(1);
  read_entry(1999,0);read_entry(0,0);read_entry(999,0);zero_checks=zero_checks+3;
 end
 repeat(16)@(negedge ap_clk);
 if(responses!=expected_responses)$fatal(1,"lost metadata responses");
 $display("METADATA_RESET_PASS checks=%0d zero=%0d data=%0d append=%0d resets=%0d cycles=%0d",checks,zero_checks,data_checks,append_checks,reset_checks,cycles);
 $finish;
end
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--sequential', action='store_true', help='require no request admission before2000initialization clocks')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence')
    rtl = args.hls_build.resolve()/'solution1/syn/verilog'
    module = rtl/'rocev2_top_retrans_meta_table_0_s.v'
    text = module.read_text()
    ports = re.findall(r'^(input|output)\s*(\[[^\]]+\])?\s+(\w+)\s*;', text, re.M)
    widths = {name: width for _, width, name in ports}
    if widths.get('rt_metaReqFifo_dout') != '[447:0]' or widths.get('rt_metaRspFifo_din') != '[319:0]':
        raise ValueError('unreviewed generated metadata port packing')
    declarations, connections = [], []
    for direction, width, name in ports:
        declarations.append(f'{"reg" if direction == "input" else "wire"} {width} {name}'+('=0;' if direction == 'input' else ';'))
        connections.append(f'.{name}({name})')
    tb = ('`timescale 1ns/1ps\nmodule tb;\n'+'\n'.join(declarations)+'\n'+
          'rocev2_top_retrans_meta_table_0_s dut('+','.join(connections)+');\n'+
          TB.replace('SEQUENTIAL', str(int(args.sequential)))+'\nendmodule\n')
    generated = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in generated}
    aggregate = hashlib.sha256()
    for p in generated:
        aggregate.update(p.name.encode()+b'\0'+p.read_bytes())
    sources = sorted(rtl.glob('rocev2_top_retrans_meta_table_0_s*.v'))
    with tempfile.TemporaryDirectory(prefix='as02-metadata-reset-') as directory:
        temp = Path(directory)
        (temp/'tb.v').write_text(tb)
        subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(temp/'test.vvp'), str(temp/'tb.v'),
                        *map(str, sources)], cwd=rtl, capture_output=True, text=True, check=True, timeout=30)
        result = subprocess.run(['vvp', str(temp/'test.vvp')], cwd=rtl, capture_output=True, text=True, timeout=60)
    print(result.stdout, end='', flush=True)
    print(result.stderr, end='', flush=True)
    match = re.search(r'METADATA_RESET_PASS checks=(\d+) zero=(\d+) data=(\d+) append=(\d+) resets=(\d+) cycles=(\d+)', result.stdout)
    unchanged = before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in generated}
    report = dict(scope=__doc__, hardware_verified=False, programming_authorized=False,
                  sequential_initialization_required=args.sequential, generated_hls_sha256=aggregate.hexdigest(),
                  generated_files=len(generated), source_sha256={str(Path(__file__).resolve().relative_to(ROOT)):
                  hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                  selected_RTL_sha256={p.name: before[p.name] for p in sources},
                  generated_testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(), inputs_unchanged=unchanged,
                  terminal_exit_status=result.returncode, stdout=result.stdout, stderr=result.stderr)
    if match:
        report.update(dict(zip(['checks', 'zero_checks', 'data_checks', 'append_checks', 'reset_checks', 'cycles'], map(int, match.groups()))))
    report['pass_test'] = result.returncode == 0 and match is not None and unchanged
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2)+'\n')
    if not report['pass_test']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
