# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact8191/31 fixture and independent CQ oracles, same29 data tests.

Only expected capability fields change. Never normalize observed snapshots,
rewrite a result, or weaken full-owner/data/CRC/nonce/receipt/tail gates.
Physical endpoints remain models; this is not actual Linux/API execution.
"""
import ast
import inspect
import segmented_wire_native_fixture as parent
import zero_rq_native_fixture as rq
import probe_atomic128_native_full as atomic
import probe_zero_native_full as zero

ROOT=parent.ROOT;once=parent.once


def __getattr__(name):return getattr(parent,name)


def clone(function,old,new):
    t=once(inspect.getsource(function),old,new);ast.parse(t)
    namespace=dict(function.__globals__)
    exec(compile(t,__file__+':'+function.__name__,'exec'),namespace)
    return namespace[function.__name__]


verify_large=clone(parent.verify_large,'[0,0,0,15,748,0xa0]','[0,0,0,31,748,0xa0]')
verify_rq=clone(rq.verify,'[0,flags,imm,15]','[0,flags,imm,31]')
verify_atomic=clone(atomic.verify,'[0,0,0,15,748,0xa0]','[0,0,0,31,748,0xa0]')
verify_zero=clone(zero.verify_zero,'[0,0,0,15,748,0xa0]','[0,0,0,31,748,0xa0]')


def bench():
    t=parent.bench()
    if t.count('if(sq_value!==4095)')!=2:raise ValueError('both actual complete RNC reads required')
    t=t.replace('if(sq_value!==4095)','if(sq_value!==8191)')
    old="read_reg(24'h403008,sq_value);if(sq_value!==15)"
    if t.count(old)!=3:raise ValueError('all three actual CQ capability reads required')
    t=t.replace(old,"read_reg(24'h403008,sq_value);if(sq_value!==31)")
    return once(t,'rq_word==2 ? rq_notification:15','rq_word==2 ? rq_notification:31')
