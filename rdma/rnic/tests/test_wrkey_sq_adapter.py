# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQ width/key adapter RTL only; NOT the generated HLS or wire path."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
RTL = ROOT/'rdma/rnic/rtl/rocev2_wrkey_sq_adapter.v'


def simulate(body):
    with tempfile.TemporaryDirectory(prefix='as02-wrkey-sq-') as directory:
        run = Path(directory)
        (run/'tb.v').write_text(body)
        subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(run/'tb'),
                        str(run/'tb.v'), str(RTL)], check=True, capture_output=True,
                       text=True, timeout=10)
        return subprocess.run(['vvp', str(run/'tb')], capture_output=True,
                              text=True, timeout=5)


class WRKeySQAdapterTests(unittest.TestCase):
    def test_exact_full_key_zero_legacy_bits_and_handshakes(self):
        result = simulate('''
`timescale 1ns/1ps
module tb;
 reg [239:0] data = 0;
 reg [31:0] key = 0;
 reg valid = 0, ready = 0;
 wire [247:0] legacy, explicit_key;
 wire lr,lv,kr,kv;
 rocev2_wrkey_sq_adapter #(.LEGACY_QP_KEY(1)) l(data,key,valid,lr,legacy,lv,ready);
 rocev2_wrkey_sq_adapter #(.LEGACY_QP_KEY(0)) k(data,key,valid,kr,explicit_key,kv,ready);
 integer n;
 reg [247:0] held_l,held_k;
 initial begin
  for(n=0;n<256;n=n+1) begin
   data = {32'hdeadbeef,32'hf1234567,32'h89abcdef,32'h12345678,
           32'h9abcdef0,32'hfffffe01,32'hbb77cc11,16'hfb81} ^ n;
   case(n%4)
    0:key=0; 1:key=32'h80000000; 2:key=32'hffffffff; 3:key=32'h12345678;
   endcase
   valid=(n%3)!=0; ready=(n%5)!=0;
   #1;
   if(legacy !== {8'd0,data}) $fatal(1,"legacy all bits and flag");
   if(explicit_key !== {7'd0,1'b1,key,data[207:0]}) $fatal(1,"full key or original low bits");
   if(lr!==ready || kr!==ready || lv!==valid || kv!==valid) $fatal(1,"AXI handshake");
   ready=0; valid=1; #1;
   held_l=legacy; held_k=explicit_key; #5;
   if(legacy!==held_l || explicit_key!==held_k || !lv || !kv || lr || kr)
      $fatal(1,"stalled stable upstream context");
  end
  $display("WRKEY_ADAPTER_PASS"); $finish;
 end
endmodule
''')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('WRKEY_ADAPTER_PASS', result.stdout)

    def test_invalid_mode_refused(self):
        result = simulate('''module tb;
 rocev2_wrkey_sq_adapter #(.LEGACY_QP_KEY(2)) dut();
 initial begin #1; $finish; end
 endmodule''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('LEGACY_QP_KEY must be exactly', result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
