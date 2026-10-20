# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual raw RX reference capture includes immutable four-bit QP permission.

Adjacent checker outcomes, network input and trusted binding are models.
Retain all six original reference/accounting/fault methods; no drain bypass.
The separate actual SQC binding and whole-native tests cover their own scope.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import test_atomic_native_rx_rtl as old
import sys

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic_access_native as source
digest=old.digest


class AtomicAccessRXRefsTests(old.NativeRXTests):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.artifacts=Path(tempfile.mkdtemp(prefix='atomic-access-refs-',dir=ROOT/'rdma/rnic/build'))
        cls.original_rtl=old.RTL;old.RTL=cls.artifacts
        (cls.artifacts/'rocev2_native_rx_refs.v').write_text(source.derive()[source.REFS])
        cls.before={str(p.relative_to(ROOT)):digest(p)for p in
            [source.REFS,Path(source.__file__).resolve(),Path(old.__file__).resolve(),Path(__file__).resolve()]}

    def refs(self,body):
        self.simulate('rocev2_native_rx_refs',
            f"enable=1;trusted_valid=1;trusted_context=356'h{(14<<352)|old.CONTEXT:089x};s_keep=16'hffff;\n"+body)

    def test_permission_is_captured_at_first_offer_even_before_ready(self):
        self.refs(r'''
s_valid=1;m_ready=0;@(negedge clk);
trusted_valid=0;trusted_context[355:352]=6;enable=0;
repeat(9)begin @(negedge clk);
 if(!m_valid || held_context[355:352]!==14 || references || !configuration_guard || fault)
  $fatal(1,"stalled first-offer permission retracted or replaced");
end
m_ready=1;s_last=1;@(negedge clk);s_valid=0;
if(held_context[355:352]!==14 || references!==1 || fault)$fatal(1,"offered permission not accepted unchanged");
checked_eof=1;@(negedge clk);checked_eof=0;
''')

    def test_RW_only_permission_is_accepted_but_permission_changes_with_live_refs_fault(self):
        self.refs(r'''
trusted_context[355:352]=6;m_ready=1;s_last=1;s_valid=1;@(negedge clk);s_valid=0;
if(held_context[355:352]!==6 || references!==1 || fault)$fatal(1,"RW-only general RX was blocked");
trusted_context[355:352]=14;s_valid=1;@(negedge clk);s_valid=0;#1;
if(!fault || m_valid || references!==1 || held_context[355:352]!==6 || queue_guard!==255)
 $fatal(1,"in-flight permission gained Atomic authority");
''')

    def test_unknown_permission_cannot_acquire_a_raw_RX_reference(self):
        self.refs(r'''
trusted_context[355:352]=4'hx;m_ready=1;s_valid=1;s_last=1;@(negedge clk);#1;
if(!fault || m_valid || s_ready || references || held_context || queue_guard!==255)
 $fatal(1,"unknown permission gained a checker reference");
''')

    @classmethod
    def tearDownClass(cls):
        old.RTL=cls.original_rtl
        if cls.before!={n:digest(ROOT/n)for n in cls.before}:raise ValueError('source changed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    cls=AtomicAccessRXRefsTests
    names=[n for n in unittest.defaultTestLoader.getTestCaseNames(cls)if n not in
        ['test_complete_header_and_body_route_without_byte_changes_under_backpressure',
         'test_short_unknown_or_malformed_header_does_not_offer_output',
         'test_parent_fault_does_not_withdraw_already_owned_header']]
    # The router is unchanged; select precisely the six reference methods
    # and three new permission methods, never silently omit a renamed test.
    names=[n for n in names if n in [
        'test_offered_reference_drains_under_pause_and_context_query_unavailable',
        'test_simultaneous_acquire_and_two_actual_checker_outcomes',
        'test_new_context_only_after_actual_last_reference_release',
        'test_invalid_unknown_alias_or_changed_context_fails_closed',
        'test_reference_underflow_unknown_outcomes_and_parent_fault_retain_guard',
        'test_reference_count_never_wraps_at_finite_capacity',
        'test_permission_is_captured_at_first_offer_even_before_ready',
        'test_RW_only_permission_is_accepted_but_permission_changes_with_live_refs_fault',
        'test_unknown_permission_cannot_acquire_a_raw_RX_reference']]
    if len(names)!=9:raise ValueError('all original reference and new permission methods required')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cls(n)for n in names))
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,
        simulations=sum(map(len,cls.reports.values())),seconds=time.monotonic()-start,tests=cls.reports,
        source_sha256=cls.before,artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in cls.artifacts.iterdir()if p.is_file()},
        checker_binding_and_network_endpoints_modeled=True,native_integrated=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
