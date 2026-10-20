# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full native fixture with strict eight-byte Atomic/WRITE physical oracles.

The original requester fixture only permitted its 65-byte/page-split transfer.
Keep those assertions for requester cases; the new phase has independent exact
key/offset/length/direction, physical page, enabled-byte and fence expectations.
Never drive DUT authority, completion, retirement or drain from this oracle.
"""
import atomic_native_full_fixture as original

ROOT=original.ROOT;link=original.link;old=original.old
FIRST_OLD=original.FIRST_OLD;NORMAL_VALUE=original.NORMAL_VALUE
fixtures=original.fixtures;input_frames=original.input_frames
once=original.once


def bench():
    t=original.bench()
    t=once(t,'if(mk!==pcie_expected_key || mo!==64\'h210)',
        "if(mk!==pcie_expected_key || (real_mac_mode ? (atomic_phase!=3 || mo!==64'h220 || ml!==8) : mo!==64'h210))")
    t=once(t,'desc_address!==pcie_expected_dma(pcie_current_offset+(desc_ram==8128 ? 0:desc_ram))',
        "desc_address!==pcie_expected_dma((real_mac_mode ? (atomic_phase==3 ? 64'h220:64'h218):pcie_current_offset)+(desc_ram==8128 ? 0:desc_ram))")
    t=once(t,'if((desc_ram==8128 && desc_length!=1) || (desc_ram!=8128 && !((desc_ram==0 && desc_length==3)||(desc_ram==3 && desc_length==62))))',
        'if(real_mac_mode ? !((desc_ram==8128 && desc_length==1)||(desc_ram==0 && desc_length==8)) :\n'
        ' ((desc_ram==8128 && desc_length!=1) || (desc_ram!=8128 && !((desc_ram==0 && desc_length==3)||(desc_ram==3 && desc_length==62)))))')
    t=once(t,'if(ma+ml>64\'d4096 || ml!=65 || mt!=commands+1)',
        "if(real_mac_mode ? (atomic_phase!=3 || !mw || ma!==64'h220 || ml!==8 || mt!==16'd1) :\n"
        " (ma+ml>64'd4096 || ml!=65 || mt!=commands+1))")
    t=once(t,"pcie_host[guard_byte]!==((guard_byte>=4093 && guard_byte<4158) ? pcie_pattern(guard_byte-4093):(((guard_byte*37)^8'h5a)&255))",
        "(real_mac_mode ? !atomic_host_byte_ok(guard_byte):\n"
        " pcie_host[guard_byte]!==((guard_byte>=4093 && guard_byte<4158) ? pcie_pattern(guard_byte-4093):(((guard_byte*37)^8'h5a)&255)))")
    t=once(t,'integer atomic_phase=0,',PROOF+'\ninteger atomic_phase=0,')
    t=once(t,'read_tlps!=5 || write_tlps!=3 || fences!=3)',
        'read_tlps!=5 || write_tlps!=3 || fences!=3 || actual_atomic_memory_commands!=5 ||\n'
        ' actual_atomic_reads!=2 || actual_atomic_writes!=3)')
    return t


PROOF=r'''
integer actual_atomic_memory_commands=0,actual_atomic_reads=0,actual_atomic_writes=0;
integer phase_memory_commands[0:4];
initial begin phase_memory_commands[0]=0;phase_memory_commands[1]=0;phase_memory_commands[2]=0;
 phase_memory_commands[3]=0;phase_memory_commands[4]=0;end
always @(posedge clk)if(!rst && real_mac_mode &&
 dut.native.network.datapath.responder.endpoint.backend_command_valid &&
 dut.native.network.datapath.responder.endpoint.backend_command_ready)begin
 if(atomic_phase<1 || atomic_phase>4 || atomic_phase==2 ||
   dut.native.network.datapath.responder.endpoint.backend_command_key!==32'd8 ||
   dut.native.network.datapath.responder.endpoint.backend_command_length!==32'd8 ||
   dut.native.network.datapath.responder.endpoint.backend_command_offset!==(atomic_phase==3 ? 64'h220:64'h218) ||
   dut.native.network.datapath.responder.endpoint.backend_command_write!==(atomic_phase==3 || phase_memory_commands[atomic_phase]==1))
  $fatal(1,"actual common backend Atomic/WRITE authority/direction");
 phase_memory_commands[atomic_phase]=phase_memory_commands[atomic_phase]+1;
 if(phase_memory_commands[atomic_phase]>(atomic_phase==3 ? 1:2))$fatal(1,"extra actual Atomic/WRITE command");
 actual_atomic_memory_commands=actual_atomic_memory_commands+1;
 if(dut.native.network.datapath.responder.endpoint.backend_command_write)actual_atomic_writes=actual_atomic_writes+1;
 else actual_atomic_reads=actual_atomic_reads+1;
end
function atomic_host_byte_ok;
 input integer index;reg [7:0] wanted;
 begin
  wanted=((index*37)^8'h5a)&255;
  if(index>=4101 && index<4109)wanted=(expected_atomic_write>>((index-4101)*8))&255;
  if(index>=4109 && index<4117 && atomic_phase>=3)wanted=(64'h0123456789abcdef>>((index-4109)*8))&255;
  atomic_host_byte_ok=pcie_host[index]===wanted;
 end
endfunction
'''
