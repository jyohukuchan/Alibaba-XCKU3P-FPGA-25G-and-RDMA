# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact opt-in shared-HLS derivative; original responder/rollback are untouched.

Only replace the existing transport instance, expose its local role ports,
and include that hardware owner's guard/fault in the ORIGINAL protection.
No new MR table, parser, integrity waiver or new/third HLS core is added.
"""
import argparse
import hashlib
import json
from pathlib import Path
import importlib.util
_recv_spec=importlib.util.spec_from_file_location('as02_recv_derivative',Path(__file__).with_name('derive_recv_responder.py'))
recv=importlib.util.module_from_spec(_recv_spec);_recv_spec.loader.exec_module(recv)

ROOT=Path(__file__).resolve().parents[3]
ORIGINAL=ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v'
SHARED=ROOT/'rdma/rnic/rtl/rocev2_shared_hls_transport.v'
LOCAL_PORTS = "    input wire [587:0] s_local_owner_context,\n    input wire s_local_owner_valid,\n    output wire s_local_owner_ready,\n    input wire [247:0] s_local_sq_tdata,\n    input wire s_local_sq_tvalid,\n    output wire s_local_sq_tready,\n    input wire [127:0] s_local_rx_tdata,\n    input wire [15:0] s_local_rx_tkeep,\n    input wire s_local_rx_tvalid,\n    output wire s_local_rx_tready,\n    input wire s_local_rx_tlast,\n    input wire s_local_rx_tuser,\n    output wire [127:0] m_local_tx_tdata,\n    output wire [15:0] m_local_tx_tkeep,\n    output wire m_local_tx_tvalid,\n    input wire m_local_tx_tready,\n    output wire m_local_tx_tlast,\n    output wire [39:0] m_local_ack_tdata,\n    output wire m_local_ack_tvalid,\n    input wire m_local_ack_tready,\n    output wire [95:0] m_local_write_command,\n    output wire m_local_write_command_valid,\n    input wire m_local_write_command_ready,\n    output wire [511:0] m_local_write_tdata,\n    output wire [63:0] m_local_write_tkeep,\n    output wire m_local_write_tvalid,\n    input wire m_local_write_tready,\n    output wire m_local_write_tlast,\n    output wire [95:0] m_local_read_command,\n    output wire m_local_read_command_valid,\n    input wire m_local_read_command_ready,\n    input wire [511:0] s_local_read_tdata,\n    input wire [63:0] s_local_read_tkeep,\n    input wire s_local_read_tvalid,\n    output wire s_local_read_tready,\n    input wire s_local_read_tlast,\n    input wire [587:0] s_local_retire_context,\n    input wire s_local_retire_valid,\n    output wire s_local_retire_ready,\n    input wire local_core_drained,\n    output wire [7:0] local_hls_queue_guard,\n    output wire local_hls_active,\n    output wire shared_hls_fault,\n    output wire [7:0] shared_hls_fault_code"


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('source derivation anchor changed: '+old)
    return text.replace(old,new,1)


def derive(text):
    text=once(text,'module rocev2_protected_responder #(','module rocev2_shared_protected_responder #(')
    text=once(text,'    parameter LOCAL_WQE_ENABLE=0','    parameter QP_TX_ENABLE=0,\n    parameter EXTERNAL_REPLAY_ENABLE=0,\n    parameter LOCAL_WQE_ENABLE=0')
    text=once(text,'    input wire [23:0] cfg_tx_psn,','    input wire [23:0] cfg_tx_psn,\n    input wire cfg_qp_tx_only,')
    text=once(text,'wire config_busy=qp_pending || conn_pending;',r'''
reg qp_apply_pending=0,qp_tx_only_pending=0;
wire [79:0] qp_apply_data;
wire qp_apply_valid;
wire qp_apply_match=(^qp_apply_data)!==1'bx && qp_apply_data[23:0]==local_qpn &&
    qp_apply_data[47:24]==tx_psn && qp_apply_data[71:48]==expected_psn &&
    qp_apply_data[79:72]==(qp_tx_only_pending ? 8'd3 : 8'd1);
wire qp_apply_bad=QP_TX_ENABLE && qp_apply_valid && (!qp_apply_pending || !qp_apply_match);
wire config_busy=qp_pending || conn_pending || (QP_TX_ENABLE && qp_apply_pending);
''')
    text=once(text,'    .s_axis_qp_tdata({32\'d0,48\'d0,expected_psn,tx_psn,local_qpn,32\'d3}),',
        "    .s_axis_qp_tdata({32'd0,(QP_TX_ENABLE && qp_tx_only_pending ? 48'h415332545850 : 48'd0),expected_psn,tx_psn,local_qpn,32'd3}),")
    text=once(text,'        startup_count<=0;context_valid<=0;qp_pending<=0;conn_pending<=0;',
        '        startup_count<=0;context_valid<=0;qp_pending<=0;conn_pending<=0;qp_apply_pending<=0;qp_tx_only_pending<=0;')
    text=once(text,'''        if(cfg_qp_valid && cfg_qp_ready) begin
            context_valid<=1;qp_pending<=1;conn_pending<=1;
            local_qpn<={21'd0,cfg_qp_number};peer_qpn<=cfg_peer_qp_number;trusted_pd<=cfg_qp_pd;
            local_ip<=cfg_local_ip;peer_ip<=cfg_peer_ip;expected_psn<=cfg_rx_psn;tx_psn<=cfg_tx_psn;
        end''',r'''
        if(QP_TX_ENABLE && qp_apply_valid && qp_apply_pending && qp_apply_match)qp_apply_pending<=0;
        if(cfg_qp_valid && cfg_qp_ready) begin
            qp_pending<=1;tx_psn<=cfg_tx_psn;
            qp_apply_pending<=QP_TX_ENABLE;
            qp_tx_only_pending<=QP_TX_ENABLE && cfg_qp_tx_only;
            if(!QP_TX_ENABLE || !cfg_qp_tx_only)begin
                context_valid<=1;conn_pending<=1;
                local_qpn<={21'd0,cfg_qp_number};peer_qpn<=cfg_peer_qp_number;trusted_pd<=cfg_qp_pd;
                local_ip<=cfg_local_ip;peer_ip<=cfg_peer_ip;expected_psn<=cfg_rx_psn;
            end
        end''')
    text=once(text,'    output reg [31:0] rx_integrity_drop_count=0\n);',
        '    output reg [31:0] rx_integrity_drop_count=0,\n'+LOCAL_PORTS+'\n);')
    text=once(text,'local_work_guard || s_local_mr_request_valid',
        'local_work_guard || (|local_hls_queue_guard) || s_local_mr_request_valid')
    start=text.index('rocev2_integrity_transport transport (')
    end=text.index(');',start)+2
    block=text[start:end]
    block=once(block,'rocev2_integrity_transport transport (','rocev2_shared_hls_transport #(.QP_TX_ENABLE(QP_TX_ENABLE),.EXTERNAL_REPLAY_ENABLE(EXTERNAL_REPLAY_ENABLE)) transport (')
    import re
    ports=re.findall(r'\b(?:input|output) wire (?:\[[^]]+\] )?(\w+)',LOCAL_PORTS)
    extra=',\n'.join('.'+n+'('+n+')'for n in ports)
    block=once(block,'.clk(clk),.rst(rst),',
        '.clk(clk),.rst(rst),\n    .trusted_local_qpn(local_qpn),.trusted_local_ready(local_configuration_idle),\n'
        '    .remote_operation_idle(state==COLLECT && word_count==0 && !lease && !config_busy && !m_reject_valid),\n'
        '    .m_axis_qp_apply_tdata(qp_apply_data),.m_axis_qp_apply_tvalid(qp_apply_valid),.m_axis_qp_apply_tready(1\'b1),\n'
        '    '+extra+',')
    text=text[:start]+block+text[end:]
    text=once(text,'if(core_rx_bad!=0 || core_tx_bad!=0 || core_overflow!=0 ||',
        'if(core_rx_bad!=0 || core_tx_bad!=0 || core_overflow!=0 || shared_hls_fault || qp_apply_bad ||')
    text=once(text,'localparam COLLECT=0,',
        'initial if(!LOCAL_WQE_ENABLE)$fatal(1,"shared transport requires SAME local MR protection");\nlocalparam COLLECT=0,')
    return recv.derive(text)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():p.error('preserve existing generated source')
    text=derive(ORIGINAL.read_text());a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x')as out:out.write(text)
    print(json.dumps(dict(source=str(ORIGINAL),source_sha256=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        derived=str(a.output),derived_sha256=hashlib.sha256(text.encode()).hexdigest(),
        original_unchanged=True,additional_HLS_instances=0)))


if __name__=='__main__':main()
