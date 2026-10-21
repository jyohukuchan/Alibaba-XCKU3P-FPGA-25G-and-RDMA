# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same native40 checks; hold only the partial case's genuine FIRST MAC.

The access case has no positive FIRST: holding tag6001 forever holds its NAK
receipt and correctly prevents abort. Keep partial1100/local71/selected71
stalls. A separate test-control actor avoids one giant simulator coroutine;
its finished flag is NOT a DUT, wire, cancel, CQ, drain or unpin certificate.
"""
import write_fatal_native_fixture as parent

ROOT=parent.ROOT;once=parent.once
ACTOR=r'''
reg wrfatal_start=0,wrfatal_finished=0;
initial begin
 wait(wrfatal_start===1'b1);
 run_write_fatal_native();
 wrfatal_finished=1;
end
'''


def __getattr__(name):return getattr(parent,name)


def bench():
    t=parent.bench()
    t=once(t,'reg runtime_write_fatal=0,wrfatal_partial=0;',
        'reg runtime_write_fatal=0,wrfatal_partial=0;\n'+ACTOR)
    t=once(t,'reject_ready=0;m_write_fatal_selected_ready=0;lrx_hold_final_MAC=1;',
        'reject_ready=0;m_write_fatal_selected_ready=0;lrx_hold_final_MAC=wrfatal_partial;')
    return once(t,'requester_wire_mode=1;if(runtime_write_fatal)run_write_fatal_native();else run_large_write_native();',
        "requester_wire_mode=1;if(runtime_write_fatal)begin wrfatal_start=1;wait(wrfatal_finished===1'b1);end else run_large_write_native();")
