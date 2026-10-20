# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short main-parent READ/WRITE integration checks.

Coherent SQ, SAME MR/PTE, executor, packet/PSN protection, unpadding, native
PCIe/RAM/fence and MAC/lifetime are real RTL. HLS is explicitly a behavioral
model; physical host/link/MAC pins are models. Internal HLS drain stays zero,
so no CQ commit, MR release, standard verbs or board operation is claimed.
"""
import ctypes as C
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import native_sq_fixture as sq
import test_native_sq_rtl as original
import test_shared_mr_responder_rtl as shared
import test_wqe_response_guard_rtl as response

ROOT=sq.ROOT
RTL=ROOT/'rdma/rnic/rtl'
TOP=RTL/'rocev2_native_rnic_endpoint.v'
EXTRA=[RTL/(n+'.v')for n in ['rocev2_shared_hls_transport','rocev2_memory_client_arbiter',
    'rocev2_wqe_hls_sq','rocev2_wqe_memory_executor','rocev2_wqe_tx_lifetime',
    'rocev2_wqe_lifetime','rocev2_wqe_mac_tx','rocev2_wqe_response_guard','rocev2_wqe_read_unpad','rocev2_cq_mmio',
    'rocev2_wqe_replay','rocev2_retry_mmio','rocev2_receive_queue','rocev2_receive_ack_tx']]
spec=importlib.util.spec_from_file_location('derive_shared',ROOT/'rdma/rnic/fpga/derive_shared_responder.py')
derive=importlib.util.module_from_spec(spec)
spec.loader.exec_module(derive)


def octets(data):
    return [int.from_bytes(data[i:i+16].ljust(16,b'\0'),'little')for i in range(0,len(data),16)]


def request(write):
    r=response.read_wire
    if not write:
        p=r.encode(opcode=r.REQUEST,source_ip='198.18.11.2',destination_ip='198.18.11.1',
            destination_qpn=196,psn=0xfffffe,remote_address=0xf123456789abc001,rkey=0,read_bytes=65)[14:]
    else:
        from rocev2_wire import write_only_frame
        p=write_only_frame(source_mac='8a:f3:fb:b9:75:31',destination_mac='b8:83:03:67:c5:d0',
            source_ip='198.18.11.2',destination_ip='198.18.11.1',destination_qpn=196,
            psn=0xfffffe,remote_address=0xf123456789abc001,rkey=0,udp_source_port=49152,
            payload=bytes((((4093+i)*37)^0x5a)&255 for i in range(65)))[14:]
    # Actual FNS emits migration bit 1. Preserve the production observer's ABI.
    p=bytearray(p);p[29]|=0x40
    return response.repair(p)


def core_model(write):
    s=(ROOT/'rdma/rtl/rocev2_integrity_transport.v').read_text()
    h=s.split('module rocev2_integrity_transport (',1)[1].split('\n);',1)[0]
    h=re.sub(r'output reg ', 'output wire ',h)
    h=re.sub(r'=0\b','',h)
    h+=' ,\n    input wire [31:0] s_axis_sq_rkey'
    values=dict(s_axis_rx_tready='active && tx_done && !rx_done',
        s_axis_qp_tready="1'b1",s_axis_conn_tready="1'b1",s_axis_sq_tready='!active',
        m_axis_tx_tdata='tx_words[tx_index]',m_axis_tx_tkeep='tx_index==TX_WORDS-1 ? TX_KEEP : 16\'hffff',
        m_axis_tx_tvalid='active && source_done && !tx_done',m_axis_tx_tlast='tx_index==TX_WORDS-1',
        m_axis_mem_read_cmd_tdata='raw_command',m_axis_mem_read_cmd_tvalid='active && WRITE && !command_done',
        s_axis_mem_read_tready='active && WRITE && command_done && !source_done',
        m_axis_mem_write_cmd_tdata='raw_command',m_axis_mem_write_cmd_tvalid='active && !WRITE && rx_done && !command_done',
        m_axis_mem_write_tdata='placement_data',m_axis_mem_write_tkeep='remaining>=64 ? 64\'hffffffffffffffff : (64\'h1<<remaining)-1',
        m_axis_mem_write_tvalid='active && !WRITE && command_done && !placement_done',
        m_axis_mem_write_tlast='remaining<=64',m_axis_ack_tdata="40'h07fffff004 | WRITE",
        m_axis_ack_tvalid='active && rx_done && (WRITE || placement_done) && !ack_done')
    assignments='\n'.join('assign '+n+'='+values.get(n,'0')+';'for n in re.findall(r'output wire\s+(?:\[[^\]]+\]\s+)?(\w+)',h))
    pkt=request(write)
    body=r'''
localparam WRITE=WRITE_VALUE,TX_WORDS=TX_WORDS_VALUE;
localparam [15:0] TX_KEEP=TX_KEEP_VALUE;
reg [127:0] tx_words[0:TX_WORDS-1];
reg [7:0] rx_bytes[0:127];
reg active=0,tx_done=0,rx_done=0,source_done=0,command_done=0,placement_done=0,ack_done=0;
reg [239:0] owner=0;
integer tx_index=0,source_bytes=0,rx_count=0,placed=0,k,amount;
wire [63:0] va=owner[111:48];
wire [9:0] qpn=owner[41:32];
wire [27:0] command_length=WRITE ? 28'd65 : 28'd68;
wire [95:0] raw_command={2'd0,qpn,va[51:48],1'b1,1'b0,va[52],1'b1,command_length,va[47:0]};
wire [31:0] remaining=68-placed;
reg [511:0] placement_data;
always @*begin
 placement_data=0;
 for(integer b=0;b<64;b=b+1)if(b<remaining)placement_data[b*8+:8]=rx_bytes[44+placed+b];
end
initial $readmemh("request.hex",tx_words);
always @(posedge clk)begin
 if(rst)begin active<=0;tx_done<=0;rx_done<=0;source_done<=!WRITE;command_done<=0;
  placement_done<=0;ack_done<=0;tx_index<=0;source_bytes<=0;rx_count<=0;placed<=0;end
 else begin
  if(s_axis_sq_tvalid && s_axis_sq_tready)begin
   if(LEGACY_QP_KEY || s_axis_sq_rkey!==0 || s_axis_sq_tdata[239:208]!==0 ||
      s_axis_sq_tdata[207:176]!==65 || s_axis_sq_tdata[175:112]!==64'hf123456789abc001 ||
      s_axis_sq_tdata[111:48]!==64'hfedcba9876543210 || s_axis_sq_tdata[41:32]!==2 ||
      s_axis_sq_tdata[31:0]!==(WRITE ? 32'd10 : 32'd12))$fatal(1,"model HLS received wrong real SQ");
   owner<=s_axis_sq_tdata;active<=1;
  end
  if(m_axis_mem_read_cmd_tvalid && m_axis_mem_read_cmd_tready)command_done<=1;
  if(s_axis_mem_read_tvalid && s_axis_mem_read_tready)begin
   amount=0;
   for(k=0;k<64;k=k+1)if(s_axis_mem_read_tkeep[k])begin
    if(s_axis_mem_read_tdata[k*8+:8]!==((((4093+source_bytes+amount)*37)^8'h5a)&255))
     $fatal(1,"real executor source byte mismatch");
    amount=amount+1;
   end
   source_bytes<=source_bytes+amount;
   if(s_axis_mem_read_tlast)begin
    if(source_bytes+amount!=65)$fatal(1,"real executor source extent");source_done<=1;
   end
  end
  if(m_axis_tx_tvalid && m_axis_tx_tready)begin
   if(m_axis_tx_tlast)tx_done<=1;else tx_index<=tx_index+1;
  end
  if(s_axis_rx_tvalid && s_axis_rx_tready)begin
   amount=0;
   for(k=0;k<16;k=k+1)if(s_axis_rx_tkeep[k])begin rx_bytes[rx_count+amount]<=s_axis_rx_tdata[k*8+:8];amount=amount+1;end
   rx_count<=rx_count+amount;if(s_axis_rx_tlast)rx_done<=1;
  end
  if(m_axis_mem_write_cmd_tvalid && m_axis_mem_write_cmd_tready)command_done<=1;
  if(m_axis_mem_write_tvalid && m_axis_mem_write_tready)begin
   placed<=placed+(remaining>=64 ? 64 : remaining);if(m_axis_mem_write_tlast)placement_done<=1;
  end
  if(m_axis_ack_tvalid && m_axis_ack_tready)ack_done<=1;
 end
end
'''
    body=body.replace('WRITE_VALUE',str(int(write))).replace('TX_WORDS_VALUE',str((len(pkt)+15)//16)).replace('TX_KEEP_VALUE',f"16'h{(1<<(len(pkt)%16 or 16))-1:x}")
    return 'module rocev2_integrity_transport #(parameter LEGACY_QP_KEY=1) ('+h+'\n);\n'+body+assignments+'\nendmodule\n'


def bench(write):
    body=sq.prefix()+r'''
enable=1;sq_command(2,1,0,0,0);
sq_deadline=cycle+5000;
while(!dut.tx_response_admission_ready || dut.tx_frame_count!=1)begin
 if(cycle>sq_deadline)$fatal(1,"main-parent issue deadline guards%h owner%0d",local_execution_guard,dut.owner_take);
 @(negedge clk);
end
send_frame(STIMULUS_LAST+1,REPLY_WORDS_VALUE);
sq_deadline=cycle+5000;
while(local_proof_flags!==7'h3f)begin
 if(cycle>sq_deadline)$fatal(1,"main-parent proof deadline flags%h native%h ex%h rx%h up%h tx%h",local_proof_flags,
  dut.native_fault_code,dut.ex_fault_code,dut.rx_fault_code,dut.up_fault_code,dut.tx_fault_code);
 @(negedge clk);
end
if(dut.ex_command_count!=1 || dut.ex_memory_status_count!=1 || dut.ex_owner_count!=1 ||
 sq_fetch_count!=1 || sq_result_count!=1 || sq_submission_owner_count!=1 || sq_submission_hls_count!=1 ||
 dut.rx_accepted_count!=1 || dut.tx_receipt_count!=1 || dut.tx_mac_proof_count!=1 ||
 !dut.h_local_hls_active || local_execution_guard!==8'h04 || fault || m_cq_valid || local_committed_count)
 $fatal(1,"main-parent did not connect genuine execution ownership");
for(sq_i=0;sq_i<16384;sq_i=sq_i+1)begin
 if(pcie_posted_valid[sq_i])$fatal(1,"unfenced host byte");
 if(PLACEMENT_VALUE && sq_i>=4093 && sq_i<4158)begin
  if(pcie_host[sq_i]!==((((sq_i-4093)*179)^((sq_i-4093)>>7)^8'hd3)&255))$fatal(1,"main READ placement byte/sentinel");
 end else if(pcie_host[sq_i]!==(((sq_i*37)^8'h5a)&255))$fatal(1,"main WRITE changed source/sentinel");
end
check_ring();
host_stage(8,405,0,0,0,0,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(50)begin @(negedge clk);if(!control_busy || quiet || config_safe || m_cq_valid || s_cq_commit_ready ||
 !dut.h_local_hls_active || local_execution_guard!==8'h04)$fatal(1,"unproved drain released WR/MR/CQ");end
$display("NATIVE_RNIC_RESULT {\"pass_test\":true,\"payload_bytes\":65,\"proof_flags\":%0d,\"descriptors\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"HLS_model\":true,\"CQ_committed\":false}",local_proof_flags,router_descriptor_count,read_tlps,write_tlps,fences);
$finish;
// Compiled simulators may return from $finish until this coroutine yields.
// End this named case explicitly, rather than fall into the unused original
// five-transaction suite's postamble. All THIS case's checks precede $finish.
disable native_rnic_case;
'''
    reply=bytearray(response.packet(write=write,mig=1,qpn=2))
    if not write:
        reply[44:109]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65))
        reply=response.repair(reply)
    frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+reply
    words=sq.local.fixture.packet()
    body=body.replace('STIMULUS_LAST+1',str(len(words))).replace('REPLY_WORDS_VALUE',str((len(frame)+15)//16)).replace('PLACEMENT_VALUE',str(int(not write)))
    tb=sq.make_tb(words,body)
    # Only the new main parent selects CQC1 at 0x403000; the original
    # native-SQ default still tests DECERR there. No old aperture is aliased.
    tb=sq.once(tb,"expect_decerr(24'h403000);",
        "read_reg(24'h403000,sq_value);if(sq_value!==32'h43514331)$fatal(1,\"main CQ aperture\");\n"
        "read_reg(24'h40300c,sq_value);if(sq_value)$fatal(1,\"main CQ initially owned\");\n"
        "expect_decerr(24'h404000);")
    tb=sq.once(tb,'initial begin\n #1 rst=0;',
        'initial begin : native_rnic_case\n #1 rst=0;')
    # This vertical slice needs ONE real MR, not the original three-MR
    # negative-authorization sweep (which remains a separate regression).
    for unused in [
        ' host_api(2,OWNER1,1,0,18,7,0,0,9,0);host_pages(OWNER1,1,9);\n',
        ' host_api(2,OWNER2,2,0,17,4,0,0,10,0);host_pages(OWNER2,2,10);\n']:
        tb=sq.once(tb,unused,'')
    tb=tb.replace('dut.network.','dut.native.network.')
    start=tb.index('rocev2_native_sq_endpoint dut(');end=tb.index(');',start)+2
    old=dict(re.findall(r'\.(\w+)\(([^()]*)\)',tb[start:end]))
    declarations=[];connections=[]
    for direction,expr,name in sq.native.pcie.ports(TOP):
        value=old.get(name,name)
        if direction=='output' and name.startswith('local_hls_'):
            value='observed_'+name
            declarations.append('wire '+('['+expr+'] 'if expr else'')+value+';')
        if name not in old:
            declarations.append(('reg 'if direction=='input'else'wire ')+('['+expr+'] 'if expr else'')+name+('=0;'if direction=='input'else';'))
        connections.append(f'.{name}({value})')
    tb=tb[:start]+'\n'.join(declarations)+'\nrocev2_native_rnic_endpoint dut('+','.join(connections)+');'+tb[end:]
    tb=sq.once(tb,"else if(mac_tx_user[16:1]!=16'h4000) $fatal(1,\"unexpected legacy TX in responder-only phase\");",
        "else if((mac_tx_user[16:1]&16'he000)!=16'h2000 && mac_tx_user[16:1]!=16'h4000)$fatal(1,\"wrong native TX class\");")
    monitor=r'''
always @(posedge clk)if(!rst)begin
 if(cycle%1000==0)$display("MAIN_PROGRESS cycle%0d flags%h",cycle,local_proof_flags);
 if(dut.ex_m_memory_command_valid && dut.ex_m_memory_command_ready)begin
  if(dut.ex_m_memory_command_key!==8 || dut.ex_m_memory_command_offset!==64'h210 ||
   dut.ex_m_memory_command_length!==65 || dut.ex_m_memory_command_tag!==1)$fatal(1,"main-path authority tuple");
  pcie_current_length=dut.ex_m_memory_command_length;pcie_current_offset=dut.ex_m_memory_command_offset;
 end
 if(fault)$fatal(1,"main native RNIC fault %h",fault_code);
 if(dut.cq_commit_valid || dut.cq_retire_valid || dut.cq_busy || dut.cq_fault)
  $fatal(1,"main invented a CQ event without genuine internal HLS drain");
end
'''
    tb=tb.replace('reg [144:0] stimulus',monitor+'\nreg [144:0] stimulus',1)
    # Existing immutable host/PCIe/AXI/guard agents are retained. Only extend
    # the stimulus array to include the one physical peer-model response.
    tb=tb.replace(f'stimulus[0:{len(words)-1}]',f'stimulus[0:{len(words)+(len(frame)+15)//16-1}]')
    return tb,words+[int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little')|(((1<<min(16,len(frame)-i))-1)<<128)|((i+16>=len(frame))<<144)for i in range(0,len(frame),16)]


class NativeRNICMainPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def run_case(self,write):
        tb,words=bench(write)
        records=[]
        for i in range(2):
            w=shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
                remote_key=0,opcode=1 if write else 2,flags=1,length=65)
            data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(data,C.byref(w)),0);records.append(bytes(data))
        with tempfile.TemporaryDirectory(prefix='as02-native-rnic-')as directory:
            p=Path(directory)
            (p/'tb.v').write_text(tb);(p/'stub.v').write_text(core_model(write))
            (p/'shared.v').write_text(derive.derive(derive.ORIGINAL.read_text()))
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
            (p/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
            (p/'request.hex').write_text(''.join(f'{v:x}\n'for v in octets(request(write))))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),str(p/'shared.v'),
                str(TOP),*map(str,EXTRA),*map(str,sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            hierarchy=(p/'test.vvp').read_text()
            for n in ['rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_shared_hls_transport',
                'rocev2_shared_protected_responder','rocev2_mr_table','rocev2_mr_page_table','rocev2_wqe_memory_executor',
                'rocev2_wqe_response_guard','rocev2_wqe_read_unpad','rocev2_wqe_tx_lifetime','rocev2_cq_mmio']:
                self.assertEqual(len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',hierarchy)),1,n)
            try:
                run=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
            except subprocess.TimeoutExpired as e:
                self.fail('30-second simulation limit; output tail: '+(e.stdout or b'')[-3000:].decode(errors='replace'))
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            result=[json.loads(l.split(' ',1)[1])for l in run.stdout.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
            self.assertEqual(len(result),1,run.stdout)
            self.assertTrue(result[0]['pass_test'])
            self.assertEqual(result[0]['proof_flags'],63)
            self.assertEqual(result[0]['fences'],int(not write))
            print(json.dumps(dict(operation='WRITE'if write else'READ',**result[0])),flush=True)

    def test_main_parent_READ_to_registered_host_memory(self):self.run_case(False)
    def test_main_parent_WRITE_from_registered_host_memory(self):self.run_case(True)


if __name__=='__main__':unittest.main()
