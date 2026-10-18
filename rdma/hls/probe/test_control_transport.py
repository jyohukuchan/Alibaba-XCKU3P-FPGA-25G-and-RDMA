#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""AXI-Lite -> finite engine -> generated HLS -> Ethernet -> modeled ACK.

Actual RTL simulation only. Neither RNIC hardware nor PCIe DMA is involved.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "rdma/host"))
sys.path.insert(0, str(ROOT / "rdma/tests"))
from rocev2_wire import decode_ethernet, icrc_ipv4, internet_checksum
from test_icrc_rtl import words
from test_control_rtl import TB as CONTROL_TB
from test_wire import CX_ACK

TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0,boot_phase=1;
reg [23:0] aa=0,ra=0;
reg [31:0] wd=0;
reg [3:0] ws=0;
reg av=0,wv=0,br=0,rv=0,rr=0;
wire ar,wr,bv,arready,rvalid;
wire [1:0] bp,rp;
wire [31:0] rd;
wire [47:0] local_mac,peer_mac;
wire [31:0] local_ip,peer_ip;
wire [23:0] local_qpn;
wire core_rst,halt,rx,busy,done,failed;
wire transport_reset=boot_phase ? rst : core_rst;
wire [183:0] qp,conn;
wire qv,cv,qr,cr;
wire [239:0] sq;
wire sv,sr;
wire [39:0] ack;
wire ack_valid,ack_ready;
wire [95:0] mem_cmd;
wire mem_valid,mem_ready;
wire [511:0] mem_data;
wire [63:0] mem_keep;
wire mem_dvalid,mem_dready,mem_last;
wire bad_wcmd,bad_wdata;
wire [31:0] psn_drop,retrans,rx_words,tx_words,rx_good,rx_bad,tx_good,tx_bad,overflow;
wire [31:0] local_ip_axis={local_ip[7:0],local_ip[15:8],local_ip[23:16],local_ip[31:24]};
wire [31:0] eth_drop,eth_rx,eth_host,eth_tx,eth_cpl;
wire [511:0] diagnostics={64'd0,eth_cpl,eth_tx,eth_host,eth_rx,eth_drop,overflow,tx_bad,tx_good,rx_bad,rx_good,tx_words,rx_words,retrans,psn_drop};
integer cycle=0,net_frames=0,last_tx_cycle=0,ack_frames=0,ack_index=0,ack_loaded=0;
integer read_transactions=0,write_transactions=0,net_stalls=0,ack_events=0;
wire quiet,guard_fault;
wire [15:0] guard_pending;
wire [31:0] guard_admitted,guard_completed;
rocev2_control #(.WINDOW(2)) control (
 .clk(clk),.rst(rst),.s_axil_awaddr(aa),.s_axil_awprot(3'd0),.s_axil_awvalid(av),.s_axil_awready(ar),
 .s_axil_wdata(wd),.s_axil_wstrb(ws),.s_axil_wvalid(wv),.s_axil_wready(wr),
 .s_axil_bresp(bp),.s_axil_bvalid(bv),.s_axil_bready(br),
 .s_axil_araddr(ra),.s_axil_arprot(3'd0),.s_axil_arvalid(rv),.s_axil_arready(arready),
 .s_axil_rdata(rd),.s_axil_rresp(rp),.s_axil_rvalid(rvalid),.s_axil_rready(rr),
 .tx_quiescent(quiet),.unexpected_memory_write(bad_wcmd || bad_wdata || guard_fault),.diagnostics(diagnostics),
 .local_mac(local_mac),.peer_mac(peer_mac),.local_ip(local_ip),.peer_ip(peer_ip),.local_qpn(local_qpn),
 .core_reset(core_rst),.halt_tx(halt),.rx_enable(rx),.busy(busy),.done(done),.failed(failed),
 .m_axis_qp_tdata(qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(qr),
 .m_axis_conn_tdata(conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(cr),
 .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sv),.m_axis_sq_tready(sr),
 .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(ack_valid),.s_axis_ack_tready(ack_ready),
 .s_axis_mem_cmd_tdata(mem_cmd),.s_axis_mem_cmd_tvalid(mem_valid),.s_axis_mem_cmd_tready(mem_ready),
 .m_axis_mem_tdata(mem_data),.m_axis_mem_tkeep(mem_keep),.m_axis_mem_tvalid(mem_dvalid),.m_axis_mem_tready(mem_dready),.m_axis_mem_tlast(mem_last));

wire [127:0] ip_rx_data,ip_tx_data;
wire [15:0] ip_rx_keep,ip_tx_keep;
wire ip_rx_valid,ip_rx_ready,ip_rx_last,ip_rx_user,ip_tx_valid,ip_tx_ready,ip_tx_last;
rocev2_integrity_transport transport (
 .clk(clk),.rst(transport_reset),.s_axis_rx_tdata(ip_rx_data),.s_axis_rx_tkeep(ip_rx_keep),.s_axis_rx_tvalid(ip_rx_valid),.s_axis_rx_tready(ip_rx_ready),.s_axis_rx_tlast(ip_rx_last),.s_axis_rx_tuser(ip_rx_user),
 .m_axis_tx_tdata(ip_tx_data),.m_axis_tx_tkeep(ip_tx_keep),.m_axis_tx_tvalid(ip_tx_valid),.m_axis_tx_tready(ip_tx_ready),.m_axis_tx_tlast(ip_tx_last),
 .s_axis_qp_tdata(qp),.s_axis_qp_tvalid(qv),.s_axis_qp_tready(qr),.s_axis_conn_tdata(conn),.s_axis_conn_tvalid(cv),.s_axis_conn_tready(cr),
 .s_axis_sq_tdata(sq),.s_axis_sq_tvalid(sv),.s_axis_sq_tready(sr),
 .m_axis_ack_tdata(ack),.m_axis_ack_tvalid(ack_valid),.m_axis_ack_tready(ack_ready),
 .m_axis_mem_write_cmd_tdata(),.m_axis_mem_write_cmd_tvalid(bad_wcmd),.m_axis_mem_write_cmd_tready(1'b1),
 .m_axis_mem_read_cmd_tdata(mem_cmd),.m_axis_mem_read_cmd_tvalid(mem_valid),.m_axis_mem_read_cmd_tready(mem_ready),
 .m_axis_mem_write_tdata(),.m_axis_mem_write_tkeep(),.m_axis_mem_write_tvalid(bad_wdata),.m_axis_mem_write_tready(1'b1),.m_axis_mem_write_tlast(),
 .s_axis_mem_read_tdata(mem_data),.s_axis_mem_read_tkeep(mem_keep),.s_axis_mem_read_tvalid(mem_dvalid),.s_axis_mem_read_tready(mem_dready),.s_axis_mem_read_tlast(mem_last),
 .local_ip_address({4{local_ip_axis}}),
 .m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(psn_drop),.core_retransmit_count(retrans),.core_rx_word_count(rx_words),.core_tx_word_count(tx_words),
 .rx_integrity_good_count(rx_good),.rx_integrity_drop_count(rx_bad),.tx_integrity_good_count(tx_good),.tx_integrity_drop_count(tx_bad),.integrity_overflow_count(overflow));

reg [127:0] input_data=0;
reg [15:0] input_keep=0;
reg input_valid=0,input_last=0;
wire input_ready;
rocev2_ethernet_rx ingress (
 .clk(clk),.rst(rst),.enable(rx),.local_mac(local_mac),.peer_mac(peer_mac),.local_ip(local_ip),.peer_ip(peer_ip),.local_qpn(local_qpn),
 .s_axis_tdata(input_data),.s_axis_tkeep(input_keep),.s_axis_tvalid(input_valid),.s_axis_tready(input_ready),.s_axis_tlast(input_last),.s_axis_tuser(97'd0),
 .m_axis_host_tdata(),.m_axis_host_tkeep(),.m_axis_host_tvalid(),.m_axis_host_tready(1'b1),.m_axis_host_tlast(),.m_axis_host_tuser(),
 .m_axis_roce_tdata(ip_rx_data),.m_axis_roce_tkeep(ip_rx_keep),.m_axis_roce_tvalid(ip_rx_valid),.m_axis_roce_tready(ip_rx_ready),.m_axis_roce_tlast(ip_rx_last),.m_axis_roce_tuser(ip_rx_user),
 .host_frame_count(eth_host),.roce_frame_count(eth_rx),.drop_frame_count(eth_drop),.overflow_count());
wire [127:0] output_data;
wire [15:0] output_keep;
wire output_valid,output_last;
reg output_ready=0;
wire [127:0] guarded_data;
wire [15:0] guarded_keep;
wire guarded_valid,guarded_ready,guarded_last;
reg model_mac_cpl=0,model_mac_in_frame=0;
wire model_mac_cpl_ready;
rocev2_tx_guard guard (
 .clk(clk),.rst(rst),.halt(halt),.completion(model_mac_cpl && model_mac_cpl_ready),
 .s_axis_tdata(ip_tx_data),.s_axis_tkeep(ip_tx_keep),.s_axis_tvalid(ip_tx_valid),.s_axis_tready(ip_tx_ready),.s_axis_tlast(ip_tx_last),
 .m_axis_tdata(guarded_data),.m_axis_tkeep(guarded_keep),.m_axis_tvalid(guarded_valid),.m_axis_tready(guarded_ready),.m_axis_tlast(guarded_last),
 .quiescent(quiet),.fault(guard_fault),.pending_frames(guard_pending),.admitted_frames(guard_admitted),.completed_frames(guard_completed));
rocev2_ethernet_tx egress (
 .clk(clk),.rst(rst),.local_mac(local_mac),.peer_mac(peer_mac),
 .s_axis_roce_tdata(guarded_data),.s_axis_roce_tkeep(guarded_keep),.s_axis_roce_tvalid(guarded_valid),.s_axis_roce_tready(guarded_ready),.s_axis_roce_tlast(guarded_last),
 .s_axis_host_tdata(128'd0),.s_axis_host_tkeep(16'd0),.s_axis_host_tvalid(1'b0),.s_axis_host_tready(),.s_axis_host_tlast(1'b0),.s_axis_host_tuser(17'd0),
 .m_axis_tdata(output_data),.m_axis_tkeep(output_keep),.m_axis_tvalid(output_valid),.m_axis_tready(output_ready),.m_axis_tlast(output_last),.m_axis_tuser(),
 .s_axis_cpl_tag(16'd0),.s_axis_cpl_ts(96'd0),.s_axis_cpl_valid(model_mac_cpl),.s_axis_cpl_ready(model_mac_cpl_ready),
 .m_axis_host_cpl_tag(),.m_axis_host_cpl_ts(),.m_axis_host_cpl_valid(),.m_axis_host_cpl_ready(1'b1),.roce_frame_count(eth_tx),.roce_completion_count(eth_cpl));

reg [145:0] acks[0:ACK_WORDS-1];
reg [31:0] ack_after[0:ACK_FRAMES-1];
reg took_input=0,stalled=0;
reg [144:0] held;
reg [31:0] rng=32'h873e159c;
AXIL_TASKS
initial begin
 // Explicit boot reset edge before the first clock, then let the real
 // controller hold/release transport reset. No forced internal registers.
 $readmemh("acks.hex",acks);
 $readmemh("ack_after.hex",ack_after);
 #1 rst=1; repeat(8) @(negedge clk); boot_phase=0; rst=0;
 write_reg(24'h40,32'hfbb97531,15,0,0); write_reg(24'h44,32'h8af3,15,1,0);
 write_reg(24'h48,32'h0367c5d0,15,2,0); write_reg(24'h4c,32'hb883,15,0,0);
 write_reg(24'h50,32'hc6120b02,15,0,0); write_reg(24'h54,32'hc6120b01,15,0,0);
 write_reg(24'h5c,32'habcdef,15,0,0); write_reg(24'h60,32'dINITIAL_PSN,15,0,0); write_reg(24'h64,32'h987654,15,0,0);
 write_reg(24'h68,32'hfedcba98,15,0,0); write_reg(24'h6c,32'dMESSAGE_BYTES,15,0,0);
 write_reg(24'h70,32'h76543210,15,0,0); write_reg(24'h74,32'hfedcba98,15,0,0);
 write_reg(24'h78,32'dTOTAL_BYTES,15,0,0); write_reg(24'h80,32'dMESSAGE_COUNT,15,0,0);
 write_reg(24'h84,32'd30000,15,0,0); write_reg(8,1,1,0,0);
 wait(done || failed);
 if(failed) $fatal(1,"finite generated-RTL run failed error=%0d",control.error);
 repeat(8) @(negedge clk);
 read_reg(16,0,0); read_reg(20,MESSAGE_COUNT,0); read_reg(24,MESSAGE_COUNT,0); read_reg(28,TOTAL_BYTES,0);
 read_reg(44,MESSAGE_COUNT,0); read_reg(48,TOTAL_BYTES,0);
 // These counters would disappear on terminal core reset without snapshots.
 read_reg(24'h90,0,0); read_reg(24'h94,0,0); read_reg(24'ha0,ACK_FRAMES,0);
 read_reg(24'ha4,0,0); read_reg(24'ha8,MESSAGE_COUNT,0); read_reg(24'hac,0,0); read_reg(24'hb0,0,0);
 read_reg(24'hc0,MESSAGE_COUNT,0); read_reg(24'hc4,MESSAGE_COUNT,0);
 if(guard_pending!=0 || guard_admitted!=MESSAGE_COUNT || guard_completed!=MESSAGE_COUNT || guard_fault)
  $fatal(1,"incomplete real RTL guard drain");
 if(net_frames!=MESSAGE_COUNT || ack_events!=ACK_FRAMES || !net_stalls) $fatal(1,"incomplete interface coverage");
 $display("RESULT {\"cycles\":%0d,\"wire_writes\":%0d,\"wire_payload_bytes\":%0d,\"success_ack_events\":%0d,\"network_stall_cycles\":%0d,\"axi_writes\":%0d,\"axi_reads\":%0d,\"separate_tx_peer_psns\":true,\"terminal_counters_preserved\":true}",cycle,net_frames,TOTAL_BYTES,ack_events,net_stalls,write_transactions,read_transactions);
 $finish;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 output_ready=cycle>5000 && rng[2:0]!=0;
 if(!input_valid || took_input) begin
  input_valid=0;
  if(ack_loaded<ACK_WORDS && ack_after[ack_loaded/4]<=net_frames && cycle>last_tx_cycle+5 && rng[5:3]!=0) begin
   {input_last,input_keep,input_data}=acks[ack_loaded][144:0]; input_valid=1; ack_loaded=ack_loaded+1;
  end
 end
end
always @(posedge clk) if(!rst) begin
 // Model an early SFD completion, never pretend this is physical EOF.
 // The actual guard, not a hard-coded testbench quiet signal, delays reset.
 model_mac_cpl<=0;
 if(output_valid && output_ready) begin
  if(!model_mac_in_frame) model_mac_cpl<=1;
  model_mac_in_frame<=!output_last;
 end
 if(core_rst && guard_pending!=0) $fatal(1,"transport reset with admitted TX pending");
 cycle=cycle+1; took_input=input_valid && input_ready;
 if(took_input) begin ack_index=ack_index+1; if(input_last) ack_frames=ack_frames+1; end
 if(stalled && (!output_valid || {output_last,output_keep,output_data}!==held)) $fatal(1,"Ethernet output changed under stall");
 stalled=output_valid && !output_ready; held={output_last,output_keep,output_data}; if(stalled) net_stalls=net_stalls+1;
 if(output_valid && output_ready) begin
  $display("OUT %032h %04h %b",output_data,output_keep,output_last);
  if(output_last) begin net_frames=net_frames+1; last_tx_cycle=cycle; end
 end
 if(ack_valid && ack_ready) ack_events=ack_events+1;
 if(cycle>35000) $fatal(1,"deadline state=%0d net=%0d ack=%0d read=%0d rxwords=%0d txwords=%0d",control.state,net_frames,ack_events,control.read_commands,rx_words,tx_words);
end
endmodule
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hls-build", type=pathlib.Path, required=True)
    parser.add_argument("--message-bytes", type=int, default=65)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--initial-psn", type=lambda s: int(s, 0), default=0x123456)
    parser.add_argument("--ack-every", type=int, choices=(1, 2), default=1, help="model cumulative ACKs within the two-request window")
    parser.add_argument("--report", type=pathlib.Path)
    parser.add_argument("--boundary", choices=("components", "endpoint", "app"), default="components")
    args = parser.parse_args()
    if not 1 <= args.message_bytes <= 4096 or not 1 <= args.count <= 32 or not 0 <= args.initial_psn <= 0xFFFFFF:
        parser.error("requires 1..4096 bytes, 1..32 messages and 24-bit PSN")
    rtl = args.hls_build.resolve() / "solution1/syn/verilog"
    if not (rtl / "rocev2_top.v").is_file():
        parser.error("missing generated transport RTL")
    acks, ack_after = [], []
    for sequence in range(args.count):
        if (sequence + 1) % args.ack_every and sequence != args.count - 1:
            continue
        ack = bytearray(CX_ACK)
        ack[47:50] = (2).to_bytes(3, "big")
        ack[51:54] = ((args.initial_psn + sequence) & 0xFFFFFF).to_bytes(3, "big")
        ack[54:58] = bytes([0x1F]) + (sequence + 1).to_bytes(3, "big")
        ack[-4:] = icrc_ipv4(ack[14:])
        acks.extend(words(bytes(ack)))
        ack_after.append(sequence + 1)
    # Share only AXI bus procedures with the component test; this harness
    # connects the actual generated transport, not that test's modeled SQ/ACK.
    tasks = CONTROL_TB[CONTROL_TB.index("task write_reg;"):CONTROL_TB.index("\ninitial begin")]
    tb = TB.replace("AXIL_TASKS", tasks)
    if args.boundary != "components":
        from app_boundary import make_tb
        tb = make_tb(tb, args.boundary)
    values = dict(MESSAGE_BYTES=args.message_bytes, MESSAGE_COUNT=args.count,
                  TOTAL_BYTES=args.message_bytes * args.count, INITIAL_PSN=args.initial_psn, ACK_WORDS=len(acks), ACK_FRAMES=len(ack_after))
    for name, value in values.items():
        tb = tb.replace(name, str(value))
    modules = [ROOT / "rdma/rtl" / name for name in ("rocev2_control.v", "rocev2_write_engine.v", "rocev2_pattern_source.v",
               "rocev2_ethernet_rx.v", "rocev2_ethernet_tx.v", "rocev2_ipv4_icrc.v", "rocev2_integrity_transport.v", "rocev2_tx_padding.v", "rocev2_tx_guard.v")]
    if args.boundary != "components":
        modules.append(ROOT / "rdma/rtl/rocev2_endpoint.v")
    if args.boundary == "app":
        modules.append(ROOT / "rdma/fpga/mqnic_app_block.v")
    axis = ROOT / "external/corundum/fpga/lib/axis/rtl"
    eth = ROOT / "external/corundum/fpga/lib/eth/rtl"
    sources = list(rtl.glob("*.v")) + modules
    sources += [axis / name for name in ("axis_fifo.v", "axis_register.v", "axis_adapter.v", "axis_arb_mux.v", "arbiter.v", "priority_encoder.v")]
    sources += [eth / name for name in ("eth_axis_rx.v", "eth_axis_tx.v", "lfsr.v")]
    with tempfile.TemporaryDirectory(prefix="as02-control-transport-") as directory:
        path = pathlib.Path(directory)
        (path / "tb.v").write_text(tb)
        (path / "acks.hex").write_text("".join(f"{word:x}\n" for word in acks))
        (path / "ack_after.hex").write_text("".join(f"{count:x}\n" for count in ack_after))
        for initial in rtl.glob("*.dat"):
            shutil.copy2(initial, path / initial.name)
        compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"), str(path / "tb.v"), *map(str, sources)],
                                  capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        result = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path, capture_output=True, text=True, timeout=180)
        print(result.stdout)
        if result.returncode or "ERROR:" in result.stdout or "ERROR:" in result.stderr:
            raise RuntimeError(result.stderr or "RTL simulation failed")
        frames, frame = [], bytearray()
        for line in result.stdout.splitlines():
            if line.startswith("OUT "):
                _, data, keep, last = line.split()
                beat = int(data, 16).to_bytes(16, "little")
                frame.extend(beat[i] for i in range(16) if int(keep, 16) & (1 << i))
                if last == "1":
                    frames.append(bytes(frame)); frame.clear()
        if len(frames) != args.count or frame:
            raise ValueError("wrong complete WRITE count")
        for sequence, frame in enumerate(frames):
            p = decode_ethernet(frame)
            start = sequence * args.message_bytes
            expected = bytes(((i * 131) ^ (i >> 8) ^ 0x5A) & 255 for i in range(start, start + args.message_bytes))
            if (frame[:14] != bytes.fromhex("b8830367c5d08af3fbb975310800") or
                p["opcode"] != 10 or p["destination_qpn"] != 0xABCDEF or
                p["psn"] != (args.initial_psn + sequence) & 0xFFFFFF or p["rkey"] != "0xfedcba98" or
                int(p["remote_address"], 0) != 0xFEDCBA9876543210 + start or p["dma_length"] != args.message_bytes or
                p["payload_bytes"] != args.message_bytes or not p["icrc_valid"] or internet_checksum(frame[14:34]) != 0 or
                frame[70:70 + args.message_bytes] != expected):
                raise ValueError(f"wrong wire WRITE {sequence}: {p}")
        reports = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
        if len(reports) != 1:
            raise ValueError("missing completed simulation record")
        generated = hashlib.sha256()
        for source in sorted([*rtl.glob("*.v"), *rtl.glob("*.dat")]):
            generated.update(source.name.encode() + b"\0" + source.read_bytes())
        record = dict(evidence_type="AXI-Lite/engine/generated transport/Ethernet RTL simulation, not hardware",
                      hardware_verified=False, pass_test=True, **reports[0], message_bytes=args.message_bytes,
                      boundary=args.boundary,
                      initial_psn=args.initial_psn, peer_psn=0x987654, all_wire_bytes_checked=True,
                      ack_every=args.ack_every,
                      rtl_tx_guard_used=True, mac_sfd_completion_modelled=True, physical_mac_drain_verified=False,
                      wire_icrcs_valid=True, wire_ipv4_checksums_valid=True, hls_build=args.hls_build.name,
                      generated_rtl_sha256=generated.hexdigest(),
                      source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in modules},
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                      axi_test_dependency_sha256=hashlib.sha256((ROOT / "rdma/tests/test_control_rtl.py").read_bytes()).hexdigest())
        if args.boundary != "components":
            record["boundary_test_dependency_sha256"] = hashlib.sha256((ROOT / "rdma/hls/probe/app_boundary.py").read_bytes()).hexdigest()
        print(json.dumps(record, indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
