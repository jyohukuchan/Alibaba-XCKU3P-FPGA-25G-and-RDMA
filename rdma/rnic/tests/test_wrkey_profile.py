# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthetic per-WR patch scope/refusal checks; NOT HLS functionality."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'rdma/rnic/hls'))
import prepare_wrkey_profile as profile


class WRKeyProfileTests(unittest.TestCase):
    def test_unlisted_target_rejected_before_any_command(self):
        with tempfile.TemporaryDirectory(prefix='as02-wrkey-scope-') as directory:
            base = Path(directory)
            bad = base/'bad.patch'
            bad.write_text(profile.PATCH.read_text().replace(profile.TARGETS[0], 'outside.hpp'))
            with patch.object(profile, 'PATCH', bad), patch.object(profile.subprocess, 'run') as run:
                with self.assertRaises(ValueError): profile.patch_copy(base)
                run.assert_not_called()

    def test_failed_dry_run_never_runs_mutating_patch(self):
        with tempfile.TemporaryDirectory(prefix='as02-wrkey-dry-') as directory:
            base = Path(directory)
            (base/'untouched').write_text('synthetic sentinel')
            with patch.object(profile.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'patch')) as run:
                with self.assertRaises(subprocess.CalledProcessError): profile.patch_copy(base)
                self.assertEqual(run.call_count, 1)
                self.assertIn('--dry-run', run.call_args.args[0])
            self.assertEqual((base/'untouched').read_text(), 'synthetic sentinel')

    def test_exact_change_set_required_and_extra_artifact_refused(self):
        for extra in [False, True]:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory(prefix='as02-wrkey-copy-') as directory:
                base = Path(directory)
                for name in profile.TARGETS:
                    p = base/name; p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('synthetic original')
                def command(args, **kwargs):
                    if '--dry-run' not in args:
                        for name in profile.TARGETS: (base/name).write_text('synthetic changed')
                        if extra: (base/'unexpected.orig').write_text('synthetic extra')
                    return subprocess.CompletedProcess(args, 0, 'synthetic command result', '')
                with patch.object(profile.subprocess, 'run', side_effect=command):
                    if extra:
                        with self.assertRaises(ValueError): profile.patch_copy(base)
                    else:
                        values, _ = profile.patch_copy(base)
                        self.assertEqual(set(values), set(profile.TARGETS))


if __name__ == '__main__':
    unittest.main()
