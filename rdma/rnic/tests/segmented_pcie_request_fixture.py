# SPDX-License-Identifier: BSD-2-Clause-Views
"""Strict root-model decoding for the actual low sealed DMA page.

Corundum's unchanged dma_if_pcie_rd emits 3DW MemRd below4GiB (default
TLP_FORCE_64_BIT_ADDR=0), 4DW otherwise. Keep every prior scenario's 4DW
guard; only large ordinary source reads to the exact third page add 3DW.
Never truncate a 64-bit address, invent a status, or accept arbitrary pages.
"""
import zero_rq_native_fixture as old

once = old.once
ROOT = old.ROOT
INPUTS = [ROOT/'external/corundum/fpga/lib/pcie/rtl'/name
          for name in ['dma_if_pcie.v', 'dma_if_pcie_rd.v']]


def apply(text):
    read = INPUTS[1].read_text()
    for token in ['parameter TLP_FORCE_64_BIT_ADDR = 0,',
                  '((req_pcie_addr_reg[PCIE_ADDR_WIDTH-1:2] >> 30) != 0) || TLP_FORCE_64_BIT_ADDR',
                  'tlp_hdr[63:34] = req_pcie_addr_reg[PCIE_ADDR_WIDTH-1:2]',
                  "tlp_hdr[31:0] = 32'd0;"]:
        if token not in read:
            raise ValueError('reviewed actual low-address TLP encoding changed')
    text = once(text, 'task check_request;', ADDRESS+'\n'+DESCRIPTOR+'\ntask check_request;')
    before = '''  if(h[127:125] !== (is_write ? 3'b011:3'b001) || h[124:120]!=0 || h[119:106]!=0 || h[95:80]!==16'h8200 || h[1:0]!=0)
   $fatal(1,"not ordinary DMA64 same-requester TC0 attr0 header %h",h);'''
    after = '''  if(runtime_segmented && !is_write && h[127:125]===3'b000)begin
   if(h[124:120]!==5'd0 || h[119:106]!==14'd0 || h[95:80]!==16'h8200 || h[33:0]!==34'd0 ||
    (segmented_read_address(h)>>12)!==(pcie_dma_page(2)>>12))
    $fatal(1,"not exact sealed low-page 3DW same-requester TC0 attr0 read header %h",h);
  end else begin
'''+before+'''
  end'''
    text = once(text, before, after)
    return once(text, "base={h[63:2],2'b0};first_address=base+first_lane;",
                '''base=segmented_read_address(h);first_address=base+first_lane;
  if(runtime_segmented)begin
   if(!read_outstanding || first_address!==(large_pcie_read_base+large_pcie_read_bytes) ||
    bytes_count<=0 || large_pcie_read_bytes>large_pcie_read_length ||
    bytes_count>large_pcie_read_length-large_pcie_read_bytes)
    $fatal(1,"actual full64 descriptor/TLP byte range or order mismatch");
   large_pcie_read_bytes=large_pcie_read_bytes+bytes_count;
  end''')


ADDRESS = r'''
function [63:0] segmented_read_address;
 input [127:0] h;
 begin
  if(runtime_segmented && h[127:125]===3'b000)segmented_read_address={32'd0,h[63:34],2'b00};
  else segmented_read_address={h[63:2],2'b00};
 end
endfunction
'''

DESCRIPTOR = r'''
// Read-only root model joins every TLP byte to the actual accepted full64
// physical descriptor. Identical test payloads on different pages cannot
// hide high-address truncation, reordered reads or excess enabled bytes.
reg [63:0] large_pcie_read_base=0;
integer large_pcie_read_length=0,large_pcie_read_bytes=0;
always @(posedge clk)if(!rst && runtime_segmented)begin
 if(m_dma_read_valid && m_dma_read_ready)begin
  large_pcie_read_base=m_dma_read_address;
  large_pcie_read_length=m_dma_read_length;
  large_pcie_read_bytes=0;
 end
 if(s_dma_read_status_valid && large_pcie_read_bytes!=large_pcie_read_length)
  $fatal(1,"actual physical descriptor completed before exact TLP bytes");
end
'''
