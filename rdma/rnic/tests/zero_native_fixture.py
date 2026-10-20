# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete native zero requester fixture: real queue/packet/replay/MAC/CQ.

The physical host/root/peer/PHY/PTP remain models, not Linux or hardware.
Zero runs permit ONLY the actual coherent SQ fetch DMA, never data-MR/DMA,
and independently keep every host/sentinel byte unchanged. Previous normal
and Atomic cases retain their exact nonzero page/DMA/fence assertions.
"""
import ctypes as C
import struct
import atomic_access_native_fixture as old
import test_zero_wqe as codec

ROOT=old.ROOT;link=old.link;once=old.once;fixtures=old.fixtures


def variant(opcode,immediate=0,zero=False):
    words,records,request=old.variant(opcode,immediate)
    if not zero:return words,records,request
    if opcode not in [1,2,3,5,6]:raise ValueError('zero Atomic is never licensed')
    result=[];cls=codec.ZeroWQETests;cls.setUpClass()
    try:
        for r in records:
            b=bytearray(r);b[16:24]=bytes(8);b[32:40]=bytes(8)
            b[24:32]=((1<<64)-1 if opcode in [1,2,6]else 0).to_bytes(8,'little')
            b[40:44]=(0xfedcba98 if opcode in [1,2,6]else 0).to_bytes(4,'little')
            w=codec.old.AtomicWQE();inp=(C.c_uint8*128).from_buffer_copy(b);out=(C.c_uint8*128)()
            if cls.lib.as02_zero_wqe_decode(C.byref(w),inp)or cls.lib.as02_zero_wqe_encode(out,C.byref(w))or \
               bytes(out)!=b or codec.old.oracle(w)!=b:raise ValueError('actual zero C128 codec/independent oracle')
            result.append(bytes(out))
    finally:cls.tearDownClass()
    p=bytearray(request[:40]);p[29]&=~0x30
    if opcode in [1,2,6]:p+=struct.pack('!QII',(1<<64)-1,0xfedcba98,0)
    if opcode in [5,6]:p+=struct.pack('!I',immediate)
    request=old.old.response.old.repair(p+bytes(4))
    # Actual AETH4/UDP28 response; do not call the legacy nonempty host READ
    # encoder with a prohibited zero payload, or alter that proven encoder.
    p=bytearray(old.old.response.old.packet(write=True,length=1,mig=1,qpn=2,psn=0x89abcd))
    p[28]=16 if opcode==2 else 17;p=old.old.response.old.repair(p)
    frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+p
    beats=[int.from_bytes(frame[n:n+16].ljust(16,bytes(1)),'little')|
        (((1<<min(16,len(frame)-n))-1)<<128)|(int(n+16>=len(frame))<<144)for n in range(0,len(frame),16)]
    if len(beats)!=4:raise ValueError('zero ACK/AETH Ethernet geometry')
    return words[:8]+beats+[0]*5+words[-4:],result,request


def bench():
    t=old.bench()
    if t.count('if(sq_value!==2047)')!=2:raise ValueError('full RNC profile assertions changed')
    t=t.replace('if(sq_value!==2047)','if(sq_value!==4095)')
    t=once(t,'wire runtime_atomic=',
        'reg runtime_zero=0;initial runtime_zero=$test$plusargs("ZERO");\n'
        'wire [31:0] runtime_local_key=runtime_zero ? 0:8;\n'
        "wire [63:0] runtime_local_va=runtime_zero ? 0:64'hfedcba9876543210;\n"
        "wire [63:0] runtime_offset=runtime_zero ? 0:64'h210;\n"
        'integer zero_local_MR_queries=0;\n'
        'always @(posedge clk)if(!rst && runtime_zero)begin\n'
        ' if(dut.native.s_local_mr_request_valid && dut.native.s_local_mr_request_ready)zero_local_MR_queries=zero_local_MR_queries+1;\n'
        ' if(dut.ex_m_memory_command_valid || dut.ex_s_memory_status_valid ||\n'
        '    dut.ex_m_axis_hls_read_tvalid || dut.ex_m_axis_memory_write_tvalid)\n'
        '  $fatal(1,"zero requester invented data-memory command/data/status");\n'
        'end\nwire runtime_atomic=')
    for a,b in [('runtime_length=runtime_atomic ?','runtime_length=runtime_zero ? 0:runtime_atomic ?'),
                ('runtime_remote=runtime_atomic ?',"runtime_remote=runtime_zero ? 64'hffffffffffffffff:runtime_atomic ?"),
                ('runtime_rkey=runtime_atomic ?',"runtime_rkey=runtime_zero ? ((runtime_native_opcode==3 || runtime_native_opcode==5) ? 0:32'hfedcba98):runtime_atomic ?")]:t=once(t,a,b)
    t=once(t,'if(runtime_atomic)begin\n if(mac_cpl_rd',
        'if(runtime_atomic || runtime_zero)begin\n if(mac_cpl_rd')
    t=once(t,'send_frame(8,runtime_atomic ? 5:runtime_native_opcode==2 ? 9:4);',
        'send_frame(8,runtime_zero ? 4:runtime_atomic ? 5:runtime_native_opcode==2 ? 9:4);')
    for a,b in [('m_work_local_key!==expected_work_key','m_work_local_key!==(runtime_zero ? 0:expected_work_key)'),
                ("m_work_local_address!==64'hfedcba9876543210",'m_work_local_address!==runtime_local_va'),
                ("m_work_local_offset!==64'h210",'m_work_local_offset!==runtime_offset'),
                ('expected_request_owner[275:244]!==8','expected_request_owner[275:244]!==runtime_local_key'),
                ("expected_request_owner[243:180]!==64'hfedcba9876543210",'expected_request_owner[243:180]!==runtime_local_va'),
                ("expected_request_owner[179:116]!==64'h210",'expected_request_owner[179:116]!==runtime_offset'),
                ('dut.ex_command_count!=1','dut.ex_command_count!=(runtime_zero ? 0:1)'),
                ('dut.ex_memory_status_count!=1','dut.ex_memory_status_count!=(runtime_zero ? 0:1)')]:t=once(t,a,b)
    for a,b in [('router_descriptor_count!==((runtime_native_opcode==2 || runtime_atomic) ? 4:3)',
                 'router_descriptor_count!==(runtime_zero ? 1:((runtime_native_opcode==2 || runtime_atomic) ? 4:3))'),
                ('read_tlps!==((runtime_native_opcode==2 || runtime_atomic) ? 2:3)',
                 'read_tlps!==(runtime_zero ? 1:((runtime_native_opcode==2 || runtime_atomic) ? 2:3))'),
                ('write_tlps!==((runtime_native_opcode==2 || runtime_atomic) ? 2:0)',
                 'write_tlps!==(runtime_zero ? 0:((runtime_native_opcode==2 || runtime_atomic) ? 2:0))'),
                ('fences!==((runtime_native_opcode==2 || runtime_atomic) ? 1:0)',
                 'fences!==(runtime_zero ? 0:((runtime_native_opcode==2 || runtime_atomic) ? 1:0))'),
                ('if(runtime_atomic && (actual_native_SFD_count!=2',
                 'if((runtime_atomic || runtime_zero) && (actual_native_SFD_count!=2')]:t=once(t,a,b)
    t=once(t,'check_ring();request_event_file=',
        'if(runtime_zero && zero_local_MR_queries)$fatal(1,"zero issued actual local MR query");\n'
        'check_ring();request_event_file=')
    # Preserve byte/operand checks and actual CQ host-ACK release, then report
    # zero observations separately from unchanged nonzero regression summary.
    t=once(t,'$display("NATIVE_RNIC_RESULT ',
        ' if(runtime_zero)$display("ZERO_NATIVE_RESULT {\\"pass_test\\":true,\\"local_MR_queries\\":%0d,\\"memory_commands\\":%0d,\\"memory_status\\":%0d,\\"actual_MAC_SFD\\":%0d}",zero_local_MR_queries,dut.ex_command_count,dut.ex_memory_status_count,actual_native_SFD_count);\n'
        '$display("NATIVE_RNIC_RESULT ')
    if 'force 'in t:raise ValueError('no internal force')
    return t
