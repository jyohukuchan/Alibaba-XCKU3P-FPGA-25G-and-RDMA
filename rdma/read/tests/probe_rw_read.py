#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Version-2 BAR -> actual combined board app/HLS -> READ responses -> BAR RAM.

All READ request bytes and all returned application/sentinel bytes are checked.
The peer and MAC SFD completion are models; no native RNIC or PCIe hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import rw_sim
ROOT=rw_sim.ROOT
sys.path.insert(0,str(ROOT / 'rdma/hls/probe'))
sys.path.insert(0,str(ROOT / 'rdma/read/host'))
import test_control_transport as old
import app_boundary
import read_wire


def replace(text,before,after):
    if text.count(before)!=1:raise ValueError('base bench changed: '+before)
    return text.replace(before,after,1)


def bench(args,word_count,input_count,packet_count):
    tasks=old.CONTROL_TB[old.CONTROL_TB.index('task write_reg;'):old.CONTROL_TB.index('\ninitial begin')]
    tb=app_boundary.make_tb(old.TB.replace('AXIL_TASKS',tasks),'app')
    tb=replace(tb,'reg [31:0] ack_after[0:ACK_FRAMES-1];','reg [31:0] ack_after[0:ACK_WORDS-1];')
    tb=replace(tb,'ack_after[ack_loaded/4]','ack_after[ack_loaded]')
    tb=replace(tb,'reg output_ready=0;','reg output_ready=0,tx_allow=0;')
    tb=replace(tb,'output_ready=cycle>5000 && rng[2:0]!=0;','output_ready=tx_allow && rng[2:0]!=0;')
    tb=replace(tb,' $readmemh("acks.hex",acks);',
        ' $readmemh("acks.hex",acks);\n $readmemh("prefill.hex",prefill_words);\n $readmemh("expected.hex",expected_words);')
    tb=replace(tb," write_reg(24'h84,32'd30000,15,0,0); write_reg(8,1,1,0,0);",r'''
 read_reg(4,32'h20000,0);read_reg(24'h108,262144,0);read_reg(24'h10c,32'h10000,0);
 write_reg(24'h100,1,15,0,0);write_reg(24'h104,READ_WINDOW,15,0,0);
 write_reg(24'h84,250000,15,0,0);
 for(ram_index=0;ram_index<RAM_WORDS;ram_index=ram_index+1)
  write_reg(24'h10000+ram_index*4,prefill_words[ram_index],15,ram_index%3,0);
 write_reg(8,1,1,0,0);
''')
    tb=replace(tb,' read_reg(44,MESSAGE_COUNT,0); read_reg(48,TOTAL_BYTES,0);',r'''
 read_reg(44,0,0);read_reg(48,0,0);
 read_reg(24'h100,1,0);read_reg(24'h110,MESSAGE_COUNT,0);read_reg(24'h114,TOTAL_BYTES,0);
 read_reg(24'h118,PADDING_BYTES,0);read_reg(24'h11c,INPUT_PACKETS,0);read_reg(24'h120,0,0);
 read_reg(24'h124,MESSAGE_COUNT,0);read_reg(24'h128,ALLOCATION_BYTES,0);read_reg(24'h130,1,0);
 for(ram_index=0;ram_index<RAM_WORDS;ram_index=ram_index+1)
  read_reg(24'h10000+ram_index*4,expected_words[ram_index],0);
''')
    tb=replace(tb,"read_reg(24'ha0,ACK_FRAMES,0)","read_reg(24'ha0,INPUT_PACKETS,0)")
    old_display=next(line for line in tb.splitlines() if '$display("RESULT ' in line)
    tb=replace(tb,old_display,r''' $display("RESULT {\"cycles\":%0d,\"wire_read_requests\":%0d,\"success_read_completions\":%0d,\"network_stall_cycles\":%0d,\"axi_writes\":%0d,\"axi_reads\":%0d,\"early_completion_events\":%0d}",cycle,net_frames,ack_events,net_stalls,write_transactions,read_transactions,early_completion_events);''')
    tb=replace(tb,'if(cycle>35000)','if(cycle>4000000)')
    extra=r'''
reg [31:0] prefill_words[0:RAM_WORDS-1],expected_words[0:RAM_WORDS-1];
integer ram_index,early_completion_events=0,observed_read_completions=0;
initial begin wait(output_valid);repeat(20) @(negedge clk);tx_allow=1;end
always @(posedge clk) if(!rst) begin
 if(ack_valid && ack_ready) begin
  if(app.endpoint.control.capture_committed<observed_read_completions+1)
   early_completion_events=early_completion_events+1;
  observed_read_completions=observed_read_completions+1;
 end
 if(done && (app.endpoint.control.capture_committed!=MESSAGE_COUNT ||
    app.endpoint.control.capture_bytes!=TOTAL_BYTES || !app.endpoint.control.capture_idle))
  $fatal(1,"DONE before all protected RAM writes committed");
end
'''
    tb=replace(tb,'\nendmodule\n','\n'+extra+'\nendmodule\n')
    allocation=((args.message_bytes+63)&~63)*args.count
    constants=dict(MESSAGE_BYTES=args.message_bytes,MESSAGE_COUNT=args.count,TOTAL_BYTES=args.message_bytes*args.count,
        INITIAL_PSN=args.initial_psn,ACK_WORDS=input_count,ACK_FRAMES=args.count,INPUT_PACKETS=packet_count,
        READ_WINDOW=args.read_window,RAM_WORDS=word_count,PADDING_BYTES=((-args.message_bytes)&3)*args.count,
        ALLOCATION_BYTES=allocation)
    for name,value in sorted(constants.items(),key=lambda item:-len(item[0])):tb=tb.replace(name,str(value))
    return tb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--message-bytes',type=int,default=65)
    parser.add_argument('--count',type=int,default=3)
    parser.add_argument('--initial-psn',type=lambda s:int(s,0),default=0xFFFFFE)
    parser.add_argument('--read-window',type=int,default=2)
    parser.add_argument('--wall-timeout',type=int,default=900)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    stride=(args.message_bytes+63)&~63
    allocation=stride*args.count
    if args.report.exists() or not 1<=args.message_bytes<=65536 or not 1<=args.count<=4096 or \
       allocation>262144 or not 1<=args.read_window<=32 or not 0<=args.initial_psn<=0xFFFFFF:
        parser.error('new report, valid bounded READ configuration required')
    payload=hashlib.shake_256(f'combined-rw-read/{args.message_bytes}/{args.count}/seed1'.encode()).digest(args.message_bytes*args.count)
    extent=min(262144,allocation+64)
    prefill=bytearray(b'\xa5'*extent);expected=bytearray(prefill)
    inputs,after=[],[]
    packets_per_operation=(args.message_bytes+4095)//4096
    packet_count=0
    for index in range(args.count):
        part=payload[index*args.message_bytes:(index+1)*args.message_bytes]
        start=index*stride
        expected[start:start+len(part)]=part
        prefill[start:start+len(part)]=bytes(b^255 for b in part)
        frames=read_wire.responses(part,initial_psn=(args.initial_psn+index*packets_per_operation)&0xFFFFFF,
            source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=2,msn=index+1)
        packet_count+=len(frames)
        for frame in frames:
            words=old.words(frame);inputs.extend(words);after.extend([index+1]*len(words))
    fixture=dict({'acks.hex':inputs,'ack_after.hex':after},**{
        name:[int.from_bytes(data[i:i+4],'little') for i in range(0,extent,4)]
        for name,data in [('prefill.hex',prefill),('expected.hex',expected)]})
    tb=bench(args,extent//4,len(inputs),packet_count)
    output,identity=rw_sim.simulate(tb,fixture,args.hls_build,args.wall_timeout)
    print(output,flush=True)
    requests=rw_sim.ethernet_frames(output)
    if len(requests)!=args.count:raise ValueError('wrong emitted READ request count')
    for index,frame in enumerate(requests):
        decoded=read_wire.decode(frame)
        want=dict(opcode=read_wire.REQUEST,destination_qpn=0xABCDEF,
            psn=(args.initial_psn+index*packets_per_operation)&0xFFFFFF,
            remote_address=0xFEDCBA9876543210+index*args.message_bytes,rkey=0xFEDCBA98,
            read_bytes=args.message_bytes,source_ip='198.18.11.2',destination_ip='198.18.11.1')
        if frame[:14]!=bytes.fromhex('b8830367c5d08af3fbb975310800') or any(decoded[k]!=v for k,v in want.items()):
            raise ValueError('wrong READ wire metadata: '+repr(decoded))
    rows=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    if len(rows)!=1 or rows[0]['wire_read_requests']!=args.count or rows[0]['success_read_completions']!=args.count:
        raise ValueError('missing READ completion result')
    deps=[Path(__file__),Path(rw_sim.__file__),Path(old.__file__),Path(app_boundary.__file__),
        Path(read_wire.__file__),ROOT / 'rdma/tests/test_control_rtl.py',ROOT / 'rdma/host/rocev2_wire.py',
        ROOT / 'rdma/tests/test_icrc_rtl.py']
    identity['source_sha256'].update({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in deps})
    report=dict(scope='Actual combined RW board-app/HLS/Ethernet/BAR RTL, not native RNIC or physical PCIe',
        hardware_verified=False,pass_test=True,boundary='combined-rw-app',**rows[0],**identity,
        message_bytes=args.message_bytes,message_count=args.count,initial_psn=args.initial_psn,
        read_window=args.read_window,response_packets=packet_count,all_request_bytes_checked=True,
        host_bar_readback_bytes_verified=len(payload),untouched_sentinel_bytes_verified=extent-len(payload),
        prior_payload_complement_prefilled=True,payload_sha256=hashlib.sha256(payload).hexdigest(),
        protected_ram_used=True,version2_bar_used=True,done_after_ram_commit_checked=True,
        rtl_tx_guard_used=True,physical_mac_completion_modeled=True,physical_mac_drain_verified=False,
        wire_icrcs_valid=True,wire_ipv4_checksums_valid=True)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
