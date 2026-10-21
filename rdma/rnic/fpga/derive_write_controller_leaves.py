# SPDX-License-Identifier: BSD-2-Clause-Views
"""Native WRITE classifier and read-only Immediate field on checked frontend.

No authority/gate/parser rewrite: classifier retains every packet byte,
frontend adds only the parsed Immediate observation for genuine RQ placement.
Original raw/Atomic/default leaves stay byte-identical.
"""
import derive_segmented_write_native_gateway as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
FRONT=RTL/'rocev2_segmented_write_rx_frontend.v'
ROUTER=RTL/'rocev2_native_atomic_rx_router.v'
FRONT_NAME='rocev2_segmented_write_native_frontend'
ROUTER_NAME='rocev2_native_write_rx_router'


def frontend():
    t=once(FRONT.read_text(),'module rocev2_segmented_write_rx_frontend #(','module '+FRONT_NAME+' #(')
    t=once(t,'    output wire m_packet_last,m_packet_notify,output wire [619:0] m_packet_rq_context,',
        '    output wire [31:0] m_packet_notification,\n    output wire m_packet_last,m_packet_notify,output wire [619:0] m_packet_rq_context,')
    return once(t,'wire first=opcode==8\'h06,notify=opcode==8\'h09;',
        "wire first=opcode==8'h06,notify=opcode==8'h09;\nassign m_packet_notification=notify ? be32(header,40):32'd0;")


def router():
    t=once(ROUTER.read_text(),'module rocev2_native_atomic_rx_router (','module '+ROUTER_NAME+' (')
    t=once(t,'    input wire clk,input wire rst,','    input wire clk,input wire rst,input wire force_write,')
    t=once(t,"header1<=s_data;atomic_packet<=opcode==8'h13 || opcode==8'h14;state<=HEADER0;",
        "header1<=s_data;atomic_packet<=force_write===1'b1 || (opcode>=8'h06 && opcode<=8'h09);state<=HEADER0;")
    # The existing alternate channel keeps its names; only its classification
    # meaning is WRITE in this distinct module. No new output geometry.
    return t
