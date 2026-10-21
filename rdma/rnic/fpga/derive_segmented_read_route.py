# SPDX-License-Identifier: BSD-2-Clause-Views
"""Preserve accepted effective routes across PSN-only QP_TX updates.

The real MR controller REQUIRES zero route fields for QP_TX. Such a command
changes TX PSN, not the previously accepted peer/IP route. Keep all qualified
READ-profile gates and change only the route observer, not controller/HLS/
predictor rules, identity/length limits, clocks, guards or default selection.
"""
import derive_segmented_read_profile as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA


def derive():
    out=parent.derive();p=RTL/'rocev2_controlled_responder.v'
    out[p]=once(out[p],
        'else if(cfg_qp_valid && cfg_qp_ready)begin\n'
        '  tx_route_valid<=cfg_qp_tx_only || cfg_qp_pd!=0;',
        'else if(cfg_qp_valid && cfg_qp_ready && !cfg_qp_tx_only)begin\n'
        '  tx_route_valid<=cfg_qp_pd!=0;')
    return out
