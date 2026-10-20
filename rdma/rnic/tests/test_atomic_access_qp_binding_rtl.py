# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQC owner/epoch/cookie binding retains separate QP access flags.

Reuse ALL prior ownership tests plus access snapshot/canonical/lease cases.
Network configuration and downstream guards/physical DMA remain models.
No default or prior proof-bound source is rewritten; no hardware is opened.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import test_atomic_qp_binding_rtl as old
import derive_atomic_access_native as source

ROOT=old.ROOT;digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


class AtomicAccessQPBindingTests(old.AtomicQPBindingTests):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.artifacts=Path(tempfile.mkdtemp(prefix='atomic-access-binding-',dir=ROOT/'rdma/rnic/build'))
        cls.original_rtl=old.RTL;cls.original_tasks=old.TASKS
        old.RTL=cls.artifacts/'rocev2_atomic_qp_binding.v';old.RTL.write_text(source.binding())
        old.TASKS=source.once(old.TASKS,'  p_cfg_peer_qpn=',
            "  p_cfg_access=txonly || pd==0 ? 4'd0:desired_access;\n  p_cfg_peer_qpn=")
        old.TASKS=source.once(old.TASKS,'p_bound_epoch!==epoch ||',
            'p_bound_access!==desired_access || p_bound_epoch!==epoch ||')
        old.TASKS="reg [3:0] desired_access=14;\ninitial begin p_cfg_access=14;end\n"+old.TASKS
        cls.inputs=[cls.original_rtl,source.CONTROL,Path(source.__file__).resolve(),Path(__file__).resolve(),Path(old.__file__).resolve()]
        cls.before={str(p.relative_to(ROOT)):digest(p)for p in cls.inputs}

    def test_RW_only_QP_still_admits_general_RX_and_preserves_permission_on_TX(self):
        self.simulate(r'''
allocate();desired_access=6;route(7,17,0);bound(64'h9123456700000001,64'hfedcba9889abcdef);
route(6,19,1);bound(64'h9123456700000001,64'hfedcba9889abcdef);
p_cfg_access=14;p_cfg_qpn=1;p_cfg_pd=19;
repeat(10)@(negedge clk);
if(p_bound_access!==6 || !p_admission_valid || p_fault)$fatal(1,"live config inputs replaced accepted RW-only permission");
''')

    def test_live_permission_snapshot_changes_only_on_drained_config_handshake(self):
        self.simulate(r'''
allocate();route(7,17,0);p_lease_guard=1;
p_cfg_qpn=7;p_cfg_pd=17;p_cfg_access=6;p_cfg_valid=1;
repeat(9)@(negedge clk);
if(p_cfg_binding_ready || p_bound_access!==14 || !p_bound_valid || p_fault || wire_queue_guard!==128)
 $fatal(1,"live QP permission changed while actual downstream lease retained");
p_cfg_valid=0;p_lease_guard=0;desired_access=6;route(7,17,0);
bound(64'h9123456700000001,64'hfedcba9889abcdef);
route(7,0,0);
if(p_bound_access || p_bound_epoch || p_bound_cookie || p_admission_valid)$fatal(1,"drained tombstone retained permission");
''')

    def test_noncanonical_or_unknown_permission_never_replaces_binding(self):
        for value in ["4'h0","4'h1","4'h2","4'h4","4'h7","4'h8","4'hf","4'hx"]:
            with self.subTest(access=value):self.simulate(r'''
allocate();route(7,17,0);p_cfg_qpn=7;p_cfg_pd=17;p_cfg_valid=1;
p_cfg_access='''+value+r''';
repeat(9)@(negedge clk);
if(p_cfg_binding_ready || p_bound_access!==14 || p_bound_epoch!==64'h9123456700000001 || p_fault)
 $fatal(1,"noncanonical or unknown per-QP permission acquired authority");
''')

    def test_TX_and_tombstone_require_zero_permission_without_revoking_RX(self):
        for pd,tx in [(17,1),(0,0)]:
            with self.subTest(pd=pd,tx=tx):self.simulate(r'''
allocate();route(7,17,0);p_cfg_qpn=7;p_cfg_valid=1;p_cfg_access=14;
'''+f'p_cfg_pd={pd};p_cfg_tx_only={tx};'+r'''
repeat(9)@(negedge clk);
if(p_cfg_binding_ready || p_bound_access!==14 || !p_bound_valid || p_fault)
 $fatal(1,"nonzero TX/tombstone permission corrupted RX binding");
''')

    @classmethod
    def tearDownClass(cls):
        old.RTL=cls.original_rtl;old.TASKS=cls.original_tasks
        if cls.before!={n:digest(ROOT/n)for n in cls.before}:raise ValueError('consumed source changed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AtomicAccessQPBindingTests))
    cls=AtomicAccessQPBindingTests
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,
        simulations=sum(map(len,cls.reports.values())),seconds=time.monotonic()-start,tests=cls.reports,
        source_sha256=cls.before,artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in cls.artifacts.iterdir()if p.is_file()},
        actual_SQC_mailbox_fetch_owner_arrays=True,native_integrated=False,hardware_verified=False,
        configuration_and_downstream_lease_and_physical_DMA_modeled=True)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
