#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual pinned HLS RTL READ probe; no board, DMA, or network access.

Checks READ_REQUEST bytes/checksums and supplies independently constructed
READ responses through the real RX integrity wrapper. Observes memory
commands, payload/padding and completion ordering without forcing the DUT.
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
sys.path.insert(0, str(ROOT / 'rdma/read/host'))
sys.path.insert(0, str(ROOT / 'rdma/tests'))
import read_wire as wire
from test_icrc_rtl import words

TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0,sv=0,sl=0,qv=0,cv=0,sqv=0;
reg [127:0] sd=0;
reg [15:0] sk=0;
wire sr,qr,cr,sqr;
wire [127:0] td;
wire [15:0] tk;
wire tv,tl;
reg tr=0;
wire [95:0] cmd;
wire cmd_valid;
reg cmd_ready=0;
wire [511:0] data;
wire [63:0] keep;
wire data_valid,data_last;
reg data_ready=0;
wire [39:0] ack;
wire ack_valid,unexpected_read;
wire [31:0] psn_drop,retrans,rx_good,rx_bad,tx_good,tx_bad,overflow;
reg [31:0] requested_bytes=65;
rocev2_integrity_transport dut (
 .clk(clk),.rst(rst),.s_axis_rx_tdata(sd),.s_axis_rx_tkeep(sk),.s_axis_rx_tvalid(sv),
 .s_axis_rx_tready(sr),.s_axis_rx_tlast(sl),.s_axis_rx_tuser(1'b0),
 .m_axis_tx_tdata(td),.m_axis_tx_tkeep(tk),.m_axis_tx_tvalid(tv),.m_axis_tx_tready(tr),.m_axis_tx_tlast(tl),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h987654,24'hfffffe,24'd2,32'd3}),.s_axis_qp_tvalid(qv),.s_axis_qp_tready(qr),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(cv),.s_axis_conn_tready(cr),
 .s_axis_sq_tdata({32'd0,requested_bytes,64'hfedcba9876543210,64'd0,4'd0,1'b1,1'b1,10'd2,32'd12}),
 .s_axis_sq_tvalid(sqv),.s_axis_sq_tready(sqr),
 .m_axis_ack_tdata(ack),.m_axis_ack_tvalid(ack_valid),.m_axis_ack_tready(1'b1),
 .m_axis_mem_write_cmd_tdata(cmd),.m_axis_mem_write_cmd_tvalid(cmd_valid),.m_axis_mem_write_cmd_tready(cmd_ready),
 .m_axis_mem_read_cmd_tdata(),.m_axis_mem_read_cmd_tvalid(unexpected_read),.m_axis_mem_read_cmd_tready(1'b1),
 .m_axis_mem_write_tdata(data),.m_axis_mem_write_tkeep(keep),.m_axis_mem_write_tvalid(data_valid),
 .m_axis_mem_write_tready(data_ready),.m_axis_mem_write_tlast(data_last),
 .s_axis_mem_read_tdata(512'd0),.s_axis_mem_read_tkeep(64'd0),.s_axis_mem_read_tvalid(1'b0),
 .s_axis_mem_read_tready(),.s_axis_mem_read_tlast(1'b0),.local_ip_address({4{32'h020b12c6}}),
 .m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(psn_drop),.core_retransmit_count(retrans),.core_rx_word_count(),.core_tx_word_count(),
 .rx_integrity_good_count(rx_good),.rx_integrity_drop_count(rx_bad),
 .tx_integrity_good_count(tx_good),.tx_integrity_drop_count(tx_bad),.integrity_overflow_count(overflow));
reg [145:0] stimulus[0:8191];
integer input_count,packets,dummy;
integer cycle=0,index=0,accepted=0,commands=0,frames=0,tx_frames=0,acks=0;
integer first_ack=-1,last_data=-1,tx_end=0,quiet=0,lane;
reg [31:0] rng=32'h98bc12d5;
reg tq=0,tc=0,tsq=0,took_input=0,qdone=0,cdone=0,sqdone=0;
reg tx_stall=0,cmd_stall=0,data_stall=0;
reg [144:0] saved_tx;
reg [95:0] saved_cmd;
reg [576:0] saved_data;
initial begin
 dummy=$value$plusargs("bytes=%d",requested_bytes);
 dummy=$value$plusargs("input_count=%d",input_count);
 packets=(requested_bytes+4095)/4096;
 if(input_count<1 || input_count>8192 || requested_bytes<1 || requested_bytes>65536) $fatal(1,"invalid probe size");
 $readmemh("input.hex",stimulus,0,input_count-1);
 #1 rst=1; repeat(8) @(negedge clk); rst=0;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 if(tq) begin qv=0;qdone=1;end
 if(tc) begin cv=0;cdone=1;end
 if(tsq) begin sqv=0;sqdone=1;end
 if(cycle==4096) begin qv=1;cv=1;end
 if(qdone && cdone && cycle>4200 && !sqdone) sqv=1;
 tr=cycle>4700 && rng[2:0]!=0;
 cmd_ready=cycle>6000 && rng[5:3]!=0;
 data_ready=cycle>6500 && rng[8:6]!=0;
 if(!sv || took_input) begin
  sv=0;
  if(tx_frames==1 && cycle>tx_end+20 && index<input_count && rng[11:9]!=0) begin
   {sl,sk,sd}=stimulus[index][144:0];sv=1;index=index+1;
  end
 end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;tq=qv && qr;tc=cv && cr;tsq=sqv && sqr;took_input=sv && sr;
 if(took_input) accepted=accepted+1;
 if(tx_stall && (!tv || {tl,tk,td}!==saved_tx)) $fatal(1,"TX changed under stall");
 if(cmd_stall && (!cmd_valid || cmd!==saved_cmd)) $fatal(1,"command changed under stall");
 if(data_stall && (!data_valid || {data_last,keep,data}!==saved_data)) $fatal(1,"payload changed under stall");
 tx_stall=tv && !tr;cmd_stall=cmd_valid && !cmd_ready;data_stall=data_valid && !data_ready;
 saved_tx={tl,tk,td};saved_cmd=cmd;saved_data={data_last,keep,data};
 if(dut.bare_tx_valid && dut.bare_tx_ready) begin
  $write("BARE %b %04h ",dut.bare_tx_last,dut.bare_tx_keep);
  for(lane=0;lane<16;lane=lane+1) if(dut.bare_tx_keep[lane]) $write("%02h",dut.bare_tx_data[lane*8+:8]);
  $display("");
 end
 if(dut.padded_tx_valid && dut.padded_tx_ready) begin
  $write("PAD %b %b %04h ",dut.padded_tx_last,dut.padded_tx_user,dut.padded_tx_keep);
  for(lane=0;lane<16;lane=lane+1) if(dut.padded_tx_keep[lane]) $write("%02h",dut.padded_tx_data[lane*8+:8]);
  $display("");
 end
 if(tv && tr) begin
  $write("NET %b ",tl);
  for(lane=0;lane<16;lane=lane+1) if(tk[lane]) $write("%02h",td[lane*8+:8]);
  $display("");
  if(tl) begin tx_frames=tx_frames+1;tx_end=cycle;end
 end
 if(cmd_valid && cmd_ready) begin
  $display("CMD %h %0d %0d %b %b %h",cmd[47:0],cmd[75:48],cmd[93:84],cmd[79],cmd[76],cmd);
  commands=commands+1;
 end
 if(data_valid && data_ready) begin
  $write("DATA %b %016h ",data_last,keep);
  for(lane=0;lane<64;lane=lane+1) if(keep[lane]) $write("%02h",data[lane*8+:8]);
  $display("");last_data=cycle;
  if(data_last) frames=frames+1;
 end
 if(ack_valid) begin
  $display("ACK %h %0d",ack,cycle);acks=acks+1;
  if(first_ack<0) first_ack=cycle;
 end
 if(unexpected_read || psn_drop!==0 || retrans!==0 || rx_bad!==0 || tx_bad!==0 || overflow!==0)
  $fatal(1,"transport fault read=%b psn=%h retrans=%h rx_bad=%h tx_bad=%h overflow=%h sq=%b cycle=%0d",unexpected_read,psn_drop,retrans,rx_bad,tx_bad,overflow,sqdone,cycle);
 if(sqdone && accepted==input_count && tx_frames==1 && commands==packets && frames==packets &&
    acks==1 && rx_good==packets && tx_good==1) quiet=quiet+1;else quiet=0;
 if(quiet==100) begin
  $display("RESULT {\"cycles\":%0d,\"packets\":%0d,\"first_completion_cycle\":%0d,\"last_data_cycle\":%0d}",cycle,packets,first_ack,last_data);
  $finish;
 end
 if(cycle>30000) $fatal(1,"READ deadline accepted=%0d cmd=%0d data=%0d tx=%0d ack=%0d rx_good=%0d",accepted,commands,frames,tx_frames,acks,rx_good);
end
endmodule
'''


def parse(output, payload):
    tx, current, commands, frames, data, acks, summaries = [], bytearray(), [], [], bytearray(), [], []
    for line in output.splitlines():
        fields = line.split()
        if line.startswith('NET '):
            current.extend(bytes.fromhex(fields[2]))
            if fields[1] == '1':
                tx.append(bytes(current)); current.clear()
        elif line.startswith('CMD '):
            commands.append(dict(address=int(fields[1], 16), length=int(fields[2]), qpn=int(fields[3]),
                                 host=int(fields[4]), last=int(fields[5])))
        elif line.startswith('DATA '):
            keep, beat = int(fields[2], 16), bytes.fromhex(fields[3])
            if keep != (1 << len(beat)) - 1 or not beat:
                raise ValueError('invalid output keep')
            data.extend(beat)
            if fields[1] == '1':
                frames.append(bytes(data)); data.clear()
        elif line.startswith('ACK '):
            acks.append(int(fields[1], 16))
        elif line.startswith('RESULT '):
            summaries.append(json.loads(line[7:]))
    if len(tx) != 1 or current or data or len(summaries) != 1:
        raise ValueError('incomplete/extra request/data/result')
    request = wire.decode(bytes.fromhex('b8830367c5d08af3fbb975310800') + tx[0])
    expected = dict(opcode=wire.REQUEST, destination_qpn=196, psn=0xFFFFFE,
                    remote_address=0xFEDCBA9876543210, rkey=0xFEDCBA98, read_bytes=len(payload))
    if any(request[k] != v for k, v in expected.items()):
        raise ValueError('READ request metadata differs: ' + repr(request))
    packets = (len(payload) + 4095) // 4096
    expected_ack = (((0xFFFFFE + packets - 1) & 0xFFFFFF) << 11) | (2 << 1)
    if acks != [expected_ack] or len(commands) != packets or len(frames) != packets:
        raise ValueError('READ completion/packet counts differ')
    for index, (command, received) in enumerate(zip(commands, frames)):
        part = payload[index * 4096:(index + 1) * 4096]
        padded = part + b'\0' * (-len(part) & 3)
        want = dict(address=index * 4096, length=len(padded), qpn=2, host=1, last=int(index == packets - 1))
        if command != want or received != padded:
            raise ValueError(f'command/data mismatch index={index}: {command}, expected={want}, bytes={len(received)}')
    return dict(summaries[0], message_bytes=len(payload), pass_test=True,
                original_requested_bytes_verified=True, padding_present_in_hls_memory_output=(-len(payload) & 3),
                memory_commands=commands, completion_metadata_rd=0,
                completion_precedes_payload_commit=summaries[0]['first_completion_cycle'] < summaries[0]['last_data_cycle'],
                hardware_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=pathlib.Path, required=True)
    parser.add_argument('--sizes', type=int, nargs='+', default=[1, 63, 64, 65, 4095, 4096, 4097, 8192, 8193])
    parser.add_argument('--report', type=pathlib.Path)
    args = parser.parse_args()
    rtl = args.hls_build.resolve() / 'solution1/syn/verilog'
    if not (rtl / 'rocev2_top.v').is_file() or any(not 1 <= n <= 65536 for n in args.sizes):
        parser.error('requires existing HLS build and sizes1..65536')
    axis = ROOT / 'external/corundum/fpga/lib/eth/lib/axis/rtl'
    names = ['rdma/rtl/rocev2_ipv4_icrc.v', 'rdma/rtl/rocev2_tx_padding.v', 'rdma/rtl/rocev2_integrity_transport.v']
    sources = list(rtl.glob('*.v')) + [ROOT / n for n in names] + [axis / n for n in ['axis_adapter.v', 'axis_fifo.v', 'axis_register.v']]
    sources.append(ROOT / 'external/corundum/fpga/lib/eth/rtl/lfsr.v')
    results = []
    with tempfile.TemporaryDirectory(prefix='as02-read-hls-') as directory:
        path = pathlib.Path(directory)
        (path / 'tb.v').write_text(TB)
        for dat in rtl.glob('*.dat'):
            shutil.copy2(dat, path / dat.name)
        compiled = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(path / 'test.vvp'),
                                   str(path / 'tb.v'), *map(str, sources)], capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        for size in args.sizes:
            payload = bytes((i * 179 ^ i >> 7 ^ 0xD3) & 255 for i in range(size))
            frames = wire.responses(payload, initial_psn=0xFFFFFE, source_ip='198.18.11.1',
                                    destination_ip='198.18.11.2', destination_qpn=2)
            stimulus = [w for frame in frames for w in words(frame[14:])]
            (path / 'input.hex').write_text(''.join(f'{w:037x}\n' for w in stimulus))
            sim = subprocess.run(['vvp', str(path / 'test.vvp'), f'+bytes={size}', f'+input_count={len(stimulus)}'],
                                 cwd=path, capture_output=True, text=True, timeout=120)
            if sim.returncode or 'ERROR:' in sim.stdout:
                print(sim.stdout)
                raise RuntimeError(sim.stderr or f'READ RTL case{size} failed')
            result = parse(sim.stdout, payload)
            results.append(result)
            print(json.dumps(result), flush=True)
    generated = hashlib.sha256()
    for file in sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')]):
        generated.update(file.name.encode() + b'\0' + file.read_bytes())
    identity = {str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources if f.is_relative_to(ROOT)}
    identity[str(pathlib.Path(__file__).relative_to(ROOT))] = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
    identity['rdma/read/host/read_wire.py'] = hashlib.sha256((ROOT / 'rdma/read/host/read_wire.py').read_bytes()).hexdigest()
    report = dict(scope='Generated HLS/integrity RTL only, no board or protected sink',hardware_verified=False,
                  complete=True,cases=results,generated_hls_sha256=generated.hexdigest(),source_sha256=identity)
    if args.report:
        with args.report.open('x') as out:
            out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
