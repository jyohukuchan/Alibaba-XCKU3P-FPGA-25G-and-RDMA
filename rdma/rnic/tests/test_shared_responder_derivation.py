# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact checked responder derivation, NOT HLS/runtime/physical qualification."""
import hashlib
import json
import os
from pathlib import Path
import re
import unittest

import probe_shared_hls_roles as probe

ROOT=probe.ROOT
derive=probe.derive


class SharedDerivationTests(unittest.TestCase):
    reports={}

    def evidence(self,**extra):
        paths=[derive.ORIGINAL,derive.SHARED,Path(derive.__file__).resolve(),Path(probe.__file__).resolve(),Path(__file__).resolve()]
        self.reports[self._testMethodName]=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths},**extra)

    def test_every_noninterface_protection_byte_roundtrips_exactly(self):
        original=derive.ORIGINAL.read_text();before=hashlib.sha256(original.encode()).hexdigest()
        text=derive.derive(original)
        text=derive.once(text,'module rocev2_shared_protected_responder #(','module rocev2_protected_responder #(')
        text=derive.once(text,'    output reg [31:0] rx_integrity_drop_count=0,\n'+derive.LOCAL_PORTS+'\n);',
            '    output reg [31:0] rx_integrity_drop_count=0\n);')
        text=derive.once(text,'local_work_guard || (|local_hls_queue_guard) || s_local_mr_request_valid',
            'local_work_guard || s_local_mr_request_valid')
        a=text.index('rocev2_shared_hls_transport transport (');b=text.index(');',a)+2
        c=original.index('rocev2_integrity_transport transport (');d=original.index(');',c)+2
        text=text[:a]+original[c:d]+text[b:]
        text=derive.once(text,'if(core_rx_bad!=0 || core_tx_bad!=0 || core_overflow!=0 || shared_hls_fault ||',
            'if(core_rx_bad!=0 || core_tx_bad!=0 || core_overflow!=0 ||')
        text=derive.once(text,'initial if(!LOCAL_WQE_ENABLE)$fatal(1,"shared transport requires SAME local MR protection");\n','')
        self.assertEqual(text,original)
        self.assertEqual(before,hashlib.sha256(derive.ORIGINAL.read_bytes()).hexdigest())
        self.evidence(all_noninterface_original_bytes_equal=True)

    def test_same_single_MR_and_single_HLS_boundary_not_extra_transport(self):
        text=derive.derive(derive.ORIGINAL.read_text())
        self.assertEqual(text.count('rocev2_shared_hls_transport transport ('),1)
        self.assertNotIn('rocev2_integrity_transport transport (',text)
        self.assertEqual(text.count('rocev2_mr_table #('),1)
        self.assertEqual(len(re.findall(r'\brocev2_integrity_transport\s+#',derive.SHARED.read_text())),1)
        self.assertIn('initial if(!LOCAL_WQE_ENABLE)$fatal',text)
        self.evidence(single_MR_and_core_boundary=True)

    def test_all_local_ports_are_exact_and_guard_does_not_depend_on_idle(self):
        names=set(re.findall(r'\b(?:input|output) wire (?:\[[^]]+\] )?(\w+)',derive.LOCAL_PORTS))
        actual={n for _,_,n in probe.ports(derive.SHARED.read_text())}
        self.assertTrue(names<=actual)
        text=derive.derive(derive.ORIGINAL.read_text())
        self.assertIn('local_work_guard || (|local_hls_queue_guard) || s_local_mr_request_valid',text)
        self.assertIn('local_core_drained===1\'b1',derive.SHARED.read_text())
        self.evidence(local_ports=len(names),real_core_drain_still_required=True)

    def test_missing_or_ambiguous_derivation_anchors_are_rejected(self):
        source=derive.ORIGINAL.read_text()
        anchors=['module rocev2_protected_responder #(','    output reg [31:0] rx_integrity_drop_count=0\n);',
            'local_work_guard || s_local_mr_request_valid','rocev2_integrity_transport transport (',
            '.clk(clk),.rst(rst),','if(core_rx_bad!=0 || core_tx_bad!=0 || core_overflow!=0 ||','localparam COLLECT=0,']
        count=0
        for a in anchors:
            if a=='.clk(clk),.rst(rst),':
                i=source.index('rocev2_integrity_transport transport (')
                changed=source[:i]+source[i:].replace(a,'removed_anchor',1)
            else:changed=source.replace(a,'removed_anchor',1)
            with self.assertRaises((ValueError,IndexError)):derive.derive(changed)
            count+=1
        self.evidence(rejected_changed_anchors=count)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_SHARED_DERIVATION_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            r=dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,
                actual_HLS_behavior=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(r,indent=2)+'\n')


if __name__=='__main__':unittest.main()
