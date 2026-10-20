#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual controlled HLS/paged responder + native-shape muxes + dma_if_pcie.

Only the AXI host, PCIe hard-IP/link/TX-sequence source and root-complex/host
memory are models. No descriptor/status/RAM agent replaces the actual DMA
engine. This is NOT native DMA, runtime page pins, or PCIe ordering signoff.
The model explicitly implements ordinary same-requester/TC attr=0 ordering.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import probe_controlled_responder as controlled
from protected_sim import simulate

probe = controlled.probe
ROOT = probe.ROOT
PCIE = ROOT / 'external/corundum/fpga/lib/pcie/rtl'
PCIE_SOURCES = [PCIE / (n + '.v') for n in (
    'dma_if_pcie', 'dma_if_pcie_rd', 'dma_if_pcie_wr',
    'dma_if_mux', 'dma_if_mux_rd', 'dma_if_mux_wr', 'dma_if_desc_mux',
    'dma_ram_demux_rd', 'dma_ram_demux_wr')]


def ports(path):
    text = path.read_text().split('\nmodule ', 1)[1].split('\n);', 1)[0]
    return re.findall(r'^\s*(input|output)\s+wire\s+(?:\[([^]]+)\]\s+)?(\w+)\s*,?$', text, re.M)


def width(expr, params):
    if not expr:
        return 1
    hi, lo = expr.split(':')
    # Expressions come ONLY from the pinned local RTL, never user input.
    return eval(hi, {'__builtins__': {}}, params) - eval(lo, {'__builtins__': {}}, params) + 1


def declaration(name, bits, kind='wire'):
    return f'{kind} ' + (f'[{bits-1}:0] ' if bits > 1 else '') + name + ('=0;' if kind == 'reg' else ';')


def descriptor_name(name):
    name = name.replace('_pcie_addr', '_dma_addr')
    match = re.fullmatch(r'(?:m|s)_axis_(read|write)_desc_(.*)', name)
    if not match:
        raise ValueError(name)
    direction, field = match.groups()
    if field.startswith('status_'):
        return f's_dma_{direction}_{field}'
    field = {'dma_addr': 'address', 'ram_addr': 'ram_address', 'len': 'length'}.get(field, field)
    return f'm_dma_{direction}_{field}'


def bundle(prefix, tag, sel):
    result = []
    for direction in ('read', 'write'):
        for field, bits in [('address', 64), ('ram_sel', sel), ('ram_address', 15),
                            ('length', 16), ('tag', tag), ('valid', 1), ('ready', 1)]:
            result.append(declaration(prefix + f'm_dma_{direction}_{field}', bits))
        for field, bits in [('tag', tag), ('error', 4), ('valid', 1)]:
            result.append(declaration(prefix + f's_dma_{direction}_status_{field}', bits))
    result += [declaration(prefix + 'm_dma_write_imm', 32), declaration(prefix + 'm_dma_write_imm_en', 1)]
    for field, bits in [('wr_cmd_sel', 2*sel), ('wr_cmd_be', 64), ('wr_cmd_addr', 18),
                        ('wr_cmd_data', 512), ('wr_cmd_valid', 2), ('wr_cmd_ready', 2), ('wr_done', 2),
                        ('rd_cmd_sel', 2*sel), ('rd_cmd_addr', 18), ('rd_cmd_valid', 2),
                        ('rd_cmd_ready', 2), ('rd_resp_data', 512), ('rd_resp_valid', 2), ('rd_resp_ready', 2)]:
        result.append(declaration(prefix + 'dma_ram_' + field, bits))
    return '\n'.join(result)


def mux(name, lower, upper, count, index, in_tag, out_tag, in_sel, out_sel):
    """Pinned actual mux, only application/data port active; others stay idle."""
    params = dict(PORTS=count, SEG_COUNT=2, SEG_DATA_WIDTH=256, SEG_ADDR_WIDTH=9,
                  SEG_BE_WIDTH=32, S_RAM_SEL_WIDTH=in_sel, M_RAM_SEL_WIDTH=out_sel,
                  RAM_ADDR_WIDTH=15, DMA_ADDR_WIDTH=64, IMM_ENABLE=0, IMM_WIDTH=32,
                  LEN_WIDTH=16, S_TAG_WIDTH=in_tag, M_TAG_WIDTH=out_tag,
                  ARB_TYPE_ROUND_ROBIN=0, ARB_LSB_HIGH_PRIORITY=1)
    declarations = []
    connections = []
    for direction, expr, port in ports(PCIE/'dma_if_mux.v'):
        if port in ('clk', 'rst'):
            signal = port
        elif port.startswith('if_ram_'):
            signal = upper + 'dma_ram_' + port[7:]
        elif port.startswith('ram_'):
            total = width(expr, params)
            bits = total // count
            leaf = lower + 'dma_' + port
            if direction == 'input':
                signal = '{' + ','.join(leaf if n == index else f"{bits}'d0" for n in reversed(range(count))) + '}'
            else:
                signal = name + '_' + port
                declarations += [declaration(signal, total), f'assign {leaf}={signal}[{bits*index} +: {bits}];']
        else:
            upstream = ((port.startswith('m_axis_') and '_status_' not in port)
                        or (port.startswith('s_axis_') and '_status_' in port))
            signal = upper + descriptor_name(port) if upstream else None
            if not upstream:
                total = width(expr, params)
                bits = total // count
                leaf = lower + descriptor_name(port)
                if direction == 'input':
                    signal = '{' + ','.join(leaf if n == index else f"{bits}'d0" for n in reversed(range(count))) + '}'
                else:
                    signal = name + '_' + port
                    declarations += [declaration(signal, total), f'assign {leaf}={signal}[{bits*index} +: {bits}];']
        connections.append(f'.{port}({signal})')
    return ('\n'.join(declarations) + '\ndma_if_mux #(' +
            ','.join(f'.{k}({v})' for k, v in params.items()) + ') ' + name +
            '(' + ','.join(connections) + ');\n')


def engine():
    params = dict(TLP_DATA_WIDTH=256, TLP_STRB_WIDTH=8, TLP_HDR_WIDTH=128, TLP_SEG_COUNT=1,
                  TX_SEQ_NUM_COUNT=1, TX_SEQ_NUM_WIDTH=5, TX_SEQ_NUM_ENABLE=1,
                  RAM_SEL_WIDTH=4, RAM_ADDR_WIDTH=15, RAM_SEG_COUNT=2,
                  RAM_SEG_DATA_WIDTH=256, RAM_SEG_BE_WIDTH=32, RAM_SEG_ADDR_WIDTH=9,
                  PCIE_ADDR_WIDTH=64, PCIE_TAG_COUNT=256, IMM_ENABLE=0, IMM_WIDTH=32,
                  LEN_WIDTH=16, TAG_WIDTH=19, READ_OP_TABLE_SIZE=256,
                  READ_TX_LIMIT=32, READ_CPLH_FC_LIMIT=0, READ_CPLD_FC_LIMIT=0,
                  WRITE_OP_TABLE_SIZE=32, WRITE_TX_LIMIT=32, TLP_FORCE_64_BIT_ADDR=0,
                  CHECK_BUS_NUMBER=1)
    constants = dict(read_enable="1'b1", write_enable="1'b1", ext_tag_enable="1'b1",
                     rcb_128b="1'b1", requester_id="16'h8200", max_read_request_size="3'd0",
                     max_payload_size="3'd0")
    declarations = []
    connections = []
    for direction, expr, port in ports(PCIE/'dma_if_pcie.v'):
        if port in ('clk', 'rst'):
            signal = port
        elif port in constants:
            signal = constants[port]
        elif port.startswith(('s_axis_read_desc_', 's_axis_write_desc_',
                              'm_axis_read_desc_status_', 'm_axis_write_desc_status_')):
            signal = 'eng_' + descriptor_name(port)
        elif port.startswith('ram_'):
            signal = 'eng_dma_' + port
        elif port.startswith('stat_'):
            signal = ''
        else:
            signal = 'tlp_' + port
            declarations.append(declaration(signal, width(expr, params), 'reg' if direction == 'input' else 'wire'))
        connections.append(f'.{port}({signal})')
    return ('\n'.join(declarations) + '\ndma_if_pcie #(' +
            ','.join(f'.{k}({v})' for k, v in params.items()) + ') generic_dma(' + ','.join(connections) + ');\n')


HOST = r'''
reg [7:0] pcie_host[0:16383],pcie_posted[0:16383];reg pcie_posted_valid[0:16383];
integer pcie_first=3565,pcie_seed=0,pcie_last_tag=0,pcie_current_length=0,pcie_current_offset=0;
integer pcie_physical_reads=0,pcie_physical_writes=0,pcie_write_bytes=0;
integer read_ram=0,read_outstanding=0,write_outstanding=0,posted_bytes=0;
integer read_tlps=0,write_tlps=0,read_completions=0,fences=0,wr_seq_hold_cycles=0;
integer init_byte,guard_byte,desc_tag,desc_ram,desc_length;
reg [63:0] desc_address;
reg engine_error=0,wr_ack_pending=0;
reg [31:0] pcie_expected_key=8;
reg wr_tlp_stalled=0,rd_tlp_stalled=0;
reg [399:0] held_wr_tlp;
reg [134:0] held_rd_tlp;
// FUNCTIONS
assign parent_dma_drained=!engine_error && !tlp_status_rd_busy && !tlp_status_wr_busy &&
 !read_outstanding && !write_outstanding && !m_dma_read_valid && !m_dma_write_valid &&
 !mid_m_dma_read_valid && !mid_m_dma_write_valid && !eng_m_dma_read_valid && !eng_m_dma_write_valid &&
 !tlp_tx_rd_req_tlp_valid && !tlp_tx_wr_req_tlp_valid && !tlp_rx_cpl_tlp_valid &&
 !(|eng_dma_ram_wr_cmd_valid) && !(|eng_dma_ram_rd_cmd_valid) && !(|eng_dma_ram_rd_resp_valid) &&
 !(|dma_ram_wr_cmd_valid) && !(|dma_ram_rd_cmd_valid) && !(|dma_ram_rd_resp_valid);
always @(posedge clk) if(!rst) begin
 if(wr_tlp_stalled && (!tlp_tx_wr_req_tlp_valid ||
    {tlp_tx_wr_req_tlp_data,tlp_tx_wr_req_tlp_strb,tlp_tx_wr_req_tlp_hdr,tlp_tx_wr_req_tlp_seq,tlp_tx_wr_req_tlp_sop,tlp_tx_wr_req_tlp_eop}!==held_wr_tlp))
  $fatal(1,"actual write TLP ownership during backpressure");
 if(rd_tlp_stalled && (!tlp_tx_rd_req_tlp_valid ||
    {tlp_tx_rd_req_tlp_hdr,tlp_tx_rd_req_tlp_seq,tlp_tx_rd_req_tlp_sop,tlp_tx_rd_req_tlp_eop}!==held_rd_tlp))
  $fatal(1,"actual read TLP ownership during backpressure");
 wr_tlp_stalled=tlp_tx_wr_req_tlp_valid&&!tlp_tx_wr_req_tlp_ready;
 rd_tlp_stalled=tlp_tx_rd_req_tlp_valid&&!tlp_tx_rd_req_tlp_ready;
 held_wr_tlp={tlp_tx_wr_req_tlp_data,tlp_tx_wr_req_tlp_strb,tlp_tx_wr_req_tlp_hdr,tlp_tx_wr_req_tlp_seq,tlp_tx_wr_req_tlp_sop,tlp_tx_wr_req_tlp_eop};
 held_rd_tlp={tlp_tx_rd_req_tlp_hdr,tlp_tx_rd_req_tlp_seq,tlp_tx_rd_req_tlp_sop,tlp_tx_rd_req_tlp_eop};
 if(tlp_status_error_cor || tlp_status_error_uncor) engine_error<=1;
 if(engine_error) $fatal(1,"actual generic PCIe engine error");
 if(mv && mr) begin
  if(mk!==pcie_expected_key || mo!==64'h210) $fatal(1,"authorized key/offset changed");
  pcie_current_length=ml;pcie_current_offset=mo;
 end
 if((m_dma_read_valid && m_dma_read_ready) || (m_dma_write_valid && m_dma_write_ready)) begin
  if(m_dma_read_valid && m_dma_read_ready && m_dma_write_valid && m_dma_write_ready) $fatal(1,"two leaf commands");
  desc_tag=m_dma_write_valid ? m_dma_write_tag:m_dma_read_tag;
  desc_ram=m_dma_write_valid ? m_dma_write_ram_address:m_dma_read_ram_address;
  desc_length=m_dma_write_valid ? m_dma_write_length:m_dma_read_length;
  desc_address=m_dma_write_valid ? m_dma_write_address:m_dma_read_address;
  if(desc_tag!=pcie_last_tag+1 || desc_length<=0 || desc_address!==pcie_expected_dma(pcie_current_offset+(desc_ram==8128 ? 0:desc_ram)))
   $fatal(1,"leaf physical page or unique tag mismatch");
  if((desc_ram==8128 && desc_length!=1) || (desc_ram!=8128 && !((desc_ram==0 && desc_length==3)||(desc_ram==3 && desc_length==62))))
   $fatal(1,"page split bounds");
  $display("PAGE_DMA %0d %h %0d %0d %0d",m_dma_write_valid,desc_address,desc_length,desc_ram,desc_tag);
  pcie_last_tag=desc_tag;
 end
 if(m_dma_read_valid && m_dma_read_ready) begin
  if(read_outstanding) $fatal(1,"overlapping actual read");
  read_outstanding=1;read_ram=m_dma_read_ram_address;pcie_physical_reads=pcie_physical_reads+1;
 end
 if(m_dma_write_valid && m_dma_write_ready) begin
  if(write_outstanding) $fatal(1,"overlapping actual write");
  write_outstanding=1;pcie_physical_writes=pcie_physical_writes+1;
 end
 if(s_dma_read_status_valid) begin
  if(!read_outstanding || s_dma_read_status_error || s_dma_read_status_tag!=pcie_last_tag) $fatal(1,"actual read status ownership");
  read_outstanding=0;
 end
 if(s_dma_write_status_valid) begin
  if(!write_outstanding || wr_ack_pending || s_dma_write_status_error || s_dma_write_status_tag!=pcie_last_tag)
   $fatal(1,"write status before final TX sequence acknowledgment");
  write_outstanding=0;
 end
 if((eng_m_dma_read_valid && eng_m_dma_read_ready) || (eng_m_dma_write_valid && eng_m_dma_write_ready)) begin
  if(eng_m_dma_write_valid) begin
   if(eng_m_dma_write_tag!==({3'b110,m_dma_write_tag}) || eng_m_dma_write_ram_sel!=12) $fatal(1,"actual write mux routing/truncation");
  end else if(eng_m_dma_read_tag!==({3'b110,m_dma_read_tag}) || eng_m_dma_read_ram_sel!=12) $fatal(1,"actual read mux routing/truncation");
  $display("GENERIC_DESC %0d %h %h",eng_m_dma_write_valid,eng_m_dma_write_valid ? eng_m_dma_write_tag:eng_m_dma_read_tag,
    eng_m_dma_write_valid ? eng_m_dma_write_ram_sel:eng_m_dma_read_ram_sel);
 end
 if(sv && sr) begin
  if(!parent_dma_drained || !dma_drained || posted_bytes) $fatal(1,"completion before actual engine/RAM/fence drain");
  for(guard_byte=0;guard_byte<16384;guard_byte=guard_byte+1)
   if(pcie_posted_valid[guard_byte] || pcie_host[guard_byte]!==((guard_byte>=4093 && guard_byte<4158) ? pcie_pattern(guard_byte-4093):(((guard_byte*37)^8'h5a)&255)))
    $fatal(1,"host payload/padding/sentinel byte%0d",guard_byte);
 end
end
initial begin
 for(init_byte=0;init_byte<16384;init_byte=init_byte+1) begin
  pcie_host[init_byte]=(init_byte*37)^8'h5a;pcie_posted_valid[init_byte]=0;
 end
end
task check_request;
 input [127:0] h;input integer is_write;
 begin
  if(h[127:125] !== (is_write ? 3'b011:3'b001) || h[124:120]!=0 || h[119:106]!=0 || h[95:80]!==16'h8200 || h[1:0]!=0)
   $fatal(1,"not ordinary DMA64 same-requester TC0 attr0 header %h",h);
 end
endtask
// Root-complex MODEL: transmit sequence is deliberately withheld after the
// entire posted request reaches the link. Only enabled payload bytes are
// queued; they remain invisible to host loads until an ordered read fence.
initial begin : root_write_agent
 reg [127:0] h;reg [63:0] base;reg [4:0] seq;
 integer dwords,word_offset,dw,b,idx,enabled,byte_pos,stall;
 reg [3:0] be;reg active;
 active=0;word_offset=0;
 repeat(20) @(negedge clk);
 forever begin
  @(negedge clk);tlp_tx_wr_req_tlp_ready=rng[10:8]!=0;
  @(posedge clk);
  if(tlp_tx_wr_req_tlp_valid && tlp_tx_wr_req_tlp_ready) begin
   if(tlp_tx_wr_req_tlp_sop) begin
    if(active || wr_ack_pending) $fatal(1,"unmatched posted write");
    h=tlp_tx_wr_req_tlp_hdr;check_request(h,1);seq=tlp_tx_wr_req_tlp_seq;
    base={h[63:2],2'b0};dwords=h[105:96];if(!dwords)dwords=1024;
    active=1;word_offset=0;write_tlps=write_tlps+1;
    $display("TLP_WRITE %h %0d",h,seq);
   end
   // This segmented interface defines the header at SOP. The pinned engine
   // may change non-SOP header copies as its remaining-dword counter moves;
   // they are not new TLP headers. Data and framing still belong to SOP h.
   if(!active || tlp_tx_wr_req_tlp_seq!==seq) $fatal(1,"posted TLP framing");
   for(dw=0;dw<8;dw=dw+1) begin
    if(tlp_tx_wr_req_tlp_strb[dw] !== (word_offset+dw<dwords)) $fatal(1,"TLP dword strobe");
    if(word_offset+dw<dwords) begin
     be=word_offset+dw==0 ? h[67:64] : (word_offset+dw==dwords-1 ? h[71:68]:4'hf);
     for(b=0;b<4;b=b+1) if(be[b]) begin
      idx=pcie_host_index(base+(word_offset+dw)*4+b);byte_pos=idx-4093;
      if(idx<4093 || idx>=4158 || tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8]!==pcie_pattern(byte_pos)) $fatal(1,"actual posted TLP payload/range");
      pcie_posted[idx]=tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8];pcie_posted_valid[idx]=1;
      pcie_write_bytes=pcie_write_bytes+1;posted_bytes=posted_bytes+1;
     end
    end
   end
   word_offset=word_offset+8;
   if(tlp_tx_wr_req_tlp_eop !== (word_offset>=dwords)) $fatal(1,"posted EOP");
   if(tlp_tx_wr_req_tlp_eop) begin
    active=0;wr_ack_pending=1;
    @(negedge clk);tlp_tx_wr_req_tlp_ready=0;
    repeat(64) begin
     @(negedge clk);wr_seq_hold_cycles=wr_seq_hold_cycles+1;
     if(s_dma_write_status_valid || parent_dma_drained || sv) $fatal(1,"TX-sequence hold bypassed");
    end
    tlp_s_axis_wr_req_tx_seq_num=seq;tlp_s_axis_wr_req_tx_seq_num_valid=1;
    @(negedge clk);tlp_s_axis_wr_req_tx_seq_num_valid=0;wr_ack_pending=0;
   end
  end
 end
end
// Root-complex MODEL: read completion uses original requester/tag/lower
// address and carries actual modeled host bytes. Actual dma_if_pcie_rd
// performs all completion parsing, RAM placement, done accounting and status.
initial begin : root_read_agent
 reg [127:0] h,cpl;reg [63:0] base,first_address;reg [4:0] seq;
 integer dw,b,first_lane,last_lane,bytes_count,total_dwords,position,idx,n;
 repeat(20) @(negedge clk);
 forever begin
  while(!tlp_tx_rd_req_tlp_valid) @(negedge clk);
  h=tlp_tx_rd_req_tlp_hdr;seq=tlp_tx_rd_req_tlp_seq;check_request(h,0);
  repeat(9) begin @(negedge clk);if(!tlp_tx_rd_req_tlp_valid || tlp_tx_rd_req_tlp_hdr!==h) $fatal(1,"read TLP not held");end
  tlp_tx_rd_req_tlp_ready=1;@(posedge clk);
  if(!tlp_tx_rd_req_tlp_sop || !tlp_tx_rd_req_tlp_eop) $fatal(1,"read TLP framing");
  @(negedge clk);tlp_tx_rd_req_tlp_ready=0;
  read_tlps=read_tlps+1; $display("TLP_READ %h %0d",h,seq);
  total_dwords=h[105:96];if(!total_dwords)total_dwords=1024;
  first_lane=0;while(!h[64+first_lane] && first_lane<4)first_lane=first_lane+1;
  if(first_lane==4) $fatal(1,"zero-byte read not allowed");
  bytes_count=0;
  for(dw=0;dw<total_dwords;dw=dw+1) for(b=0;b<4;b=b+1)
   if(dw==0 ? h[64+b] : (dw==total_dwords-1 ? h[68+b]:1'b1)) bytes_count=bytes_count+1;
  base={h[63:2],2'b0};first_address=base+first_lane;
  repeat(17) @(negedge clk);
  tlp_s_axis_rd_req_tx_seq_num=seq;tlp_s_axis_rd_req_tx_seq_num_valid=1;
  @(negedge clk);tlp_s_axis_rd_req_tx_seq_num_valid=0;
  if(read_ram==8128) begin
   if(bytes_count!=1 || first_address!==64'h8123456789abcffd || posted_bytes!=65) $fatal(1,"readback fence identity/data");
   fences=fences+1;
   repeat(200) begin @(negedge clk);if(sv || parent_dma_drained) $fatal(1,"readback fence bypassed");end
   // Explicit MODEL ordering rule, not an assertion about a physical link.
   for(n=0;n<16384;n=n+1) if(pcie_posted_valid[n]) begin
    pcie_host[n]=pcie_posted[n];pcie_posted_valid[n]=0;
   end
   posted_bytes=0;
  end else if(posted_bytes) $fatal(1,"new read before previous WRITE fence");
  cpl=0;cpl[127:125]=3'b010;cpl[124:120]=5'b01010;cpl[105:96]=total_dwords;
  cpl[95:80]=16'h0100;cpl[75:64]=bytes_count;cpl[63:48]=h[95:80];cpl[47:40]=h[79:72];cpl[38:32]=first_address[6:0];
  // COMPLETION_ERROR_INJECTION
  for(position=0;position<total_dwords*4;position=position+32) begin
   @(negedge clk);tlp_rx_cpl_tlp_data=0;tlp_rx_cpl_tlp_hdr=cpl;
   for(b=0;b<32;b=b+1) if(position+b<total_dwords*4) begin
    idx=pcie_host_index(base+position+b);if(idx<0) $fatal(1,"unknown full64 host address");
    tlp_rx_cpl_tlp_data[b*8+:8]=pcie_host[idx];
   end
   tlp_rx_cpl_tlp_sop=position==0;tlp_rx_cpl_tlp_eop=position+32>=total_dwords*4;
   tlp_rx_cpl_tlp_valid=1;@(posedge clk);while(!tlp_rx_cpl_tlp_ready) @(posedge clk);
   @(negedge clk);tlp_rx_cpl_tlp_valid=0;
  end
  read_completions=read_completions+1;
 end
end
'''


def bench(error=None):
    tb = controlled.bench()
    start = tb.index('reg [7:0] pcie_host')
    end = tb.index('localparam AXIL_ADDR_WIDTH=12;', start)
    functions = tb[tb.index('function [63:0] pcie_dma_page;', start):tb.index('task pcie_accept_descriptor;', start)]
    graph = (bundle('mid_', 18, 3) + '\n' + bundle('eng_', 19, 4) + '\n' +
             mux('interface_mux', '', 'mid_', 3, 2, 16, 18, 1, 3) +
             mux('control_data_mux', 'mid_', 'eng_', 2, 1, 18, 19, 3, 4) + engine())
    tb = tb[:start] + graph + HOST.replace('// FUNCTIONS', functions) + tb[end:]
    tb = tb.replace('RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16;', 'RAM_SEL_WIDTH=1,DMA_LEN_WIDTH=16,TAG_WIDTH=16;')
    tb = tb.replace('rocev2_controlled_responder dut(', 'rocev2_controlled_responder #(.RAM_SEL_WIDTH(RAM_SEL_WIDTH)) dut(')
    # These inputs now come ONLY from actual mux/PCIe RTL, never host agents.
    names = ['parent_dma_drained', 'm_dma_read_ready', 'm_dma_write_ready',
             *['s_dma_' + d + '_status_' + f for d in ('read', 'write') for f in ('tag', 'error', 'valid')],
             *['dma_ram_' + f for f in ('wr_cmd_sel', 'wr_cmd_be', 'wr_cmd_addr', 'wr_cmd_data',
                                        'wr_cmd_valid', 'rd_cmd_sel', 'rd_cmd_addr', 'rd_cmd_valid', 'rd_resp_ready')]]
    for name in names:
        tb, count = re.subn(r'\breg (\[[^]]+\] )?' + name + r'=0;', lambda m: 'wire ' + (m[1] or '') + name + ';', tb)
        if count != 1:
            raise ValueError(('expected unique actual-engine input', name, count))
    tb = tb.replace(' parent_dma_drained=1;', ' // Parent drain is derived from actual engine/mux/RAM signals, never tied high.')
    # All other native-shape interfaces are idle; descriptors and RAM are routed
    # through actual mux RTL, including all three otherwise-lost tag bits.
    tb = tb.replace(' $display("RESULT ', '''
 if(!parent_dma_drained || engine_error || wr_seq_hold_cycles!=256 || read_tlps!=8 || write_tlps!=4 || read_completions!=8 || fences!=2)
  $fatal(1,"actual PCIe path coverage/drain missing");
 $display("PCIE_RESULT {\\"pass_test\\":true,\\"read_tlps\\":%0d,\\"write_tlps\\":%0d,\\"read_completions\\":%0d,\\"fences\\":%0d,\\"write_bytes\\":%0d,\\"wr_tx_sequence_hold_cycles\\":%0d}",read_tlps,write_tlps,read_completions,fences,pcie_write_bytes,wr_seq_hold_cycles);
 $display("RESULT ''', 1)
    if error:
        # A real PCIe Unsupported Request completion, not an injected DMA
        # descriptor status. Generic RTL parses it and emits error code10.
        target = 'read_ram==3' if error == 'read' else 'read_ram==8128'
        tb = tb.replace('// COMPLETION_ERROR_INJECTION', f'''
  if({target}) begin
   cpl[127:125]=0;cpl[105:96]=0;cpl[79:77]=3'b001;
   total_dwords=1;
  end
''')
        tb = tb.replace('if(engine_error) $fatal', 'if(engine_error && !expect_fault) $fatal')
        tb = tb.replace('if(sv && !dma_drained)', 'if(sv && se==0 && !dma_drained)')
        tb = tb.replace('if(!read_outstanding || s_dma_read_status_error || s_dma_read_status_tag!=pcie_last_tag)',
                        'if(!read_outstanding || (s_dma_read_status_error && s_dma_read_status_error!=10) || s_dma_read_status_tag!=pcie_last_tag)')
        tb = tb.replace('if(sv && sr) begin\n  if(!parent_dma_drained', 'if(sv && sr && se==0) begin\n  if(!parent_dma_drained')
    return '\n'.join('`include "' + str(p) + '"' for p in PCIE_SOURCES) + '\n' + tb


def stimulus():
    fixtures, body, cases = probe.stimulus()
    body = '\n'.join(body).replace('$display("CASE valid_second_write");',
        'host_stage(5,OWNER0,0,8,0,0,0,0);$display("CASE valid_second_write");')
    begin = body.index('fork\n begin')
    end = body.index('configure_mr(0,17,7,16);', begin) + len('configure_mr(0,17,7,16);')
    body = body[:begin] + r'''
fork
 begin while(!mv) @(negedge clk);host_finish(5,OWNER0,0,8,3);end
 begin
  expiry=cycle+5000;while(completed==completed_before && cycle<expiry) @(negedge clk);
  if(completed!=completed_before+1) $fatal(1,"controller deadlocked actual DMA");
 end
join
host_api(2,OWNER0+3,0,0,17,7,0,0,16,0);host_pages(OWNER0+3,0,16);pcie_expected_key=16;
''' + body[end:]
    return fixtures, body, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--completion-error', choices=['read', 'fence'],
                        help='inject a real UR completion at READ piece2 or WRITE readback fence')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence: choose fresh report')
    extra = [*PCIE_SOURCES, controlled.TOP, controlled.CONTROL, *controlled.registers.SOURCES,
             controlled.registers.HEADER, *controlled.integration.paged.SOURCES, Path(__file__),
             Path(controlled.__file__), Path(controlled.integration.__file__), Path(probe.__file__),
             Path(controlled.registers.__file__), ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',
             ROOT/'rdma/rnic/tests/protected_sim.py']
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if args.completion_error:
        endpoint = dict(source_mac='b8:83:03:67:c5:d0', destination_mac='8a:f3:fb:b9:75:31',
            source_ip='198.18.11.1', destination_ip='198.18.11.2', udp_source_port=49152,
            destination_qpn=2, psn=probe.PSN, remote_address=probe.VA+0x210, rkey=8)
        frame = (probe.read_wire.encode(**endpoint, opcode=probe.read_wire.REQUEST, read_bytes=65)
                 if args.completion_error == 'read' else probe.rocev2_wire.write_only_frame(**endpoint, payload=probe.PAYLOAD))
        fixtures = probe.words(frame[14:])
        cases = [dict(name='actual_pcie_UR_'+args.completion_error)]
        body = r'''
expect_fault=1;send_frame(0,FRAME_COUNT);
// The page engine faults before the guard finishes its mandatory READ zero
// drain and consumes the aggregate error. Check the final guarded completion,
// not an assumption that these independent stages fail in the same cycle.
expiry=cycle+4000;while(!dut.endpoint.guard_fault && cycle<expiry) @(negedge clk);
if(!dut.endpoint.guard_fault || !fault || fc!=34 || commands!=1 || statuses!=1 || completed || txframes || accepted!=1 || se!=EXPECTED_ERROR || !engine_error)
 $fatal(1,"actual UR did not reach protected failure fault%0d cmd%0d st%0d complete%0d tx%0d se%0d engine%0d",fc,commands,statuses,completed,txframes,se,engine_error);
repeat(200) @(negedge clk);
read_reg(AS02_CTL_STATUS,host_value);
if(tv || quiet || dut.memory_drained || parent_dma_drained || !(host_value & AS02_ST_FATAL) || !(host_value & AS02_ST_PAUSED))
 $fatal(1,"actual PCIe error released memory or admitted traffic");
if(EXPECT_FENCE ? (posted_bytes!=0 || pcie_write_bytes!=65 || fences!=1) : (pcie_write_bytes!=0 || read_tlps!=2))
 $fatal(1,"partial/error DMA coverage");
$display("PCIE_RESULT {\"pass_test\":true,\"read_tlps\":%0d,\"write_tlps\":%0d,\"read_completions\":%0d,\"fences\":%0d,\"write_bytes\":%0d,\"wr_tx_sequence_hold_cycles\":%0d}",read_tlps,write_tlps,read_completions,fences,pcie_write_bytes,wr_seq_hold_cycles);
$display("RESULT {\"pass_test\":true,\"guard_fault\":%0d,\"commands\":%0d,\"statuses\":%0d,\"completed\":%0d,\"tx_frames\":%0d,\"page_release_proof\":false}",fc,commands,statuses,completed,txframes);
$finish;
'''.replace('FRAME_COUNT', str(len(fixtures))).replace('EXPECTED_ERROR', '10').replace('EXPECT_FENCE', '1' if args.completion_error == 'fence' else '0')
    else:
        fixtures, body, cases = stimulus()
    tb = bench(args.completion_error).replace('STIMULUS_LAST', str(len(fixtures)-1)).replace('// TEST_BODY', body)
    output, identity = simulate(tb, {'input.hex': fixtures}, args.hls_build, wall_timeout=180)
    print(output, flush=True)
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if before != after:
        raise ValueError('actual PCIe probe sources changed')
    identity['source_sha256'].update(after)
    rows = [json.loads(l[7:]) for l in output.splitlines() if l.startswith('RESULT ')]
    pcie = [json.loads(l[12:]) for l in output.splitlines() if l.startswith('PCIE_RESULT ')]
    assert len(rows) == len(pcie) == 1 and rows[0]['pass_test'] and pcie[0]['pass_test']
    if args.completion_error:
        assert rows[0]['guard_fault'] == 34 and rows[0]['completed'] == rows[0]['tx_frames'] == 0
        assert not rows[0]['page_release_proof'] and not probe.rw_sim.ethernet_frames(output)
        report = dict(scope='Actual controlled HLS/mux/generic PCIe DMA RTL parses UR completion and retains failed lease; root-complex/host/link MODELS',
            pass_test=True, actual_pcie_tlp_engine=True, actual_dma_muxes=True, parent_drain_tied_high=False,
            hardware_verified=False, native_dma_verified=False, runtime_pins_verified=False, completion_claim=False,
            completion_error=args.completion_error, summary=rows[0], pcie_summary=pcie[0], **identity)
        with args.report.open('x') as out:
            out.write(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        return
    assert rows[0]['completed'] == 5
    frames = probe.rw_sim.ethernet_frames(output)
    good = [c for c in cases if not c.get('expected_error') and not c.get('expected_integrity_drop')]
    assert len(frames) == len(good) == 5
    responses = []
    for case, packet in zip(good, frames):
        assert probe.rocev2_wire.internet_checksum(packet[:20]) == 0
        ethernet = bytes.fromhex('b8830367c5d08af3fbb975310800') + packet
        if case['operation'] == 'read':
            d = probe.read_wire.decode(ethernet)
            assert d['opcode'] == probe.read_wire.ONLY and d['payload'] == probe.PAYLOAD and d['syndrome'] & 0xe0 == 0
        else:
            d = probe.rocev2_wire.decode_ethernet(ethernet)
            assert d['opcode'] == 0x11 and d['icrc_valid'] and d['aeth_syndrome'] & 0xe0 == 0
        assert d['psn'] == case['psn'] and d['destination_qpn'] == 196
        responses.append(dict(case=case['name'], ipv4_hex=packet.hex(), wire_checksums_verified=True))
    replies = [l for l in output.splitlines() if l.startswith('HOST_REPLY ')]
    leaves = [l for l in output.splitlines() if l.startswith('PAGE_DMA ')]
    routed = [l for l in output.splitlines() if l.startswith('GENERIC_DESC ')]
    assert len(replies) == 20 and len(leaves) == len(routed) == 12
    assert [int(l.split()[-1]) for l in leaves] == list(range(1, 13))
    assert [int(l.split()[2], 16) for l in routed] == [0x60000 + i for i in range(1, 13)]
    report = dict(scope='Actual controlled HLS/paged DMA, 3-port interface + 2-port control/data muxes and generic PCIe DMA RTL; hard-IP/link/root-complex/host memory MODELS',
        pass_test=True, actual_pcie_tlp_engine=True, actual_dma_muxes=True, parent_drain_tied_high=False,
        hardware_verified=False, board_integrated=False, native_dma_verified=False,
        runtime_pins_verified=False, kernel_callbacks_executed=False, completion_claim=False,
        summary=rows[0], pcie_summary=pcie[0], cases=cases, responses=responses, host_replies=replies,
        leaf_descriptors=leaves, routed_descriptors=routed, application_tag_width=16, engine_tag_width=19,
        native_profile_requires_DMA_TAG_WIDTH=19, RAM_ADDR_WIDTH=15, app_RAM_SEL_WIDTH=1,
        PCIe_TLP_DATA_WIDTH=256, TX_SEQ_NUM_ENABLE=True, PCIE_TAG_COUNT=256,
        write_bytes_checked=130, read_bytes_checked=195, **identity)
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
