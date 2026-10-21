# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual ACK owner/tag/EOF/tail leaf for the separate message-RQ cohort.

Exact per-packet proof/PSN/MSN/Immediate fields stay unchanged on the wire.
Packet release now frees only ACK ownership; message_queue still retains
the posted RQ through genuine whole-message CQ commit/retire. This leaf
alone does not select/qualify a whole native graph or change old defaults.
"""
import derive_segmented_immediate as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
ACK=RTL/'rocev2_receive_ack_tx.v'


def derive():
    out=parent.derive();t=out[ACK]
    t=once(t,'s_owner_context[307:276]<=4096','s_owner_context[307:276]<=1048576')
    t=once(t,'(core_notification_flags==0 || core_notification_flags==1 || core_notification_flags==3)',
        '(core_notification_flags==0 || core_notification_flags==1 || core_notification_flags==3 ||\n'
        '      core_notification_flags==4 || core_notification_flags==8 || core_notification_flags==16 || core_notification_flags==17)')
    t=once(t,'(core_notification_flags!=0 || core_notification==0)',
        '((core_notification_flags&1)!=0 || core_notification==0)')
    t=once(t,'// a replacement CRC engine or a whole-core/requester drain certificate.',
        '// a replacement CRC engine or a whole-core/requester drain certificate.\n'
        '// In this cohort s_retire releases ONLY this packet ACK slot. The\n'
        '// genuine message RQ owner stays held through whole CQ commit/retire.')
    return t
