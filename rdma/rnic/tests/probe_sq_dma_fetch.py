#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""SQ client + real Corundum backend/RAM/muxes/generic PCIe DMA engine.

Only trusted config/PCIe hard-IP/link/root complex/host memory are MODELS.
No descriptor/status/RAM replacement agent or CPU payload-copy shortcut.
No native coherent allocation/pins/AXI queue CSR/verbs/CQE/RDMA completion.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import probe_controlled_pcie as pcie
import test_sq_fetch_rtl as sq
import test_wqe_codec as codec

ROOT=sq.ROOT
TOP=ROOT/'rdma/rnic/rtl/rocev2_sq_dma_fetch.v'
PCIE=pcie.PCIE
SOURCES=[TOP,sq.RTL,ROOT/'rdma/rnic/rtl/rocev2_corundum_dma_backend.v',*pcie.PCIE_SOURCES]
SOURCES += [PCIE/(n+'.v')for n in ['dma_client_axis_sink','dma_client_axis_source','dma_psdpram']]
SOURCES += [ROOT/'external/corundum/fpga/lib/axis/rtl'/(n+'.v')for n in ['axis_register','arbiter','priority_encoder']]

HOST=r'''
reg [511:0] records[0:6];reg [7:0] host[0:255];
integer cycle=0,read_tlps=0,read_completions=0,descriptors=0,observed_results=0,lane,i;
integer generic_error_seen=0,parent_proof_hold_cycles=0;reg [31:0] rng=32'h455a1234;
reg allow_parent_drain=1;
reg descriptor_stalled=0,tlp_stalled=0,result_stalled=0;
reg [127:0] saved_descriptor;reg [134:0] saved_tlp;
reg [703:0] saved_result;
wire [703:0] result_fields={m_result_data,m_result_error,m_result_qpn,m_result_pd,m_result_epoch,m_result_sequence,m_result_tag};
wire actual_parent_dma_drained=!tlp_status_rd_busy && !tlp_status_wr_busy &&
 !m_dma_read_valid && !m_dma_write_valid && !mid_m_dma_read_valid && !mid_m_dma_write_valid &&
 !eng_m_dma_read_valid && !eng_m_dma_write_valid && !tlp_tx_rd_req_tlp_valid && !tlp_tx_wr_req_tlp_valid &&
 !tlp_rx_cpl_tlp_valid && !(|eng_dma_ram_wr_cmd_valid) && !(|eng_dma_ram_rd_cmd_valid) &&
 !(|eng_dma_ram_rd_resp_valid) && !(|dma_ram_wr_cmd_valid) && !(|dma_ram_rd_cmd_valid) && !(|dma_ram_rd_resp_valid);
// Extra test qualification may ONLY withhold the real engine/mux proof,
// never make a false-positive drain signal. Native parent fault recovery is
// separate; this is a root-complex/host model, not the actual whole parent.
assign parent_dma_drained=actual_parent_dma_drained && allow_parent_drain;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>10000)$fatal(1,"SQ actual PCIe deadline descriptors=%d results=%d",descriptors,observed_results);
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 if(fault)$fatal(1,"actual fetch/backend protocol fault %h",fault_code);
 if(tlp_status_error_uncor)$fatal(1,"unexpected uncorrectable PCIe parser error");
 if(tlp_status_error_cor)generic_error_seen=generic_error_seen+1;
 if(descriptor_stalled && (!m_dma_read_valid || {m_dma_read_address,m_dma_read_length,m_dma_read_tag,m_dma_read_ram_address,m_dma_read_ram_sel}!==saved_descriptor))
  $fatal(1,"actual read descriptor retracted/changed");
 descriptor_stalled=m_dma_read_valid&&!m_dma_read_ready;
 saved_descriptor={m_dma_read_address,m_dma_read_length,m_dma_read_tag,m_dma_read_ram_address,m_dma_read_ram_sel};
 if(tlp_stalled && (!tlp_tx_rd_req_tlp_valid || {tlp_tx_rd_req_tlp_hdr,tlp_tx_rd_req_tlp_seq,tlp_tx_rd_req_tlp_sop,tlp_tx_rd_req_tlp_eop}!==saved_tlp))
  $fatal(1,"actual read TLP retracted/changed");
 tlp_stalled=tlp_tx_rd_req_tlp_valid&&!tlp_tx_rd_req_tlp_ready;
 saved_tlp={tlp_tx_rd_req_tlp_hdr,tlp_tx_rd_req_tlp_seq,tlp_tx_rd_req_tlp_sop,tlp_tx_rd_req_tlp_eop};
 if(result_stalled && (!m_result_valid || result_fields!==saved_result))$fatal(1,"fetched bytes/context changed under stall");
 result_stalled=m_result_valid&&!m_result_ready;saved_result=result_fields;
 if(m_dma_write_valid || tlp_tx_wr_req_tlp_valid)$fatal(1,"SQ fetch unexpectedly writes host memory");
 if(m_dma_read_valid&&m_dma_read_ready)begin
  descriptors=descriptors+1;
  if(m_dma_read_length!==64 || m_dma_read_ram_address!==0 || m_dma_read_ram_sel!==0 || m_dma_read_tag!==descriptors)
   $fatal(1,"SQ descriptor width/tag/extent mismatch");
  $display("SQ_DESCRIPTOR %h %0d %0d",m_dma_read_address,m_dma_read_length,m_dma_read_tag);
 end
 if(eng_m_dma_read_valid&&eng_m_dma_read_ready)begin
  if(eng_m_dma_read_tag!=={3'b110,m_dma_read_tag} || eng_m_dma_read_ram_sel!==12)$fatal(1,"actual19-bit tag/RAM mux routing");
 end
 if(m_result_valid&&m_result_ready)observed_results=observed_results+1;
end
function integer host_index;
 input [63:0] address;
 begin
  if(address>=64'h8123456789abc000 && address<64'h8123456789abc080)host_index=address-64'h8123456789abc000;
  else if(address>=64'hfedcba9876543000 && address<64'hfedcba9876543080)host_index=128+address-64'hfedcba9876543000;
  else begin host_index=-1;$fatal(1,"DMA escaped both exact coherent rings: %h",address);end
 end
endfunction
task load_slot;
 input integer slot,record_index;
 integer b;
 begin for(b=0;b<64;b=b+1)host[slot*64+b]=records[record_index][b*8+:8];end
endtask
task take_result;
 input integer record_index,error_code,q;input [15:0] pd_value;
 input [63:0] epoch_value,sequence_value;input [15:0] tag_value;
 integer deadline;
 begin
  deadline=cycle+2000;while(!m_result_valid)begin if(cycle>deadline)$fatal(1,"actual SQ result deadline");@(negedge clk);end
  if(m_result_data!==(error_code ? 512'd0 : records[record_index]) || m_result_error!==error_code || m_result_qpn!==q ||
   m_result_pd!==pd_value || m_result_epoch!==epoch_value || m_result_sequence!==sequence_value || m_result_tag!==tag_value || !queue_guard[q])
   $fatal(1,"actual PCIe descriptor bytes/context mismatch q=%d seq=%d error=%d",m_result_qpn,m_result_sequence,m_result_error);
  repeat(13)begin @(negedge clk);if(!m_result_valid || !queue_guard[q])$fatal(1,"held SQ result lost owner");end
  $display("SQ_RECORD %0d %0d %0d %h",q,sequence_value,error_code,m_result_data);
  m_result_ready=1;@(posedge clk);@(negedge clk);m_result_ready=0;
 end
endtask
initial begin: root_complex_read_model
 reg [127:0] h,cpl;reg [63:0] address;reg [4:0] seq;
 integer b,position,bytes_count,request_number,idx;
 repeat(20)@(negedge clk);
 forever begin
  while(!tlp_tx_rd_req_tlp_valid)@(negedge clk);
  h=tlp_tx_rd_req_tlp_hdr;seq=tlp_tx_rd_req_tlp_seq;
  if(h[127:125]!==3'b001 || h[124:120]!=0 || h[119:106]!=0 || h[95:80]!==16'h8200 ||
   h[105:96]!==16 || h[71:64]!==8'hff || h[5:0]!=0)$fatal(1,"not exact64B ordinary DMA64/TC0/attr0 read: %h",h);
  address={h[63:2],2'b0};idx=host_index(address);if(idx<0)$fatal(1,"bad full DMA address");
  repeat(9)begin @(negedge clk);if(!tlp_tx_rd_req_tlp_valid || tlp_tx_rd_req_tlp_hdr!==h)$fatal(1,"read TLP ownership lost");end
  tlp_tx_rd_req_tlp_ready=1;@(posedge clk);
  if(!tlp_tx_rd_req_tlp_sop || !tlp_tx_rd_req_tlp_eop)$fatal(1,"read request framing");
  @(negedge clk);tlp_tx_rd_req_tlp_ready=0;read_tlps=read_tlps+1;request_number=read_tlps;
  repeat(17)begin @(negedge clk);if(parent_dma_drained || m_result_valid)$fatal(1,"fetch advanced before completion");end
  tlp_s_axis_rd_req_tx_seq_num=seq;tlp_s_axis_rd_req_tx_seq_num_valid=1;
  @(negedge clk);tlp_s_axis_rd_req_tx_seq_num_valid=0;
  cpl=0;cpl[127:125]=3'b010;cpl[124:120]=5'b01010;cpl[105:96]=16;
  cpl[95:80]=16'h0100;cpl[75:64]=64;cpl[63:48]=h[95:80];cpl[47:40]=h[79:72];cpl[38:32]=address[6:0];
  bytes_count=64;
  if(ERROR_CASE && request_number==1)begin
   cpl[127:125]=0;cpl[105:96]=0;cpl[79:77]=1;bytes_count=4;allow_parent_drain=0;
  end
  for(position=0;position<bytes_count;position=position+32)begin
   repeat(3)@(negedge clk);
   tlp_rx_cpl_tlp_data=0;tlp_rx_cpl_tlp_hdr=cpl;
   for(b=0;b<32;b=b+1)if(position+b<bytes_count)tlp_rx_cpl_tlp_data[b*8+:8]=host[host_index(address+position+b)];
   tlp_rx_cpl_tlp_sop=position==0;tlp_rx_cpl_tlp_eop=position+32>=bytes_count;tlp_rx_cpl_tlp_valid=1;
   @(posedge clk);while(!tlp_rx_cpl_tlp_ready)@(posedge clk);
   @(negedge clk);tlp_rx_cpl_tlp_valid=0;
  end
  read_completions=read_completions+1;
 end
end
'''


def bench(error=False):
    params=dict(MAX_QPS=8,RAM_SIZE=8192,RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,
                SEG_BE_WIDTH=32,SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=1,DMA_LEN_WIDTH=16,TAG_WIDTH=16)
    declarations=[]
    driven={'parent_dma_drained','m_dma_read_ready','m_dma_write_ready'}
    driven.update('s_dma_'+d+'_status_'+f for d in ['read','write']for f in ['tag','error','valid'])
    driven.update('dma_ram_'+f for f in ['wr_cmd_sel','wr_cmd_be','wr_cmd_addr','wr_cmd_data','wr_cmd_valid',
                                      'rd_cmd_sel','rd_cmd_addr','rd_cmd_valid','rd_resp_ready'])
    ports=pcie.ports(TOP)
    if len(ports)!=79:raise ValueError('SQ backend interface changed')
    if [(d,expr.strip())for d,expr,n in ports if n=='queue_pending']!=[('output','MAX_QPS-1:0')]:
        raise ValueError('full per-QP pending ownership output changed')
    for direction,expr,name in ports:
        kind='reg'if direction=='input'and name not in driven else'wire'
        declarations.append(pcie.declaration(name,pcie.width(expr,params),kind))
    graph=pcie.bundle('mid_',18,3)+'\n'+pcie.bundle('eng_',19,4)+'\n'
    graph+=pcie.mux('interface_mux','','mid_',3,2,16,18,1,3)
    graph+=pcie.mux('control_data_mux','mid_','eng_',2,1,18,19,3,4)+pcie.engine()
    configure=sq.TB[sq.TB.index('task configure;'):sq.TB.index('task wait_command;')]
    body=r'''
initial begin
 rst=0;repeat(2)@(negedge clk);rst=1;
 $readmemh("records.hex",records);load_slot(0,0);load_slot(1,1);load_slot(2,2);load_slot(3,3);
 repeat(8)@(negedge clk);rst=0;repeat(32)@(negedge clk);
 configure(1,0,16'hf123,64'h8000000000000001,64'h8123456789abc000,0,1,0);
 configure(1,7,16'habcd,64'h9000000000000001,64'hfedcba9876543000,0,1,0);
 configure(2,0,0,64'h8000000000000001,0,2,0,0);configure(2,7,0,64'h9000000000000001,0,2,0,0);
 enable=1;while(!tlp_tx_rd_req_tlp_valid)@(negedge clk);enable=0;
 // An unrelated queue still cannot retire while real parent PCIe work exists.
 configure(3,7,0,64'h9000000000000001,0,0,0,19);
 take_result(0,ERROR_CASE ? 10 : 0,0,16'hf123,64'h8000000000000001,1,1);
 if(ERROR_CASE)begin
  repeat(40)begin
   @(negedge clk);parent_proof_hold_cycles=parent_proof_hold_cycles+1;
   if(dma_drained || !busy || backend_command_count!=1 || descriptors!=1 || dut.memory.idle)
    $fatal(1,"terminal read error bypassed withheld parent drain");
  end
  if(!actual_parent_dma_drained)$fatal(1,"actual generic engine did not drain");
  configure(3,0,0,64'h8000000000000001,0,0,0,19);allow_parent_drain=1;
 end
 enable=1;
 take_result(2,0,7,16'habcd,64'h9000000000000001,1,2);
 if(ERROR_CASE)begin
  take_result(3,0,7,16'habcd,64'h9000000000000001,2,3);enable=0;
  if(queue_halted!==1)$fatal(1,"failed fetch queue did not halt");
  while(!parent_dma_drained || !dma_drained)@(negedge clk);
  configure(3,0,0,64'h8000000000000001,0,0,0,0);
  configure(1,0,16'hf123,64'h8000000000000001,64'h8123456789abc000,0,1,17);
  load_slot(0,6);configure(1,0,16'hf123,64'h8000000000000002,64'h8123456789abc000,0,1,0);
  configure(2,0,0,64'h8000000000000002,0,1,0,0);enable=1;
  take_result(6,0,0,16'hf123,64'h8000000000000002,1,4);
 end else begin
  take_result(1,0,0,16'hf123,64'h8000000000000001,2,3);
  take_result(3,0,7,16'habcd,64'h9000000000000001,2,4);
  load_slot(0,4);load_slot(1,5);configure(2,0,0,64'h8000000000000001,0,4,0,0);
  take_result(4,0,0,16'hf123,64'h8000000000000001,3,5);
  take_result(5,0,0,16'hf123,64'h8000000000000001,4,6);
 end
 enable=0;repeat(40)@(negedge clk);
 if(!parent_dma_drained || !dma_drained || busy || fault || backend_fence_count || descriptors!==observed_results ||
  descriptors!==read_tlps || read_tlps!==read_completions || fetch_count!==descriptors || result_count!==descriptors ||
  observed_results!==(ERROR_CASE ? 4 : 6) || generic_error_seen!==(ERROR_CASE ? 1 : 0))$fatal(1,"actual SQ DMA coverage/drain/error mismatch");
 $display("SQ_PCIE_RESULT {\"pass_test\":true,\"descriptors\":%0d,\"read_tlps\":%0d,\"read_completions\":%0d,\"results\":%0d,\"generic_correctable_events\":%0d,\"parent_proof_hold_cycles\":%0d,\"cycles\":%0d}",descriptors,read_tlps,read_completions,observed_results,generic_error_seen,parent_proof_hold_cycles,cycle);
 $finish;
end
'''
    return ('`timescale 1ns/1ps\nmodule tb;\n'+f'localparam ERROR_CASE={int(error)};\n'+
            '\n'.join(declarations)+'\nrocev2_sq_dma_fetch dut(.*);\nalways #2 clk=~clk;\n'+
            graph+HOST.replace('ERROR_CASE',str(int(error)))+configure+body+'\nendmodule\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--error',action='store_true');p.add_argument('--report',required=True,type=Path)
    args=p.parse_args()
    if args.report.exists():p.error('preserve previous evidence')
    own=[Path(__file__).resolve(),Path(pcie.__file__).resolve(),Path(sq.__file__).resolve(),
         Path(codec.__file__).resolve(),codec.KERNEL/'wqe.c',codec.KERNEL/'wqe.h']
    before={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in SOURCES+own}
    build_directory=ROOT/'rdma/rnic/build'
    # Fresh CI/source checkouts have no ignored build directory yet.
    build_directory.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='sq-pcie-error-'if args.error else'sq-pcie-',dir=build_directory))
    c=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
        '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(codec.KERNEL),str(codec.KERNEL/'wqe.c'),
        '-o',str(run/'wqe.so')],capture_output=True,text=True,timeout=30)
    if c.returncode:raise RuntimeError(c.stdout+c.stderr)
    lib=C.CDLL(str(run/'wqe.so'));lib.as02_wqe_encode.argtypes=[C.POINTER(C.c_uint8),C.POINTER(codec.WQE)]
    records=[]
    for i,(q,sequence,epoch)in enumerate([(0,1,0x8000000000000001),(0,2,0x8000000000000001),
           (7,1,0x9000000000000001),(7,2,0x9000000000000001),(0,3,0x8000000000000001),
           (0,4,0x8000000000000001),(0,1,0x8000000000000002)]):
        w=codec.candidate(sequence=sequence,epoch=epoch,wr_id=0xf123456700000000+i,
                          local_address=0xfedcba9876543000+i*64,opcode=1+i%2,remote_key=[0,0x80000000,0xffffffff][i%3])
        out=(C.c_uint8*64)();assert lib.as02_wqe_encode(out,C.byref(w))==0 and bytes(out)==codec.oracle(w)
        records.append(bytes(out))
    (run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
    (run/'tb.v').write_text(bench(args.error));started=time.monotonic()
    command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,SOURCES)]
    report=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,error_case=args.error,
        directory=str(run.relative_to(ROOT)),source_sha256=before,compiler_command=command,
        bench_sha256=hashlib.sha256((run/'tb.v').read_bytes()).hexdigest(),
        records_sha256=hashlib.sha256((run/'records.hex').read_bytes()).hexdigest(),
        actual_PCIe_engine=True,actual_backend_segmented_RAM_and_clients=True,actual_native_shape_muxes=True,
        hardware_verified=False,real_coherent_queue_allocation=False,standard_verbs_implemented=False,
        local_WQE_MR_authorization_connected=False,RDMA_completion_claim=False,
        compile_timeout_seconds=60,simulation_timeout_seconds=60)
    try:
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=60)
        (run/'simulation.log').write_text(s.stdout+s.stderr);print(s.stdout+s.stderr,flush=True)
        if s.returncode or 'ERROR:'in s.stdout+s.stderr:raise RuntimeError('actual PCIe SQ simulation failed')
        rows=[json.loads(l[15:])for l in s.stdout.splitlines()if l.startswith('SQ_PCIE_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual PCIe SQ summary')
        if before!={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}:raise ValueError('sources changed during execution')
        report.update(pass_test=True,terminal_exit_status=0,summary=rows[0],source_sha256_before_after_equal=True,
            record_bytes_verified=64*rows[0]['results'],successful_descriptor_bytes_verified=64*(rows[0]['results']-int(args.error)),
            zeroed_error_record_bytes_verified=64*int(args.error),no_host_write_or_fence=True,raw_simulator_returncode=s.returncode)
    except Exception as e:
        report.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        with args.report.open('x')as f:json.dump(report,f,indent=2);f.write('\n')


if __name__=='__main__':main()
