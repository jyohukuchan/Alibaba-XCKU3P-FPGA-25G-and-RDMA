#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Characterize actual pinned HLS responder and its missing key authorization.

OFFLINE ONLY. The deployed endpoint rejects these incoming request opcodes.
This intentionally unprotected transport probe must never be board-loaded.
Wrong-key memory commands are evidence of a missing guard, NOT feature passes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'rdma/read/tests'),str(ROOT/'rdma/read/host'),str(ROOT/'rdma/tests'),str(ROOT/'rdma/host')]
import rw_sim
import read_wire
import rocev2_wire
from test_icrc_rtl import words

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=0,iv=0,il=0,qv=0,cv=0,tr=0,wr=0,dr=0;
reg [127:0] id=0;reg [15:0] ik=0;
wire ir,qr,cr;wire [127:0] td;wire [15:0] tk;wire tv,tl;
wire [95:0] wc,rc;wire wv,rv;wire [511:0] wd;wire [63:0] wk;wire wdv,wl;
reg [511:0] rd=0;reg [63:0] rk=0;reg rdv=0,rl=0;wire rr;
wire [31:0] rxgood,rxbad,txgood,txbad,overflow,psndrop,retrans;
rocev2_integrity_transport dut(
 .clk(clk),.rst(rst),.s_axis_rx_tdata(id),.s_axis_rx_tkeep(ik),.s_axis_rx_tvalid(iv),.s_axis_rx_tready(ir),.s_axis_rx_tlast(il),.s_axis_rx_tuser(1'b0),
 .m_axis_tx_tdata(td),.m_axis_tx_tkeep(tk),.m_axis_tx_tvalid(tv),.m_axis_tx_tready(tr),.m_axis_tx_tlast(tl),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h987654,24'hfffffe,24'd2,32'd3}),.s_axis_qp_tvalid(qv),.s_axis_qp_tready(qr),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(cv),.s_axis_conn_tready(cr),
 .s_axis_sq_tdata(240'd0),.s_axis_sq_tvalid(1'b0),.s_axis_sq_tready(),
 .m_axis_ack_tdata(),.m_axis_ack_tvalid(),.m_axis_ack_tready(1'b1),
 .m_axis_mem_write_cmd_tdata(wc),.m_axis_mem_write_cmd_tvalid(wv),.m_axis_mem_write_cmd_tready(wr),
 .m_axis_mem_read_cmd_tdata(rc),.m_axis_mem_read_cmd_tvalid(rv),.m_axis_mem_read_cmd_tready(1'b1),
 .m_axis_mem_write_tdata(wd),.m_axis_mem_write_tkeep(wk),.m_axis_mem_write_tvalid(wdv),.m_axis_mem_write_tready(dr),.m_axis_mem_write_tlast(wl),
 .s_axis_mem_read_tdata(rd),.s_axis_mem_read_tkeep(rk),.s_axis_mem_read_tvalid(rdv),.s_axis_mem_read_tready(rr),.s_axis_mem_read_tlast(rl),
 .local_ip_address({4{32'h020b12c6}}),.m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(psndrop),.core_retransmit_count(retrans),.core_rx_word_count(),.core_tx_word_count(),
 .rx_integrity_good_count(rxgood),.rx_integrity_drop_count(rxbad),.tx_integrity_good_count(txgood),.tx_integrity_drop_count(txbad),.integrity_overflow_count(overflow));
reg [144:0] stimulus[0:511];
integer cycle=0,dummy,input_count=0,index=0,accepted=0,lane,read_offset=0;
integer txframes=0,wcommands=0,rcommands=0,wframes=0,rframes=0,quiet=0,read_mode=0;
reg qdone=0,cdone=0,read_active=0;
reg [31:0] rng=32'h455a12fd;
reg txstalled=0,wcstalled=0,wdstalled=0,rdstalled=0;
reg [144:0] saved_tx;reg [95:0] saved_wc;reg [576:0] saved_wd,saved_rd;
function [7:0] pattern;input integer offset;begin pattern=(offset*179)^(offset>>7)^8'hd3;end endfunction
initial begin
 // Explicit edge is required by the generated HLS reset inversion.
 #1 rst=1;
 dummy=$value$plusargs("input_count=%d",input_count);dummy=$value$plusargs("read=%d",read_mode);
 if(input_count<1 || input_count>512) $fatal(1,"invalid input");
 $readmemh("input.hex",stimulus,0,input_count-1);
 repeat(8) @(negedge clk);rst=0;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 if(cycle==4096) begin qv=1;cv=1;end
 if(qdone) qv=0;if(cdone) cv=0;
 if(!iv && qdone && cdone && cycle>4500 && index<input_count && rng[2:0]!=0) begin
  {il,ik,id}=stimulus[index];iv=1;
 end
 tr=cycle>4700 && rng[5:3]!=0;wr=cycle>4800 && rng[8:6]!=0;dr=cycle>4900 && rng[11:9]!=0;
 rdv=read_active && cycle>4800;rd=0;rk=0;rl=0;
 if(rdv) begin
  for(lane=0;lane<64;lane=lane+1) if(read_offset+lane<65) begin rd[lane*8+:8]=pattern(read_offset+lane);rk[lane]=1;end
  rl=read_offset+64>=65;
 end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(qv && qr) qdone<=1;if(cv && cr) cdone<=1;
 if(iv && ir) begin iv<=0;index=index+1;accepted=accepted+1;end
 if(txstalled && (!tv || {tl,tk,td}!==saved_tx)) $fatal(1,"TX unstable");
 if(wcstalled && (!wv || wc!==saved_wc)) $fatal(1,"write command unstable");
 if(wdstalled && (!wdv || {wl,wk,wd}!==saved_wd)) $fatal(1,"write data unstable");
 if(rdstalled && (!rdv || {rl,rk,rd}!==saved_rd)) $fatal(1,"read source unstable");
 txstalled=tv&&!tr;wcstalled=wv&&!wr;wdstalled=wdv&&!dr;rdstalled=rdv&&!rr;
 saved_tx={tl,tk,td};saved_wc=wc;saved_wd={wl,wk,wd};saved_rd={rl,rk,rd};
 if(rv) begin
  $display("MEMR %h %d %d %b %b",rc[47:0],rc[75:48],rc[93:84],rc[79],rc[76]);
  rcommands=rcommands+1;read_active<=1;read_offset=0;
 end
 if(rdv && rr) begin
  read_offset=read_offset+64;if(rl) begin read_active<=0;rframes=rframes+1;end
 end
 if(wv && wr) begin
  $display("MEMW %h %d %d %b %b",wc[47:0],wc[75:48],wc[93:84],wc[79],wc[76]);wcommands=wcommands+1;
 end
 if(wdv && dr) begin
  $write("DATA %b %h ",wl,wk);for(lane=0;lane<64;lane=lane+1) if(wk[lane]) $write("%02h",wd[lane*8+:8]);$display("");
  if(wl) wframes=wframes+1;
 end
 if(tv && tr) begin
  $write("OUT %h %h %b",td,tk,tl);$display("");if(tl) txframes=txframes+1;
 end
 if(rxbad!==0 || txbad!==0 || overflow!==0 || psndrop!==0 || retrans!==0)
  $fatal(1,"unknown/nonzero transport/integrity fault");
 if(accepted==input_count && txframes==1 && ((read_mode && rframes==1) || (!read_mode && wframes==1))) quiet=quiet+1;else quiet=0;
 if(quiet==100) begin
  $display("RESULT {\"cycles\":%d,\"read_commands\":%d,\"write_commands\":%d,\"tx_frames\":%d,\"rx_good\":%d,\"tx_good\":%d}",cycle,rcommands,wcommands,txframes,rxgood,txgood);$finish;
 end
 if(cycle>12000) $fatal(1,"deadline accepted=%d wcmd=%d rcmd=%d wframe=%d rframe=%d tx=%d qdone=%b cdone=%b rxgood=%d",accepted,wcommands,rcommands,wframes,rframes,txframes,qdone,cdone,rxgood);
end
endmodule
'''


def simulate(hls_build,operation,key,address):
    payload=bytes((i*179 ^ i>>7 ^ 0xd3)&255 for i in range(65))
    endpoint=dict(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
                  source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
                  destination_qpn=2,psn=0x987654,remote_address=address,rkey=key)
    if operation=='write':frame=rocev2_wire.write_only_frame(**endpoint,payload=payload)
    else:frame=read_wire.encode(**endpoint,opcode=read_wire.REQUEST,read_bytes=65)
    tb=TB.replace('input_count=0','input_count='+str(len(words(frame[14:]))))
    tb=tb.replace('read_mode=0','read_mode='+str(int(operation=='read')))
    output,identity=rw_sim.simulate(tb,{'input.hex':words(frame[14:])},hls_build,wall_timeout=60)
    commands=[];data=bytearray();summaries=[]
    for line in output.splitlines():
        fields=line.split()
        if line.startswith(('MEMW ','MEMR ')):
            commands.append(dict(kind=fields[0],address=int(fields[1],16),length=int(fields[2]),
                                 qpn=int(fields[3]),host=int(fields[4]),last=int(fields[5])))
        elif line.startswith('DATA '):
            part=bytes.fromhex(fields[3]);assert int(fields[2],16)==(1<<len(part))-1;data+=part
        elif line.startswith('RESULT '):summaries.append(json.loads(line[7:]))
    frames=rw_sim.ethernet_frames(output)
    assert len(summaries)==len(commands)==len(frames)==1,'missing/extra response or memory command'
    assert summaries[0]['rx_good']==summaries[0]['tx_good']==1
    command=commands[0]
    assert command['address']==address&((1<<48)-1) and command['qpn']==2
    assert command['host']==1 and command['last']==1
    ip=frames[0] # helper returns IP bytes here: no Ethernet was instantiated.
    assert ip[0]==0x45 and int.from_bytes(ip[2:4],'big')==len(ip)
    assert rocev2_wire.internet_checksum(ip[:20])==0,'invalid actual response IPv4 checksum'
    ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+ip
    if operation=='read':
        response=read_wire.decode(ethernet)
        assert response['opcode']==read_wire.ONLY and response['payload']==payload
        assert response['psn']==0x987654 and response['destination_qpn']==196
        assert response['syndrome']&0xe0==0,'READ response must be a success AETH, not NAK/RNR'
        assert command['kind']=='MEMR' and command['length']==65 and not data
    else:
        response=rocev2_wire.decode_ethernet(ethernet)
        # Credit bits0..4 need not equal the CX455A's0x1f. Check the
        # protocol syndrome bits, retaining rejection of NAK/RNR responses.
        assert response['opcode']==0x11 and response['icrc_valid'] and response['aeth_syndrome']&0xe0==0,(response,command)
        assert response['psn']==0x987654 and response['destination_qpn']==196
        assert command['kind']=='MEMW' and command['length']==68 and data==payload+b'\0'*3
    result=dict(summaries[0],operation=operation,requested_key=f'0x{key:08x}',configured_key='0xfedcba98',
                key_matches=key==0xfedcba98,request_address=f'0x{address:016x}',memory_command=command,
                response_valid=True,payload_bytes_verified=65,wire_checksums_verified=True,
                wire_response_ipv4_hex=ip.hex(),memory_write_data_hex=bytes(data).hex(),
                actual_payload_sha256=hashlib.sha256(response['payload'] if operation=='read' else bytes(data[:65])).hexdigest(),
                reference_payload_sha256=hashlib.sha256(payload).hexdigest(),
                unprotected_transport_accepted_request=True,authorization_gap_observed=key!=0xfedcba98,
                address_upper_bits_lost=address>>48!=0)
    return result,identity


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.report.exists():p.error('preserve existing evidence')
    cases=[];identity=None
    for operation in ('write','read'):
        for key in (0xfedcba98,0x01234567):
            result,identity=simulate(args.hls_build,operation,key,0x123456789000)
            cases.append(result);print(json.dumps(result),flush=True)
    result,identity=simulate(args.hls_build,'read',0xfedcba98,0xfedcba9876543210)
    cases.append(result);print(json.dumps(result),flush=True)
    report=dict(scope='Offline unprotected actual HLS responder characterization; gaps are not RNIC feature passes',
                hardware_verified=False,board_integrated=False,deployed_endpoint_accepts_inbound_requests=False,
                completion_claim=False,cases=cases,**identity)
    report['source_sha256']['rdma/rnic/tests/probe_responder_transport.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name in ('rdma/read/host/read_wire.py','rdma/read/tests/rw_sim.py','rdma/host/rocev2_wire.py','rdma/tests/test_icrc_rtl.py'):
        report['source_sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
