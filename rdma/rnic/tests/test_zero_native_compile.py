# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compiler process ownership only; no RTL/runtime qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import time
import unittest
from unittest import mock
import probe_zero_native_full as probe


class CompilerOwnership(unittest.TestCase):
    def run_owned(self,waits,kill_effect=None):
        process=mock.MagicMock(pid=12345,returncode=0)
        process.wait.side_effect=waits
        context=mock.MagicMock()
        context.__enter__.return_value=process
        with mock.patch.object(probe.subprocess,'Popen',return_value=context) as launch, \
                mock.patch.object(probe.os,'killpg',side_effect=kill_effect) as kill:
            try:
                result=probe.compile_owned(['compiler'],'run','log',{'TMPDIR':'tmp'})
            except subprocess.TimeoutExpired as error:
                result=error
        launch.assert_called_once_with(['compiler'],cwd='run',stdout='log',
            stderr=subprocess.STDOUT,env={'TMPDIR':'tmp'},start_new_session=True)
        return result,process,kill

    def test_normal_exit_keeps_exact_execution_limit_without_signals(self):
        result,process,kill=self.run_owned([0])
        self.assertEqual(result,0)
        process.wait.assert_called_once_with(timeout=1200)
        kill.assert_not_called()

    def test_timeout_kills_owned_descendants_even_if_launcher_exits_first(self):
        timeout=subprocess.TimeoutExpired(['compiler'],1200)
        result,process,kill=self.run_owned([timeout,0,0])
        self.assertIs(result,timeout)
        self.assertEqual(process.wait.call_args_list,[mock.call(timeout=1200),mock.call(timeout=5),mock.call()])
        self.assertEqual(kill.call_args_list,[mock.call(12345,signal.SIGTERM),mock.call(12345,signal.SIGKILL)])

    def test_unresponsive_cleanup_retains_original_timeout(self):
        timeout=subprocess.TimeoutExpired(['compiler'],1200)
        result,process,kill=self.run_owned([timeout,subprocess.TimeoutExpired(['compiler'],5),0])
        self.assertIs(result,timeout)
        self.assertEqual(kill.call_args_list,[mock.call(12345,signal.SIGTERM),mock.call(12345,signal.SIGKILL)])

    def test_already_gone_group_is_not_replaced_by_another_target(self):
        timeout=subprocess.TimeoutExpired(['compiler'],1200)
        result,process,kill=self.run_owned([timeout,0,0],ProcessLookupError())
        self.assertIs(result,timeout)
        self.assertEqual(kill.call_args_list,[mock.call(12345,signal.SIGTERM),mock.call(12345,signal.SIGKILL)])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    if args.report.exists():parser.error('preserve prior evidence')
    paths=[Path(__file__).resolve(),Path(probe.__file__).resolve()]
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    before={str(p.relative_to(probe.ROOT)):digest(p)for p in paths}
    start=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompilerOwnership))
    if before!={n:digest(probe.ROOT/n)for n in before}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,
        seconds=time.monotonic()-start,source_sha256=before,process_and_signals_mocked=True,
        actual_timeout_or_RTL_runtime=False,hardware_changed=False)
    with args.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
