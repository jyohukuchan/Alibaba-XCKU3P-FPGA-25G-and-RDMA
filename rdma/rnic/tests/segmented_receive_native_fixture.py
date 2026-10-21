# SPDX-License-Identifier: BSD-2-Clause-Views
"""All32 unchanged native regression oracles on the new receive source profile.

Change only expected exact RNC/RQC/CQC identities. Actual output, payload,
owner, DMA, nonce, MAC, CQ and cardinality assertions are not normalized or
weakened. This fixture does not yet add large incoming receive execution.
"""
import segmented_immediate_native_fixture as parent

ROOT=parent.ROOT;once=parent.once


def __getattr__(name):return getattr(parent,name)


verify_large=parent.clone(parent.wire.verify_large,[('[0,0,0,15,748,0xa0]','[0,0,0,255,748,0xa0]')])
verify_large_read=parent.clone(parent.read.verify_large_read,[('[0,0,0,63,748,0xa0]','[0,0,0,255,748,0xa0]')])
verify_rq=parent.profile.clone(parent.profile.rq.verify,'[0,flags,imm,15]','[0,flags,imm,255]')
verify_atomic=parent.profile.clone(parent.profile.atomic.verify,'[0,0,0,15,748,0xa0]','[0,0,0,255,748,0xa0]')
verify_zero=parent.profile.clone(parent.profile.zero.verify_zero,'[0,0,0,15,748,0xa0]','[0,0,0,255,748,0xa0]')
verify_large_immediate=parent.clone(parent.wire.verify_large,[
    ('    wanted=[1,15,0,0x89abcdef,0xfedcba98]',
     '    owner|=get(48,4)<<588\n    wanted=[1,15,0,0x89abcdef,0xfedcba98]'),
    ('[0,0,0,15,748,0xa0]','[0,0,0,255,748,0xa0]')])


def bench():
    t=parent.bench()
    if t.count('if(sq_value!==32767)')!=2 or t.count("read_reg(24'h403008,sq_value);if(sq_value!==127)")!=4:
        raise ValueError('all exact original native identity assertions required')
    t=t.replace('if(sq_value!==32767)','if(sq_value!==65535)')
    t=t.replace("read_reg(24'h403008,sq_value);if(sq_value!==127)","read_reg(24'h403008,sq_value);if(sq_value!==255)")
    t=once(t,"read_reg(24'h405008,sq_value);if(sq_value!==15)","read_reg(24'h405008,sq_value);if(sq_value!==31)")
    return once(t,'rq_word==2 ? rq_notification:127','rq_word==2 ? rq_notification:255')
