# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual8193 SEND/WRITE Immediate plus every prior native fixture/oracle.

Only physical host/root/peer/PHY/PTP boundaries are driven. The peer ACKs
each real wire EOF; final actual MAC receipt is withheld. Full C128 records,
Immediate-only-LAST wire bytes, all host sentinels and exact whole CQ owner
are independent oracles, never normalized observed outputs or fake grants.
"""
import ast
import ctypes as C
import hashlib
import inspect
import json
import struct
import segmented_read_command_queue_native_fixture as parent
import segmented_read_native_fixture as read
import segmented_wire_native_fixture as wire
import segmented_executor_native_fixture as executor
import segmented_profile_native_fixture as profile
import zero_rq_native_fixture as rq
import test_segmented_immediate_wqe as codec

ROOT=parent.ROOT;once=parent.once;LENGTH=8193;FIRST=0xfffffe
CODEC_REPORT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-immediate-wqe-003.json'


def __getattr__(name):return getattr(parent,name)


def clone(function,replacements):
    text=inspect.getsource(function)
    for old,new in replacements:text=once(text,old,new)
    ast.parse(text);namespace=dict(function.__globals__)
    exec(compile(text,__file__+':'+function.__name__,'exec'),namespace)
    return namespace[function.__name__]


# Expected ABI changes only; all existing packet/owner/cardinality assertions
# still inspect the unedited actual new native output and captures.
verify_large=clone(wire.verify_large,[('[0,0,0,15,748,0xa0]','[0,0,0,127,748,0xa0]')])
verify_large_read=clone(read.verify_large_read,[('[0,0,0,63,748,0xa0]','[0,0,0,127,748,0xa0]')])
verify_rq=profile.clone(profile.rq.verify,'[0,flags,imm,15]','[0,flags,imm,127]')
verify_atomic=profile.clone(profile.atomic.verify,'[0,0,0,15,748,0xa0]','[0,0,0,127,748,0xa0]')
verify_zero=profile.clone(profile.zero.verify_zero,'[0,0,0,15,748,0xa0]','[0,0,0,127,748,0xa0]')
verify_executor=clone(executor.verify_executor,[("retained=int(name in ['WRITE','SEND'])",
    "retained=int(name in ['WRITE','SEND','SEND_IMM'])")])
verify_large_immediate=clone(wire.verify_large,[
    ('    wanted=[1,15,0,0x89abcdef,0xfedcba98]',
     '    owner|=get(48,4)<<588\n    wanted=[1,15,0,0x89abcdef,0xfedcba98]'),
    ('[0,0,0,15,748,0xa0]','[0,0,0,127,748,0xa0]')])


def large_immediate_variant(opcode,immediate):
    if opcode not in [5,6]or immediate!=0x89abcdef:raise ValueError('explicit new Immediate fixture required')
    proof=json.loads(CODEC_REPORT.read_text())
    if not proof.get('pass_test')or not proof.get('source_unchanged')or proof.get('methods')!=26:
        raise ValueError('actual new C128 codec/full old regression evidence required')
    for n,h in proof['source_sha256'].items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h:raise ValueError('codec source changed:'+n)
    words,records,request=rq.old.variant(opcode,immediate,False);actual=[]
    cls=codec.SegmentedImmediateWQE;cls.setUpClass()
    try:
        for raw in records:
            raw=bytearray(raw);raw[32:36]=LENGTH.to_bytes(4,'little')
            w=codec.AtomicWQE();data=(C.c_uint8*128).from_buffer_copy(raw);out=(C.c_uint8*128)()
            if cls.lib.as02_segmented_immediate_wqe_decode(C.byref(w),data)or cls.lib.as02_segmented_immediate_wqe_encode(out,C.byref(w))or \
               bytes(out)!=raw or codec.old.old.old.old.oracle(w)!=raw:
                raise ValueError('actual full-range Immediate C128/independent bytes mismatch')
            actual.append(bytes(out))
    finally:cls.tearDownClass()
    frames=[]
    for offset in range(0,LENGTH,4096):
        count=min(4096,LENGTH-offset);first=offset==0;last=offset+count==LENGTH
        code=(0 if first else 3 if last else 1)if opcode==5 else(6 if first else 9 if last else 7)
        p=bytearray(request[:28]);p+=bytes([code,0x40|(((-count)&3)<<4),0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+((FIRST+offset//4096)&0xffffff).to_bytes(3,'big')
        if opcode==6 and first:p+=struct.pack('!QII',int.from_bytes(actual[0][24:32],'little'),int.from_bytes(actual[0][40:44],'little'),LENGTH)
        if last:p+=immediate.to_bytes(4,'big')
        p+=bytes(((((4093+offset+i)*37)^0x5a)&255)for i in range(count))+bytes((-count)&3)+bytes(4)
        frames.append(bytes.fromhex('b8830367c5d08af3fbb975310800')+wire.packet_tool.repair(p))
    template=b''.join((w&((1<<128)-1)).to_bytes(16,'little')[:((w>>128)&0xffff).bit_count()]for w in words[8:12]);acks=[]
    for index in range(3):
        p=bytearray(template[14:]);p[37:40]=((FIRST+index)&0xffffff).to_bytes(3,'big')
        acks+=rq.split.encode_frame(template[:14]+wire.packet_tool.repair(p))
    if len(acks)!=12:raise ValueError('three whole four-beat peer ACKs required')
    return words,actual,frames,acks


def bench():
    t=parent.bench()
    if t.count('if(sq_value!==16383)')!=2:raise ValueError('both exact RNC reads required')
    t=t.replace('if(sq_value!==16383)','if(sq_value!==32767)')
    old="read_reg(24'h403008,sq_value);if(sq_value!==63)"
    if t.count(old)!=4:raise ValueError('all four exact CQ ABI reads required')
    t=t.replace(old,"read_reg(24'h403008,sq_value);if(sq_value!==127)")
    t=once(t,'rq_word==2 ? rq_notification:63','rq_word==2 ? rq_notification:127')
    t=once(t,'wire observed_source_operation=!runtime_zero && (runtime_native_opcode==1 || runtime_native_opcode==3);',
        'wire observed_source_operation=!runtime_zero && (runtime_native_opcode==1 || runtime_native_opcode==3 || runtime_native_opcode==5 || runtime_native_opcode==6);')
    t=once(t,'if(runtime_native_opcode!=1 && runtime_native_opcode!=3)$fatal(1,"large ordinary source opcode");',
        'if(runtime_native_opcode!=1 && runtime_native_opcode!=3 && runtime_native_opcode!=5 && runtime_native_opcode!=6)$fatal(1,"large source opcode");')
    t=once(t,"dut.h_request_done_data[803:796]!==(runtime_native_opcode==1 ? 8'h0a:8'h04)",
        "dut.h_request_done_data[803:796]!==(runtime_native_opcode==1 ? 8'h0a:runtime_native_opcode==5 ? 8'h05:runtime_native_opcode==6 ? 8'h0b:8'h04)")
    if 'force 'in t:raise ValueError('no owner/MR/status/receipt/retirement injection')
    return t
