#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched opt-in native duplex routing, keeping the original graph/rollback.

Replace only the existing shared HLS transport and its matched raw-core top.
No second MR table or extra HLS instance, global drain or memory bypass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import derive_qp_tx_bridge as bridge

ROOT=Path(__file__).resolve().parents[3]
ORIGINAL=ROOT/'rdma/rnic/rtl/rocev2_shared_hls_transport.v'
EXTRA=[ROOT/'rdma/rnic/rtl'/n for n in ['rocev2_memory_origin_router.v',
    'rocev2_duplex_rx_mux.v','rocev2_duplex_tx_router.v']]

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('duplex derivation anchor changed: '+old)
    return text.replace(old,new,1)

def memory(direction):
    read=direction=='read'
    return memory_instance(read,'rd'if read else'wr')

def memory_instance(read,prefix):
    p=dict(clk='clk',rst='rst',local_owned='local_role',remote_owned='remote_inflight',
        s_command='h_m_axis_mem_'+('read'if read else'write')+'_cmd_tdata',
        s_command_valid='h_m_axis_mem_'+('read'if read else'write')+'_cmd_tvalid',
        s_command_ready='h_m_axis_mem_'+('read'if read else'write')+'_cmd_tready',
        m_local_command='m_local_'+('read'if read else'write')+'_command',
        m_local_command_valid='m_local_'+('read'if read else'write')+'_command_valid',
        m_local_command_ready='m_local_'+('read'if read else'write')+'_command_ready',
        m_remote_command='m_axis_mem_'+('read'if read else'write')+'_cmd_tdata',
        m_remote_command_valid='m_axis_mem_'+('read'if read else'write')+'_cmd_tvalid',
        m_remote_command_ready='m_axis_mem_'+('read'if read else'write')+'_cmd_tready',
        busy='',local_busy=prefix+'_local_busy',remote_busy=prefix+'_remote_busy',fault=prefix+'_fault',fault_code='')
    for port in ['s_data','s_keep','s_valid','s_last','s_local_data','s_local_keep','s_local_valid','s_local_last',
        's_remote_data','s_remote_keep','s_remote_valid','s_remote_last']:
        p[port]="512'd0"if port.endswith('data')else"64'd0"if port.endswith('keep')else"1'b0"
    for port in ['s_ready','s_local_ready','s_remote_ready','m_local_data','m_local_keep','m_local_valid','m_local_last',
        'm_remote_data','m_remote_keep','m_remote_valid','m_remote_last','m_data','m_keep','m_valid','m_last']:p[port]=''
    for port in ['m_local_ready','m_remote_ready','m_ready']:p[port]="1'b0"
    if read:
        for side,base in [('local','s_local_read'),('remote','s_axis_mem_read')]:
            for port,suffix in [('data','tdata'),('keep','tkeep'),('valid','tvalid'),('ready','tready'),('last','tlast')]:
                p['s_'+side+'_'+port]=base+'_'+suffix
        for port,suffix in [('data','tdata'),('keep','tkeep'),('valid','tvalid'),('ready','tready'),('last','tlast')]:
            p['m_'+port]='h_s_axis_mem_read_'+suffix
    else:
        for port,suffix in [('data','tdata'),('keep','tkeep'),('valid','tvalid'),('ready','tready'),('last','tlast')]:
            p['s_'+port]='h_m_axis_mem_write_'+suffix
        for side,base in [('local','m_local_write'),('remote','m_axis_mem_write')]:
            for port,suffix in [('data','tdata'),('keep','tkeep'),('valid','tvalid'),('ready','tready'),('last','tlast')]:
                p['m_'+side+'_'+port]=base+'_'+suffix
    return 'rocev2_memory_origin_router #(.READ_RETURN('+str(int(read))+')) '+prefix+'_origin(\n'+',\n'.join('.'+n+'('+v+')'for n,v in p.items())+'\n);\n'

ROUTING=r'''
wire remote_inflight=remote_operation_idle===1'b0 || remote_receive_held===1'b1 || recv_held || rnr_pending || recv_owner_pending;
wire rd_fault,wr_fault,tx_route_fault;
wire rd_local_busy,wr_local_busy,rd_remote_busy,wr_remote_busy,tx_local_busy,tx_remote_busy;
wire local_rx_ready;
rocev2_duplex_rx_mux rx_packets(
 .clk(clk),.rst(rst),
 .s_local_data(s_local_rx_tdata),.s_local_keep(s_local_rx_tkeep),.s_local_valid(s_local_rx_tvalid && local_role),
 .s_local_ready(local_rx_ready),.s_local_last(s_local_rx_tlast),.s_local_user(s_local_rx_tuser),
 .s_remote_data(s_axis_rx_tdata),.s_remote_keep(s_axis_rx_tkeep),.s_remote_valid(s_axis_rx_tvalid),
 .s_remote_ready(s_axis_rx_tready),.s_remote_last(s_axis_rx_tlast),.s_remote_user(s_axis_rx_tuser),
 .m_data(h_s_axis_rx_tdata),.m_keep(h_s_axis_rx_tkeep),.m_valid(h_s_axis_rx_tvalid),.m_ready(h_s_axis_rx_tready),
 .m_last(h_s_axis_rx_tlast),.m_user(h_s_axis_rx_tuser),.busy()
);
assign s_local_rx_tready=local_rx_ready && local_role;
rocev2_duplex_tx_router tx_packets(
 .clk(clk),.rst(rst),.local_owned(local_role),.remote_owned(remote_inflight),
 .s_data(h_m_axis_tx_tdata),.s_keep(h_m_axis_tx_tkeep),.s_valid(h_m_axis_tx_tvalid),.s_ready(h_m_axis_tx_tready),.s_last(h_m_axis_tx_tlast),
 .m_local_data(m_local_tx_tdata),.m_local_keep(m_local_tx_tkeep),.m_local_valid(m_local_tx_tvalid),.m_local_ready(m_local_tx_tready),.m_local_last(m_local_tx_tlast),
 .m_remote_data(m_axis_tx_tdata),.m_remote_keep(m_axis_tx_tkeep),.m_remote_valid(m_axis_tx_tvalid),.m_remote_ready(m_axis_tx_tready),.m_remote_last(m_axis_tx_tlast),
 .local_busy(tx_local_busy),.remote_busy(tx_remote_busy),.fault(tx_route_fault)
);
assign s_axis_sq_tready=1'b0;
assign m_axis_ack_tdata=h_m_axis_ack_tdata;assign m_axis_ack_tvalid=1'b0;
assign m_local_ack_tdata=h_m_axis_ack_tdata;assign m_local_ack_tvalid=h_m_axis_ack_tvalid && local_role;
assign h_m_axis_ack_tready=m_local_ack_tready && local_role;
'''

def derive():
    text=ORIGINAL.read_text()
    text=once(text,'wire local_role=role==LOCAL,remote_role=role==REMOTE;',
        'wire local_role=role==LOCAL,remote_role=1\'b1;\n'
        'initial if(!REQUEST_CQ_ENABLE)$fatal(1,"duplex requires matched full request/receive receipt profile");')
    start=text.index('assign h_s_axis_rx_tdata=')
    end=text.index('wire bad_owner=',start)
    text=text[:start]+ROUTING+memory('read')+memory('write')+r'''
wire core_offers=rd_local_busy || wr_local_busy || tx_local_busy || h_m_axis_ack_tvalid;
wire remote_core_offers=rd_remote_busy || wr_remote_busy || tx_remote_busy;
wire routing_fault=rd_fault || wr_fault || tx_route_fault || (h_m_axis_ack_tvalid && !local_role);
'''+text[end:]
    text=once(text,'wire incoming_fault=bad_owner','wire incoming_fault=routing_fault || bad_owner')
    text=once(text,'(trusted_local_ready===1\'b1) && !rnr_pending && !recv_owner_pending && (!s_axis_rx_tvalid || !last_local);',
        '(trusted_local_ready===1\'b1);')
    text=once(text,'s_recv_retire_context===recv_owner[587:0] && remote_operation_idle===1\'b1 &&\n    !core_offers',
        's_recv_retire_context===recv_owner[587:0] && remote_operation_idle===1\'b1 &&\n    !remote_core_offers')
    text=once(text,'            end else if(rnr_pending || recv_owner_pending || (s_axis_rx_tvalid && (!s_local_owner_valid || last_local)))role<=REMOTE;',
        '            end')
    start=text.index('        if(remote_role && remote_operation_idle===1\'b1')
    end=text.index('\n        end',start)+len('\n        end')
    text=text[:start]+text[end:]
    text=once(text,'recv_held<=0;recv_proved<=0;recv_owner<=0;role<=NONE;last_local<=0;',
        'recv_held<=0;recv_proved<=0;recv_owner<=0;')
    text='// Matched duplex variant: independent request/response ownership; same core/MR.\n'+text
    return text

def derive_bridge():
    return once(bridge.derive(),'rocev2_native_request_top transport (','rocev2_native_duplex_top transport (')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous generated RTL')
    a.output.mkdir(parents=True)
    (a.output/'shared_hls.v').write_text(derive());(a.output/'qp_bridge.v').write_text(derive_bridge())
    info=dict(scope=__doc__,source_sha256={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()
        for x in [ORIGINAL,*EXTRA,Path(__file__).resolve(),Path(bridge.__file__).resolve(),
            Path(bridge.legacy.__file__).resolve(),bridge.legacy.BRIDGE]},
        original_unchanged=True,third_HLS_core_added=False,second_MR_table_added=False,
        extra_RTL=[str(x.relative_to(ROOT))for x in EXTRA],source_only=True,hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),original_unchanged=True,third_HLS_core_added=False)))

if __name__=='__main__':main()
