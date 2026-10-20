#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""One actual coherent WQE/MR/HLS/executor/paged-PCIe WRITE source to IP wire.

Physical host/link, initial host pages and final wire/CQ owner are MODELS.
No peer ACK/protected READ-response ingress/MAC completion, Linux pins, board
or standard verbs is claimed. The HLS/payload/execution/DMA chain is actual
RTL, not a copied authorized tuple or separately modeled HLS source command.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import tempfile

import test_native_memory_executor_rtl as native
import probe_wrkey_wire as wire

ROOT=native.ROOT


def once(text,old,new):return native.memory.sq.once(text,old,new)


SOURCE=r'''
reg source_qv=0,source_cv=0,source_qdone=0,source_cdone=0,allow_source_sq=0;
wire source_qr,source_cr,source_sqr,source_tx_valid,source_tx_last;
wire [127:0] source_tx_data;wire [15:0] source_tx_keep;
wire [31:0] source_rxgood,source_rxbad,source_txgood,source_txbad,source_overflow,source_psndrop,source_retrans;
wire source_ack,source_write_command,source_write_data;
wire [95:0] source_write_raw;
wire [511:0] source_write_payload;wire [63:0] source_write_keep;wire source_write_last;
reg source_tx_ready=0;
integer source_frames=0,source_payload_bytes=0,source_raw_commands=0,source_sq_count=0,source_tx_stalls=0,source_lane;
reg source_stalled=0;reg [144:0] source_held;
assign m_hls_sq_tready=source_sqr && allow_source_sq;
rocev2_integrity_transport #(.LEGACY_QP_KEY(0)) source_transport(
 .clk(clk),.rst(rst),
 .s_axis_rx_tdata(128'd0),.s_axis_rx_tkeep(16'd0),.s_axis_rx_tvalid(1'b0),.s_axis_rx_tready(),.s_axis_rx_tlast(1'b0),.s_axis_rx_tuser(1'b0),
 .m_axis_tx_tdata(source_tx_data),.m_axis_tx_tkeep(source_tx_keep),.m_axis_tx_tvalid(source_tx_valid),.m_axis_tx_tready(source_tx_ready),.m_axis_tx_tlast(source_tx_last),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h123456,24'hfffffe,24'd2,32'd3}),.s_axis_qp_tvalid(source_qv),.s_axis_qp_tready(source_qr),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(source_cv),.s_axis_conn_tready(source_cr),
 .s_axis_sq_tdata(m_hls_sq_tdata[239:0]),.s_axis_sq_rkey(m_hls_sq_tdata[239:208]),
 .s_axis_sq_tvalid(m_hls_sq_tvalid && allow_source_sq),.s_axis_sq_tready(source_sqr),
 .m_axis_ack_tdata(),.m_axis_ack_tvalid(source_ack),.m_axis_ack_tready(1'b0),
 .m_axis_mem_write_cmd_tdata(e_s_hls_write_command),.m_axis_mem_write_cmd_tvalid(e_s_hls_write_command_valid),.m_axis_mem_write_cmd_tready(e_s_hls_write_command_ready),
 .m_axis_mem_write_tdata(e_s_axis_hls_write_tdata),.m_axis_mem_write_tkeep(e_s_axis_hls_write_tkeep),
 .m_axis_mem_write_tvalid(e_s_axis_hls_write_tvalid),.m_axis_mem_write_tready(e_s_axis_hls_write_tready),.m_axis_mem_write_tlast(e_s_axis_hls_write_tlast),
 .m_axis_mem_read_cmd_tdata(e_s_hls_read_command),.m_axis_mem_read_cmd_tvalid(e_s_hls_read_command_valid),.m_axis_mem_read_cmd_tready(e_s_hls_read_command_ready),
 .s_axis_mem_read_tdata(e_m_axis_hls_read_tdata),.s_axis_mem_read_tkeep(e_m_axis_hls_read_tkeep),
 .s_axis_mem_read_tvalid(e_m_axis_hls_read_tvalid),.s_axis_mem_read_tready(e_m_axis_hls_read_tready),.s_axis_mem_read_tlast(e_m_axis_hls_read_tlast),
 .local_ip_address({4{32'h020b12c6}}),.m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(source_psndrop),.core_retransmit_count(source_retrans),.core_rx_word_count(),.core_tx_word_count(),
 .rx_integrity_good_count(source_rxgood),.rx_integrity_drop_count(source_rxbad),
 .tx_integrity_good_count(source_txgood),.tx_integrity_drop_count(source_txbad),.integrity_overflow_count(source_overflow));
always @(negedge clk)if(!rst)begin
 source_qv=!source_qdone;source_cv=!source_cdone;
 source_tx_ready=(cycle%11)!=0 && (cycle%11)!=1 && (cycle%11)!=2;
end
always @(posedge clk)if(!rst)begin
 if(source_qv && source_qr)source_qdone<=1;if(source_cv && source_cr)source_cdone<=1;
 if(source_stalled && (!source_tx_valid || {source_tx_last,source_tx_keep,source_tx_data}!==source_held))$fatal(1,"actual HLS source TX changed under stall");
 source_stalled=source_tx_valid&&!source_tx_ready;source_held={source_tx_last,source_tx_keep,source_tx_data};
 if(source_stalled)source_tx_stalls=source_tx_stalls+1;
 if(m_hls_sq_tvalid && m_hls_sq_tready)begin
  if(!m_hls_sq_tdata[240] || m_hls_sq_tdata[247:241]!=0 || m_hls_sq_tdata[239:208]!=0 || e_owner_count!=1 || executor_queue_guard!==8'h04)
   $fatal(1,"actual source HLS key0/full owner ABI");
  source_sq_count=source_sq_count+1;
 end
 if(e_s_hls_read_command_valid && e_s_hls_read_command_ready)source_raw_commands=source_raw_commands+1;
 if(e_m_axis_hls_read_tvalid && e_m_axis_hls_read_tready)begin
  for(source_lane=0;source_lane<64;source_lane=source_lane+1)begin
   if(e_m_axis_hls_read_tkeep[source_lane])begin
    if(source_payload_bytes>=65 || e_m_axis_hls_read_tdata[source_lane*8+:8]!==pcie_host[4093+source_payload_bytes])$fatal(1,"actual HLS received wrong registered host payload");
    source_payload_bytes=source_payload_bytes+1;
   end else if(e_m_axis_hls_read_tdata[source_lane*8+:8]!==0)$fatal(1,"actual HLS host tail not zero");
  end
  if(e_m_axis_hls_read_tlast!==(source_payload_bytes==65))$fatal(1,"actual HLS source data last");
 end
 if(source_tx_valid && source_tx_ready)begin
  $display("OUT %032h %04h %b",source_tx_data,source_tx_keep,source_tx_last);
  if(source_tx_last)source_frames=source_frames+1;
 end
 if(source_ack || e_s_hls_write_command_valid || e_s_axis_hls_write_tvalid)$fatal(1,"unsolicited actual HLS receive/ACK effect");
 if(source_overflow!==0 || source_psndrop!==0 || source_retrans!==0 || source_rxbad!==0 || source_txbad!==0 || source_rxgood!==0)
  $fatal(1,"actual source HLS protocol/integrity error");
end
'''


def bench(words):
    tb=native.make_tb(words,False)
    # $finish schedules shutdown at the end of the current process in
    # Verilator, whereas Icarus exits immediately. Explicitly return from
    # THIS new local-only case, instead of falling through into the old,
    # different five-incoming-operation scenario's unreachable final checks.
    # All actual local-case guards/PCIe/data/ring assertions still execute.
    tb=once(tb,'initial begin\n #1 rst=0;','initial begin : local_executor_case\n #1 rst=0;')
    start=tb.index("\ne_s_hls_read_command=96'h")
    end=tb.index('while(!e_m_memory_event_valid)',start)
    tb=tb[:start]+r'''
payload_deadline=cycle+5000;
'''+tb[end:]
    tb=once(tb,'m_hls_sq_tready=1;@(posedge clk);@(negedge clk);m_hls_sq_tready=0;',r'''
if(!source_qdone || !source_cdone)$fatal(1,"actual HLS trusted QP/connection setup incomplete");
allow_source_sq=1;@(posedge clk);while(!m_hls_sq_tready)@(posedge clk);@(negedge clk);
''')
    tb=once(tb,'sq_command(3,1,35,0,0);',r'''
while(source_frames!=1 || source_txgood!=1)begin if(cycle>payload_deadline)$fatal(1,"actual HLS IP source deadline");@(negedge clk);end
if(source_sq_count!=1 || source_raw_commands!=1 || source_payload_bytes!=65 || !source_tx_stalls || executor_queue_guard!==8'h04)
 $fatal(1,"actual HLS source/SQ/memory chain scope");
sq_command(3,1,35,0,0);
''')
    # The real HLS now drives these inputs, rather than the explicit unit
    # models. No raw-command/data/ready assignment survives in this bench.
    inputs=['m_hls_sq_tready','e_s_hls_read_command','e_s_hls_read_command_valid',
        'e_s_hls_write_command','e_s_hls_write_command_valid','e_s_axis_hls_write_tdata',
        'e_s_axis_hls_write_tkeep','e_s_axis_hls_write_tlast','e_s_axis_hls_write_tvalid','e_m_axis_hls_read_tready']
    for name in inputs:
        tb,count=re.subn(r'\breg (\[[^]]+\]\s+)?'+name+r'=0;',lambda m:'wire '+(m[1]or'')+name+';',tb)
        if count!=1:raise ValueError('modeled HLS declaration changed '+name)
        if re.search(r'\b'+name+r'\s*(?:<=|=(?!=))',tb):raise ValueError('model driver survived '+name)
    tb=once(tb,'rocev2_wqe_memory_executor executor(',SOURCE+'\nrocev2_wqe_memory_executor executor(')
    finish=tb.index('$finish;',tb.index('$display("NATIVE_EXECUTOR_RESULT '))
    tb=tb[:finish]+r'''
$display("SOURCE_EXECUTOR_HLS_RESULT {\"pass_test\":true,\"HLS_SQ\":%0d,\"HLS_raw_commands\":%0d,\"HLS_source_bytes\":%0d,\"IP_packets\":%0d,\"TX_stalls\":%0d}",source_sq_count,source_raw_commands,source_payload_bytes,source_frames,source_tx_stalls);
$finish;disable local_executor_case;'''+tb[finish+len('$finish;'):]
    return tb


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--verilator',type=Path,help='additional two-state run; NOT a four-state replacement')
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.report.exists():p.error('preserve old evidence; choose fresh report')
    words=native.memory.sq.local.fixture.packet();tb=bench(words)
    paths=native.sq.input_paths(tb)+[Path(__file__).resolve(),Path(native.__file__).resolve(),
        Path(native.memory.__file__).resolve(),Path(native.executor.__file__).resolve(),
        ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',ROOT/'rdma/host/rocev2_wire.py',Path(wire.__file__).resolve()]
    if args.verilator:
        import native_executor_compiled_sim as compiled
        paths+=[Path(compiled.__file__).resolve(),Path(compiled.fast.__file__).resolve()]
    before={str(q.relative_to(ROOT)):wire.delivery.digest(q)for q in paths}
    obj=native.shared.SharedMRResponderRTLTests();obj.setUpClass();records=[]
    try:
        for i in range(2):
            w=native.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
                remote_key=0,opcode=1,flags=1,length=65)
            data=(C.c_uint8*64)();code=obj.lib.as02_wqe_encode(data,C.byref(w))
            if code or bytes(data)!=native.shared.codec.oracle(w):raise ValueError('actual C/independent WQE bytes')
            records.append(bytes(data))
    finally:obj.directory.cleanup()
    run=Path(tempfile.mkdtemp(prefix='native-executor-hls-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,source_sha256=before,
        actual_C_UBSan_WQE_records=[r.hex()for r in records],retained_directory=str(run.relative_to(ROOT)),
        actual_coherent_SQ_SAME_MR_HLS_executor_paged_PCIe=True,
        physical_host_link_and_wire_CQ_models=True,actual_peer_ACK_or_RDMA_completion=False,
        protected_READ_response_implemented=False,hardware_verified=False,board_integrated=False,standard_verbs=False)
    previous=wire.delivery.bounded.tempfile
    class ExistingRun:
        @staticmethod
        def mkdtemp(**kwargs):return str(run)
    try:
        wire.delivery.bounded.tempfile=ExistingRun
        fixtures={'input.hex':words,'records.hex':[int.from_bytes(r,'little')for r in records]}
        if args.verilator:output,identity=compiled.simulate(tb,fixtures,args.hls_build,args.verilator.resolve(),run)
        else:output,identity=wire.delivery.simulate(tb,fixtures,args.hls_build)
        identity.update(original_testbench_assertions_preserved=False,
            new_bounded_actual_executor_source_case=True,original_fixture_protection_PCIe_ring_assertions_retained=True)
        report['actual_HLS_identity']=identity
        names=['rocev2_wqe_memory_executor','rocev2_wqe_hls_sq','rocev2_native_sq_endpoint',
            'rocev2_mr_table','rocev2_mr_page_table','rocev2_pcie_parent_guard','rocev2_top','rocev2_integrity_transport']
        if args.verilator:counts={n:identity['hierarchy_module_counts'].get(n,0)for n in names}
        else:
            vvp=(run/'test.vvp').read_text()
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
        # Native already has a legacy initiator AND protected responder;
        # the new local source is the third genuine, unmodified HLS core.
        if any(counts[n]!=(3 if n in ['rocev2_top','rocev2_integrity_transport']else 1)for n in names):raise ValueError('actual native/HLS/executor hierarchy '+str(counts))
        report['actual_elaborated_module_counts']=counts
        packets=wire.packets(output)
        if len(packets)!=1:raise ValueError('one actual source IP packet required')
        packet=packets[0];payload=bytes((((4093+i)*37)^0x5a)&255 for i in range(65))
        if(len(packet)!=128 or packet[0]!=0x45 or packet[9]!=17 or int.from_bytes(packet[2:4],'big')!=128 or
            int.from_bytes(packet[6:8],'big')&0x3fff or packet[12:16]!=bytes([198,18,11,2])or packet[16:20]!=bytes([198,18,11,1])or
            int.from_bytes(packet[22:24],'big')!=4791 or int.from_bytes(packet[24:26],'big')!=108 or packet[26:28]!=b'\0\0'or
            packet[28]!=10 or packet[29]!=0x70 or packet[30:32]!=b'\xff\xff'or packet[32]&0x3f or packet[36]&0x7f or
            int.from_bytes(packet[33:36],'big')!=196 or int.from_bytes(packet[37:40],'big')!=0xfffffe or
            int.from_bytes(packet[40:48],'big')!=0xf123456789abc001 or int.from_bytes(packet[48:52],'big')!=0 or
            int.from_bytes(packet[52:56],'big')!=65 or packet[56:-4]!=payload+b'\0'*3 or
            wire.internet_checksum(packet[:20])or packet[-4:]!=wire.icrc_ipv4(packet)):
            raise ValueError('actual native registered-host bytes/key0/full VA64/PSN/pad/IPv4/ICRC packet')
        rows=[json.loads(l[23:])for l in output.splitlines()if l.startswith('NATIVE_EXECUTOR_RESULT ')]
        source_rows=[json.loads(l[27:])for l in output.splitlines()if l.startswith('SOURCE_EXECUTOR_HLS_RESULT ')]
        if len(rows)!=1 or len(source_rows)!=1 or not rows[0]['pass_test']or not source_rows[0]['pass_test']:raise ValueError('actual native source summaries')
        if before!={n:wire.delivery.digest(ROOT/n)for n in before}:raise ValueError('source changed during probe')
        report.update(pass_test=True,terminal_exit_status=0,summary=rows[0],HLS_summary=source_rows[0],
            packet_hex=packet.hex(),source_payload_bytes_checked=65,IPv4_ICRC_checked=True,
            actual_C_to_coherent_SQ_to_MR_to_HLS_to_executor_to_PCIe_to_IP=True,
            simulation_seconds=identity['simulation_seconds'],simulation_timeout_seconds=30 if args.verilator else 120,
            four_state_simulation=not bool(args.verilator),compiled_two_state_additional_only=bool(args.verilator),
            source_sha256_before_after_equal=True)
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error),terminal_exit_status=1);raise
    finally:
        wire.delivery.bounded.tempfile=previous
        report['artifact_sha256']={str(q.relative_to(ROOT)):wire.delivery.digest(q)for q in run.iterdir()if q.is_file()}
        with args.report.open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()
