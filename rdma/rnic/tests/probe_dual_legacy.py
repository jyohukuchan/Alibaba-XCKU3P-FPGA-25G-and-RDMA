#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Retain actual original WRITE/READ through the new same-port composition.

One65-byte operation only. Actual new protected responder/mux/PCIe RTL is
present but has no published MR/QP and must issue NO descriptor/TLP. MAC and
remote RNIC are models. This is not native DMA or a full board/timing pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import probe_dual_ethernet as dual

pcie = dual.pcie
ROOT = dual.ROOT
sys.path.insert(0, str(ROOT/'rdma/read/tests'))
import probe_rw_write as write
import probe_rw_read as read
import rw_sim


def attach(tb, hls_build):
    start = tb.index('mqnic_app_block #(')
    end = tb.index('\n);', start)+4
    original = dict(re.findall(r'\.(\w+)\(([^()]*)\)', tb[start:end]))
    mapping = {n.replace('s_axil_app_ctrl_', 's_axil_rw_'): value for n, value in original.items()
               if n.startswith('s_axil_app_ctrl_')}
    mapping.update(clk='clk', rst='rst',
        s_axis_host_tx_tdata="128'd0", s_axis_host_tx_tkeep="16'd0", s_axis_host_tx_tvalid="1'b0",
        s_axis_host_tx_tlast="1'b0", s_axis_host_tx_tuser="17'd0",
        m_axis_mac_tx_tdata='app_tx_data[255:128]', m_axis_mac_tx_tkeep='app_tx_keep[31:16]',
        m_axis_mac_tx_tvalid='app_tx_valid[1]', m_axis_mac_tx_tready='output_ready',
        m_axis_mac_tx_tlast='app_tx_last[1]', s_axis_mac_cpl_tag="16'd0", s_axis_mac_cpl_ts="96'd0",
        s_axis_mac_cpl_valid='model_mac_cpl', s_axis_mac_cpl_ready='app_cpl_ready[1]',
        m_axis_host_cpl_ready="1'b1", s_axis_mac_rx_tdata='input_data', s_axis_mac_rx_tkeep='input_keep',
        s_axis_mac_rx_tvalid='input_valid', s_axis_mac_rx_tready='app_rx_ready[1]',
        s_axis_mac_rx_tlast='input_last', s_axis_mac_rx_tuser="97'd0", m_axis_host_rx_tready="1'b1",
        cfg_ethernet_enable="1'b1", cfg_ethernet_epoch="32'd1", cfg_local_mac="48'h8af3fbb97531",
        cfg_peer_mac="48'hb8830367c5d0", cfg_local_ip="32'hc6120b02",
        parent_dma_drained='actual_parent_idle')
    params = dict(AXIL_RW_ADDR_WIDTH=24, AXIL_RESPONDER_ADDR_WIDTH=12, TX_TAG_WIDTH=16,
                  TS_WIDTH=96, RX_USER_WIDTH=97, RAM_SIZE=8192, RAM_ADDR_WIDTH=15,
                  SEG_COUNT=2, SEG_DATA_WIDTH=256, SEG_BE_WIDTH=32, SEG_ADDR_WIDTH=9,
                  RAM_SEL_WIDTH=1, DMA_LEN_WIDTH=16, DMA_TAG_WIDTH=16)
    declarations = []
    connections = []
    engine_inputs = ('m_dma_read_ready', 'm_dma_write_ready',
        *['s_dma_'+d+'_status_'+f for d in ('read','write') for f in ('tag','error','valid')],
        *['dma_ram_'+f for f in ('wr_cmd_sel','wr_cmd_be','wr_cmd_addr','wr_cmd_data',
                                 'wr_cmd_valid','rd_cmd_sel','rd_cmd_addr','rd_cmd_valid','rd_resp_ready')])
    for direction, expr, name in pcie.ports(dual.TOP):
        signal = mapping.get(name, name)
        if name not in mapping:
            declarations.append(pcie.declaration(name, pcie.width(expr, params),
                'reg' if direction == 'input' and name not in engine_inputs else 'wire'))
        connections.append(f'.{name}({signal})')
    graph = pcie.bundle('mid_',18,3)+'\n'+pcie.bundle('eng_',19,4)+'\n'
    graph += pcie.mux('interface_mux','','mid_',3,2,16,18,1,3)
    graph += pcie.mux('control_data_mux','mid_','eng_',2,1,18,19,3,4)+pcie.engine()
    monitor = r'''
reg parent_error=0;
wire actual_parent_idle=!parent_error && !tlp_status_rd_busy && !tlp_status_wr_busy &&
 !m_dma_read_valid && !m_dma_write_valid && !mid_m_dma_read_valid && !mid_m_dma_write_valid &&
 !eng_m_dma_read_valid && !eng_m_dma_write_valid && !tlp_tx_rd_req_tlp_valid && !tlp_tx_wr_req_tlp_valid &&
 !(|eng_dma_ram_wr_cmd_valid) && !(|eng_dma_ram_rd_cmd_valid) && !(|eng_dma_ram_rd_resp_valid);
always @(posedge clk) if(!rst) begin
 if(tlp_status_error_cor || tlp_status_error_uncor) parent_error<=1;
 if(m_dma_read_valid || m_dma_write_valid || eng_m_dma_read_valid || eng_m_dma_write_valid ||
    tlp_tx_rd_req_tlp_valid || tlp_tx_wr_req_tlp_valid || parent_error || fault)
  $fatal(1,"unconfigured responder exposed DMA/traffic or shared fault");
 if(m_axis_host_cpl_valid || response_pending_frames) $fatal(1,"legacy completion entered wrong role");
end
'''
    instance = '\n'.join(declarations)+'\n'+graph+monitor+'\nrocev2_dual_ethernet_endpoint app('+','.join(connections)+');\n'
    tb = tb[:start]+instance+tb[end:]
    tb = tb.replace('app.endpoint.', 'app.initiator.')
    production, _ = rw_sim.modules(hls_build)
    includes = [dual.TOP, dual.INGRESS, *pcie.PCIE_SOURCES, pcie.controlled.TOP,
        pcie.controlled.CONTROL, *pcie.controlled.registers.SOURCES, *pcie.controlled.integration.paged.SOURCES,
        ROOT/'rdma/rnic/rtl/rocev2_mr_table.v', ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',
        ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v']
    includes = list(dict.fromkeys(p for p in includes if p not in production))
    return '\n'.join('`include "'+str(p)+'"' for p in includes)+'\n'+tb, includes


def write_case():
    ack = bytearray(write.old.CX_ACK)
    ack[47:50]=(2).to_bytes(3,'big');ack[51:54]=(0xfffffe).to_bytes(3,'big')
    ack[54:58]=bytes([0x1f])+(1).to_bytes(3,'big');ack[-4:]=write.old.icrc_ipv4(ack[14:])
    inputs=write.old.words(bytes(ack))
    tasks=write.old.CONTROL_TB[write.old.CONTROL_TB.index('task write_reg;'):write.old.CONTROL_TB.index('\ninitial begin')]
    tb=write.app_boundary.make_tb(write.old.TB.replace('AXIL_TASKS',tasks),'app')
    for name,value in dict(MESSAGE_BYTES=65,MESSAGE_COUNT=1,TOTAL_BYTES=65,
                          INITIAL_PSN=0xfffffe,ACK_WORDS=len(inputs),ACK_FRAMES=1).items():
        tb=tb.replace(name,str(value))
    return tb,{'acks.hex':inputs,'ack_after.hex':[1]},None,0


def read_case(args):
    payload=hashlib.shake_256(b'combined-rw-read/65/1/seed1').digest(65)
    extent=192
    prefill=bytearray(b'\xa5'*extent);expected=bytearray(prefill)
    expected[:65]=payload;prefill[:65]=bytes(b^255 for b in payload)
    wire=read.read_wire.responses(payload,initial_psn=0xfffffe,source_ip='198.18.11.1',
        destination_ip='198.18.11.2',destination_qpn=2,msn=1)
    inputs=[]
    for frame in wire:inputs += read.old.words(frame)
    fixture={'acks.hex':inputs,'ack_after.hex':[1]*len(inputs)}
    for name,data in [('prefill.hex',prefill),('expected.hex',expected)]:
        fixture[name]=[int.from_bytes(data[i:i+4],'little') for i in range(0,extent,4)]
    short=argparse.Namespace(message_bytes=65,count=1,initial_psn=0xfffffe,read_window=1,hls_build=args.hls_build)
    return read.bench(short,extent//4,len(inputs),len(wire)),fixture,payload,extent-65


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--operation',choices=['write','read'],required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve evidence: choose fresh report')
    tb,fixtures,payload,sentinels=read_case(args) if args.operation=='read' else write_case()
    tb,includes=attach(tb,args.hls_build)
    extras=[*includes,Path(__file__),Path(dual.__file__),Path(pcie.__file__),Path(write.__file__),
        Path(read.__file__),Path(write.old.__file__),Path(write.app_boundary.__file__),
        Path(read.read_wire.__file__),ROOT/'rdma/tests/test_control_rtl.py',ROOT/'rdma/host/rocev2_wire.py',
        ROOT/'rdma/tests/test_icrc_rtl.py']
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extras}
    output,identity=rw_sim.simulate(tb,fixtures,args.hls_build,wall_timeout=240)
    print(output,flush=True)
    after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extras}
    if before!=after:raise ValueError('dual legacy probe source changed')
    identity['source_sha256'].update(after)
    frames=rw_sim.ethernet_frames(output)
    assert len(frames)==1 and frames[0][:14]==bytes.fromhex('b8830367c5d08af3fbb975310800')
    frame=frames[0]
    assert write.old.internet_checksum(frame[14:34])==0
    if args.operation=='read':
        d=read.read_wire.decode(frame)
        assert d['opcode']==read.read_wire.REQUEST and d['destination_qpn']==0xabcdef and d['psn']==0xfffffe
        assert d['remote_address']==0xfedcba9876543210 and d['rkey']==0xfedcba98 and d['read_bytes']==65
    else:
        d=write.old.decode_ethernet(frame)
        want=bytes(((i*131)^(i>>8)^0x5a)&255 for i in range(65))
        assert d['opcode']==10 and d['destination_qpn']==0xabcdef and d['psn']==0xfffffe and d['icrc_valid']
        assert d['rkey']=='0xfedcba98' and int(d['remote_address'],0)==0xfedcba9876543210 and frame[70:135]==want
    rows=[json.loads(l[7:]) for l in output.splitlines() if l.startswith('RESULT ')]
    assert len(rows)==1
    if args.operation=='read':assert rows[0]['wire_read_requests']==rows[0]['success_read_completions']==1
    report=dict(scope='Actual original initiator WRITE/READ inside same-port dual Ethernet endpoint; MAC and peer MODELS, real unconfigured responder/mux/PCIe engine present',
        pass_test=True,hardware_verified=False,native_dma_verified=False,board_integrated=False,
        completion_claim=False,operation=args.operation,message_bytes=65,message_count=1,summary=rows[0],
        legacy_wire_frame_hex=frame.hex(),wire_headers_checksums_verified=True,
        capture_payload_bytes_verified=65 if args.operation=='read' else 0,
        capture_sentinel_bytes_verified=sentinels,all_responder_descriptors_and_TLPs_forbidden=True,
        original_initiator_sources_modified=False,control_aperture_decode_integrated=False,**identity)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
