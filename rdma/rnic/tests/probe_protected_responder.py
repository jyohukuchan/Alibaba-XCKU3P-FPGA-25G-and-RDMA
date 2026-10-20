#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite offline MR-protected responder test using actual pinned generated HLS.

No FPGA, socket, driver or network changes. This is not board/DMA signoff.
All memory placement uses the emitted full-width command in a simulated RAM.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'rdma/read/host'),str(ROOT/'rdma/tests'),str(ROOT/'rdma/host')]
import read_wire
import rocev2_wire
from test_icrc_rtl import words
from protected_sim import simulate
import rw_sim

VA=0xfedcba9876543000
DMA=0x8123456789abc000
PSN=0x987654
PAYLOAD=bytes((i*179 ^ i>>7 ^ 0xd3)&255 for i in range(65))

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=0,iv=0,il=0,tr=0,qv=0,cv=0,car=0,reject_ready=0;
reg [127:0] id=0;reg [15:0] ik=0;
wire ir,qr,qready,cr,cav;wire [31:0] cak;wire [7:0] ce;
reg [1:0] cc=1;reg [2:0] ci=0;reg [15:0] cp=17;
reg [31:0] ck=0;reg [3:0] cf=7;
wire [127:0] td;wire [15:0] tk;wire tv,tl;
wire mw,mv;wire [63:0] ma;wire [31:0] ml;wire [15:0] mt;
reg mr=0,wdr=0,rdv=0,rl=0,sv=0;reg [511:0] rd=0;reg [63:0] rk=0;
wire [511:0] wd;wire [63:0] wk;wire wdv,wl,rr,sr;
reg [15:0] st=0;reg [7:0] se=0;
wire reject_valid,quiet,fault;wire [7:0] reject_error,fc;wire [23:0] reject_qpn,reject_psn;
wire [31:0] accepted,rejected,completed,rxgood,rxbad,deferred;
rocev2_protected_responder dut(
 .clk(clk),.rst(rst),.s_axis_rx_tdata(id),.s_axis_rx_tkeep(ik),.s_axis_rx_tvalid(iv),.s_axis_rx_tready(ir),.s_axis_rx_tlast(il),.s_axis_rx_tuser(1'b0),
 .m_axis_tx_tdata(td),.m_axis_tx_tkeep(tk),.m_axis_tx_tvalid(tv),.m_axis_tx_tready(tr),.m_axis_tx_tlast(tl),
 .cfg_qp_number(3'd2),.cfg_peer_qp_number(24'd196),.cfg_qp_pd(16'd17),
 .cfg_local_ip(32'hc6120b02),.cfg_peer_ip(32'hc6120b01),.cfg_rx_psn(24'h987654),.cfg_tx_psn(24'hfffffe),
 .cfg_qp_valid(qv),.cfg_qp_ready(qr),.qp_ready(qready),
 .cfg_mr_command(cc),.cfg_mr_index(ci),.cfg_mr_pd(cp),.cfg_mr_key(ck),
 .cfg_mr_virtual_address(64'hfedcba9876543000),.cfg_mr_dma_address(64'h8123456789abc000),.cfg_mr_length(64'd4096),.cfg_mr_access(cf),
 .cfg_mr_valid(cv),.cfg_mr_ready(cr),.cfg_mr_response_error(ce),.cfg_mr_response_key(cak),.cfg_mr_response_valid(cav),.cfg_mr_response_ready(car),
 .m_memory_command_write(mw),.m_memory_command_address(ma),.m_memory_command_length(ml),.m_memory_command_tag(mt),.m_memory_command_valid(mv),.m_memory_command_ready(mr),
 .m_axis_memory_write_tdata(wd),.m_axis_memory_write_tkeep(wk),.m_axis_memory_write_tvalid(wdv),.m_axis_memory_write_tready(wdr),.m_axis_memory_write_tlast(wl),
 .s_axis_memory_read_tdata(rd),.s_axis_memory_read_tkeep(rk),.s_axis_memory_read_tvalid(rdv),.s_axis_memory_read_tready(rr),.s_axis_memory_read_tlast(rl),
 .s_memory_status_tag(st),.s_memory_status_error(se),.s_memory_status_valid(sv),.s_memory_status_ready(sr),
 .m_reject_error(reject_error),.m_reject_qpn(reject_qpn),.m_reject_psn(reject_psn),.m_reject_valid(reject_valid),.m_reject_ready(reject_ready),
 .quiescent(quiet),.fault(fault),.fault_code(fc),.accepted_count(accepted),.rejected_count(rejected),.completed_count(completed),
 .tx_deferred_cycles(deferred),.rx_integrity_good_count(rxgood),.rx_integrity_drop_count(rxbad));
reg [144:0] stimulus[0:STIMULUS_LAST];
reg [7:0] memory[0:4095];
integer cycle=0,lane,offset=0,data_offset=0,backend_length=0,command_cycle=0,data_done_cycle=0;
integer commands=0,wframes=0,rframes=0,txframes=0,statuses=0;
reg backend_active=0,backend_write=0,backend_done=0,status_done=0;
reg [15:0] backend_tag=0;
reg [31:0] rng=32'h455a1234;
reg mcstall=0,wdstall=0,txstall=0,rdstall=0;
reg [112:0] saved_mc;reg [576:0] saved_wd,saved_rd;reg [144:0] saved_tx;
integer expiry,command_before,write_before,tx_before,rejected_before,completed_before,i;
reg revoke_watch=0;
reg expect_fault=0;

always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 mr=rng[2:0]!=0;wdr=cycle>command_cycle+100 && rng[5:3]!=0;tr=rng[8:6]!=0;
 rdv=backend_active && !backend_write && !backend_done && cycle>command_cycle+100;
 rd=0;rk=0;rl=data_offset+64>=backend_length;
 if(rdv) for(lane=0;lane<64;lane=lane+1) if(data_offset+lane<backend_length) begin
  rd[lane*8+:8]=memory[offset+data_offset+lane];rk[lane]=1;
 end
 sv=backend_active && backend_done && !status_done && cycle>data_done_cycle+200;
 st=backend_tag;se=0;
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(cycle>18000) $fatal(1,"global deadline commands=%d tx=%d a/r/c=%d/%d/%d fault=%b/%d",commands,txframes,accepted,rejected,completed,fault,fc);
 if(fault && !expect_fault) $fatal(1,"unexpected fault %d",fc);
 if(mcstall && (!mv || {mw,ma,ml,mt}!==saved_mc)) $fatal(1,"command instability");
 if(wdstall && (!wdv || {wl,wk,wd}!==saved_wd)) $fatal(1,"write instability");
 if(txstall && (!tv || {tl,tk,td}!==saved_tx)) $fatal(1,"TX instability");
 if(rdstall && (!rdv || {rl,rk,rd}!==saved_rd)) $fatal(1,"read-source instability");
 mcstall=mv&&!mr;wdstall=wdv&&!wdr;txstall=tv&&!tr;rdstall=rdv&&!rr;
 saved_mc={mw,ma,ml,mt};saved_wd={wl,wk,wd};saved_tx={tl,tk,td};saved_rd={rl,rk,rd};
 if(revoke_watch && (cr || cav || quiet)) $fatal(1,"MR reconfigured before operation and TX drain");
 if(mv && mr) begin
  if(backend_active && !status_done) $fatal(1,"overlapping backend lease");
  if(ma<64'h8123456789abc000 || ma+ml>64'h8123456789abd000 || ml!=65 || mt!=commands+1)
   $fatal(1,"bad full-width command %h/%d/%d",ma,ml,mt);
  offset=ma-64'h8123456789abc000;backend_length=ml;backend_tag=mt;backend_write=mw;
  data_offset=0;command_cycle=cycle;backend_active=1;backend_done=0;status_done=0;commands=commands+1;
  $display("COMMAND %b %h %d %d",mw,ma,ml,mt);
 end
 if(wdv && wdr) begin
  if(!backend_active || !backend_write || backend_done) $fatal(1,"unexpected write data");
  $write("DATA %b %h ",wl,wk);
  for(lane=0;lane<64;lane=lane+1) if(wk[lane]) begin
   if(data_offset+lane>=backend_length) $fatal(1,"pad/overflow reached memory");
   memory[offset+data_offset+lane]=wd[lane*8+:8];$write("%02h",wd[lane*8+:8]);
  end
  $display("");data_offset=data_offset+64;
  if(wl) begin backend_done=1;data_done_cycle=cycle;wframes=wframes+1;end
 end
 if(rdv && rr) begin
  data_offset=data_offset+64;
  if(rl) begin backend_done=1;data_done_cycle=cycle;rframes=rframes+1;end
 end
 if(tv && !status_done) $fatal(1,"response visible before memory completion");
 if(tv && tr) begin
  $display("OUT %h %h %b",td,tk,tl);if(tl) txframes=txframes+1;
 end
 if(sv && sr) begin status_done=1;statuses=statuses+1;$display("COMMIT %d %d",st,cycle);end
end

task configure_epoch;
 input [31:0] floor;
 begin
  @(negedge clk);cc=3;ck=floor;cv=1;car=0;
  @(posedge clk);while(!cr) @(posedge clk);
  @(negedge clk);cv=0;
  while(!cav) @(negedge clk);
  if(ce!==0 || cak!==floor) $fatal(1,"explicit MR epoch rejected");
  car=1;@(negedge clk);car=0;
 end
endtask
task configure_mr;
 input [2:0] index;input [15:0] pd;input [3:0] flags;input [31:0] result_key;
 begin
  @(negedge clk);ci=index;cp=pd;cf=flags;cc=1;ck=0;cv=1;car=0;
  @(posedge clk);while(!cr) @(posedge clk);
  @(negedge clk);cv=0;
  while(!cav) @(negedge clk);
  if(ce!==0 || cak!==result_key) $fatal(1,"MR registration error/key %d/%h",ce,cak);
  repeat(3) @(negedge clk);car=1;@(negedge clk);car=0;
 end
endtask
task send_frame;
 input integer start,count;
 begin
  command_before=commands;write_before=wframes;tx_before=txframes;rejected_before=rejected;completed_before=completed;
  for(i=start;i<start+count;i=i+1) begin
   @(negedge clk);{il,ik,id}=stimulus[i];iv=1;
   @(posedge clk);while(!ir) @(posedge clk);
  end
  @(negedge clk);iv=0;
 end
endtask
task deny;
 input [7:0] expected_error;
 begin
  expiry=cycle+200;while(!reject_valid && cycle<expiry) @(negedge clk);
  if(!reject_valid || reject_error!==expected_error) $fatal(1,"wrong rejection got=%d expected=%d",reject_error,expected_error);
  repeat(5) begin
   @(negedge clk);if(!reject_valid || reject_error!==expected_error) $fatal(1,"reject not stable");
  end
  reject_ready=1;@(negedge clk);reject_ready=0;
  repeat(20) @(negedge clk);
  if(commands!=command_before || wframes!=write_before || txframes!=tx_before || completed!=completed_before || rejected!=rejected_before+1 || !quiet)
   $fatal(1,"rejected request side effect or failed recovery");
  $display("DENIED %d",expected_error);
 end
endtask
task allow;
 begin
  expiry=cycle+2000;while(completed==completed_before && cycle<expiry) @(negedge clk);
  if(completed!=completed_before+1 || commands!=command_before+1 || txframes!=tx_before+1 || rejected!=rejected_before || !quiet)
   $fatal(1,"authorized operation did not complete a/r/c=%d/%d/%d cmd=%d tx=%d quiet=%b",accepted,rejected,completed,commands,txframes,quiet);
  repeat(20) @(negedge clk);
 end
endtask

initial begin
 #1 rst=1;
 $readmemh("input.hex",stimulus);
 for(i=0;i<4096;i=i+1) memory[i]=(i*37)^8'h5a;
 repeat(8) @(negedge clk);rst=0;
 repeat(4100) @(negedge clk);
 configure_epoch(0);
 configure_mr(0,17,7,8);configure_mr(1,18,7,9);configure_mr(2,17,4,10);
 @(negedge clk);qv=1;
 @(posedge clk);while(!qr) @(posedge clk);
 @(negedge clk);qv=0;
 while(!qready) @(negedge clk);
 // TEST_BODY
 if(deferred==0 || statuses!=commands || completed!=commands || fault) $fatal(1,"completion/early response scenario not exercised");
 $display("RESULT {\"pass_test\":true,\"cycles\":%0d,\"commands\":%0d,\"write_frames\":%0d,\"read_frames\":%0d,\"tx_frames\":%0d,\"statuses\":%0d,\"accepted\":%0d,\"rejected\":%0d,\"completed\":%0d,\"rx_good\":%0d,\"rx_bad\":%0d,\"deferred_tx_cycles\":%0d}",cycle,commands,wframes,rframes,txframes,statuses,accepted,rejected,completed,rxgood,rxbad,deferred);
 $finish;
end
endmodule
'''


def stimulus():
    fixtures=[];body=[];cases=[];psn=PSN
    def add(name,operation='write',key=8,address=VA+0x210,error=0,mutate=None):
        nonlocal psn
        args=dict(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
                  source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
                  destination_qpn=2,psn=psn,remote_address=address,rkey=key)
        if operation=='write':frame=rocev2_wire.write_only_frame(**args,payload=PAYLOAD)
        else:frame=read_wire.encode(**args,opcode=read_wire.REQUEST,read_bytes=65)
        if mutate:frame=mutate(frame)
        parts=words(frame[14:]);start=len(fixtures);fixtures.extend(parts)
        body.append(f'$display("CASE {name}");send_frame({start},{len(parts)});')
        if error:body.append(f'deny(8\'d{error});')
        else:body.append('allow();');psn=(psn+1)&0xffffff
        cases.append(dict(name=name,operation=operation,key=key,address=f'0x{address:016x}',
                          expected_error=error,psn=int.from_bytes(frame[14+37:14+40],'big')))
    def change(offset,value):
        def mutate(frame):
            ethernet=frame[:14];packet=bytearray(frame[14:]);packet[offset:offset+len(value)]=value
            packet[10:12]=b'\0\0';packet[10:12]=rocev2_wire.internet_checksum(packet[:20]).to_bytes(2,'big')
            packet[-4:]=rocev2_wire.icrc_ipv4(packet)
            return ethernet+packet
        return mutate
    add('wrong_write_key',key=0x80000008,error=1)
    add('wrong_read_key',operation='read',key=0x80000008,error=1)
    add('wrong_pd',key=9,error=2)
    add('read_only_write',key=10,error=3)
    add('below_mr',address=VA-1,error=4)
    add('past_mr_end',operation='read',address=VA+4095,error=4)
    add('overflow_va',operation='read',address=(1<<64)-32,error=4)
    add('wrong_qp',error=17,mutate=change(33,(3).to_bytes(3,'big')))
    add('wrong_peer',error=17,mutate=change(12,bytes([198,18,11,3])))
    add('unexpected_psn',error=18,mutate=change(37,(PSN+1).to_bytes(3,'big')))
    add('length_mismatch',error=16,mutate=change(52,(64).to_bytes(4,'big')))
    add('unsupported_first',error=19,mutate=change(28,b'\x06'))
    add('valid_high_va_write')
    add('read_after_write',operation='read')
    add('valid_second_write')
    # Hold INVALIDATE valid during this entire operation. It cannot handshake
    # until the response's last beat drains, then revoke and reuse the slot.
    last_allow=body.pop()
    body += [r'''
fork
 begin
  while(!mv) @(negedge clk);
  ci=0;cp=17;cc=2;ck=8;cv=1;car=0;revoke_watch=1;
  while(completed==completed_before) @(negedge clk);
  revoke_watch=0;
  @(posedge clk);while(!cr) @(posedge clk);
  @(negedge clk);cv=0;
  while(!cav) @(negedge clk);
  if(ce!==0 || cak!==0) $fatal(1,"invalidation failed");
  car=1;@(negedge clk);car=0;
 end
 begin
  expiry=cycle+2000;while(completed==completed_before && cycle<expiry) @(negedge clk);
  if(completed!=completed_before+1) $fatal(1,"lease never drained");
 end
join
configure_mr(0,17,7,16);
''']
    add('stale_key_after_reuse',operation='read',key=8,error=1)
    add('fresh_key_read',operation='read',key=16)
    # Integrity rejection must not touch MR, advance PSN, or create a local
    # authorization rejection. Follow it by a good request with the SAME PSN.
    args=dict(source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=2,
              psn=psn,remote_address=VA+0x210,rkey=16,opcode=read_wire.REQUEST,read_bytes=65)
    corrupt=bytearray(read_wire.encode(**args));corrupt[-1]^=1
    parts=words(corrupt[14:]);start=len(fixtures);fixtures.extend(parts)
    body += [f'$display("CASE bad_icrc");send_frame({start},{len(parts)});',r'''
repeat(150) @(negedge clk);
if(rxbad!=1 || commands!=command_before || txframes!=tx_before || rejected!=rejected_before || !quiet)
 $fatal(1,"ICRC rejection escaped or failed recovery");
''']
    cases.append(dict(name='bad_icrc',expected_integrity_drop=True))
    add('after_bad_icrc_read',operation='read',key=16)
    return fixtures,body,cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve previous evidence: use a new report')
    fixtures,body,cases=stimulus()
    tb=TB.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY','\n'.join(body))
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=120)
    print(output,flush=True)
    summaries=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    assert len(summaries)==1 and summaries[0]['pass_test']
    expected_good=[case for case in cases if not case.get('expected_error') and not case.get('expected_integrity_drop')]
    actual_frames=rw_sim.ethernet_frames(output)
    assert len(actual_frames)==len(expected_good)==summaries[0]['commands']
    responses=[]
    for case,packet in zip(expected_good,actual_frames):
        assert rocev2_wire.internet_checksum(packet[:20])==0
        ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if case['operation']=='read':
            decoded=read_wire.decode(ethernet)
            assert decoded['opcode']==read_wire.ONLY and decoded['payload']==PAYLOAD
            assert decoded['syndrome']&0xe0==0
        else:
            decoded=rocev2_wire.decode_ethernet(ethernet)
            assert decoded['opcode']==0x11 and decoded['icrc_valid'] and decoded['aeth_syndrome']&0xe0==0
        assert decoded['psn']==case['psn'] and decoded['destination_qpn']==196
        responses.append(dict(case=case['name'],ipv4_hex=packet.hex(),wire_checksums_verified=True,
                              payload_bytes_verified=65 if case['operation']=='read' else 0))
    commands=[];write_data=bytearray()
    for line in output.splitlines():
        if line.startswith('COMMAND '):
            _,kind,address,length,tag=line.split()
            commands.append(dict(write=kind=='1',address=f'0x{int(address,16):016x}',length=int(length),tag=int(tag)))
        if line.startswith('DATA '):
            _,last,keep,hex_data=line.split();part=bytes.fromhex(hex_data)
            assert int(keep,16)==(1<<len(part))-1;write_data.extend(part)
    assert write_data==PAYLOAD*sum(case['operation']=='write' for case in expected_good)
    for command,case in zip(commands,expected_good):
        assert int(command['address'],16)==DMA+int(case['address'],16)-VA
        assert command['write']==(case['operation']=='write') and command['length']==65
    report=dict(scope='Offline protected actual-HLS responder, single QP/single outstanding/<=4096B prototype',
                hardware_verified=False,board_integrated=False,pci_dma_implemented=False,completion_claim=False,
                cases=cases,summary=summaries[0],memory_commands=commands,responses=responses,
                write_payload_bytes_verified=len(write_data),write_payload_sha256=hashlib.sha256(write_data).hexdigest(),
                expected_payload_sha256=hashlib.sha256(PAYLOAD*sum(case['operation']=='write' for case in expected_good)).hexdigest(),
                **identity)
    for name in ('rdma/rnic/tests/probe_protected_responder.py','rdma/rnic/tests/protected_sim.py',
                 'rdma/host/rocev2_wire.py','rdma/read/host/read_wire.py','rdma/tests/test_icrc_rtl.py'):
        report['source_sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
