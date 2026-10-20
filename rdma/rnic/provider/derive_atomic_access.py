# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in checked public provider cohort; standard uverbs ABI is unchanged.

Accept new matched RNC2047 as well as existing511/1023. Generic libibverbs
serializes MR/QP permission and Atomic operands, no hardware128 user ABI.
Never install this generated copy or advertise Atomic before qualification.
"""
from pathlib import Path

SOURCE=Path(__file__).resolve().parent/'as02.c'


def once(t,a,b):
    if t.count(a)!=1:raise ValueError('provider derivation anchor changed: '+a)
    return t.replace(a,b)


def derive():
    t=once(SOURCE.read_text(),'#define AS02_FW_IMMEDIATE (((uint64_t)0x10000<<32)|1023U)',
        '#define AS02_FW_IMMEDIATE (((uint64_t)0x10000<<32)|1023U)\n'
        '#define AS02_FW_ATOMIC_ACCESS (((uint64_t)0x10000<<32)|2047U)')
    return once(t,'response.base.fw_ver!=AS02_FW_IMMEDIATE)',
        'response.base.fw_ver!=AS02_FW_IMMEDIATE && response.base.fw_ver!=AS02_FW_ATOMIC_ACCESS)')
