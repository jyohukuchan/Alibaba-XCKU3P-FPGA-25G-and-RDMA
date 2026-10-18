# SPDX-License-Identifier: BSD-2-Clause-Views
"""Reuse the wire oracle/AXI tasks with the real endpoint or full board app.

Only the DUT boundary changes; no hierarchical forcing or modeled transport.
MAC SFD completions and the remote RNIC are still modeled by the caller.
"""


def make_tb(tb, boundary):
    if boundary not in ("endpoint", "app"):
        raise ValueError("unknown integration boundary")
    start = tb.index("rocev2_control #(")
    end = tb.index("reg [145:0] acks", start)
    node = "endpoint" if boundary == "endpoint" else "app.endpoint"
    signals = [("s_axil_awaddr", "aa"), ("s_axil_awprot", "3'd0"), ("s_axil_awvalid", "av"), ("s_axil_awready", "ar"),
               ("s_axil_wdata", "wd"), ("s_axil_wstrb", "ws"), ("s_axil_wvalid", "wv"), ("s_axil_wready", "wr"),
               ("s_axil_bresp", "bp"), ("s_axil_bvalid", "bv"), ("s_axil_bready", "br"),
               ("s_axil_araddr", "ra"), ("s_axil_arprot", "3'd0"), ("s_axil_arvalid", "rv"), ("s_axil_arready", "arready"),
               ("s_axil_rdata", "rd"), ("s_axil_rresp", "rp"), ("s_axil_rvalid", "rvalid"), ("s_axil_rready", "rr")]
    common = '''reg [127:0] input_data=0;
reg [15:0] input_keep=0;
reg input_valid=0,input_last=0;
wire input_ready;
wire [127:0] output_data;
wire [15:0] output_keep;
wire output_valid,output_last;
reg output_ready=0;
reg model_mac_cpl=0,model_mac_in_frame=0;
wire model_mac_cpl_ready;
'''
    if boundary == "endpoint":
        instance = "rocev2_endpoint #(.WINDOW(2)) endpoint (\n .clk(clk),.rst(rst),\n"
        signals += [("s_axis_host_tx_tdata", "128'd0"), ("s_axis_host_tx_tkeep", "16'd0"),
                    ("s_axis_host_tx_tvalid", "1'b0"), ("s_axis_host_tx_tready", ""),
                    ("s_axis_host_tx_tlast", "1'b0"), ("s_axis_host_tx_tuser", "17'd0"),
                    ("m_axis_mac_tx_tdata", "output_data"), ("m_axis_mac_tx_tkeep", "output_keep"),
                    ("m_axis_mac_tx_tvalid", "output_valid"), ("m_axis_mac_tx_tready", "output_ready"),
                    ("m_axis_mac_tx_tlast", "output_last"), ("m_axis_mac_tx_tuser", ""),
                    ("s_axis_mac_cpl_tag", "16'd0"), ("s_axis_mac_cpl_ts", "96'd0"),
                    ("s_axis_mac_cpl_valid", "model_mac_cpl"), ("s_axis_mac_cpl_ready", "model_mac_cpl_ready"),
                    ("m_axis_host_cpl_tag", ""), ("m_axis_host_cpl_ts", ""), ("m_axis_host_cpl_valid", ""), ("m_axis_host_cpl_ready", "1'b1"),
                    ("s_axis_mac_rx_tdata", "input_data"), ("s_axis_mac_rx_tkeep", "input_keep"),
                    ("s_axis_mac_rx_tvalid", "input_valid"), ("s_axis_mac_rx_tready", "input_ready"),
                    ("s_axis_mac_rx_tlast", "input_last"), ("s_axis_mac_rx_tuser", "97'd0"),
                    ("m_axis_host_rx_tdata", ""), ("m_axis_host_rx_tkeep", ""), ("m_axis_host_rx_tvalid", ""),
                    ("m_axis_host_rx_tready", "1'b1"), ("m_axis_host_rx_tlast", ""), ("m_axis_host_rx_tuser", "")]
    else:
        common += '''wire [255:0] app_tx_data;
wire [31:0] app_tx_keep;
wire [1:0] app_tx_valid,app_tx_last,app_rx_ready,app_cpl_ready;
assign output_data=app_tx_data[255:128];
assign output_keep=app_tx_keep[31:16];
assign output_valid=app_tx_valid[1];
assign output_last=app_tx_last[1];
assign input_ready=app_rx_ready[1];
assign model_mac_cpl_ready=app_cpl_ready[1];
'''
        signals = [(name.replace("s_axil_", "s_axil_app_ctrl_"), value) for name, value in signals]
        instance = "mqnic_app_block #(.AXIL_APP_CTRL_ADDR_WIDTH(24)) app (\n .clk(clk),.rst(rst),\n"
        signals += [("s_axis_sync_tx_tdata", "256'd0"), ("s_axis_sync_tx_tkeep", "32'd0"),
                    ("s_axis_sync_tx_tvalid", "2'd0"), ("s_axis_sync_tx_tready", ""),
                    ("s_axis_sync_tx_tlast", "2'd0"), ("s_axis_sync_tx_tuser", "34'd0"),
                    ("m_axis_sync_tx_tdata", "app_tx_data"), ("m_axis_sync_tx_tkeep", "app_tx_keep"),
                    ("m_axis_sync_tx_tvalid", "app_tx_valid"), ("m_axis_sync_tx_tready", "{output_ready,1'b1}"),
                    ("m_axis_sync_tx_tlast", "app_tx_last"), ("m_axis_sync_tx_tuser", ""),
                    ("s_axis_sync_tx_cpl_tag", "32'd0"), ("s_axis_sync_tx_cpl_ts", "192'd0"),
                    ("s_axis_sync_tx_cpl_valid", "{model_mac_cpl,1'b0}"), ("s_axis_sync_tx_cpl_ready", "app_cpl_ready"),
                    ("m_axis_sync_tx_cpl_tag", ""), ("m_axis_sync_tx_cpl_ts", ""), ("m_axis_sync_tx_cpl_valid", ""), ("m_axis_sync_tx_cpl_ready", "2'b11"),
                    ("s_axis_sync_rx_tdata", "{input_data,128'd0}"), ("s_axis_sync_rx_tkeep", "{input_keep,16'd0}"),
                    ("s_axis_sync_rx_tvalid", "{input_valid,1'b0}"), ("s_axis_sync_rx_tready", "app_rx_ready"),
                    ("s_axis_sync_rx_tlast", "{input_last,1'b0}"), ("s_axis_sync_rx_tuser", "194'd0"),
                    ("m_axis_sync_rx_tdata", ""), ("m_axis_sync_rx_tkeep", ""), ("m_axis_sync_rx_tvalid", ""),
                    ("m_axis_sync_rx_tready", "2'b11"), ("m_axis_sync_rx_tlast", ""), ("m_axis_sync_rx_tuser", "")]
    instance += ",\n".join(" ." + name + "(" + value + ")" for name, value in signals) + "\n);\n"
    aliases = dict(core_rst="core_reset", halt="halt_tx", quiet="tx_quiescent", guard_fault="guard_fault",
                   guard_pending="guard_pending", guard_admitted="guard_admitted", guard_completed="guard_completed",
                   busy="control.busy", done="control.done", failed="control.failed", rx_words="rx_words", tx_words="tx_words",
                   ack_valid="av", ack_ready="ar")
    common += "\n".join("assign " + name + "=" + node + "." + value + ";" for name, value in aliases.items()) + "\n"
    tb = tb[:start] + common + instance + tb[end:]
    for attribute in ("error", "state", "read_commands"):
        tb = tb.replace("control." + attribute, node + ".control." + attribute)
    return tb
