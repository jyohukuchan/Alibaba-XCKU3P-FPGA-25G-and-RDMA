#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual nonaliasing AXI decode/Ethernet CSR/same-port/HLS/mux/PCIe RTL.

No raw MAC/IP/epoch configuration drivers or raw MR/PTE/QP bypass. Physical
MAC/PCIe/link/root-complex/host/AXI source remain MODELS, not native hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import probe_dual_ethernet as dual
from protected_sim import simulate

pcie=dual.pcie
ROOT=dual.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_native_endpoint.v'
CONFIG=ROOT/'rdma/rnic/rtl/rocev2_ethernet_config_regs.v'
HEADER=ROOT/'rdma/rnic/kernel/native_regs.h'
AXI=ROOT/'external/corundum/fpga/lib/axi/rtl'
XBAR=[AXI/(n+'.v') for n in ('axil_crossbar','axil_crossbar_rd','axil_crossbar_wr',
                            'axil_crossbar_addr','axil_register_rd','axil_register_wr')]

SETUP=r'''
 read_reg(0,host_value);if(host_value!==32'h524f4332)$fatal(1,"old v2 root ID changed: %h",host_value);
 read_reg(4,host_value);if(host_value!==32'h20000)$fatal(1,"old v2 ABI changed");
 read_reg(24'h401000,host_value);if(host_value!==32'h524e4531)$fatal(1,"Ethernet CSR address decode");
 read_reg(24'h401004,host_value);if(host_value!==32'h10000)$fatal(1,"Ethernet CSR ABI");
 write_reg(24'h401020,32'hfbb97531,15,0,0);write_reg(24'h401024,32'h8af3,15,0,0);
 write_reg(24'h401028,32'h0367c5d0,15,0,0);write_reg(24'h40102c,32'hb883,15,0,0);
 write_reg(24'h401030,32'hc6120b02,15,0,0);write_reg(24'h401034,1,15,0,0);
 write_reg(24'h401010,1,15,0,0);
 read_reg(24'h40100c,host_value);if(host_value!=1 || ethernet_config_error || !ethernet_enabled)$fatal(1,"actual safe config commit");
 write_reg(24'h010000,32'ha55af0f0,15,0,0);read_reg(24'h010000,host_value);
 if(host_value!==32'ha55af0f0)$fatal(1,"old capture RAM aperture changed");
 read_reg(24'h400020,host_value);if(host_value!=0)$fatal(1,"capture RAM aliased responder staging");
 expect_decerr(24'h300010);
 read_reg(0,host_value);if(host_value!==32'h524f4332)$fatal(1,"unmapped access hit old controls");
 read_reg(24'h40100c,host_value);if(host_value!=1 || ethernet_config_error)$fatal(1,"unmapped access hit Ethernet controls");
'''

DECERR=r'''
always @(posedge clk) if(!rst && cycle<4300) begin
 if(s_axil_arvalid && s_axil_arready)$display("NATIVE_AR %h",s_axil_araddr);
 if(s_axil_rvalid)$display("NATIVE_R %h resp%h",s_axil_rdata,s_axil_rresp);
 if(dut.bus_arvalid[0] && dut.bus_arready[0])$display("LEGACY_AR %h",dut.bus_araddr[23:0]);
 if(dut.bus_rvalid[0])$display("LEGACY_R %h",dut.bus_rdata[31:0]);
end
task expect_decerr;
 input [23:0] address;
 begin
  fork
   begin @(negedge clk);s_axil_awaddr=address;s_axil_awvalid=1;
    @(posedge clk);while(!s_axil_awready)@(posedge clk);@(negedge clk);s_axil_awvalid=0;end
   begin @(negedge clk);s_axil_wdata=1;s_axil_wstrb=15;s_axil_wvalid=1;
    @(posedge clk);while(!s_axil_wready)@(posedge clk);@(negedge clk);s_axil_wvalid=0;end
  join
  while(!s_axil_bvalid)@(negedge clk);
  if(s_axil_bresp!==2'b11)$fatal(1,"unmapped write did not DECERR");
  repeat(5)begin @(negedge clk);if(s_axil_bvalid!==1'b1 || s_axil_bresp!==2'b11)$fatal(1,"DECERR write not retained");end
  s_axil_bready=1;@(negedge clk);s_axil_bready=0;
  @(negedge clk);s_axil_araddr=address;s_axil_arvalid=1;
  @(posedge clk);while(!s_axil_arready)@(posedge clk);@(negedge clk);s_axil_arvalid=0;
  while(!s_axil_rvalid)@(negedge clk);
  if(s_axil_rresp!==2'b11 || s_axil_rdata!==32'd0)$fatal(1,"unmapped read did not DECERR/zero");
  repeat(5)begin @(negedge clk);if(s_axil_rvalid!==1'b1 || s_axil_rresp!==2'b11 || s_axil_rdata!==32'd0)$fatal(1,"DECERR read not retained");end
  s_axil_rready=1;@(negedge clk);s_axil_rready=0;
 end
endtask
'''


def bench():
    tb=dual.bench()
    start=tb.index('rocev2_dual_ethernet_endpoint dut(')
    end=tb.index(');',start)+2
    mapping=dict(re.findall(r'\.(\w+)\(([^()]*)\)',tb[start:end]))
    mapping={n.replace('s_axil_responder_','s_axil_'):sig for n,sig in mapping.items()
             if not n.startswith(('s_axil_rw_','cfg_'))}
    params=dict(TX_TAG_WIDTH=16,TS_WIDTH=96,RX_USER_WIDTH=97,RAM_SIZE=8192,RAM_ADDR_WIDTH=15,
        SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,SEG_ADDR_WIDTH=9,
        RAM_SEL_WIDTH=1,DMA_LEN_WIDTH=16,DMA_TAG_WIDTH=16)
    declarations=[];connections=[]
    for direction,expr,name in pcie.ports(RTL):
        signal=mapping.get(name,name)
        if name not in mapping:
            declarations.append(pcie.declaration(name,pcie.width(expr,params),'reg' if direction=='input' else 'wire'))
        connections.append(f'.{name}({signal})')
    tb=tb[:start]+'\n'.join(declarations)+'\nrocev2_native_endpoint dut('+','.join(connections)+');\n'+tb[end:]
    tb=tb.replace('dut.responder.','dut.datapath.responder.')
    # The pinned Corundum benches clock two initial unreset cycles before
    # asserting reset. Without that real clocked transition, Icarus can leave
    # zero-initialized register-slice combinational-next signals unevaluated.
    # No RTL initialization/permission/timing rule or DUT state is forced.
    tb=tb.replace('#1 rst=1;','#1 rst=0;repeat(2)@(negedge clk);rst=1;')
    tb=tb.replace('localparam AXIL_ADDR_WIDTH=12;','localparam AXIL_ADDR_WIDTH=24;')
    tb=tb.replace('input [11:0] address;','input [23:0] address;')
    # Only register-address constants acquire a base. IDs/ABI values and word
    # counts remain values, not addresses. This is the same actual C ABI.
    header=pcie.controlled.registers.HEADER.read_text()
    for name,value in re.findall(r'^#define (AS02_CTL_\w+) (0x[0-9a-fA-F]+|\d+)U$',header,re.M):
        if name.endswith(('_VALUE','_WORDS')):continue
        before=f"localparam {name}=32'h{int(value,0):x};"
        after=f"localparam {name}=32'h{0x400000+int(value,0):x};"
        if tb.count(before)!=1:raise ValueError(('control address not unique',name))
        tb=tb.replace(before,after)
    tb=tb.replace('task host_stage;',DECERR+'\ntask host_stage;',1)
    tb=tb.replace(' read_reg(AS02_CTL_ID,host_value);',SETUP+'\n read_reg(AS02_CTL_ID,host_value);',1)
    run=' host_api(7,101,0,0,0,0,0,0,0,0);'
    if tb.count(run)!=1:raise ValueError('RUN setup changed')
    tb=tb.replace(run,run+r'''
 // Stage changes are harmless while running. Unsafe COMMIT must preserve all
 // active route fields/epoch and must not cancel or corrupt the live path.
 write_reg(24'h401020,32'h11223344,15,0,0);write_reg(24'h401010,1,15,0,0);
 read_reg(24'h40100c,host_value);if(host_value!=1 || !ethernet_config_error)$fatal(1,"unsafe config commit was not rejected");
 read_reg(24'h401040,host_value);if(host_value!==32'hfbb97531)$fatal(1,"unsafe commit changed active MAC");
''')
    tb=tb.replace('cycle>50000','cycle>70000')
    for signal in ['awready','wready','bvalid','arready','rvalid']:
        tb=tb.replace(f'while(!s_axil_{signal})',f"while(s_axil_{signal}!==1'b1)")
    for signal in ['bvalid','rvalid']:
        tb=tb.replace(f'if(!s_axil_{signal} ||',f"if(s_axil_{signal}!==1'b1 ||")
    return '\n'.join('`include "'+str(p)+'"' for p in [RTL,CONFIG,*XBAR])+'\n'+tb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve evidence: choose fresh report')
    fixtures,body,cases,ordinary=dual.stimulus()
    body+=r'''
host_api(8,102,0,0,0,0,0,0,0,2);
if(!config_safe)$fatal(1,"STOP did not yield actual safe configuration boundary");
write_reg(24'h401014,1,15,0,0);if(ethernet_config_error)$fatal(1,"safe parser clear failed");
write_reg(24'h401010,1,15,0,0);
read_reg(24'h40100c,host_value);if(host_value!=2 || ethernet_config_error)$fatal(1,"safe reconfiguration epoch");
read_reg(24'h401040,host_value);if(host_value!==32'h11223344)$fatal(1,"atomic safe new MAC");
read_reg(24'h010000,host_value);if(host_value!==32'ha55af0f0)$fatal(1,"new controls aliased old capture RAM");
read_reg(0,host_value);if(host_value!==32'h524f4332)$fatal(1,"old API root changed after new operations");
$display("NATIVE_CONTROL_RESULT {\"pass_test\":true,\"ethernet_epoch\":%0d,\"config_safe\":%0d,\"old_aperture_retained\":true,\"unmapped_read_write_DECERR\":true}",ethernet_epoch,config_safe);
'''
    extra=[RTL,CONFIG,HEADER,*XBAR,dual.TOP,dual.INGRESS,Path(__file__),Path(dual.__file__),
        Path(pcie.__file__),*pcie.PCIE_SOURCES,pcie.controlled.TOP,pcie.controlled.CONTROL,
        *pcie.controlled.registers.SOURCES,pcie.controlled.registers.HEADER,*pcie.controlled.integration.paged.SOURCES,
        Path(pcie.controlled.__file__),Path(pcie.controlled.integration.__file__),Path(dual.probe.__file__),
        Path(pcie.controlled.registers.__file__),ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',ROOT/'rdma/rnic/tests/protected_sim.py']
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    tb=bench().replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=240)
    print(output,flush=True)
    after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if before!=after:raise ValueError('native-control sources changed')
    identity['source_sha256'].update(after)
    rows=[json.loads(l[22:]) for l in output.splitlines() if l.startswith('NATIVE_CONTROL_RESULT ')]
    assert len(rows)==1 and rows[0]['pass_test'] and rows[0]['ethernet_epoch']==2
    wire=dual.probe.rw_sim.ethernet_frames(output)
    good=[c for c in cases if not c.get('expected_error') and not c.get('expected_integrity_drop')]
    assert len(wire)==len(good)==5
    for case,frame in zip(good,wire):
        assert frame[:14]==bytes.fromhex('b8830367c5d08af3fbb975310800')
        assert dual.probe.rocev2_wire.internet_checksum(frame[14:34])==0
        if case['operation']=='read':
            d=dual.probe.read_wire.decode(frame)
            assert d['opcode']==dual.probe.read_wire.ONLY and d['payload']==dual.probe.PAYLOAD and d['syndrome']&0xe0==0
        else:
            d=dual.probe.rocev2_wire.decode_ethernet(frame)
            assert d['opcode']==0x11 and d['icrc_valid'] and d['aeth_syndrome']&0xe0==0
        assert d['psn']==case['psn'] and d['destination_qpn']==196
    rx=dual.frames(output,'HOST_RX');tx=dual.frames(output,'HOST_TX')
    assert len(rx)==len(tx)==1 and rx[0][0]==tx[0][0]==ordinary
    assert all(u==0x0123456789abcdef012345678 for u in rx[0][1])
    assert all(u==0x9234<<1 for u in tx[0][1])
    replies=[l for l in output.splitlines() if l.startswith('HOST_REPLY ')]
    assert len(replies)==21
    report=dict(scope='Actual single AXI native map/crossbar/enforcing Ethernet CSR/same-port protected HLS + mux/PCIe RTL; physical MAC/PCIe/host/AXI MODELS',
        pass_test=True,hardware_verified=False,native_dma_verified=False,board_integrated=False,
        runtime_pins_verified=False,standard_verbs_verified=False,completion_claim=False,
        summary=rows[0],actual_AXI_crossbar=True,raw_Ethernet_config_driven=False,raw_MR_PTE_QP_driven=False,
        control_aperture_decode_integrated=True,privileged_ethernet_configuration_CSR_implemented=True,
        legacy_initiator_READ_WRITE_exercised=False,host_replies=replies,responder_frames_hex=[p.hex() for p in wire],
        write_bytes_checked=130,read_bytes_checked=195,all_host_sidebands_checked=True,**identity)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
