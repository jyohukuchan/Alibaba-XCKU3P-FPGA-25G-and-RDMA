# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short reproducible Atomic feature composition; physical boundary models."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import probe_atomic_responder as probe


class AtomicResponderTests(unittest.TestCase):
    def test_wire_atomic_MR_exclusive_paged_RMW_replay_and_failure_composition(self):
        with tempfile.TemporaryDirectory(prefix='as02-atomic-report-')as directory:
            report=Path(directory)/'report.json'
            result=subprocess.run([sys.executable,str(Path(probe.__file__).resolve()),
                '--report',str(report)],cwd=probe.ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(report.read_text())
            self.assertTrue(data['pass_test']);self.assertEqual(len(data['tests']),14)
            self.assertTrue(all(v==1 for v in data['actual_elaborated_module_counts'].values()))
            self.assertFalse(data['native_integrated']);self.assertFalse(data['hardware_verified'])
            for case,record in data['tests'].items():
                with self.subTest(case=case):
                    self.assertEqual(record['exit_code'],0)
                    self.assertTrue(record['summary']['pass_test'])
                    self.assertLess(record['seconds'],30)
                    self.assertTrue(all(x['wire_oracle_pass']for x in record['independent_wire_replies']))


if __name__=='__main__':unittest.main()
