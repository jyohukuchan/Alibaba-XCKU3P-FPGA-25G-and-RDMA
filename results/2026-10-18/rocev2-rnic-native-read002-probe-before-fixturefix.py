#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Coupled coherent native READ WQE/MR/HLS/protected-RX/unpad/PCIe/fence.

One request, one valid-ICRC wrong-QP rejection, then one65B READ response.
Actual unchanged HLS extracts padded data; production unpad/executor place
ONLY original WQE bytes in actual shared paged DMA. Host/link/connection/
issued-wire controller and final CQ remain MODELS. No board/pins/verbs/CQ.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import tempfile

import test_native_response_guard_rtl as native
import probe_native_executor_hls as source
import test_wqe_read_unpad_rtl as unpad
import native_executor_compiled_sim as compiled

ROOT=native.ROOT
wire=source.wire
once=source.once


UNPAD=r'''
wire [95:0] padded_command;wire padded_command_valid,padded_command_ready;
wire [511:0] padded_data;wire [63:0] padded_keep;wire padded_last,padded_valid,padded_ready;
wire [7:0] response_guard_bits,pad_guard;wire pad_busy,pad_fault;wire [7:0] pad_fault_code;
wire [31:0] pad_context_count,pad_command_count,pad_discard_count;
wire guard_token_valid,pad_context_ready;
wire guard_token_ready=e_s_read_response_ready && pad_context_ready;
assign e_s_read_response_valid=guard_token_valid && pad_context_ready;
assign wire_queue_guard=response_guard_bits | pad_guard;
rocev2_wqe_read_unpad read_unpad(
 .clk(clk),.rst(rst),.enable(1'b1),.s_context(e_s_read_response_context),
 .s_context_valid(guard_token_valid && e_s_read_response_ready),.s_context_ready(pad_context_ready),
 .downstream_queue_guard(executor_queue_guard | completion_queue_guard),
 .s_command(padded_command),.s_command_valid(padded_command_valid),.s_command_ready(padded_command_ready),
 .m_command(e_s_hls_write_command),.m_command_valid(e_s_hls_write_command_valid),.m_command_ready(e_s_hls_write_command_ready),
 .s_axis_tdata(padded_data),.s_axis_tkeep(padded_keep),.s_axis_tlast(padded_last),.s_axis_tvalid(padded_valid),.s_axis_tready(padded_ready),
 .m_axis_tdata(e_s_axis_hls_write_tdata),.m_axis_tkeep(e_s_axis_hls_write_tkeep),.m_axis_tlast(e_s_axis_hls_write_tlast),
 .m_axis_tvalid(e_s_axis_hls_write_tvalid),.m_axis_tready(e_s_axis_hls_write_tready),
 .queue_guard(pad_guard),.busy(pad_busy),.fault(pad_fault),.fault_code(pad_fault_code),
 .context_count(pad_context_count),.command_count(pad_command_count),.discarded_padding_bytes(pad_discard_count));
wire source_rx_ready;wire [39:0] source_ack_data;reg source_ack_ready=0;
reg [511:0] issued_header=0;integer issued_words=0;
wire [23:0] observed_issued_psn={issued_header[37*8+:8],issued_header[38*8+:8],issued_header[39*8+:8]};
integer padded_bytes=0,normalized_commands=0,ack_count=0,normalized_bytes=0;
reg ack_stalled=0;reg [39:0] held_ack;
'''


MONITOR=r'''
always @(posedge clk)if(!rst)begin
 if(source_qv && source_qr)source_qdone<=1;if(source_cv && source_cr)source_cdone<=1;
 if(source_stalled && (!source_tx_valid || {source_tx_last,source_tx_keep,source_tx_data}!==source_held))$fatal(1,"READ request changed under stall");
 source_stalled=source_tx_valid&&!source_tx_ready;source_held={source_tx_last,source_tx_keep,source_tx_data};
 if(source_stalled)source_tx_stalls=source_tx_stalls+1;
 if(m_hls_sq_tvalid && m_hls_sq_tready)begin
  if(!m_hls_sq_tdata[240] || m_hls_sq_tdata[247:241]!=0 || m_hls_sq_tdata[239:208]!=0 ||
   m_hls_sq_tdata[31:0]!=12 || e_owner_count!=1 || executor_queue_guard!==8'h04)$fatal(1,"actual READ full owner/SQ ABI");
  source_sq_count=source_sq_count+1;
 end
 if(source_tx_valid && source_tx_ready)begin
  if(issued_words>=4)$fatal(1,"extra outgoing READ request");
  issued_header[issued_words*128+:128]=source_tx_data;issued_words=issued_words+1;
  $display("OUT %032h %04h %b",source_tx_data,source_tx_keep,source_tx_last);
  if(source_tx_last)source_frames=source_frames+1;
 end
 if(padded_command_valid && padded_command_ready)begin
  if(padded_command!==EXPECTED_PAD_COMMAND || response_tokens!=1)$fatal(1,"actual HLS padded READ command/full routing %h",padded_command);
  source_raw_commands=source_raw_commands+1;
 end
 if(e_s_hls_write_command_valid && e_s_hls_write_command_ready)begin
  if(e_s_hls_write_command!==EXPECTED_PAYLOAD_COMMAND)$fatal(1,"normalized READ command changed full fields %h",e_s_hls_write_command);
  normalized_commands=normalized_commands+1;
 end
 if(padded_valid && padded_ready)begin
  for(source_lane=0;source_lane<64;source_lane=source_lane+1)if(padded_keep[source_lane])begin
   if(padded_bytes>=68 || padded_data[source_lane*8+:8]!==
    (padded_bytes<65 ? pcie_pattern(padded_bytes) : 8'd0))$fatal(1,"actual HLS READ padded bytes");
   padded_bytes=padded_bytes+1;
  end
  if(padded_last!==(padded_bytes==68))$fatal(1,"actual HLS READ padded last");
 end
 if(e_s_axis_hls_write_tvalid && e_s_axis_hls_write_tready)begin
  for(source_lane=0;source_lane<64;source_lane=source_lane+1)begin
   if(e_s_axis_hls_write_tkeep[source_lane])begin
    if(normalized_bytes>=65 || e_s_axis_hls_write_tdata[source_lane*8+:8]!==pcie_pattern(normalized_bytes))$fatal(1,"normalized READ source bytes");
    normalized_bytes=normalized_bytes+1;
   end else if(e_s_axis_hls_write_tdata[source_lane*8+:8]!==0)$fatal(1,"wire pad leaked past normalized keep");
  end
  if(e_s_axis_hls_write_tlast!==(normalized_bytes==65))$fatal(1,"normalized READ last");
 end
 if(ack_stalled && (!source_ack || source_ack_data!==held_ack))$fatal(1,"early HLS ACK metadata retracted");
 ack_stalled=source_ack&&!source_ack_ready;held_ack=source_ack_data;
 if(source_ack && source_ack_ready)begin
  if(source_ack_data!==40'h07fffff004 || !e_m_memory_event_valid || e_m_memory_event_error ||
   executor_queue_guard!==8'h04 || !control_busy || quiet || config_safe)$fatal(1,"HLS READ ACK substituted for fenced memory/owner");
  ack_count=ack_count+1;
 end
 if(e_s_hls_read_command_valid || e_m_axis_hls_read_tvalid || pad_fault)$fatal(1,"READ issued wrong source memory/pad fault%h",pad_fault_code);
 if(source_overflow!==0 || source_psndrop!==0 || source_retrans!==0 || source_rxbad!==0 || source_txbad!==0)$fatal(1,"actual READ HLS protocol/integrity fault");
end
'''


def bench(words):
    tb=native.make_tb(words)
    tb=once(tb,'initial begin\n #1 rst=0;','initial begin : local_read_case\n #1 rst=0;')
    # Remove only the modeled raw-command/data agent, not its authority/host/
    # fence/sentinel/STOP/retire checks. The actual HLS drives these ports.
    start=tb.index("\ne_s_hls_write_command=96'h")
    end=tb.index('while(!e_m_memory_event_valid)',start)
    tb=tb[:start]+'\npayload_deadline=cycle+5000;\n'+tb[end:]
    tb=once(tb,'m_hls_sq_tready=1;@(posedge clk);@(negedge clk);m_hls_sq_tready=0;',r'''
if(!source_qdone || !source_cdone)$fatal(1,"READ trusted connection not initialized");
allow_source_sq=1;@(posedge clk);while(!m_hls_sq_tready)@(posedge clk);@(negedge clk);
payload_deadline=cycle+5000;
while(source_frames!=1 || source_txgood!=1)begin if(cycle>payload_deadline)$fatal(1,"actual READ request not emitted");@(negedge clk);end
if(issued_words!=4 || observed_issued_psn!==24'hfffffe || source_sq_count!=1 || source_raw_commands ||
 s_local_memory_command_valid || local_memory_busy)$fatal(1,"READ response expectation before actual issued request");
''')
    tb=once(tb,'sq_command(3,1,35,0,0);',r'''
payload_deadline=cycle+5000;while(!source_ack)begin if(cycle>payload_deadline)$fatal(1,"READ HLS ACK metadata missing");@(negedge clk);end
if(source_rxgood!=1 || padded_bytes!=68 || normalized_bytes!=65 || source_raw_commands!=1 || normalized_commands!=1 ||
 pad_busy || pad_context_count!=1 || pad_command_count!=1 || pad_discard_count!=3 || pad_guard || source_frames!=1)
 $fatal(1,"actual READ HLS/guard/unpad/DMA scope");
source_ack_ready=1;@(posedge clk);@(negedge clk);source_ack_ready=0;
if(ack_count!=1)$fatal(1,"actual READ HLS ACK ownership");
sq_command(3,1,35,0,0);
''')
    tb=once(tb,"reg response_allow_frame=0,response_ready=0;",'reg response_allow_frame=0;wire response_ready;')
    tb=once(tb,'always @(negedge clk)response_ready=!rst && response_allow_frame && cycle%11>2;',
        'assign response_ready=source_rx_ready && response_allow_frame;')
    tb=once(tb,'.s_expect_psn(24\'hfffffe)','.s_expect_psn(observed_issued_psn)')
    tb=once(tb,'.m_read_response_valid(e_s_read_response_valid)','.m_read_response_valid(guard_token_valid)')
    tb=once(tb,'.m_read_response_ready(e_s_read_response_ready)','.m_read_response_ready(guard_token_ready)')
    tb=once(tb,'.queue_guard(wire_queue_guard)','.queue_guard(response_guard_bits)')
    # Build the SAME unchanged transport wrapper used by the WRITE proof,
    # replacing only test-agent connections with actual guarded RX/HLS paths.
    src=source.SOURCE.split('always @(posedge clk)if(!rst)begin',1)[0]
    src=once(src,".s_axis_rx_tdata(128'd0),.s_axis_rx_tkeep(16'd0),.s_axis_rx_tvalid(1'b0),.s_axis_rx_tready(),.s_axis_rx_tlast(1'b0),.s_axis_rx_tuser(1'b0)",
        '.s_axis_rx_tdata(rg_m_axis_hls_rx_tdata),.s_axis_rx_tkeep(rg_m_axis_hls_rx_tkeep),.s_axis_rx_tvalid(rg_m_axis_hls_rx_tvalid && response_allow_frame),.s_axis_rx_tready(source_rx_ready),.s_axis_rx_tlast(rg_m_axis_hls_rx_tlast),.s_axis_rx_tuser(1\'b0)')
    src=once(src,".m_axis_ack_tdata(),.m_axis_ack_tvalid(source_ack),.m_axis_ack_tready(1'b0)",
        '.m_axis_ack_tdata(source_ack_data),.m_axis_ack_tvalid(source_ack),.m_axis_ack_tready(source_ack_ready)')
    for a,b in [('e_s_hls_write_command','padded_command'),('e_s_hls_write_command_valid','padded_command_valid'),
        ('e_s_hls_write_command_ready','padded_command_ready'),('e_s_axis_hls_write_tdata','padded_data'),
        ('e_s_axis_hls_write_tkeep','padded_keep'),('e_s_axis_hls_write_tvalid','padded_valid'),
        ('e_s_axis_hls_write_tready','padded_ready'),('e_s_axis_hls_write_tlast','padded_last')]:
        src=re.sub(r'\b'+a+r'\b',b,src)
    driven=['m_hls_sq_tready','e_s_hls_read_command','e_s_hls_read_command_valid','e_s_hls_write_command',
        'e_s_hls_write_command_valid','e_s_axis_hls_write_tdata','e_s_axis_hls_write_tkeep',
        'e_s_axis_hls_write_tlast','e_s_axis_hls_write_tvalid','e_m_axis_hls_read_tready']
    for name in driven:
        tb,n=re.subn(r'\breg (\[[^]]+\]\s+)?'+name+r'=0;',lambda m:'wire '+(m[1]or'')+name+';',tb)
        if n!=1:raise ValueError('model declaration changed '+name)
        if re.search(r'\b'+name+r'\s*(?:<=|=(?!=))',tb):raise ValueError('model HLS driver survived '+name)
    # Independent ABI oracle (same saved full VA/QPN/length), never guessed
    # routing literals and never data/command rewriting inside the HLS core.
    monitor=MONITOR.replace('EXPECTED_PAD_COMMAND',unpad.raw_command(length=68,qpn=2)).replace(
        'EXPECTED_PAYLOAD_COMMAND',unpad.raw_command(length=65,qpn=2))
    tb=once(tb,'rocev2_wqe_memory_executor executor(',UNPAD+src+monitor+'\nrocev2_wqe_memory_executor executor(')
    end=tb.index('$finish;',tb.index('$display("NATIVE_EXECUTOR_RESULT '))
    tb=tb[:end]+r'''
$display("NATIVE_READ_HLS_RESULT {\"pass_test\":true,\"actual_HLS_requests\":%0d,\"protected_tokens\":%0d,\"HLS_padded_bytes\":%0d,\"payload_bytes\":%0d,\"discarded_pad\":%0d,\"ACK_metadata\":%0d,\"rejected_wrong_QP\":%0d}",source_sq_count,response_tokens,padded_bytes,normalized_bytes,pad_discard_count,ack_count,rg_rejected_count);
$finish;disable local_read_case;'''+tb[end+len('$finish;'):]
    return f'`include "{unpad.RTL}"\n'+tb


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--verilator',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.report.exists():p.error('preserve evidence; choose fresh report')
    words=native.native.memory.sq.local.fixture.packet();tb=bench(words)
    paths=native.native.sq.input_paths(tb)+[Path(__file__).resolve(),Path(native.__file__).resolve(),Path(native.native.__file__).resolve(),
        Path(native.native.memory.__file__).resolve(),Path(native.response.__file__).resolve(),Path(native.response.read_wire.__file__).resolve(),
        Path(unpad.__file__).resolve(),unpad.RTL,Path(source.__file__).resolve(),Path(compiled.__file__).resolve(),Path(compiled.fast.__file__).resolve(),
        ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(native.native.executor.__file__).resolve()]
    before={str(q.relative_to(ROOT)):wire.delivery.digest(q)for q in paths}
    obj=native.native.shared.SharedMRResponderRTLTests();obj.setUpClass();records=[]
    try:
        for i in range(2):
            w=native.native.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,remote_key=0,opcode=2,flags=1,length=65)
            data=(C.c_uint8*64)();err=obj.lib.as02_wqe_encode(data,C.byref(w))
            if err or bytes(data)!=native.native.shared.codec.oracle(w):raise ValueError('actual C/UBSan WQE bytes')
            records.append(bytes(data))
    finally:obj.directory.cleanup()
    good=bytearray(native.response.packet(mig=1,qpn=2));good=native.response.repair(good)
    bad=bytearray(good);bad[35]=3;bad=native.response.repair(bad)
    response_words=[int.from_bytes(v[n:n+16].ljust(16,b'\0'),'little')for v in [bad,good]for n in range(0,len(v),16)]
    run=Path(tempfile.mkdtemp(prefix='native-read-hls-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,source_sha256=before,retained_directory=str(run.relative_to(ROOT)),
        HLS_RX_extraction_memory_command_data_are_ACTUAL_RTL=True,
        physical_peer_host_link_connection_issued_controller_and_CQ_models=True,
        actual_native_RDMA_CQ_or_kernel_pins=False,hardware_verified=False,board_integrated=False,standard_verbs=False,
        protected_input_packets_hex=[bad.hex(),good.hex()],actual_C_UBSan_WQE_records=[r.hex()for r in records])
    try:
        output,identity=compiled.simulate(tb,{'input.hex':words,'records.hex':[int.from_bytes(r,'little')for r in records],
            'response.hex':response_words},args.hls_build,args.verilator.resolve(),run)
        report['actual_HLS_identity']=identity
        names=['rocev2_wqe_read_unpad','rocev2_wqe_response_guard','rocev2_wqe_memory_executor','rocev2_wqe_hls_sq',
            'rocev2_mr_table','rocev2_mr_page_table','rocev2_native_sq_endpoint','rocev2_pcie_parent_guard','rocev2_top','rocev2_integrity_transport']
        counts={n:identity['hierarchy_module_counts'].get(n,0)for n in names}
        if any(counts[n]!=(3 if n in ['rocev2_top','rocev2_integrity_transport']else 1)for n in names):raise ValueError('actual READ HLS/native hierarchy '+str(counts))
        report['actual_elaborated_module_counts']=counts
        packets=wire.packets(output)
        if len(packets)!=1:raise ValueError('exactly one actual READ request required')
        pkt=packets[0]
        if(len(pkt)!=60 or pkt[0]!=0x45 or pkt[9]!=17 or int.from_bytes(pkt[2:4],'big')!=60 or
           int.from_bytes(pkt[6:8],'big')&0x3fff or pkt[12:16]!=bytes([198,18,11,2])or pkt[16:20]!=bytes([198,18,11,1])or
           int.from_bytes(pkt[22:24],'big')!=4791 or int.from_bytes(pkt[24:26],'big')!=40 or pkt[26:28]!=b'\0\0'or
           pkt[28]!=12 or pkt[29]!=0x40 or pkt[30:32]!=b'\xff\xff'or pkt[32]&0x3f or pkt[36]&0x7f or
           int.from_bytes(pkt[33:36],'big')!=196 or int.from_bytes(pkt[37:40],'big')!=0xfffffe or
           int.from_bytes(pkt[40:48],'big')!=0xf123456789abc001 or int.from_bytes(pkt[48:52],'big')!=0 or
           int.from_bytes(pkt[52:56],'big')!=65 or wire.internet_checksum(pkt[:20])or pkt[-4:]!=wire.icrc_ipv4(pkt)):
            raise ValueError('actual READ request key0/VA64/QPN/PSN/length/IPv4/ICRC')
        summary=[json.loads(l[len('NATIVE_READ_HLS_RESULT '):])for l in output.splitlines()if l.startswith('NATIVE_READ_HLS_RESULT ')]
        dma=[json.loads(l[23:])for l in output.splitlines()if l.startswith('NATIVE_EXECUTOR_RESULT ')]
        if len(summary)!=1 or len(dma)!=1 or not summary[0]['pass_test']or not dma[0]['pass_test']:raise ValueError('actual READ coupled summaries')
        if (dma[0]['physical_descriptors'],dma[0]['read_tlps'],dma[0]['write_tlps'],dma[0]['fences'])!=(4,2,2,1):raise ValueError('real SQ/placement/fence descriptors')
        if before!={n:wire.delivery.digest(ROOT/n)for n in before}:raise ValueError('source changed during coupled READ')
        report.update(pass_test=True,terminal_exit_status=0,summary=summary[0],DMA_summary=dma[0],request_packet_hex=pkt.hex(),
            payload_bytes_verified=65,wire_padding_bytes_discarded=3,full_host_and_ring_sentinels_verified=True,
            actual_protected_RX_to_HLS_to_unpad_to_executor_to_PCIe_fence=True,
            early_HLS_ACK_not_WR_completion=True,compiled_two_state_additional_only=True,four_state_simulation=False,
            simulation_seconds=identity['simulation_seconds'],source_sha256_before_after_equal=True)
    except Exception as error:report.update(error_type=type(error).__name__,error=str(error),terminal_exit_status=1);raise
    finally:
        report['artifact_sha256']={str(q.relative_to(ROOT)):wire.delivery.digest(q)for q in run.iterdir()if q.is_file()}
        with args.report.open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()
