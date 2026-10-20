#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual same-port Ethernet/initiator/protected responder/mux/PCIe RTL.

MAC completions, host AXI, privileged stable Ethernet configuration and PCIe
hard-IP/link/root-complex/host memory remain MODELS. Not a native board pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import probe_controlled_pcie as pcie
from protected_sim import simulate

ROOT = pcie.ROOT
TOP = ROOT/'rdma/rnic/rtl/rocev2_dual_ethernet_endpoint.v'
INGRESS = ROOT/'rdma/rnic/rtl/rocev2_responder_ethernet_rx.v'
probe = pcie.probe

MAC_MODEL = r'''
reg [15:0] mac_cpl_tags[0:31];integer mac_cpl_due[0:31];
integer mac_cpl_wr=0,mac_cpl_rd=0,mac_response_cpls=0,mac_host_cpls=0;
integer host_rx_frames=0,host_tx_frames=0,host_cpl_frames=0;
reg mac_in_frame=0;
reg [16:0] mac_frame_user=0;
reg [96:0] mac_rx_user=0;
wire [127:0] mac_tx_data;
wire [15:0] mac_tx_keep;
wire mac_tx_valid,mac_tx_last;
wire [16:0] mac_tx_user;
assign td=mac_tx_data;assign tk=mac_tx_keep;assign tl=mac_tx_last;
assign tv=mac_tx_valid && mac_tx_user[16:1]==16'h4000;
always @(posedge clk) if(!rst) begin
 if(mac_tx_valid && tr) begin
  if(!mac_in_frame) begin
   mac_frame_user=mac_tx_user;
   if(mac_cpl_wr-mac_cpl_rd>=32) $fatal(1,"MAC completion model queue full");
   mac_cpl_tags[mac_cpl_wr%32]=mac_tx_user[16:1];mac_cpl_due[mac_cpl_wr%32]=cycle+17;mac_cpl_wr=mac_cpl_wr+1;
  end else if(mac_tx_user!==mac_frame_user) $fatal(1,"mixed packet completion tags");
  mac_in_frame=!mac_tx_last;
  if(mac_tx_user[16]) begin
   $display("HOST_TX %h %h %b %h",mac_tx_data,mac_tx_keep,mac_tx_last,mac_tx_user);
   if(mac_tx_last)host_tx_frames=host_tx_frames+1;
  end else if(mac_tx_user[16:1]!=16'h4000) $fatal(1,"unexpected legacy TX in responder-only phase");
 end
 if(m_axis_host_rx_tvalid && m_axis_host_rx_tready) begin
  $display("HOST_RX %h %h %b %h",m_axis_host_rx_tdata,m_axis_host_rx_tkeep,m_axis_host_rx_tlast,m_axis_host_rx_tuser);
  if(m_axis_host_rx_tlast)host_rx_frames=host_rx_frames+1;
 end
 if(m_axis_host_cpl_valid && m_axis_host_cpl_ready) begin
  if(m_axis_host_cpl_tag!=16'h9234 || m_axis_host_cpl_ts!=96'h123456789abcdef) $fatal(1,"wrong/aliased host completion");
  host_cpl_frames=host_cpl_frames+1;
 end
end
always @(negedge clk) if(!rst) begin
 if(s_axis_mac_cpl_valid && !s_axis_mac_cpl_ready) begin end
 else begin
  s_axis_mac_cpl_valid=0;
  if(mac_cpl_rd<mac_cpl_wr && cycle>=mac_cpl_due[mac_cpl_rd%32]) begin
   s_axis_mac_cpl_tag=mac_cpl_tags[mac_cpl_rd%32];s_axis_mac_cpl_ts=96'h123456789abcdef;s_axis_mac_cpl_valid=1;
   if(s_axis_mac_cpl_tag==16'h4000)mac_response_cpls=mac_response_cpls+1;
   else if(s_axis_mac_cpl_tag[15])mac_host_cpls=mac_host_cpls+1;
   mac_cpl_rd=mac_cpl_rd+1;
  end
 end
 m_axis_host_rx_tready=rng[14:12]!=0;
end
task send_host_frame;
 input integer start,count;
 integer j;
 begin
  for(j=start;j<start+count;j=j+1) begin
   @(negedge clk);{s_axis_host_tx_tlast,s_axis_host_tx_tkeep,s_axis_host_tx_tdata}=stimulus[j];
   s_axis_host_tx_tuser={16'h9234,1'b0};s_axis_host_tx_tvalid=1;
   @(posedge clk);while(!s_axis_host_tx_tready) @(posedge clk);
  end
  @(negedge clk);s_axis_host_tx_tvalid=0;
 end
endtask
'''


def bench():
    tb = pcie.bench()
    start = tb.index('rocev2_controlled_responder #(')
    end = tb.index(');', start)+2
    old = dict(re.findall(r'\.(\w+)\(([^()]*)\)', tb[start:end]))
    mapping = {name.replace('s_axil_', 's_axil_responder_', 1) if name.startswith('s_axil_') else name: sig
               for name, sig in old.items()}
    for name in list(mapping):
        if name.startswith(('s_axis_rx_', 'm_axis_tx_')):
            del mapping[name]
    mapping.update(dict(
        s_axis_mac_rx_tdata='id', s_axis_mac_rx_tkeep='ik', s_axis_mac_rx_tvalid='iv',
        s_axis_mac_rx_tready='ir', s_axis_mac_rx_tlast='il', s_axis_mac_rx_tuser='mac_rx_user',
        m_axis_mac_tx_tdata='mac_tx_data', m_axis_mac_tx_tkeep='mac_tx_keep', m_axis_mac_tx_tvalid='mac_tx_valid',
        m_axis_mac_tx_tready='tr', m_axis_mac_tx_tlast='mac_tx_last', m_axis_mac_tx_tuser='mac_tx_user',
        cfg_ethernet_enable="1'b1", cfg_ethernet_epoch="32'd1", cfg_local_mac="48'h8af3fbb97531",
        cfg_peer_mac="48'hb8830367c5d0", cfg_local_ip="32'hc6120b02"))
    params = dict(AXIL_RW_ADDR_WIDTH=24, AXIL_RESPONDER_ADDR_WIDTH=12, TX_TAG_WIDTH=16,
                  TS_WIDTH=96, RX_USER_WIDTH=97, RAM_SIZE=8192, RAM_ADDR_WIDTH=15,
                  SEG_COUNT=2, SEG_DATA_WIDTH=256, SEG_BE_WIDTH=32, SEG_ADDR_WIDTH=9,
                  RAM_SEL_WIDTH=1, DMA_LEN_WIDTH=16, DMA_TAG_WIDTH=16)
    declarations = []
    connections = []
    for direction, expr, name in pcie.ports(TOP):
        signal = mapping.get(name, name)
        if name not in mapping:
            declarations.append(pcie.declaration(name, pcie.width(expr, params), 'reg' if direction == 'input' else 'wire'))
        connections.append(f'.{name}({signal})')
    instance = '\n'.join(declarations) + '\nrocev2_dual_ethernet_endpoint dut(' + ','.join(connections) + ');\n'
    tb = tb[:start] + instance + tb[end:]
    tb = tb.replace('dut.endpoint.', 'dut.responder.endpoint.')
    # No request-side config is externally driven; aliases only observe actual
    # connections through the protected responder, as in the earlier probe.
    tb = tb.replace('reg [144:0] stimulus', MAC_MODEL+'\nreg [144:0] stimulus', 1)
    tb = tb.replace(' repeat(4100) @(negedge clk);', '''
 m_axis_host_rx_tready=1;m_axis_host_cpl_ready=1;
 repeat(4100) @(negedge clk);
''')
    tb = tb.replace('while(completed==completed_before && cycle<expiry)',
                    'while((completed==completed_before || !quiet) && cycle<expiry)')
    tb = tb.replace('expiry=cycle+2000;while', 'expiry=cycle+4000;while')
    tb = tb.replace('cycle>35000', 'cycle>50000')
    tb = tb.replace(' if(!parent_dma_drained || engine_error', '''
 if(mac_response_cpls!=5 || mac_host_cpls!=1 || host_rx_frames!=1 || host_tx_frames!=1 || host_cpl_frames!=1 || !response_tx_quiescent)
  $fatal(1,"Ethernet roles/completion/drain coverage rx%0d tx%0d hcpl%0d rcpl%0d",host_rx_frames,host_tx_frames,host_cpl_frames,mac_response_cpls);
 $display("ETH_RESULT {\\"pass_test\\":true,\\"host_rx_frames\\":%0d,\\"host_tx_frames\\":%0d,\\"host_completions\\":%0d,\\"responder_completions\\":%0d}",host_rx_frames,host_tx_frames,host_cpl_frames,mac_response_cpls);
 if(!parent_dma_drained || engine_error''', 1)
    return '\n'.join('`include "'+str(p)+'"' for p in [TOP, INGRESS]) + '\n' + tb


def stimulus():
    old, body, cases = pcie.stimulus()
    frames = []
    packet = bytearray()
    start = 0
    mapping = {}
    fixtures = []
    for index, word in enumerate(old):
        data = (word & ((1<<128)-1)).to_bytes(16, 'little')
        packet += bytes(data[i] for i in range(16) if (word>>128)&(1<<i))
        if word & (1<<144):
            ethernet = bytes.fromhex('8af3fbb97531b8830367c5d00800') + packet
            parts = probe.words(ethernet)
            mapping[start, index-start+1] = len(fixtures), len(parts)
            fixtures += parts
            start = index+1
            packet.clear()
    assert not packet
    def replace_send(match):
        begin, count = map(int, match.groups())
        begin, count = mapping[begin, count]
        return f'send_frame({begin},{count})'
    body = re.sub(r'send_frame\((\d+),(\d+)\)', replace_send, body)
    ordinary = bytes.fromhex('8af3fbb97531b8830367c5d088b5') + bytes((i*17+3)&255 for i in range(50))
    ordinary_start = len(fixtures)
    parts = probe.words(ordinary)
    fixtures += parts
    body += f'''
mac_rx_user=97'h0123456789abcdef012345678;
send_frame({ordinary_start},{len(parts)});
expiry=cycle+1000;while((host_rx_frames!=1 || !quiet) && cycle<expiry) @(negedge clk);
if(host_rx_frames!=1 || !quiet || commands!=5 || completed!=5) $fatal(1,"ordinary RX touched protected memory");
send_host_frame({ordinary_start},{len(parts)});
expiry=cycle+1000;while((host_cpl_frames!=1 || host_tx_frames!=1) && cycle<expiry) @(negedge clk);
if(host_cpl_frames!=1 || host_tx_frames!=1) $fatal(1,"ordinary host TX/completion lost");
repeat(20) @(negedge clk);
'''
    return fixtures, body, cases, ordinary


def frames(output, prefix):
    result = []
    packet = bytearray()
    users = []
    for line in output.splitlines():
        if line.startswith(prefix+' '):
            _, data, keep, last, user = line.split()
            data = int(data, 16).to_bytes(16, 'little')
            packet.extend(data[i] for i in range(16) if int(keep, 16)&(1<<i))
            users.append(int(user, 16))
            if last == '1':
                result.append((bytes(packet), users))
                packet.clear();users = []
    assert not packet
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence: choose fresh report')
    extras = [TOP, INGRESS, Path(__file__), Path(pcie.__file__), *pcie.PCIE_SOURCES,
        pcie.controlled.TOP, pcie.controlled.CONTROL, *pcie.controlled.registers.SOURCES,
        pcie.controlled.registers.HEADER, *pcie.controlled.integration.paged.SOURCES,
        Path(pcie.controlled.__file__), Path(pcie.controlled.integration.__file__), Path(probe.__file__),
        Path(pcie.controlled.registers.__file__), ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',
        ROOT/'rdma/rnic/tests/protected_sim.py']
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in extras}
    fixtures, body, cases, ordinary = stimulus()
    tb = bench().replace('STIMULUS_LAST', str(len(fixtures)-1)).replace('// TEST_BODY', body)
    output, identity = simulate(tb, {'input.hex': fixtures}, args.hls_build, wall_timeout=240)
    print(output, flush=True)
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in extras}
    if before != after:
        raise ValueError('same-port probe sources changed')
    identity['source_sha256'].update(after)
    summaries = [json.loads(l[11:]) for l in output.splitlines() if l.startswith('ETH_RESULT ')]
    assert len(summaries) == 1 and summaries[0]['pass_test']
    wire = probe.rw_sim.ethernet_frames(output)
    good = [c for c in cases if not c.get('expected_error') and not c.get('expected_integrity_drop')]
    assert len(wire) == len(good) == 5
    for case, frame in zip(good, wire):
        assert frame[:14] == bytes.fromhex('b8830367c5d08af3fbb975310800')
        assert probe.rocev2_wire.internet_checksum(frame[14:34]) == 0
        if case['operation'] == 'read':
            d = probe.read_wire.decode(frame)
            assert d['opcode'] == probe.read_wire.ONLY and d['payload'] == probe.PAYLOAD and d['syndrome']&0xe0 == 0
        else:
            d = probe.rocev2_wire.decode_ethernet(frame)
            assert d['opcode'] == 0x11 and d['icrc_valid'] and d['aeth_syndrome']&0xe0 == 0
        assert d['psn'] == case['psn'] and d['destination_qpn'] == 196
    host_rx = frames(output, 'HOST_RX');host_tx = frames(output, 'HOST_TX')
    assert len(host_rx) == len(host_tx) == 1 and host_rx[0][0] == host_tx[0][0] == ordinary
    assert all(u == 0x0123456789abcdef012345678 for u in host_rx[0][1])
    assert all(u == (0x9234<<1) for u in host_tx[0][1])
    report = dict(scope='Actual same-port Ethernet steering/unchanged initiator/protected responder + native-shape mux/generic PCIe RTL; physical MAC/PCIe/host/config MODELS',
        pass_test=True, hardware_verified=False, native_dma_verified=False, board_integrated=False,
        standard_verbs_verified=False, completion_claim=False, legacy_initiator_instantiated=True,
        legacy_initiator_READ_WRITE_exercised=False, control_aperture_decode_integrated=False,
        privileged_ethernet_configuration_CSR_implemented=False, ethernet_summary=summaries[0],
        responder_frames_hex=[f.hex() for f in wire], ordinary_host_frame_hex=ordinary.hex(),
        all_host_sidebands_checked=True, write_bytes_checked=130, read_bytes_checked=195, **identity)
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
