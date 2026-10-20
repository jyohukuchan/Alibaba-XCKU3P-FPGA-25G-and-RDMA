# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked128-byte requester SQ/RQ fetch candidate, never a second QP table.

Replace the existing fetch hierarchy only in a FUTURE matched128-byte queue
profile. Preserve trusted configuration/epochs/pending/downstream/drain guards,
finite tags and the real Corundum DMA/RAM backend. Current default64-byte
profile/driver are unchanged. This does NOT authorize a WQE or complete a WR.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];RTL=ROOT/'rdma/rnic/rtl'
FETCH=RTL/'rocev2_sq_fetch.v';DMA=RTL/'rocev2_sq_dma_fetch.v'


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('review exact fetch anchor '+old)
    return text.replace(old,new)


def derive():
    t=FETCH.read_text()
    t=once(t,'module rocev2_sq_fetch #(','module rocev2_atomic128_sq_fetch #(')
    t=once(t,'// Trusted coherent DMA64 SQ rings ->64-byte fetched records/trusted contexts.',
        '// Candidate matched128-byte SQ/RQ records; trusted contexts stay outside fetched data.')
    t=once(t,'output wire [511:0] m_result_data,','output wire [1023:0] m_result_data,')
    t=once(t,'reg [511:0] data=0;','reg [1023:0] data=0;\nreg second_beat=0;')
    if t.count('<<6')!=2:raise ValueError('exact ring range and stride shifts')
    t=t.replace('<<6','<<7')
    t=once(t,'cfg_dma_base[5:0]==0','cfg_dma_base[6:0]==0')
    t=once(t,'assign m_command_length=64;','assign m_command_length=128;')
    t=once(t,"assign m_result_data=error==0 ? data : 512'd0;","assign m_result_data=error==0 ? data : 1024'd0;")
    if t.count('data<=0;data_seen<=0;')!=2:raise ValueError('exact reset/new-owner buffer clearing')
    t=t.replace('data<=0;data_seen<=0;','data<=0;data_seen<=0;second_beat<=0;')
    t=once(t,"case(s_axis_read_tkeep==64'hffffffffffffffff && s_axis_read_tlast)\n                1'b1:begin data<=s_axis_read_tdata;data_seen<=1;end",
        "case(s_axis_read_tkeep==64'hffffffffffffffff && s_axis_read_tlast==second_beat)\n"
        "                1'b1:begin\n"
        "                    if(second_beat)data[1023:512]<=s_axis_read_tdata;else data[511:0]<=s_axis_read_tdata;\n"
        "                    data_seen<=second_beat;second_beat<=1;\n"
        "                end")
    dma=DMA.read_text()
    dma=once(dma,'module rocev2_sq_dma_fetch #(','module rocev2_atomic128_sq_dma_fetch #(')
    dma=once(dma,'output wire [511:0] m_result_data,','output wire [1023:0] m_result_data,')
    dma=once(dma,'rocev2_sq_fetch #(','rocev2_atomic128_sq_fetch #(')
    return {FETCH:t,DMA:dma}
