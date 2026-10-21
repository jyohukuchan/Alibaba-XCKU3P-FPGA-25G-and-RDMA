# SPDX-License-Identifier: BSD-2-Clause-Views
"""Identical36 actual native tests with explicitly different expected CSR IDs.

Change only EXPECTED RNC/RQC/CQC constants, never observed events/bytes.
No tuple normalization, no gate/clock/oracle/deadline/geometry relaxation.
"""
import segmented_write_payload_native_fixture as parent
import segmented_immediate_native_fixture as original

ROOT=parent.ROOT;once=parent.once;clone=original.clone


def __getattr__(name):return getattr(parent,name)


verify_large=clone(original.wire.verify_large,[('[0,0,0,15,748,0xa0]','[0,0,0,511,748,0xa0]')])
verify_large_read=clone(original.read.verify_large_read,[('[0,0,0,63,748,0xa0]','[0,0,0,511,748,0xa0]')])
verify_rq=original.profile.clone(original.profile.rq.verify,'[0,flags,imm,15]','[0,flags,imm,511]')
verify_atomic=original.profile.clone(original.profile.atomic.verify,'[0,0,0,15,748,0xa0]','[0,0,0,511,748,0xa0]')
verify_zero=original.profile.clone(original.profile.zero.verify_zero,'[0,0,0,15,748,0xa0]','[0,0,0,511,748,0xa0]')
verify_large_immediate=clone(original.wire.verify_large,[
    ('    wanted=[1,15,0,0x89abcdef,0xfedcba98]','    owner|=get(48,4)<<588\n    wanted=[1,15,0,0x89abcdef,0xfedcba98]'),
    ('[0,0,0,15,748,0xa0]','[0,0,0,511,748,0xa0]')])
verify_large_receive=clone(parent.parent.verify_large_receive,[('[LENGTH,int(opcode==5),immediate,255]','[LENGTH,int(opcode==5),immediate,511]')])
verify_large_write=clone(parent.verify_large_write,[('[8193,3,0x89abcdef,255]','[8193,3,0x89abcdef,511]')])


def bench():
    t=parent.bench()
    if t.count('if(sq_value!==65535)')!=2 or t.count("read_reg(24'h403008,sq_value);if(sq_value!==255)")!=6:
        raise ValueError('every original actual identity assertion must remain')
    t=t.replace('if(sq_value!==65535)','if(sq_value!==131071)')
    t=t.replace("read_reg(24'h403008,sq_value);if(sq_value!==255)","read_reg(24'h403008,sq_value);if(sq_value!==511)")
    t=once(t,"read_reg(24'h405008,sq_value);if(sq_value!==31)","read_reg(24'h405008,sq_value);if(sq_value!==63)")
    return once(t,'rq_word==2 ? rq_notification:255','rq_word==2 ? rq_notification:511')
