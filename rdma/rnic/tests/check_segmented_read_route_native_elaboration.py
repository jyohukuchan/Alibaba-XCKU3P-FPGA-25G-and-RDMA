#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact complete READ graph with qualified effective-route QP_TX observer.

Reuse every original READ-profile elaboration/identity/width/domain/clock/
drain/module-count gate; source adapter adds actual-controller route proof.
This is compile-only, not native data/CQ or physical execution.
"""
import check_segmented_read_profile_native_elaboration as checked
import segmented_read_route_native_sources as source


if __name__=='__main__':
    checked.source=source
    checked.__doc__=__doc__
    checked.main()
