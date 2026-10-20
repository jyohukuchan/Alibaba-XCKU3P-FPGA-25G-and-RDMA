# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthetic patch/snapshot-scope tests, NOT HLS reset/function evidence."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'rdma/rnic/hls'))
spec = importlib.util.spec_from_file_location('build_meta_reset_candidate', ROOT/'rdma/rnic/hls/build_meta_reset_profile.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)

FIXTURE = '\n'*251+'''#pragma HLS INLINE off

\tstatic retransMetaEntry meta_table[META_TABLE_SIZE];
#if defined( __VITIS_HLS__)
\t#pragma HLS bind_storage variable=meta_table type=RAM_T2P impl=BRAM
#else
\t#pragma HLS RESOURCE variable=meta_table core=RAM_T2P_BRAM
#endif
\t#pragma HLS DEPENDENCE variable=meta_table inter false

\tretransMetaReq req;

    if (!meta_upd_req.empty())
'''


class MetadataProfileTests(unittest.TestCase):
    def test_only_allowed_file_changes_in_new_copy(self):
        with tempfile.TemporaryDirectory(prefix='as02-meta-profile-') as directory:
            original = Path(directory)/'original'
            copy = Path(directory)/'copy'
            for base in [original, copy]:
                p = base/candidate.TARGET
                p.parent.mkdir(parents=True)
                p.write_text(FIXTURE)
                (base/'other.hpp').write_text('unchanged fixture')
            before = candidate.digest(original/candidate.TARGET)
            hashes, log = candidate.patch_copy(copy)
            self.assertEqual(candidate.digest(original/candidate.TARGET), before)
            self.assertEqual(hashes['other.hpp'], candidate.digest(original/'other.hpp'))
            self.assertEqual(set(hashes), {candidate.TARGET, 'other.hpp'})
            modified = (copy/candidate.TARGET).read_text()
            self.assertIn('HLS reset variable=meta_table off', modified)
            self.assertIn('HLS reset variable=clear_complete', modified)
            self.assertIn('clear_index == META_TABLE_SIZE - 1', modified)
            self.assertLess(modified.index('if (!clear_complete)'), modified.index('if (!meta_upd_req.empty())'))
            for field in ['psn', 'next', 'opCode', 'localAddr', 'remoteAddr', 'length', 'lst', 'offs', 'valid', 'isTail']:
                self.assertIn('zero.'+field+' = ', modified)
            self.assertIn('patching file '+candidate.TARGET, log)

    def test_unlisted_patch_target_refused_before_mutation(self):
        with tempfile.TemporaryDirectory(prefix='as02-meta-target-') as directory:
            base = Path(directory)
            bad_patch = base/'bad.patch'
            bad_patch.write_text(candidate.PATCH.read_text().replace(candidate.TARGET, 'elsewhere.hpp'))
            before = {p.name: candidate.digest(p) for p in base.iterdir()}
            with patch.object(candidate, 'PATCH', bad_patch), patch.object(candidate.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    candidate.patch_copy(base)
                run.assert_not_called()
            self.assertEqual(before, {p.name: candidate.digest(p) for p in base.iterdir()})

    def test_extra_patch_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='as02-meta-artifact-') as directory:
            base = Path(directory)
            p = base/candidate.TARGET
            p.parent.mkdir(parents=True)
            p.write_text(FIXTURE)
            real_run = candidate.subprocess.run
            def extra_artifact(*args, **kwargs):
                result = real_run(*args, **kwargs)
                (base/'unexpected.txt').write_text('synthetic unwanted patch artifact')
                return result
            with patch.object(candidate.subprocess, 'run', side_effect=extra_artifact):
                with self.assertRaises(ValueError):
                    candidate.patch_copy(base)
