// SPDX-License-Identifier: BSD-2-Clause-Views
// Read-only failed-execution observer. No signal writes or extra deadlines.
`timescale 1ns/1ps
module segmented_write_front_observe;
integer sample=0;
always @(negedge tb.clk)begin
 if(sample<30 || sample%1024==0)
  $display("WRITE_FRONT_OBSERVE time%0t raw%0b/%0b checked%0b/%0b state%0d words%0d guard_state%0d MR%0d owners%0d output%0d fault%0h",
   $time,tb.raw_valid,tb.raw_ready,tb.checked_valid,tb.checked_ready,tb.dut.state,
   tb.dut.word_count,tb.dut.protection.state,tb.queries,tb.grants,tb.replayed_frames,tb.fault_code);
 sample=sample+1;
 if(tb.output_valid && tb.replay_index<4)
  $display("WRITE_FRONT_BYTES time%0t owned%0b start%0d count%0d index%0d actual%037h expected%037h ram0%032h",
   $time,tb.replay_owned,tb.replay_start,tb.replay_words,tb.replay_index,
   {tb.output_last,tb.output_keep,tb.output_data},tb.input_words[tb.replay_start+tb.replay_index],tb.dut.frame_data[0]);
end
endmodule
