# SPDX-License-Identifier: BSD-2-Clause-Views
"""Board selection/snapshot tests. Synthetic files are NOT FPGA evidence."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
board=load('rnic_prepare_board',ROOT/'rdma/rnic/fpga/prepare_board.py')
native=load('rnic_prepare_native_for_board',ROOT/'rdma/rnic/fpga/prepare_native.py')


class BoardAnalysisTests(unittest.TestCase):
    def test_metadata_reset_evidence_must_cover_all_entries_and_interrupted_reset(self):
        valid=dict(pass_test=True,terminal_exit_status=0,sequential_initialization_required=True,
            inputs_unchanged=True,checks=8024,zero_checks=4023,data_checks=2000,append_checks=2001,reset_checks=16)
        board.metadata_reset_proof(valid)
        for field,value in [('pass_test',False),('terminal_exit_status',1),('sequential_initialization_required',False),
                            ('inputs_unchanged',False),('checks',8023),('zero_checks',4022),('data_checks',1999),
                            ('append_checks',2000),('reset_checks',15)]:
            with self.assertRaises(ValueError):board.metadata_reset_proof(dict(valid,**{field:value}))

    def test_two_state_or_altered_assertions_cannot_stand_in_for_metadata_wire_evidence(self):
        board.four_state_proof(dict(four_state_simulation=True,original_testbench_assertions_preserved=True))
        for r in [{},dict(four_state_simulation=False,original_testbench_assertions_preserved=True),
                  dict(four_state_simulation=True,original_testbench_assertions_preserved=False)]:
            with self.assertRaises(ValueError):board.four_state_proof(r)

    def test_real_pinned_selection_uses_only_actual_native_parents(self):
        with tempfile.TemporaryDirectory(prefix='as02-board-selection-') as directory:
            temp=Path(directory);profile=temp/'profile';native.prepare(profile)
            hls=temp/'hls';rtl=hls/'solution1/syn/verilog';rtl.mkdir(parents=True)
            (rtl/'rocev2_top.v').write_text('module rocev2_top; endmodule\n')
            sources,constraints,ip,data,makefile=board.collect(hls,profile)
            for name in ['mqnic_core.v','mqnic_core_pcie.v','mqnic_app_block.v']:
                self.assertEqual([p for p in sources if p.name==name],[profile/name])
            self.assertIn(ROOT/'fpga/fpga_as02mc04_25g_cdc.v',sources)
            self.assertIn(ROOT/'rdma/rnic/rtl/rocev2_pcie_parent_guard.v',sources)
            self.assertIn(ROOT/'rdma/rnic/rtl/rocev2_parent_rx_admission.v',sources)
            self.assertIn(ROOT/'fpga/mac_flow_control_cdc.xdc',constraints)
            self.assertEqual(len(constraints),13);self.assertEqual(len(ip),3)
            self.assertEqual(data,[]);self.assertEqual(makefile,ROOT/'external/as02mc04-port/Makefile')

    def test_frozen_snapshot_survives_original_change_but_detects_copy_change(self):
        with tempfile.TemporaryDirectory(prefix='as02-board-snapshot-') as directory:
            temp=Path(directory);profile=temp/'profile';profile.mkdir()
            config=profile/'config_25g.tcl';config.write_text('# fixture only\n')
            source=temp/'data.v';source.write_text('module data;endmodule\n')
            constraint=temp/'fixture.xdc';constraint.write_text('# fixture\n')
            ip=temp/'fixture.tcl';ip.write_text('# fixture\n')
            makefile=temp/'Makefile';makefile.write_text('# fixture\n')
            driver=ROOT/'rdma/rnic/fpga/build_board.tcl';output=temp/'new'
            with (mock.patch.object(board,'verify',return_value=({driver},'fixture-only')),
                  mock.patch.object(board,'collect',return_value=([source],[constraint],[ip],[],makefile))):
                report=board.prepare(output,temp/'hls',profile,temp/'fns',temp/'evidence')
            self.assertFalse(report['release_authorized']);self.assertFalse(report['full_board_physical_gate_passed'])
            frozen=output/'inputs';manifest=frozen/'inputs.sha256'
            subprocess.run(['sha256sum','--check','--status',str(manifest)],cwd=frozen,check=True)
            frozen_source=next(p for p in frozen.rglob('data.v'))
            old=frozen_source.read_bytes();source.write_text('// later source revision, not used by this snapshot\n')
            self.assertEqual(frozen_source.read_bytes(),old)
            environment=dict(os.environ,AS02_RNIC_SOURCE_ONLY='1')
            cmd=['tclsh',report['driver'],str(output)]
            result=subprocess.run(cmd,env=environment,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('IMAGE_AUTHORIZED=0',result.stdout)
            frozen_source.write_text('// corrupt frozen input\n')
            result=subprocess.run(cmd,env=environment,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((output/'project').exists())

    def test_existing_output_refused_before_validation_or_writes(self):
        with tempfile.TemporaryDirectory(prefix='as02-board-existing-') as directory:
            with mock.patch.object(board,'verify',side_effect=AssertionError('must not validate')):
                with self.assertRaises(ValueError):board.prepare(Path(directory),None,None,None,None)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_unsafe_profile_denied_before_HLS_or_output_access(self):
        with tempfile.TemporaryDirectory(prefix='as02-board-profile-') as directory:
            temp=Path(directory);profile=temp/'profile';profile.mkdir()
            r=dict(pass_test=True,board_built=False,output_directory=str(profile),source_sha256={},profile_sha256={},generated_sha256={},
                required_profile=dict(APP_ID='0x41535232',APP_DMA_ENABLE=0,DMA_TAG_WIDTH=16,app_DMA_TAG_WIDTH=13,TX_SEQ_NUM_ENABLE=0))
            (profile/'native-profile.json').write_text(json.dumps(r))
            with mock.patch.dict(board.old_gate.PHYSICAL_INPUTS,{},clear=True):
                with self.assertRaisesRegex(ValueError,'unsafe native DMA'):
                    board.prepare(temp/'out',temp/'missing-hls',profile,temp/'fns',temp/'evidence')
            self.assertFalse((temp/'out').exists())

    def test_Tcl_path_quotes_do_not_execute_substitutions(self):
        value='space $not_a_var [not_a_command] {braces} \\path'
        code='set actual '+board.tcl(value)+'\nif {$actual ne [lindex $argv 0]} {error "path changed"}\n'
        result=subprocess.run(['tclsh','/dev/stdin',value],input=code,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_analysis_driver_has_no_image_programming_or_clock_relaxation(self):
        text=(ROOT/'rdma/rnic/fpga/build_board.tcl').read_text()
        commands='\n'.join(l for l in text.splitlines() if not l.lstrip().startswith('#'))
        self.assertNotRegex(commands,r'\b(write_bitstream|program_hw_devices|program_hw_cfgmem|open_hw_target)\b')
        self.assertIn('full_board_routed.dcp',commands)
        self.assertIn('report_bus_skew',commands);self.assertIn('report_cdc -details',commands)
        self.assertIn('PHYSICAL_RELEASE_AUTHORIZED=0',commands)
        self.assertNotRegex(commands,r'\b(set_false_path|set_multicycle_path|set_clock_groups|create_clock)\b')
