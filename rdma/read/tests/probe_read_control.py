#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real READ controller -> generated HLS -> protected RAM -> host RTL port.

Checks DONE follows actual RAM commitment and transport reset follows DONE.
This is not a PCIe app, physical MAC completion, or native RNIC test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import probe_read_capture as capture

ROOT = capture.ROOT
base = capture.base
replace = capture.replace_once
ENGINE_RTL = ROOT / 'rdma/read/rtl/rocev2_read_engine.v'

ENGINE = r'''
reg engine_start=0,boot_phase=1;
wire engine_ready,engine_done,engine_failed,engine_core_reset,engine_halt,engine_rx,engine_busy;
wire engine_capture_clear,engine_ack_ready,buffer_host_idle;
wire [3:0] engine_state;
wire [31:0] engine_error,engine_issued,engine_acked,engine_total,engine_lease;
wire [63:0] engine_elapsed;
wire [183:0] engine_qp,engine_conn;
wire [239:0] engine_sq;
wire transport_reset=boot_phase ? rst : engine_core_reset;
wire modeled_tx_quiet=tx_frames==0 || cycle>tx_end+64;
integer observed_rx_good=0,observed_tx_good=0;
rocev2_read_engine controller (
 .clk(clk),.rst(rst),.start(engine_start),.clear(1'b0),.abort_run(1'b0),.start_ready(engine_ready),
 .cfg_local_qpn(24'd2),.cfg_peer_qpn(24'd196),.cfg_tx_psn(24'hfffffe),.cfg_peer_psn(24'h987654),
 .cfg_peer_ip(32'hc6120b01),.cfg_rkey(32'hfedcba98),.cfg_remote_address(64'hfedcba9876543210),
 .cfg_remote_bytes({32'd0,requested_bytes}),.cfg_message_bytes(requested_bytes),.cfg_message_count(32'd1),
 .cfg_read_window(32'd1),.cfg_timeout_cycles(32'd250000),.tx_quiescent(modeled_tx_quiet),
 .memory_fault(buffer_fault),.capture_idle(buffer_idle),.capture_host_idle(buffer_host_idle),
 .captured_count(committed),.captured_bytes(committed_bytes),.capture_clear(engine_capture_clear),
 .capture_enable(capture_enable),.lease_bytes(engine_lease),.core_reset(engine_core_reset),
 .halt_tx(engine_halt),.rx_enable(engine_rx),.busy(engine_busy),.done(engine_done),.failed(engine_failed),
 .state(engine_state),.error_code(engine_error),.issued_count(engine_issued),.acked_count(engine_acked),
 .duplicate_ack_count(),.total_bytes(engine_total),.elapsed_cycles(engine_elapsed),
 .m_axis_qp_tdata(engine_qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(qr),
 .m_axis_conn_tdata(engine_conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(cr),
 .m_axis_sq_tdata(engine_sq),.m_axis_sq_tvalid(sqv),.m_axis_sq_tready(sqr),
 .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(ack_valid),.s_axis_ack_tready(engine_ack_ready));
always @(posedge clk) if(!rst) begin
 if(rx_good>observed_rx_good) observed_rx_good=rx_good;
 if(tx_good>observed_tx_good) observed_tx_good=tx_good;
 if(engine_failed) $fatal(1,"READ controller failed code=%0d state=%0d",engine_error,engine_state);
 if(engine_done && (committed!=1 || committed_bytes!=requested_bytes || !buffer_idle ||
    !engine_core_reset || engine_issued!=1 || engine_acked!=1 || engine_total!=requested_bytes ||
    engine_lease!=((requested_bytes+63)&~63))) $fatal(1,"DONE before complete protected capture");
end
'''


def bench():
    tb = capture.bench()
    tb = replace(tb, 'reg rst=0,sv=0,sl=0,qv=0,cv=0,sqv=0;', 'reg rst=0,sv=0,sl=0;wire qv,cv,sqv;')
    tb = replace(tb, '.clk(clk),.rst(rst),.s_axis_rx_tdata(sd)', '.clk(clk),.rst(transport_reset),.s_axis_rx_tdata(sd)')
    tb = replace(tb, ".s_axis_qp_tdata({32'hfedcba98,48'd0,24'h987654,24'hfffffe,24'd2,32'd3})",
                 '.s_axis_qp_tdata(engine_qp)')
    tb = replace(tb, ".s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2})",
                 '.s_axis_conn_tdata(engine_conn)')
    tb = replace(tb, ".s_axis_sq_tdata({32'd0,requested_bytes,64'hfedcba9876543210,64'd0,4'd0,1'b1,1'b1,10'd2,32'd12})",
                 '.s_axis_sq_tdata(engine_sq)')
    tb = replace(tb, ".m_axis_ack_tready(1'b1)", '.m_axis_ack_tready(engine_ack_ready)')
    tb = replace(tb, 'if(tq) begin qv=0;qdone=1;end', 'if(tq) qdone=1;')
    tb = replace(tb, 'if(tc) begin cv=0;cdone=1;end', 'if(tc) cdone=1;')
    tb = replace(tb, 'if(tsq) begin sqv=0;sqdone=1;end', 'if(tsq) sqdone=1;')
    tb = replace(tb, ' if(cycle==4096) begin qv=1;cv=1;end\n', '')
    tb = replace(tb, ' if(prefill_done && qdone && cdone && cycle>4200 && !sqdone) sqv=1;\n', '')
    tb = replace(tb, 'reg prefill_done=0,transport_done=0,capture_enable=0;',
                 'reg prefill_done=0,transport_done=0;wire capture_enable;')
    tb = replace(tb, ".clk(clk),.rst(rst),.clear(1'b0),.capture_enable(capture_enable)",
                 '.clk(clk),.rst(rst),.clear(engine_capture_clear),.capture_enable(capture_enable)')
    tb = replace(tb, '.host_idle(),.idle(buffer_idle)', '.host_idle(buffer_host_idle),.idle(buffer_idle)')
    tb = replace(tb, ' @(negedge clk);capture_enable=1;prefill_done=1;',
                 ' @(negedge clk);if(!engine_ready) $fatal(1,"controller not ready after prefill");\n'
                 ' prefill_done=1;boot_phase=0;engine_start=1;@(negedge clk);engine_start=0;')
    tb = replace(tb, ' @(negedge clk);capture_enable=0;',
                 ' @(negedge clk);if(!engine_done || capture_enable) $fatal(1,"capture not quiesced after DONE");')
    tb = replace(tb, '    acks==1 && rx_good==packets && tx_good==1)',
                 '    acks==1 && engine_done && observed_rx_good==packets && observed_tx_good==1)')
    tb = replace(tb, ' $finish;\nend\nalways @(posedge clk) if(!rst) begin',
                 ' $display("CONTROL_RESULT issued=%0d completed=%0d committed=%0d",engine_issued,engine_acked,committed);\n'
                 ' $finish;\nend\nalways @(posedge clk) if(!rst) begin')
    return replace(tb, '\nendmodule\n', '\n' + ENGINE + '\nendmodule\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--sizes', type=int, nargs='+', default=[65, 4097])
    parser.add_argument('--wall-timeout', type=int, default=600)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or any(not 1<=n<=65536 for n in args.sizes):
        parser.error('select a new report and sizes1..65536')
    rtl = args.hls_build.resolve() / 'solution1/syn/verilog'
    axis = ROOT / 'external/corundum/fpga/lib/eth/lib/axis/rtl'
    sources = sorted(rtl.glob('*.v')) + [ROOT / ('rdma/rtl/' + n) for n in
        ['rocev2_ipv4_icrc.v', 'rocev2_tx_padding.v', 'rocev2_integrity_transport.v']]
    sources += [capture.SINK_RTL, ENGINE_RTL] + [axis / n for n in ['axis_adapter.v','axis_fifo.v','axis_register.v']]
    sources.append(ROOT / 'external/corundum/fpga/lib/eth/rtl/lfsr.v')
    results = []
    with tempfile.TemporaryDirectory(prefix='as02-read-control-') as directory:
        path = Path(directory)
        (path / 'tb.v').write_text(bench())
        for dat in rtl.glob('*.dat'):
            shutil.copy2(dat, path / dat.name)
        compiled = subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path / 'test.vvp'),
                                  str(path / 'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        for size in args.sizes:
            payload=bytes((i*179 ^ i>>7 ^ 0xD3)&255 for i in range(size))
            frames=base.wire.responses(payload,initial_psn=0xFFFFFE,source_ip='198.18.11.1',
                                       destination_ip='198.18.11.2',destination_qpn=2)
            stimulus=[w for frame in frames for w in base.words(frame[14:])]
            (path / 'input.hex').write_text(''.join(f'{w:037x}\n' for w in stimulus))
            sim=subprocess.run(['vvp',str(path / 'test.vvp'),f'+bytes={size}',f'+input_count={len(stimulus)}'],
                               cwd=path,capture_output=True,text=True,timeout=args.wall_timeout)
            if sim.returncode or 'ERROR:' in sim.stdout:
                print(sim.stdout,flush=True)
                raise RuntimeError(sim.stderr or f'READ control case{size} failed')
            result=base.parse(sim.stdout,payload)
            captures=[json.loads(line[15:]) for line in sim.stdout.splitlines() if line.startswith('CAPTURE_RESULT ')]
            if len(captures)!=1 or captures[0]['host_readback_bytes_verified']!=size or \
               sim.stdout.count('CONTROL_RESULT issued=1 completed=1 committed=1')!=1:
                raise ValueError('missing protected READ controller completion/readback evidence')
            result.update(captures[0],protected_capture_used=True,read_controller_used=True,
                          done_after_ram_commit_checked=True,physical_mac_completion_modeled=True,
                          early_ack_before_commit_observed='EARLY_ACK_CAPTURE_NOT_COMMITTED' in sim.stdout)
            results.append(result)
            print(json.dumps(result),flush=True)
    generated=hashlib.sha256()
    for file in sorted([*rtl.glob('*.v'),*rtl.glob('*.dat')]):
        generated.update(file.name.encode()+b'\0'+file.read_bytes())
    dependencies=sources+[Path(__file__),Path(capture.__file__),Path(base.__file__),
        ROOT / 'rdma/read/host/read_wire.py',ROOT / 'rdma/host/rocev2_wire.py',ROOT / 'rdma/tests/test_icrc_rtl.py']
    report=dict(scope='READ control/HLS/protected RAM/host RTL port; no Ethernet app, PCIe or native RNIC',
                complete=True,hardware_verified=False,cases=results,generated_hls_sha256=generated.hexdigest(),
                source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in dependencies if f.is_relative_to(ROOT)})
    with args.report.open('x') as out:
        out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
