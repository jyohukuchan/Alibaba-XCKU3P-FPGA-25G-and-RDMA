#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state real board TX FIFO/CDC/MAC checks, <=30s per simulation.

Byte-exact XGMII/FCS/tags, slow producer and retained completions; genuine
bad-frame and oversize FIFO errors must remain fatal. Not native RNIC proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import segmented_board_tx_fixture as board

ROOT = board.ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BoardTX(unittest.TestCase):
    reports = {}

    def simulate(self, lengths, gap, expected_error=None):
        run = Path(tempfile.mkdtemp(prefix='segmented-board-tx-', dir=ROOT/'rdma/rnic/build'))
        frames = [bytes((i*37+index*61)&255 for i in range(length)) for index, length in enumerate(lengths)]
        words = []
        for index, frame in enumerate(frames):
            for offset in range(0, len(frame), 16):
                chunk = frame[offset:offset+16]
                last = offset+len(chunk) == len(frame)
                user = ((0x2001+index)<<1) | (expected_error == 'bad' and last)
                words.append(int.from_bytes(chunk, 'little') | ((1<<len(chunk))-1)<<128 | last<<144 | user<<145)
        text = TESTBENCH.replace('LINK_RTL', board.replace_link(board.old.LINK))
        for key, value in dict(WORD_COUNT=len(words), FRAME_COUNT=len(frames), SOURCE_GAP=gap).items():
            text = text.replace(key, str(value))
        (run/'tb.v').write_text(text)
        (run/'input.hex').write_text(''.join(f'{word:041x}\n' for word in words))
        sources = list(dict.fromkeys([*board.old.SOURCES, *board.SOURCES]))
        command = ['iverilog', '-g2012', '-s', 'tb', '-o', str(run/'test'), str(run/'tb.v'), *map(str, sources)]
        c = subprocess.run(command, capture_output=True, text=True, timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        self.assertEqual(c.returncode, 0, c.stdout+c.stderr)
        self.assertFalse(any('expects' in line and 'bits' in line for line in c.stderr.splitlines()), c.stderr)
        start = time.monotonic()
        c = subprocess.run(['vvp', str(run/'test')], cwd=run, capture_output=True, text=True, timeout=30)
        seconds = time.monotonic()-start
        output = c.stdout+c.stderr
        (run/'simulation.log').write_text(output)
        if expected_error:
            self.assertNotEqual(c.returncode, 0, output)
            expected = 'overflow1 bad0' if expected_error == 'oversize' else 'overflow0 bad1'
            self.assertIn('actual board synchronous TX FIFO error '+expected, output)
            self.assertNotIn('ACTUAL_MAC_SFD ', output)
            self.assertNotIn('RESULT ', output)
        else:
            self.assertEqual(c.returncode, 0, output)
            self.assertNotIn('ERROR:', output)
            self.assertEqual(board.old.frames(output), [(0x2001+i, frame) for i, frame in enumerate(frames)])
            rows = [json.loads(line.split(' ', 1)[1]) for line in output.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(rows, [dict(source_frames=len(frames), queue_frames=len(frames), actual_wire_EOFs=len(frames),
                                         actual_SFD=len(frames), actual_completions=len(frames))])
        self.reports[self._testMethodName] = dict(pass_test=True, seconds=seconds,
            expected_fatal=expected_error, process_exit=c.returncode, lengths=lengths, source_gap=gap,
            directory=str(run.relative_to(ROOT)),
            artifact_sha256={str(p.relative_to(ROOT)): digest(p) for p in run.iterdir() if p.is_file()})

    def test_three_large_frames_slow_source_actual_MAC_and_held_receipts(self):
        self.simulate([4170, 4154, 62], 1)

    def test_small_and_jumbo_frames_keep_tags_and_FCS(self):
        self.simulate([60, 79, 9214, 62], 0)

    def test_oversize_frame_still_fails_closed_at_actual_board_FIFO(self):
        self.simulate([32769], 0, 'oversize')

    def test_bad_frame_still_fails_closed_at_actual_board_FIFO(self):
        self.simulate([4170], 1, 'bad')


TESTBENCH = r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1;
LINK_RTL
reg [161:0] words[0:WORD_COUNT-1];
reg [161:0] drive=0;reg source_valid=0,receipt_ready=0;
integer source_frames=0,queue_frames=0,completions=0,cycle=0,i,deadline;
assign link_s_data=drive[127:0];assign link_s_keep=drive[143:128];
assign link_s_last=drive[144];assign link_s_user=drive[161:145];assign link_s_valid=source_valid;
assign link_m_cpl_ready=receipt_ready;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;
 if(cycle>16000)$fatal(1,"board TX deadline");
 if(link_s_valid && link_s_ready && link_s_last)source_frames=source_frames+1;
 if(board_tx_valid && board_tx_ready)begin
  if(queue_frames>=source_frames)$fatal(1,"board frame queue leaked an incomplete source frame");
  if(board_tx_last)queue_frames=queue_frames+1;
 end
 if(link_m_cpl_valid && link_m_cpl_ready)begin
  if(link_m_cpl_tag!==16'h2001+completions)$fatal(1,"real board MAC completion tag/order");
  completions=completions+1;
 end
end
initial begin
 $readmemh("input.hex",words);
 repeat(8)@(negedge clk);rst=0;repeat(8)@(negedge clk);
 for(i=0;i<WORD_COUNT;i=i+1)begin
  @(negedge clk);drive=words[i];source_valid=1;
  @(posedge clk);while(!link_s_ready)@(posedge clk);
  @(negedge clk);source_valid=0;
  repeat(SOURCE_GAP)@(negedge clk);
 end
 while(board_wire_eofs<FRAME_COUNT)@(negedge clk);
 repeat(1100)begin
  @(negedge clk);
  if(completions || !link_m_cpl_valid)$fatal(1,"held real MAC receipt disappeared or retired early");
 end
 receipt_ready=1;deadline=cycle+1000;
 while(completions!=FRAME_COUNT)begin
  @(negedge clk);if(cycle>deadline)$fatal(1,"real board MAC completion drain deadline");
 end
 if(source_frames!=FRAME_COUNT || queue_frames!=FRAME_COUNT || board_wire_eofs!=FRAME_COUNT || actual_SFD_count!=FRAME_COUNT)
  $fatal(1,"board TX actual source/queue/wire/SFD cardinality");
 $display("RESULT {\"source_frames\":%0d,\"queue_frames\":%0d,\"actual_wire_EOFs\":%0d,\"actual_SFD\":%0d,\"actual_completions\":%0d}",
  source_frames,queue_frames,board_wire_eofs,actual_SFD_count,completions);
 $finish;
end
endmodule
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    if args.report.exists():
        p.error('preserve earlier evidence')
    files = list(dict.fromkeys([Path(__file__).resolve(), Path(board.__file__).resolve(), Path(board.old.__file__).resolve(),
                               *board.old.SOURCES, *board.INPUTS]))
    before = {str(p.relative_to(ROOT)): digest(p) for p in files}
    start = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoardTX))
    if any(digest(ROOT/name) != expected for name, expected in before.items()):
        raise ValueError('board FIFO fixture/source changed during tests')
    report = dict(scope=__doc__, pass_test=result.wasSuccessful(), methods=result.testsRun,
                  seconds=time.monotonic()-start, source_sha256=before, tests=BoardTX.reports,
                  four_state=True, simulation_limit_seconds=30, actual_board_parameters=board.parameters(),
                  native_RNIC_runtime=False, hardware_verified=False)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
