# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched complete Immediate HLS integrity bridge; not native graph selection.

Full280-bit SQ arrives from actual typed owner staging, never an old side-key
adapter. Preserve actual RX/TX width adapters, padding, checksum and ICRC.
"""
import derive_duplex_transport as parent

once=parent.once

def derive():
    text=parent.derive_bridge()
    text=once(text,'module rocev2_qptx_integrity_transport #','module rocev2_immediate_integrity_transport #')
    for a,b in [('input wire [647:0] s_recv_owner_tdata','input wire [679:0] s_recv_owner_tdata'),
                ('output wire [679:0] m_recv_done_tdata','output wire [751:0] m_recv_done_tdata'),
                ('input wire [587:0] s_request_owner_tdata','input wire [619:0] s_request_owner_tdata'),
                ('output wire [655:0] m_request_done_tdata','output wire [687:0] m_request_done_tdata'),
                ('input wire [239:0] s_axis_sq_tdata','input wire [279:0] s_axis_sq_tdata'),
                ('    input wire [31:0] s_axis_sq_rkey,\n','')]:text=once(text,a,b)
    start=text.index('wire [247:0] keyed_sq_data;');end=text.index('generate if(REQUEST_CQ_ENABLE)',start)
    text=text[:start]+'''wire [279:0] keyed_sq_data=s_axis_sq_tdata;
wire keyed_sq_valid=s_axis_sq_tvalid;
wire keyed_sq_ready;
assign s_axis_sq_tready=keyed_sq_ready;
initial if(!REQUEST_CQ_ENABLE || LEGACY_QP_KEY)$fatal(1,"matched complete Immediate profile required");
'''+text[end:]
    start=text.index('generate if(REQUEST_CQ_ENABLE)begin : native_request_core')
    end=text.index('end else if(RECV_RETIRE_ENABLE)',start)
    primary=text[start:end]
    primary=once(primary,'rocev2_native_duplex_top transport (','rocev2_native_immediate_top transport (')
    stop=text.index('end endgenerate',end)+len('end endgenerate')
    return text[:start]+primary+'end endgenerate'+text[stop:]
