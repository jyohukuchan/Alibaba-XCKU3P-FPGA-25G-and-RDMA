# SPDX-License-Identifier: BSD-2-Clause-Views
"""Existing real requester operations on the matched complete duplex profile.

Unused RQ remains real/present, not substituted with the exclusive core.
No internal drain assignment; all original memory/MAC/CQ checks remain.
"""
import native_request_cq_fixture as parent

send=parent.send
variant=parent.variant
verify=parent.verify

def case(base_case):
    tb,words,records,request=parent.case(base_case)
    once=parent.qp.main.sq.once
    tb=once(tb,'.REQUEST_CQ_ENABLE(1)',
        '.REQUEST_CQ_ENABLE(1),.SEPARATE_RQ_ENABLE(1),.RECV_CANCEL_ENABLE(1),.DUPLEX_ENABLE(1)')
    tb=once(tb,'if(sq_value!==255)$fatal(1,"actual requester CQ capability missing");',
        'if(sq_value!==511)$fatal(1,"actual complete duplex requester capability missing");')
    return tb,words,records,request
