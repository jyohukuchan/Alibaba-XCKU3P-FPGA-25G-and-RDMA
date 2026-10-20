#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual new per-WR metadata RTL: all2000entries/13fields/reset/append.

Preserves the earlier all-entry test's assertions, randomized backpressure,
16resets including interrupted sweeps,250000cycle bound and short wall bound.
Only the independently reviewed NEW generated C-struct packing is changed;
an unexpected generated port width is rejected, never inferred into a pass.
No warm-reset/RTL result is claimed until this runs on completed new HLS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

import probe_metadata_reset as baseline

ROOT = baseline.ROOT


def testbench_body():
    text = baseline.TB.replace('[319:0]', '[383:0]').replace('[447:0]', '[511:0]')
    function = '''function [383:0] entry;
 input integer index;
 reg [383:0] v;
 begin
  v=0;
  v[31:0]=index==0 ? 0 : (32'h89abcdef^(index*32'h9e3779b1));
  v[32]=(~index)&1;v[40]=(index>>1)&1;
  v[87:64]=24'hfedcba^index;v[111:96]=(index*17)^16'hcafe;
  v[159:128]=32'h89876543^index;
  v[255:192]=64'hfedcba9876543210^(index*64'h123456789);
  v[319:256]=64'h8102030405060708^(index*64'hfedcba987);
  v[351:320]=32'hfdb97531^index;v[352]=index&1;v[363:360]=index&15;
  v[368]=(index>>1)&1;v[376]=1;entry=v;
 end
endfunction'''
    text, count = re.subn(r'function \[383:0\] entry;.*?endfunction', function, text, flags=re.S)
    if count != 1:
        raise ValueError('unreviewed original testbench entry function')
    substitutions = {
        'r[383:64]=v;r[384]=1': 'r[447:64]=v;r[448]=1',
        'r[111:96]=next_index;r[392]=1': 'r[175:160]=next_index;r[456]=1',
        'value[47:32]': 'value[111:96]',
        'value[312]=0': 'value[376]=0',
    }
    for before, after in substitutions.items():
        if before not in text:
            raise ValueError('unreviewed original testbench packing: '+before)
        text = text.replace(before, after)
    return text.replace('SEQUENTIAL', '1')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence')
    rtl = args.hls_build.resolve()/'solution1/syn/verilog'
    module = rtl/'rocev2_top_retrans_meta_table_0_s.v'
    ports = re.findall(r'^(input|output)\s*(\[[^\]]+\])?\s+(\w+)\s*;', module.read_text(), re.M)
    widths = {n:w for _,w,n in ports}
    if widths.get('rt_metaReqFifo_dout') != '[511:0]' or widths.get('rt_metaRspFifo_din') != '[383:0]':
        raise ValueError('unreviewed per-WR generated metadata port packing')
    declarations = [f'{"reg" if d == "input" else "wire"} {w} {n}'+('=0;' if d == 'input' else ';') for d,w,n in ports]
    connections = [f'.{n}({n})' for _,_,n in ports]
    tb = ('`timescale 1ns/1ps\nmodule tb;\n'+'\n'.join(declarations)+'\n'+
          'rocev2_top_retrans_meta_table_0_s dut('+','.join(connections)+');\n'+
          testbench_body()+'\nendmodule\n')
    files = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    before = {p.name:digest(p) for p in files}
    aggregate = hashlib.sha256()
    for p in files: aggregate.update(p.name.encode()+b'\0'+p.read_bytes())
    sources = sorted(rtl.glob('rocev2_top_retrans_meta_table_0_s*.v'))
    own = {str(p.relative_to(ROOT)):digest(p) for p in
           [Path(__file__).resolve(), Path(baseline.__file__).resolve()]}
    run = Path(tempfile.mkdtemp(prefix='wrkey-metadata-rtl-', dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(tb)
    with (run/'compile.log').open('x') as log:
        subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(run/'test.vvp'),
                        str(run/'tb.v'), *map(str,sources)], cwd=rtl,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
    with (run/'simulation.log').open('x') as log:
        result = subprocess.run(['vvp', str(run/'test.vvp')], cwd=rtl,
                                stdout=log, stderr=subprocess.STDOUT, text=True, timeout=60)
    output = (run/'simulation.log').read_text()
    print(output, end='', flush=True)
    match = re.search(r'METADATA_RESET_PASS checks=(\d+) zero=(\d+) data=(\d+) append=(\d+) resets=(\d+) cycles=(\d+)', output)
    report = dict(scope=__doc__, hardware_verified=False, programming_authorized=False,
        directory=str(run), metadata_entries=2000, metadata_fields=13,
        sequential_initialization_required=True, four_state_simulation=True,
        source_sha256=own, generated_hls_sha256=aggregate.hexdigest(), generated_files=len(files),
        selected_RTL_sha256={p.name:before[p.name] for p in sources},
        generated_testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
        original_testbench_assertions_and_deadlines_preserved=True,
        terminal_exit_status=result.returncode,
        inputs_unchanged=before == {p.name:digest(p) for p in files} and
                         own == {p:digest(ROOT/p) for p in own})
    if match:
        report.update(dict(zip(['checks','zero_checks','data_checks','append_checks','reset_checks','cycles'],map(int,match.groups()))))
    report['pass_test'] = (result.returncode == 0 and report['inputs_unchanged'] and match is not None and
        [report[k] for k in ['checks','zero_checks','data_checks','append_checks','reset_checks']] == [8024,4023,2000,2001,16])
    report['artifact_sha256'] = {str(p.relative_to(ROOT)):digest(p) for p in
                                [run/'tb.v', run/'compile.log', run/'simulation.log']}
    with args.report.open('x') as out: out.write(json.dumps(report, indent=2)+'\n')
    if not report['pass_test']: raise SystemExit(1)


if __name__ == '__main__':
    main()
