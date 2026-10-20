# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full actual128 native requester: CAS/FADD/READ/Immediate and responder.

Actual C codec/SQ/PCIe/MR/PTE/result DMA/fence/HLS/replay/MAC/CQ. CAS/FADD
use real XGMII/FCS/SFD/CDC; ordinary regression keeps the prior MAC-pin
model. Physical host/root/peer/PHY/PTP input remain explicit models.
"""
import ctypes as C
import struct
import atomic_native_full_memory_fixture as old
import test_atomic_wqe as codec
import test_atomic128_response_rtl as response

ROOT=old.ROOT;link=old.link;once=old.once
COMPARE=0xfedcba9876543210;ARGUMENT=0x8123456789abcdef;OLD_VALUE=0xfedcba9876543210
REMOTE=0xf123456789abc008;RKEY=0x81234567


def variant(opcode,immediate=0):
    words,records,request=old.old.old.variant(2 if opcode in [7,8]else opcode,immediate)
    if opcode in [7,8]:
        out=[]
        for r in records:
            b=bytearray(r);b[24:32]=REMOTE.to_bytes(8,'little');b[32:36]=(8).to_bytes(4,'little')
            b[40:44]=RKEY.to_bytes(4,'little');b[44:46]=opcode.to_bytes(2,'little')
            out.append(bytes(b)+(COMPARE if opcode==7 else 0).to_bytes(8,'little')+
                ARGUMENT.to_bytes(8,'little')+bytes(48))
        records=out
        p=bytearray(request[:40]);p[28]=19 if opcode==7 else 20
        p+=struct.pack('!QIQQ',REMOTE,RKEY,ARGUMENT,COMPARE if opcode==7 else 0)+bytes(4)
        request=response.old.repair(p)
        packet=bytearray(response.packet(mig=1,qpn=2,psn=0x89abcd))
        packet[44:52]=OLD_VALUE.to_bytes(8,'big');packet=response.old.repair(packet)
        frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+packet
        beats=[int.from_bytes(frame[n:n+16].ljust(16,bytes(1)),'little')|
            (((1<<min(16,len(frame)-n))-1)<<128)|(int(n+16>=len(frame))<<144)for n in range(0,len(frame),16)]
        if len(beats)!=5:raise ValueError('actual AtomicACK frame geometry')
        words=words[:8]+beats+[0]*4+words[-4:]
    else:records=[r+bytes(64)for r in records]
    result=[];cls=codec.AtomicWQETests;cls.setUpClass()
    try:
        for raw in records:
            w=codec.AtomicWQE();inp=(C.c_uint8*128).from_buffer_copy(raw);out=(C.c_uint8*128)()
            if cls.lib.as02_atomic_wqe_decode(C.byref(w),inp):raise ValueError('actual C128 decode')
            if cls.lib.as02_atomic_wqe_encode(out,C.byref(w))or bytes(out)!=raw or codec.oracle(w)!=raw:
                raise ValueError('actual C128 encoder/independent oracle')
            result.append(bytes(out))
    finally:cls.tearDownClass()
    return words,result,request


def bench():
    t=old.bench()
    # All these testbench declarations are requester contexts, never posted RQ.
    t=t.replace('[619:0]','[747:0]').replace('[687:0]','[815:0]')
    for obj in ['held_request_proof','dut.h_request_done_data']:
        for a,b in [('643:620','771:748'),('667:644','795:772'),('675:668','803:796'),('687:676','815:804')]:
            t=t.replace(obj+'['+a+']',obj+'['+b+']')
    t=once(t,'reg real_mac_mode=0,hold_atomic_wire=0;',DECLARATIONS)
    t=once(t,' if($test$plusargs("WRITE"))runtime_native_opcode=1;',
        ' if($test$plusargs("WRITE"))runtime_native_opcode=1;\n'
        ' if($test$plusargs("CAS"))runtime_native_opcode=7;\n if($test$plusargs("FADD"))runtime_native_opcode=8;')
    # Actual full operands are observed at the production frontend handoff.
    t=once(t,'.m_work_wr_id(m_work_wr_id),',
        '.m_work_compare(work_compare),.m_work_swap_add(work_swap_add),.m_work_wr_id(m_work_wr_id),')
    t=once(t,'work_fields={m_work_wr_id,',
        'work_fields={work_swap_add,work_compare,dut.m_work_immediate,m_work_wr_id,')
    t=once(t,'if(dut.m_work_handoff && dut.m_work_immediate!==runtime_immediate)',
        'if(dut.m_work_handoff && (dut.m_work_immediate!==runtime_immediate ||\n'
        ' work_compare!==runtime_compare || work_swap_add!==runtime_argument))')
    # Real coherent128-byte ring, including both complete records and sentinels.
    for a,b in [('[0:16511]','[0:16639]'),('init_byte<16512','init_byte<16640'),
                ("64'hfedcba9876543080","64'hfedcba9876543100"),
                ('reg [511:0] sq_records','reg [1023:0] sq_records'),
                ('init_byte<128','init_byte<256'),('sq_i<128','sq_i<256'),
                ('sq_records[init_byte/64][(init_byte%64)*8+:8]','sq_records[init_byte/128][(init_byte%128)*8+:8]'),
                ('sq_records[sq_i/64][(sq_i%64)*8+:8]','sq_records[sq_i/128][(sq_i%128)*8+:8]'),
                ('desc_length!=64 || desc_ram!=0','desc_length!=128 || desc_ram!=0')]:
        if a not in t:raise ValueError('ring fixture anchor '+a)
        t=t.replace(a,b)
    # New format features refuse old kernel negotiation; no capability bypass.
    for a,b in [('if(sq_value!==5)','if(sq_value!==13)'),('if(sq_value!==7)','if(sq_value!==15)')]:
        if a not in t:raise ValueError('profile fixture changed')
        t=t.replace(a,b)
    t=once(t,'  $fclose(fp);',
        "  read_reg(24'h402020,sq_value);if(sq_value!==128)$fatal(1,\"actual SQ descriptor stride\");\n"
        "  read_reg(24'h405020,sq_value);if(sq_value!==128)$fatal(1,\"actual RQ descriptor stride\");\n  $fclose(fp);")
    # Preserve the existing ordinary DMA page-split checks, use exact3+5 Atomic.
    t=once(t,'pcie_pattern=(pos*179)^(pos>>7)^pcie_seed^8\'hd3;',
        "pcie_pattern=runtime_atomic ? ((REQUEST_OLD>>(pos*8))&255):(pos*179)^(pos>>7)^pcie_seed^8'hd3;")
    t=once(t,'desc_ram==3 && desc_length==62','desc_ram==3 && desc_length==(runtime_atomic ? 5:62)')
    for a,b in [('ml!=65','ml!=runtime_length'),('posted_bytes!=65','posted_bytes!=runtime_length'),
                ('m_work_length!==65','m_work_length!==runtime_length'),
                ('dut.ex_m_memory_command_length!==65','dut.ex_m_memory_command_length!==runtime_length'),
                ('expected_request_owner[307:276]!==65','expected_request_owner[307:276]!==runtime_length'),
                ('guard_byte<4158','guard_byte<4093+runtime_length'),('idx>=4158','idx>=4093+runtime_length'),
                ('sq_i<4158','sq_i<4093+runtime_length'),('m_work_remote_key!==0','m_work_remote_key!==runtime_rkey'),
                ('expected_request_owner[51:20]!==0','expected_request_owner[51:20]!==runtime_rkey')]:
        if a not in t:raise ValueError('result fixture anchor '+a)
        t=t.replace(a,b)
    t=t.replace("64'hf123456789abc001)","runtime_remote)")
    t=once(t,"held_request_proof[803:796]!==(runtime_native_opcode==2 ?",
        "held_request_proof[803:796]!==(runtime_native_opcode==7 ? 8'h13 : runtime_native_opcode==8 ? 8'h14 : runtime_native_opcode==2 ?")
    t=once(t,'expected_request_owner[619:588]!==runtime_immediate ||',
        'expected_request_owner[747:620]!=={runtime_argument,runtime_compare} ||\n expected_request_owner[619:588]!==runtime_immediate ||')
    t=once(t,'send_frame(8,runtime_native_opcode==2 ? 9 : 4);',
        'send_frame(8,runtime_atomic ? 5:runtime_native_opcode==2 ? 9:4);')
    # Atomic result placement has the same3+5 page split as the normal READ.
    for a,b in [('runtime_native_opcode==2 ? 4 : 3','(runtime_native_opcode==2 || runtime_atomic) ? 4:3'),
                ('runtime_native_opcode==2 ? 2 : 3','(runtime_native_opcode==2 || runtime_atomic) ? 2:3'),
                ('runtime_native_opcode==2 ? 2 : 0','(runtime_native_opcode==2 || runtime_atomic) ? 2:0'),
                ('runtime_native_opcode==2 ? 1 : 0','(runtime_native_opcode==2 || runtime_atomic) ? 1:0'),
                ('if(runtime_native_opcode==2 && sq_i>=4093','if((runtime_native_opcode==2 || runtime_atomic) && sq_i>=4093'),
                ("((((sq_i-4093)*179)^((sq_i-4093)>>7)^8'hd3)&255)",'pcie_pattern(sq_i-4093)')]:
        t=once(t,a,b)
    # Do not leak compare's low20 bits into the legacy CQ window/padding.
    t=once(t,"({20'd0,expected_request_owner}>>","({20'd0,expected_request_owner[619:0]}>>")
    t=once(t,'$fclose(request_event_file);',CQ_EXTENSION+'\n$fclose(request_event_file);')
    t=once(t,r'\"payload_bytes\":65',r'\"payload_bytes\":%0d')
    t=once(t,'runtime_native_opcode,router_descriptor_count,read_tlps,write_tlps,fences);',
        'runtime_native_opcode,runtime_length,router_descriptor_count,read_tlps,write_tlps,fences);')
    # Switch only at the drained post-bootstrap physical boundary.
    t=once(t,'enable=1;\nif(!$test$plusargs("ATOMIC_ONLY"))begin',
        'if(runtime_atomic)begin\n if(mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)\n'
        ' $fatal(1,"requester actual MAC switch needs drained prior physical receipts");\n'
        ' requester_wire_mode=1;end\nenable=1;\nif(!$test$plusargs("ATOMIC_ONLY"))begin')
    t=once(t,'if(real_mac_mode || rst)mac_clk=~mac_clk;','if(use_actual_link || rst)mac_clk=~mac_clk;')
    t=once(t,'assign link_s_valid=real_mac_mode &&','assign link_s_valid=use_actual_link &&')
    t=once(t,'assign link_m_cpl_ready=real_mac_mode && s_axis_mac_cpl_ready;',
        'assign link_m_cpl_ready=use_actual_link && s_axis_mac_cpl_ready && allow_actual_receipt;')
    t=once(t,'.m_axis_mac_tx_tready(real_mac_mode ?','.m_axis_mac_tx_tready(use_actual_link ?')
    for name in ['tag','ts']:
        t=once(t,'.s_axis_mac_cpl_'+name+'(real_mac_mode ?', '.s_axis_mac_cpl_'+name+'(use_actual_link ?')
    t=once(t,'.s_axis_mac_cpl_valid(real_mac_mode ? link_m_cpl_valid:',
        '.s_axis_mac_cpl_valid(use_actual_link ? link_m_cpl_valid && allow_actual_receipt:')
    for a,b in [('&& !real_mac_mode;','&& !use_actual_link;'),
                ('if(!rst && !real_mac_mode) begin','if(!rst && !use_actual_link) begin')]:
        if a not in t:raise ValueError('physical MAC model boundary changed')
        t=t.replace(a,b)
    t=once(t,"if(mac_tx_valid && tr && (mac_tx_user[16:1]&16'he000)==16'h2000)",
        "if(mac_tx_valid && (use_actual_link ? link_s_ready && !hold_atomic_wire:tr) && (mac_tx_user[16:1]&16'he000)==16'h2000)")
    t=once(t,'check_ring();request_event_file=',
        'if(runtime_atomic && (actual_native_SFD_count!=2 || actual_SFD_count!=2 || actual_Atomic_SFD_count))\n'
        ' $fatal(1,"two real requester MAC SFD/CDC receipts required");\ncheck_ring();request_event_file=')
    if 'force 'in t:raise ValueError('no internal force')
    return t


DECLARATIONS=r'''
reg real_mac_mode=0,hold_atomic_wire=0,requester_wire_mode=0;
wire use_actual_link=real_mac_mode || requester_wire_mode;
wire runtime_atomic=runtime_native_opcode==7 || runtime_native_opcode==8;
wire [31:0] runtime_length=runtime_atomic ? 8:65;
wire [63:0] runtime_remote=runtime_atomic ? 64'hf123456789abc008:64'hf123456789abc001;
wire [31:0] runtime_rkey=runtime_atomic ? 32'h81234567:0;
wire [63:0] runtime_compare=runtime_native_opcode==7 ? 64'hfedcba9876543210:0;
wire [63:0] runtime_argument=runtime_atomic ? 64'h8123456789abcdef:0;
localparam [63:0] REQUEST_OLD=64'hfedcba9876543210;
wire [63:0] work_compare,work_swap_add;
wire allow_actual_receipt=!(requester_wire_mode && hold_request_mac_cpl && link_m_cpl_tag==16'h2002);
'''

CQ_EXTENSION=r'''
read_reg(24'h403094,sq_value);if(sq_value!==748)$fatal(1,"CQ full-owner geometry");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h403098,sq_value);if(sq_value!==32'ha0)$fatal(1,"CQ extension base");$fdisplay(request_event_file,"%08h",sq_value);
for(request_word=0;request_word<4;request_word=request_word+1)begin
 read_reg(24'h4030a0+request_word*4,sq_value);
 if(sq_value!==((expected_request_owner[747:620]>>(request_word*32))&32'hffffffff))
  $fatal(1,"CQ immutable complete Atomic operands");
 $fdisplay(request_event_file,"%08h",sq_value);
end
'''

