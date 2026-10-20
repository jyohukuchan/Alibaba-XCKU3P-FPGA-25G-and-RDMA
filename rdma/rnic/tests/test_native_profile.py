# SPDX-License-Identifier: BSD-2-Clause-Views
"""Separate native copy/patch safety, not synthesis or hardware evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('prepare_native',ROOT/'rdma/rnic/fpga/prepare_native.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)


class NativeProfileTests(unittest.TestCase):
    def test_copy_patch_preserves_originals_and_connects_actual_parent(self):
        before={p:profile.digest(ROOT/p) for p,_ in profile.INPUTS.values()}
        with tempfile.TemporaryDirectory(prefix='as02-native-profile-') as directory:
            output=Path(directory)/'new'
            result=profile.prepare(output)
            self.assertTrue(result['pass_test']);self.assertFalse(result['board_built'])
            self.assertEqual(result['source_sha256'],before)
            parent=(output/'mqnic_core_pcie.v').read_text()
            self.assertIn('.status_rd_busy(rnic_parent_rd_busy)',parent)
            self.assertIn('.status_wr_busy(rnic_parent_wr_busy)',parent)
            self.assertIn('.parent_dma_drained(rnic_parent_drained)',parent)
            core=(output/'mqnic_core.v').read_text()
            self.assertIn('.parent_dma_drained(rnic_app_parent_drained)',core)
            self.assertIn('!(|if_data_dma_read_desc_status_valid)',core)
            app=(output/'mqnic_app_block.v').read_text()
            self.assertIn('rocev2_native_endpoint #(',app)
            self.assertNotIn('assign m_axis_data_dma_read_desc_valid =',app)
            self.assertIn('.m_dma_read_valid(m_axis_data_dma_read_desc_valid)',app)
            self.assertIn('rocev2_parent_rx_admission parent_rx_admission',app)
            self.assertIn('.s_axis_mac_rx_tvalid(rnic_rx_valid)',app)
            self.assertIn('assign ctrl_dma_ram_wr_cmd_ready = 0;',app)
            self.assertIn('assign ctrl_dma_ram_wr_done = 0;',app)
            self.assertIn('assign ctrl_dma_ram_rd_resp_valid = 0;',app)
            self.assertIn('DMA_TAG_WIDTH!=16',app)
            config=(output/'config_25g.tcl').read_text()
            self.assertIn('dict set params DMA_TAG_WIDTH "19"',config)
            self.assertIn('dict set params APP_ID "32\'h41534e31"',config)
        self.assertEqual(before,{p:profile.digest(ROOT/p) for p in before})

    def test_existing_directory_refused_without_writes(self):
        with tempfile.TemporaryDirectory(prefix='as02-native-existing-') as directory:
            path=Path(directory);before=list(path.iterdir())
            with self.assertRaises(ValueError):profile.prepare(path)
            self.assertEqual(before,list(path.iterdir()))

    def test_changed_immutable_input_rejected_before_output_created(self):
        original=profile.INPUTS
        try:
            profile.INPUTS=dict(original)
            source,_=profile.INPUTS['mqnic_core.v']
            profile.INPUTS['mqnic_core.v']=(source,'0'*64)
            with tempfile.TemporaryDirectory(prefix='as02-native-mismatch-') as directory:
                path=Path(directory)/'new'
                with self.assertRaises(ValueError):profile.prepare(path)
                self.assertFalse(path.exists())
        finally:profile.INPUTS=original

    def test_patch_target_set_is_narrow_and_known(self):
        headers=[line for line in profile.PATCH.read_text().splitlines() if line.startswith(('--- ','+++ '))]
        expected={prefix+name for name in profile.INPUTS for prefix in ['--- a/','+++ b/']}
        self.assertEqual(set(headers),expected);self.assertEqual(len(headers),len(expected))
