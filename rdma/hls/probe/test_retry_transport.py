#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Withhold one ACK and verify real generated transport/pattern-memory replay.

Full board-app RTL boundary, real 4ns clock and 1ms retry timer. RNIC and
MAC SFD completions remain models; no network or physical FPGA is accessed.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile

import test_control_transport as base
from app_boundary import make_tb

ROOT = base.ROOT


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("retry bench dependency changed: " + old)
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hls-build", type=pathlib.Path, required=True)
    parser.add_argument("--message-bytes", type=int, default=65)
    parser.add_argument("--wall-timeout", type=int, default=1800)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    if not 1 <= args.message_bytes <= 4096:
        parser.error("requires 1..4096-byte WRITE_ONLY")
    if args.report and args.report.exists():
        parser.error("preserve previous evidence: select a new report path")
    rtl = args.hls_build.resolve() / "solution1/syn/verilog"
    if not (rtl / "rocev2_top.v").is_file():
        parser.error("missing generated transport RTL")
    tasks = base.CONTROL_TB[base.CONTROL_TB.index("task write_reg;"):base.CONTROL_TB.index("\ninitial begin")]
    tb = base.TB.replace("AXIL_TASKS", tasks)
    tb = replace_once(tb, "32'd30000", "32'd1000000")
    tb = replace_once(tb, "cycle>35000", "cycle>1100000")
    tb = replace_once(tb, "read_reg(44,MESSAGE_COUNT,0); read_reg(48,TOTAL_BYTES,0);",
                      "read_reg(44,2,0); read_reg(48,TOTAL_BYTES*2,0);")
    tb = replace_once(tb, "read_reg(24'h94,0,0);", "read_reg(24'h94,1,0);")
    for address in ("a8", "c0", "c4"):
        tb = replace_once(tb, f"read_reg(24'h{address},MESSAGE_COUNT,0);", f"read_reg(24'h{address},2,0);")
    tb = replace_once(tb, "guard_admitted!=MESSAGE_COUNT || guard_completed!=MESSAGE_COUNT",
                      "guard_admitted!=2 || guard_completed!=2")
    tb = replace_once(tb, "net_frames!=MESSAGE_COUNT || ack_events!=ACK_FRAMES || !net_stalls",
                      "net_frames!=2 || ack_events!=ACK_FRAMES || !net_stalls || cycle<250000")
    display = next(line for line in tb.splitlines() if '$display("RESULT ' in line)
    tb = replace_once(tb, display, r''' $display("RESULT {\"cycles\":%0d,\"wire_transmissions\":%0d,\"success_ack_events\":%0d,\"network_stall_cycles\":%0d,\"axi_reads\":%0d,\"axi_writes\":%0d}",cycle,net_frames,ack_events,net_stalls,read_transactions,write_transactions);''')
    # Observe virtual-clock progress without changing timer, watchdog,
    # stimulus, expected replay or any assertion. Keep stdout live on disk.
    tb = replace_once(tb, "cycle=cycle+1; took_input=input_valid && input_ready;",
                      "cycle=cycle+1; took_input=input_valid && input_ready;\n"
                      ' if(cycle%50000==0) begin $display("RETRY_PROGRESS CYCLE=%0d NET_FRAMES=%0d ACKS=%0d",cycle,net_frames,ack_events); $fflush(); end')
    tb = make_tb(tb, "app")
    ack = bytearray(base.CX_ACK)
    ack[47:50] = (2).to_bytes(3, "big")
    ack[51:54] = (0xFFFFFE).to_bytes(3, "big")
    ack[54:58] = b"\x1f\0\0\x01"
    ack[-4:] = base.icrc_ipv4(ack[14:])
    ack_words = base.words(bytes(ack))
    for name, value in dict(MESSAGE_BYTES=args.message_bytes, MESSAGE_COUNT=1, TOTAL_BYTES=args.message_bytes,
                            INITIAL_PSN=0xFFFFFE, ACK_WORDS=len(ack_words), ACK_FRAMES=1).items():
        tb = tb.replace(name, str(value))
    modules = sorted((ROOT / "rdma/rtl").glob("*.v")) + [ROOT / "rdma/fpga/mqnic_app_block.v"]
    axis = ROOT / "external/corundum/fpga/lib/axis/rtl"
    eth = ROOT / "external/corundum/fpga/lib/eth/rtl"
    sources = sorted(rtl.glob("*.v")) + modules
    sources += [axis / name for name in ("axis_fifo.v", "axis_register.v", "axis_adapter.v", "axis_arb_mux.v", "arbiter.v", "priority_encoder.v")]
    sources += [eth / name for name in ("eth_axis_rx.v", "eth_axis_tx.v", "lfsr.v")]
    with tempfile.TemporaryDirectory(prefix="as02-retry-transport-") as temporary:
        path = pathlib.Path(temporary)
        (path / "tb.v").write_text(tb)
        (path / "acks.hex").write_text("".join(f"{word:x}\n" for word in ack_words))
        # A real first ACK would normally follow transmission 1. Withhold it
        # completely and deliver the RNIC response only after actual replay.
        (path / "ack_after.hex").write_text("2\n")
        for data in rtl.glob("*.dat"):
            shutil.copy2(data, path / data.name)
        compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                   str(path / "tb.v"), *map(str, sources)], capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        simulation_log = args.report.with_suffix(".simulation.log").resolve() if args.report else path / "simulation.log"
        simulation_log.parent.mkdir(parents=True, exist_ok=True)
        print(f"SIMULATION_LOG={simulation_log}", flush=True)
        with simulation_log.open("x") as output:
            simulated = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path, stdout=output,
                                       stderr=subprocess.STDOUT, text=True, timeout=args.wall_timeout)
        simulated_stdout = simulation_log.read_text()
        print(simulated_stdout)
        if simulated.returncode or "ERROR:" in simulated_stdout:
            raise RuntimeError(f"simulation exit={simulated.returncode}\n" + simulated_stdout)
    frames, packet = [], bytearray()
    for line in simulated_stdout.splitlines():
        if line.startswith("OUT "):
            _, data, keep, last = line.split()
            beat = int(data, 16).to_bytes(16, "little")
            packet.extend(beat[lane] for lane in range(16) if int(keep, 16) & (1 << lane))
            if last == "1":
                frames.append(bytes(packet)); packet.clear()
    if len(frames) != 2 or packet:
        raise ValueError("expected one original WRITE and one complete retransmission")
    payload = bytes(((i * 131) ^ (i >> 8) ^ 0x5A) & 255 for i in range(args.message_bytes))
    for frame in frames:
        decoded = base.decode_ethernet(frame)
        if (frame[:14] != bytes.fromhex("b8830367c5d08af3fbb975310800") or
            decoded["opcode"] != 10 or decoded["destination_qpn"] != 0xABCDEF or decoded["psn"] != 0xFFFFFE or
            decoded["rkey"] != "0xfedcba98" or int(decoded["remote_address"], 0) != 0xFEDCBA9876543210 or
            decoded["dma_length"] != args.message_bytes or decoded["payload_bytes"] != args.message_bytes or
            not decoded["icrc_valid"] or base.internet_checksum(frame[14:34]) != 0 or
            frame[70:70+args.message_bytes] != payload):
            raise ValueError("retransmission changed PSN/key/address/payload or checksum")
    results = [json.loads(line[7:]) for line in simulated_stdout.splitlines() if line.startswith("RESULT ")]
    if len(results) != 1 or results[0]["wire_transmissions"] != 2 or results[0]["success_ack_events"] != 1:
        raise ValueError("missing completed real transport retry evidence")
    generated = hashlib.sha256()
    for source in sorted([*rtl.glob("*.v"), *rtl.glob("*.dat")]):
        generated.update(source.name.encode() + b"\0" + source.read_bytes())
    dependencies = [ROOT / "rdma/hls/probe/test_control_transport.py", ROOT / "rdma/hls/probe/app_boundary.py",
                    ROOT / "rdma/tests/test_control_rtl.py"]
    record = dict(evidence_type="full app/generated transport ACK-loss/replay RTL simulation, not RNIC hardware",
                  hardware_verified=False, pass_test=True, **results[0], boundary="app",
                  unique_writes=1, unique_payload_bytes=args.message_bytes, wire_payload_bytes=args.message_bytes*2,
                  withheld_ack_count=1, actual_transport_retransmissions=1, pattern_reads=2,
                  replay_key_address_psn_payload_checked=True, wire_icrcs_valid=True, wire_ipv4_checksums_valid=True,
                  core_clock_ps=4000, original_timer_clock_unmodified=True, physical_mac_drain_verified=False,
                  hls_build=args.hls_build.name, generated_rtl_sha256=generated.hexdigest(),
                  source_sha256={source.name: hashlib.sha256(source.read_bytes()).hexdigest() for source in modules},
                  dependency_sha256={source.name: hashlib.sha256(source.read_bytes()).hexdigest() for source in dependencies},
                  test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                  host_wall_timeout_seconds=args.wall_timeout,
                  virtual_watchdog_and_retransmit_timer_unchanged=True,
                  simulation_log=str(simulation_log))
    print(json.dumps(record, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
