# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in full integrity bridge around the new state-readback HLS core.

The old released/frozen bridge is not changed. No CRC/padding/MR bypass.
"""
from pathlib import Path
import prepare_wrkey_transport as legacy

def derive():
    text=legacy.derive_bridge(legacy.BRIDGE.read_text())
    changes=[
        ('module rocev2_integrity_transport #','module rocev2_qptx_integrity_transport #'),
        ('    input wire rst,','    input wire rst,\n'
         '    output wire [79:0] m_axis_qp_apply_tdata,\n'
         '    output wire m_axis_qp_apply_tvalid,\n'
         '    input wire m_axis_qp_apply_tready,'),
        ('rocev2_top transport (','rocev2_qptx_top transport (\n'
         '    .m_axis_qp_apply_TDATA(m_axis_qp_apply_tdata),\n'
         '    .m_axis_qp_apply_TVALID(m_axis_qp_apply_tvalid),\n'
         '    .m_axis_qp_apply_TREADY(m_axis_qp_apply_tready),')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('QP TX bridge anchor changed: '+old)
        text=text.replace(old,new,1)
    text=text.replace('parameter LEGACY_QP_KEY = 1','parameter LEGACY_QP_KEY = 1, parameter EXTERNAL_REPLAY_ENABLE = 0, parameter RNR_ENABLE = 0, parameter RECV_RETIRE_ENABLE = 0, parameter REQUEST_CQ_ENABLE = 0')
    text=text.replace('    input wire rst,','    input wire rst,\n'
        '    input wire [55:0] s_rnr_event_tdata,\n'
        '    input wire s_rnr_event_tvalid,\n'
        '    output wire s_rnr_event_tready,\n'
        '    output wire rnr_fault,\n'
        '    input wire [647:0] s_recv_owner_tdata,input wire s_recv_owner_tvalid,output wire s_recv_owner_tready,\n'
        '    output wire [679:0] m_recv_done_tdata,output wire m_recv_done_tvalid,input wire m_recv_done_tready,\n'
        '    output wire recv_fault,\n'
        '    input wire [587:0] s_request_owner_tdata,input wire s_request_owner_tvalid,output wire s_request_owner_tready,\n'
        '    output wire [655:0] m_request_done_tdata,output wire m_request_done_tvalid,input wire m_request_done_tready,\n'
        '    output wire request_fault,',1)
    start=text.index('rocev2_qptx_top transport (');end=text.index(');',start)+2
    instance=text[start:end]
    rnr=instance.replace('rocev2_qptx_top transport (',
        'rocev2_native_rnr_top transport (\n'
        '    .s_axis_rnr_event_TDATA(s_rnr_event_tdata),\n'
        '    .s_axis_rnr_event_TVALID(s_rnr_event_tvalid),\n'
        '    .s_axis_rnr_event_TREADY(s_rnr_event_tready),\n'
        '    .regRnrFault(rnr_fault),')
    recv=rnr.replace('rocev2_native_rnr_top transport (',
        'rocev2_native_recv_top transport (\n'
        '    .s_axis_recv_owner_TDATA(s_recv_owner_tdata),.s_axis_recv_owner_TVALID(s_recv_owner_tvalid),.s_axis_recv_owner_TREADY(s_recv_owner_tready),\n'
        '    .m_axis_recv_done_TDATA(m_recv_done_tdata),.m_axis_recv_done_TVALID(m_recv_done_tvalid),.m_axis_recv_done_TREADY(m_recv_done_tready),\n'
        '    .regRecvFault(recv_fault),')
    idle='assign s_recv_owner_tready=0;assign m_recv_done_tdata=0;assign m_recv_done_tvalid=0;assign recv_fault=0;\n'
    request=recv.replace('rocev2_native_recv_top transport (',
        'rocev2_native_request_top transport (\n'
        '    .s_axis_request_owner_TDATA({4\'d0,s_request_owner_tdata}),.s_axis_request_owner_TVALID(s_request_owner_tvalid),.s_axis_request_owner_TREADY(s_request_owner_tready),\n'
        '    .m_axis_request_done_TDATA(m_request_done_tdata),.m_axis_request_done_TVALID(m_request_done_tvalid),.m_axis_request_done_TREADY(m_request_done_tready),\n'
        '    .regRequestFault(request_fault),')
    request_idle='assign s_request_owner_tready=0;assign m_request_done_tdata=0;assign m_request_done_tvalid=0;assign request_fault=0;\n'
    replacement='generate if(REQUEST_CQ_ENABLE)begin : native_request_core\n'+request+\
        '\nend else if(RECV_RETIRE_ENABLE)begin : native_recv_core\n'+request_idle+recv+\
        '\nend else if(RNR_ENABLE)begin : native_rnr_core\n'+idle+rnr+\
        '\nend else if(EXTERNAL_REPLAY_ENABLE)begin : native_replay_core\nassign s_rnr_event_tready=0;assign rnr_fault=0;\n'+instance.replace(
        'rocev2_qptx_top transport (','rocev2_native_replay_top transport (')+\
        '\nend else begin : normal_qptx_core\nassign s_rnr_event_tready=0;assign rnr_fault=0;\n'+instance+'\nend endgenerate'
    replacement=replacement.replace('begin : native_replay_core\n','begin : native_replay_core\n'+idle)
    replacement=replacement.replace('begin : normal_qptx_core\n','begin : normal_qptx_core\n'+idle)
    for branch in ['native_rnr_core','native_replay_core','normal_qptx_core']:
        replacement=replacement.replace('begin : '+branch+'\n','begin : '+branch+'\n'+request_idle)
    text=text[:start]+replacement+text[end:]
    return text
