#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual complete Atomic128/QP-access graph, compile-only, no hardware proof.

Reuse the strict complete-native multiplicity/ABI/drain verifier, selecting
the new29-module private cohort. No default source or prior proof is changed.
The original full native clocks, capacities and free-space guard remain.
"""
import atomic_access_native_sources as source
import check_atomic128_native_elaboration as checked


if __name__=='__main__':
    checked.source=source
    checked.__doc__=__doc__
    checked.main()
