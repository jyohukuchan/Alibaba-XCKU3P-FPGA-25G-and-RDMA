#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exercise real generated HLS timer RTL at 4ns, including output stalls.

This is a sub-block simulation, not physical timing or RNIC interoperability.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile

TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0,clear_valid=0,set_valid=0,space=1;
reg [31:0] clear_data=0;
reg [23:0] set_data=0;
wire clear_read,set_read,retry_valid;
wire [63:0] retry_data;
integer cycle=0,events=0,last_event=0,last_qp=0,origin=0,expected=0,qp,phase;
integer first_min=300000,first_max=0,elapsed;
rocev2_top_transport_timer_0_s dut (
 .ap_clk(clk),.ap_rst(rst),.ap_start(1'b1),.ap_continue(1'b1),.ap_done(),.ap_idle(),.ap_ready(),
 .rxClearTimer_req_dout(clear_data),.rxClearTimer_req_empty_n(clear_valid),.rxClearTimer_req_read(clear_read),
 .rxClearTimer_req_num_data_valid(3'd1),.rxClearTimer_req_fifo_cap(3'd7),
 .txSetTimer_req_dout(set_data),.txSetTimer_req_empty_n(set_valid),.txSetTimer_req_read(set_read),
 .txSetTimer_req_num_data_valid(3'd1),.txSetTimer_req_fifo_cap(3'd7),
 .timer2retrans_req_din(retry_data),.timer2retrans_req_full_n(space),.timer2retrans_req_write(retry_valid),
 .timer2retrans_req_num_data_valid(3'd0),.timer2retrans_req_fifo_cap(3'd7));
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(retry_valid) begin
  if(!space || retry_data[63:16]!==0 || ^retry_data===1'bx) $fatal(1,"invalid retry FIFO write");
  events=events+1; last_event=cycle; last_qp=retry_data[15:0];
 end
 if(cycle>10000000) $fatal(1,"timer RTL deadline");
end
task set_timer;
 input integer index;
 begin
  @(negedge clk); set_data=index; set_valid=1;
  @(posedge clk); while(!set_read) @(posedge clk);
  @(negedge clk); set_valid=0; origin=cycle;
 end
endtask
task clear_timer;
 input integer index;
 input stop;
 begin
  @(negedge clk); clear_data={15'd0,stop,index[15:0]}; clear_valid=1;
  @(posedge clk); while(!clear_read) @(posedge clk);
  @(negedge clk); clear_valid=0; origin=cycle;
 end
endtask
task await_retry;
 input integer index;
 begin
  while(events==expected && cycle-origin<250128) @(negedge clk);
  elapsed=last_event-origin;
  if(events!=expected+1 || last_qp!=index || elapsed<250000 || elapsed>250128)
   $fatal(1,"wrong clock interval qp=%0d gotqp=%0d elapsed=%0d events=%0d expected=%0d",index,last_qp,elapsed,events,expected+1);
  expected=events;
 end
endtask
initial begin
 #1 rst=1; repeat(8) @(negedge clk); rst=0; repeat(32) @(negedge clk);
 for(qp=0;qp<8;qp=qp+1) begin
  set_timer(qp); await_retry(qp);
  if(elapsed<first_min) first_min=elapsed;
  if(elapsed>first_max) first_max=elapsed;
  clear_timer(qp,1); repeat(16) @(negedge clk);
 end
 // ACK restart at every phase of the eight-entry scan, without changing
 // the real RAMs/counters by testbench force or hierarchical assignments.
 for(phase=0;phase<8;phase=phase+1) begin
  set_timer(phase); repeat(100000+phase) @(negedge clk);
  clear_timer(phase,0); await_retry(phase);
  clear_timer(phase,1); repeat(16) @(negedge clk);
 end
 // A final ACK can stop the timer immediately before a new WRITE starts.
 // Exercise read-after-write hazards between update types, not only scans.
 for(phase=0;phase<8;phase=phase+1) begin
  set_timer(phase); repeat(100000+phase) @(negedge clk);
  clear_timer(phase,1); set_timer(phase); await_retry(phase);
  clear_timer(phase,1); repeat(16) @(negedge clk);
 end
 set_timer(7); repeat(10000) @(negedge clk); clear_timer(7,1);
 repeat(250128) @(negedge clk);
 if(events!=expected) $fatal(1,"stopped timer retried");
 space=0; set_timer(7); repeat(250128) @(negedge clk);
 if(events!=expected) $fatal(1,"retry ignored FIFO backpressure");
 space=1; phase=cycle;
 while(events==expected && cycle-phase<128) @(negedge clk);
 if(events!=expected+1 || last_qp!=7) $fatal(1,"retry lost on output recovery");
 expected=events;
 // Failed/aborted sessions must not leave armed timers after per-run reset.
 set_timer(6); repeat(10000) @(negedge clk);
 rst=1; repeat(8) @(negedge clk); rst=0;
 repeat(250128) @(negedge clk);
 if(events!=expected) $fatal(1,"armed timer survived warm reset");
 set_timer(6); await_retry(6);
 $display("RESULT {\"pass_test\":true,\"cycles\":%0d,\"retry_events_checked\":%0d,\"first_retry_qps_checked\":8,\"first_retry_min_clocks\":%0d,\"first_retry_max_clocks\":%0d,\"ack_restart_scan_phases_checked\":8,\"stop_restart_phases_checked\":8,\"ack_stop_checked\":true,\"retry_output_backpressure_checked\":true,\"warm_reset_checked\":true}",cycle,events,first_min,first_max);
 $finish;
end
endmodule
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hls-build", required=True, type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    parser.add_argument("--simulator", choices=("iverilog", "verilator"), default="iverilog")
    parser.add_argument("--timeout", type=int, default=240, help="wall-clock simulator limit; protocol-cycle assertions are unchanged")
    parser.add_argument("--failure-dir", type=pathlib.Path, help="preserve the temporary generated bench/binary on a terminal simulation failure")
    args = parser.parse_args()
    rtl = args.hls_build.resolve() / "solution1/syn/verilog"
    timer_sources = sorted(rtl.glob("rocev2_top_transport_timer_0_s*.v"))
    if len(timer_sources) not in (1, 2) or not (rtl / "rocev2_top_transport_timer_0_s.v").is_file():
        parser.error("expected generated timer (with a BRAM model only for historical BRAM-table builds)")
    with tempfile.TemporaryDirectory(prefix="as02-generated-timer-") as temporary:
        path = pathlib.Path(temporary)
        (path / "tb.v").write_text(TB)
        for data in rtl.glob("*.dat"):
            shutil.copy2(data, path / data.name)
        # Register-table builds also instantiate generated mux/operator helpers.
        # Compile their exact build; only the timer top is elaborated.
        all_sources = [str(path / "tb.v"), *map(str, sorted(rtl.glob("*.v")))]
        if args.simulator == "iverilog":
            command = ["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"), *all_sources]
            run_command = ["vvp", str(path / "test.vvp")]
        else:
            # Generated HLS uses #0 on power-up initial assignments. Verilator
            # ignores that delta only; this bench explicitly resets for eight
            # clocks before observation and also checks an armed warm reset.
            command = ["verilator", "--binary", "--timing", "--top-module", "tb", "-j", "4",
                       "-Wno-fatal", "-Wno-ZERODLY", "--Mdir", str(path / "obj"), "-o", "timer", *all_sources]
            run_command = [str(path / "obj/timer")]
        compiled = subprocess.run(command, timeout=120, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        result = subprocess.run(run_command, cwd=path, timeout=args.timeout,
                                capture_output=True, text=True)
        if result.returncode or "ERROR:" in result.stdout + result.stderr:
            if args.failure_dir:
                shutil.copytree(path, args.failure_dir)
            raise RuntimeError(f"simulator exit={result.returncode}\n" + result.stdout + result.stderr)
        records = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
        if len(records) != 1 or not records[0]["pass_test"]:
            raise ValueError("missing complete generated timer evidence")
        generated = hashlib.sha256()
        for source in sorted([*rtl.glob("*.v"), *rtl.glob("*.dat")]):
            generated.update(source.name.encode() + b"\0" + source.read_bytes())
        record = dict(evidence_type="generated HLS timer RTL simulation, not physical timing or hardware",
                      hardware_verified=False, core_clock_ps=4000, max_qps=8, **records[0],
                      timer_table_storage="registers" if len(timer_sources) == 1 else "BRAM",
                      simulator=args.simulator, powerup_zero_delay_delta_ignored=args.simulator == "verilator",
                      hls_build=args.hls_build.name, generated_rtl_sha256=generated.hexdigest(),
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        print(json.dumps(record, indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
