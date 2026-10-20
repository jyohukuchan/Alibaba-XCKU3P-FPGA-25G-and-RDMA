#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state actual per-WR SQ/adapter/HLS/padding/ICRC IPv4 packet test.

Four requests on one QP, exact zero/high/all-one/distinct keys and PSN wrap.
WRITE's memory source is explicitly a model; no registered host memory,
native DMA, Ethernet MAC/physical link, peer completion or verbs is proven.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import wrkey_delivery_sim as delivery

ROOT = delivery.ROOT
sys.path.insert(0, str(ROOT/'rdma/host'))
from rocev2_wire import internet_checksum, icrc_ipv4

KEYS = [0, 0x80000000, 0xffffffff, 0x12345678]
REMOTE = [0xfedcba9876540000+i*0x101 for i in range(4)]

TB = r'''
`timescale 1ns/1ps
module tb;
localparam WRITE=WRITE_VALUE;
reg clk=0;always #2 clk=~clk;
reg rst=0,qv=0,cv=0,sqv=0,mr=0;
reg [239:0] sq=0;
reg [31:0] key=0;
wire qr,cr,sqr,tv,tl;
wire [127:0] td;wire [15:0] tk;
wire [95:0] rc;wire rcv,rr;
reg rcr=0,rv=0,rl=0;
reg [511:0] rd=0;reg [63:0] rk=0;
wire wcv,wv,ackv;
wire [31:0] rxgood,rxbad,txgood,txbad,overflow,psndrop,retrans;
rocev2_integrity_transport #(.LEGACY_QP_KEY(0)) dut(
 .clk(clk),.rst(rst),
 .s_axis_rx_tdata(128'd0),.s_axis_rx_tkeep(16'd0),.s_axis_rx_tvalid(1'b0),.s_axis_rx_tready(),.s_axis_rx_tlast(1'b0),.s_axis_rx_tuser(1'b0),
 .m_axis_tx_tdata(td),.m_axis_tx_tkeep(tk),.m_axis_tx_tvalid(tv),.m_axis_tx_tready(mr),.m_axis_tx_tlast(tl),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h123456,24'hfffffe,24'd2,32'd3}),.s_axis_qp_tvalid(qv),.s_axis_qp_tready(qr),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(cv),.s_axis_conn_tready(cr),
 .s_axis_sq_tdata(sq),.s_axis_sq_rkey(key),.s_axis_sq_tvalid(sqv),.s_axis_sq_tready(sqr),
 .m_axis_ack_tdata(),.m_axis_ack_tvalid(ackv),.m_axis_ack_tready(1'b1),
 .m_axis_mem_write_cmd_tdata(),.m_axis_mem_write_cmd_tvalid(wcv),.m_axis_mem_write_cmd_tready(1'b1),
 .m_axis_mem_write_tdata(),.m_axis_mem_write_tkeep(),.m_axis_mem_write_tvalid(wv),.m_axis_mem_write_tready(1'b1),.m_axis_mem_write_tlast(),
 .m_axis_mem_read_cmd_tdata(rc),.m_axis_mem_read_cmd_tvalid(rcv),.m_axis_mem_read_cmd_tready(rcr),
 .s_axis_mem_read_tdata(rd),.s_axis_mem_read_tkeep(rk),.s_axis_mem_read_tvalid(rv),.s_axis_mem_read_tready(rr),.s_axis_mem_read_tlast(rl),
 .local_ip_address({4{32'h020b12c6}}),.m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(psndrop),.core_retransmit_count(retrans),.core_rx_word_count(),.core_tx_word_count(),
 .rx_integrity_good_count(rxgood),.rx_integrity_drop_count(rxbad),.tx_integrity_good_count(txgood),.tx_integrity_drop_count(txbad),.integrity_overflow_count(overflow));
reg [239:0] requests[0:3];reg [31:0] keys[0:3];
reg [31:0] rng=32'hc05e455a;
reg qdone=0,cdone=0,active=0;
integer cycle=0,issued=0,frames=0,commands=0,read_frames=0,offset=0,source_id=0;
integer lane,quiet=0,network_stalls=0,sq_stalls=0;
reg txstall=0,sqstall=0,rdstall=0;
reg [144:0] saved_tx;reg [271:0] saved_sq;reg [576:0] saved_rd;
function [7:0] pattern;
 input integer id,byte_offset;
 begin pattern=(byte_offset*131)^(byte_offset>>8)^id^8'h5a;end
endfunction
initial begin
 #1 rst=1;
 $readmemh("sq.hex",requests);$readmemh("keys.hex",keys);
 repeat(8)@(negedge clk);rst=0;qv=1;cv=1;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 if(qdone)qv=0;if(cdone)cv=0;
 if(!sqv && issued<4 && qdone && cdone && cycle>2200) begin
  sq=requests[issued];key=keys[issued];sqv=1;
 end
 mr=cycle>2500 && rng[2:0]!=0;
 rcr=WRITE && !active && rng[5:3]!=0;
 rv=active;rd=0;rk=0;rl=0;
 if(active)begin
  for(lane=0;lane<64;lane=lane+1)if(offset+lane<65)begin
   rd[lane*8+:8]=pattern(source_id,offset+lane);rk[lane]=1;
  end
  rl=offset+64>=65;
 end
end
always @(posedge clk) if(!rst)begin
 cycle=cycle+1;
 if(qv&&qr)qdone<=1;if(cv&&cr)cdone<=1;
 if(txstall && (!tv || {tl,tk,td}!==saved_tx))$fatal(1,"TX changed under stall");
 if(sqstall && (!sqv || {key,sq}!==saved_sq))$fatal(1,"per-WR key/SQ changed under stall");
 if(rdstall && (!rv || {rl,rk,rd}!==saved_rd))$fatal(1,"source changed under stall");
 txstall=tv&&!mr;sqstall=sqv&&!sqr;rdstall=rv&&!rr;
 saved_tx={tl,tk,td};saved_sq={key,sq};saved_rd={rl,rk,rd};
 if(txstall)network_stalls=network_stalls+1;if(sqstall)sq_stalls=sq_stalls+1;
 if(sqv&&sqr)begin issued=issued+1;sqv<=0;end
 if(wcv!==0 || wv!==0 || ackv!==0)$fatal(1,"unexpected incoming memory/ACK side effect");
 if(!WRITE && rcv!==0)$fatal(1,"READ request issued a source memory read");
 if(rcv&&rcr)begin
  if(!WRITE || active || commands>=4 || rc[47:0]!==48'h4000+commands*256 ||
     rc[75:48]!==28'd65 || rc[93:84]!==10'd2 || rc[79]!==((commands&1)!=0))
    $fatal(1,"unexpected source command %h count=%0d",rc,commands);
  source_id=commands;commands=commands+1;offset=0;active<=1;
 end
 if(rv&&rr)begin
  offset=offset+64;if(rl)begin active<=0;read_frames=read_frames+1;end
 end
 if(tv&&mr)begin $display("OUT %032h %04h %b",td,tk,tl);if(tl)frames=frames+1;end
 if(overflow!==0 || psndrop!==0 || retrans!==0 || rxbad!==0 || txbad!==0 || rxgood!==0)
  $fatal(1,"unexpected/unknown integrity/protocol error");
 if(issued==4 && frames==4 && txgood==4 && commands==WRITE*4 && read_frames==WRITE*4 && !active)
  quiet=quiet+1;else quiet=0;
 if(quiet==64)begin
  if(!network_stalls)$fatal(1,"network backpressure not exercised");
  $display("RESULT {\"cycles\":%0d,\"requests\":%0d,\"IP_packets\":%0d,\"source_commands\":%0d,\"source_frames\":%0d,\"network_stalls\":%0d,\"SQ_stalls\":%0d}",cycle,issued,frames,commands,read_frames,network_stalls,sq_stalls);
  $finish;
 end
 if(cycle>8000)$fatal(1,"deadline issued=%0d frames=%0d commands=%0d source=%0d txgood=%0d",issued,frames,commands,read_frames,txgood);
end
endmodule
'''


def packets(output):
    result, current = [], bytearray()
    for line in output.splitlines():
        if line.startswith('OUT '):
            _,data,keep,last = line.split()
            beat = int(data,16).to_bytes(16,'little')
            current.extend(beat[n] for n in range(16) if int(keep,16)&(1<<n))
            if last == '1': result.append(bytes(current));current.clear()
    if current: raise ValueError('truncated output IP packet')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True, help='prepared per-WR transport delivery')
    parser.add_argument('--operation', choices=['read','write'], required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists(): parser.error('preserve previous evidence')
    write = args.operation == 'write'
    opcode = 10 if write else 12
    sq = [(0xdeadbeef<<208)|(65<<176)|(REMOTE[n]<<112)|((0x4000+n*256)<<48)|
          (1<<43)|((n&1)<<42)|(2<<32)|opcode for n in range(4)]
    helper = Path(__file__).resolve()
    own = {str(p.relative_to(ROOT)):delivery.digest(p) for p in
           [helper, ROOT/'rdma/host/rocev2_wire.py']}
    tb = TB.replace('WRITE_VALUE', str(int(write)))
    output, identity = delivery.simulate(tb, {'sq.hex':sq,'keys.hex':KEYS}, args.hls_build)
    print(output, end='', flush=True)
    actual = packets(output)
    if len(actual) != 4: raise ValueError('wrong packet count')
    checked = []
    for n, p in enumerate(actual):
        padding = 3 if write else 0
        payload = bytes(((i*131)^(i>>8)^n^0x5a)&255 for i in range(65)) if write else b''
        if (len(p) != (128 if write else 60) or p[0] != 0x45 or p[9] != 17 or
                int.from_bytes(p[2:4],'big') != len(p) or internet_checksum(p[:20]) != 0 or
                p[12:16] != bytes([198,18,11,2]) or p[16:20] != bytes([198,18,11,1]) or
                int.from_bytes(p[22:24],'big') != 4791 or
                int.from_bytes(p[24:26],'big') != len(p)-20 or
                p[28] != opcode or (p[29]>>4)&3 != padding or
                int.from_bytes(p[33:36],'big') != 196 or
                int.from_bytes(p[37:40],'big') != ((0xfffffe+n)&0xffffff) or
                int.from_bytes(p[40:48],'big') != REMOTE[n] or
                int.from_bytes(p[48:52],'big') != KEYS[n] or
                int.from_bytes(p[52:56],'big') != 65 or
                p[56:-4] != payload+b'\0'*padding or p[-4:] != icrc_ipv4(p)):
            raise ValueError('per-WR packet header/key/address/PSN/payload/pad/checksum mismatch '+str(n))
        checked.append(dict(index=n,rkey=f'0x{KEYS[n]:08x}',remote_address=f'0x{REMOTE[n]:016x}',
            psn=f'0x{((0xfffffe+n)&0xffffff):06x}',bytes=len(p),sha256=hashlib.sha256(p).hexdigest(),hex=p.hex()))
    result = [json.loads(s[7:]) for s in output.splitlines() if s.startswith('RESULT ')]
    if len(result) != 1: raise ValueError('missing RTL result')
    if own != {n:delivery.digest(ROOT/n) for n in own}: raise ValueError('test source changed')
    identity['source_sha256'].update(own)
    report = dict(scope=__doc__, pass_test=True, operation=args.operation, **identity,
        **result[0], generated_testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
        all_wire_keys_addresses_PSN_lengths_checked=True, zero_key_not_QP_fallback=True,
        all_wire_IPv4_checksums_and_ICRCs_valid=True, same_QP_distinct_keys=True,
        packets=checked, payload_bytes_checked=260 if write else 0,
        native_key_mode=0, physical_host_memory_model=True,
        full_parent_functional_tested=False, native_hardware_verified=False,
        hardware_verified=False, standard_verbs_implemented=False,
        peer_completion_or_general_recovery_verified=False)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','packets']},indent=2))


if __name__ == '__main__':
    main()
