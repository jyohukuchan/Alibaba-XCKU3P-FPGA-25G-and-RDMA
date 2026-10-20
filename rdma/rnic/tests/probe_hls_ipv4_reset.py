#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Characterize actual generated IPv4 static construction across clocked resets.

No header repair, forced internal state, transport stub, or hardware access.
This narrow state-level test is not the full HLS/PCIe/wire integration gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--expect-defect', action='store_true', help='characterize old broken candidate, not a release pass')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve evidence: choose a new report')
    rtl = args.hls_build.resolve() / 'solution1/syn/verilog'
    path = rtl / 'rocev2_top_ipv4_generate_ipv4_512_s.v'
    text = path.read_text()
    guard = re.findall(r'^reg\s+\[0:0\]\s+(guard_variable_for_void_ipv4_generate_ipv4_stream_stream_stream_ap_uint_ap_ui);', text, re.M)
    if len(guard) != 1 or 'header_header_2' not in text or 'gi_state' not in text:
        raise ValueError('unreviewed generated IPv4 state layout')
    declarations, connections = [], []
    for direction, width, name in re.findall(r'^(input|output)\s*(\[[^\]]+\])?\s+(\w+)\s*;', text, re.M):
        declarations.append(f'{"reg" if direction == "input" else "wire"} {width} {name}' + ('=0;' if direction == 'input' else ';'))
        connections.append(f'.{name}({name})')
    tb = '\n'.join(declarations) + '\nrocev2_top_ipv4_generate_ipv4_512_s dut(' + ','.join(connections) + ');\n'
    tb += r'''
always #2 ap_clk=~ap_clk;
integer delay_cycles, reset_cycles, pulse;
initial begin
 if(!$value$plusargs("DELAY=%d",delay_cycles))$fatal;
 if(!$value$plusargs("RESET=%d",reset_cycles))$fatal;
 ap_start=1;ap_continue=1;tx_ip2crcFifo_full_n=1;
 // This generated dataflow block has a blocking local-IP scalar FIFO read
 // before the nonblocking metadata check. Model that constant source too.
 local_ip_address_empty_n=1;local_ip_address_num_data_valid=1;local_ip_address_fifo_cap=2;
 // No input metadata/payload. Only the actual static constructor can write
 // its fixed IPv4 fields; no testbench assignment to any DUT internal state.
 if(delay_cycles==0)begin #1;ap_rst=1;ap_start=0;end
 else begin repeat(delay_cycles)@(negedge ap_clk);ap_rst=1;ap_start=0;end
 repeat(reset_cycles)@(negedge ap_clk);ap_rst=0;ap_start=1;
 repeat(64)@(negedge ap_clk);
 $display("RESET_STATE %0d %0d %h %h %h %h",delay_cycles,reset_cycles,
          dut.header_header_2[7:0],dut.header_header_2[71:64],dut.gi_state,dut.GUARD);
 // Repeated warm resets must also reconstruct, without a bitstream reload.
 for(pulse=0;pulse<3;pulse=pulse+1)begin
  ap_rst=1;ap_start=0;repeat(reset_cycles)@(negedge ap_clk);ap_rst=0;ap_start=1;
  repeat(64)@(negedge ap_clk);
  $display("WARM_STATE %0d %0d %h %h %h %h",delay_cycles,reset_cycles,
           dut.header_header_2[7:0],dut.header_header_2[71:64],dut.gi_state,dut.GUARD);
 end
 $finish;
end
'''.replace('GUARD', guard[0])
    tb = '`timescale 1ns/1ps\nmodule tb;\n' + tb + '\nendmodule\n'
    generated = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in generated}
    aggregate = hashlib.sha256()
    for p in generated:
        aggregate.update(p.name.encode() + b'\0' + p.read_bytes())
    rows = []
    with tempfile.TemporaryDirectory(prefix='as02-ipv4-reset-') as directory:
        temp = Path(directory)
        (temp / 'tb.v').write_text(tb)
        subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(temp / 'test.vvp'),
                        str(temp / 'tb.v'), str(path)], capture_output=True, text=True, check=True, timeout=30)
        for delay in [*range(9), 16, 64]:
            for reset in [1, 8]:
                result = subprocess.run(['vvp', str(temp / 'test.vvp'), f'+DELAY={delay}', f'+RESET={reset}'],
                                        capture_output=True, text=True, check=True, timeout=5)
                print(result.stdout, end='', flush=True)
                seen = []
                for line in result.stdout.splitlines():
                    if not line.startswith(('RESET_STATE ', 'WARM_STATE ')):
                        continue
                    kind, d, r, version, ttl, state, flag = line.split()
                    row = dict(kind=kind, delay_cycles=int(d), reset_cycles=int(r),
                               version_IHL_hex=version, TTL_hex=ttl, state_hex=state, ctor_flag_hex=flag,
                               valid=(version == '45' and ttl == '64' and int(state, 16) == 0 and flag == '1'))
                    seen.append(row)
                if len(seen) != 4:
                    raise ValueError('missing reset-state observations')
                rows.extend(seen)
    if before != {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in generated}:
        raise ValueError('HLS inputs changed during characterization')
    defects = [r for r in rows if not r['valid']]
    if args.expect_defect:
        matches = (any(r['delay_cycles'] > 0 and r['reset_cycles'] == 8 and
                       r['version_IHL_hex'] == '00' and r['TTL_hex'] == '00' and r['ctor_flag_hex'] == '1'
                       for r in defects) and all(r['valid'] for r in rows if r['delay_cycles'] == 0))
    else:
        matches = not defects
    report = dict(scope=__doc__, characterization_pass=matches, release_reset_gate_pass=not defects,
                  expected_old_defect=args.expect_defect, hardware_verified=False,
                  generated_hls_sha256=aggregate.hexdigest(), generated_files=len(generated),
                  selected_module_sha256=before[path.name], observations=rows,
                  invalid_observations=len(defects), total_observations=len(rows),
                  source_sha256={str(Path(__file__).resolve().relative_to(ROOT)):
                                 hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'observations'}, indent=2))
    if not matches:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
