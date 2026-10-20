# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state duplex memory router; command producers/memory are explicit models."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_memory_origin_router.v'
TB=r'''`timescale 1ns/1ps
module tb;
// PORTS
rocev2_memory_origin_router #(.READ_RETURN(MODE),.DEPTH(2)) dut(.*);
always #2 clk=~clk;
task command;
 input [1:0] direction;input [27:0] size;
 begin
  @(negedge clk);s_command={direction,18'h28b0,size,48'h123456789abc};s_command_valid=1;
  #1;if(!s_command_ready || m_local_command[95:94] || m_remote_command[95:94] ||
   m_local_command[93:0]!==s_command[93:0] || m_remote_command[93:0]!==s_command[93:0])$fatal(1,"exact command provenance/94bits");
  @(posedge clk);@(negedge clk);s_command_valid=0;
 end
endtask
task payload;
 input direction;input [511:0] value;input [63:0] keep;input last;
 begin
  @(negedge clk);
  if(MODE)begin
   if(direction)begin s_local_data=value;s_local_keep=keep;s_local_last=last;s_local_valid=1;end
   else begin s_remote_data=value;s_remote_keep=keep;s_remote_last=last;s_remote_valid=1;end
  end else begin s_data=value;s_keep=keep;s_last=last;s_valid=1;end
  #1;if(MODE ? (!m_valid || m_data!==value || m_keep!==keep || m_last!==last):
   (direction ? (!m_local_valid || m_remote_valid || m_local_data!==value || m_local_keep!==keep):
    (!m_remote_valid || m_local_valid || m_remote_data!==value || m_remote_keep!==keep)))$fatal(1,"data origin or exact bytes");
  @(posedge clk);@(negedge clk);s_valid=0;s_local_valid=0;s_remote_valid=0;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;local_owned=1;remote_owned=1;
 m_local_command_ready=1;m_remote_command_ready=1;m_local_ready=1;m_remote_ready=1;m_ready=1;
 // BODY
 $display("MEMORY_ORIGIN_RESULT {\"pass_test\":true,\"read_return\":%0d}",MODE);$finish;
end
endmodule
'''

class MemoryOriginTests(unittest.TestCase):
    reports={}
    def simulate(self,mode,body):
        ports=re.findall(r'\b(input|output) (?:wire|reg) (\[[^]]+\] )?(\w+)',RTL.read_text())
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        tb=TB.replace('// PORTS',decl).replace('MODE',str(mode)).replace('// BODY',body)
        before={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in [RTL,Path(__file__).resolve()]}
        with tempfile.TemporaryDirectory(prefix='as02-origin-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('MEMORY_ORIGIN_RESULT ')]
            self.assertEqual(len(rows),1);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before))
    def test_interleaved_clients_retain_origin_until_exact_EOF(self):
        for mode in [0,1]:
            self.simulate(mode,r'''
command(1,65);command(2,68);
payload(0,512'h1234,64'hffffffffffffffff,0);
payload(0,512'h56,64'h1,1);
payload(1,512'habcd,64'hffffffffffffffff,0);
payload(1,512'h12345678,64'hf,1);
repeat(3)@(negedge clk);if(busy || fault)$fatal(1,"tokens leaked");
command(2,1);command(1,1);payload(1,512'ha5,1,1);payload(0,512'h5a,1,1);
repeat(3)@(negedge clk);if(busy || fault)$fatal(1,"wrap/order");
''')
    def test_backpressure_and_unselected_client_cannot_overtake(self):
        for mode in [0,1]:
            self.simulate(mode,r'''
command(1,1);command(2,1);
if(1)begin
 m_remote_ready=0;m_ready=0;
 if(MODE)begin s_remote_data=512'h1234;s_remote_keep=1;s_remote_last=1;s_remote_valid=1;
  s_local_data=512'habcd;s_local_keep=1;s_local_last=1;s_local_valid=1;end
 else begin s_data=512'h1234;s_keep=1;s_last=1;s_valid=1;end
 repeat(17)begin @(negedge clk);if(fault || dut.count!=2 || s_local_ready || s_ready || s_remote_ready ||
  (MODE ? (!m_valid || m_data!==512'h1234):(!m_remote_valid || m_local_valid || m_remote_data!==512'h1234)))$fatal(1,"stall/other client overtook");end
 s_valid=0;s_remote_valid=0;s_local_valid=0;m_remote_ready=1;m_ready=1;
end
payload(0,512'h1234,1,1);payload(1,512'habcd,1,1);
repeat(3)@(negedge clk);if(fault || busy)$fatal(1,"stall leaked");
'''.replace('MODE',str(mode)))
    def test_invalid_or_unowned_origins_quarantine(self):
        for origin,owned in [("2'd0",True),("2'd3",True),("2'bxx",True),("2'd2",False),("2'd1",False)]:
            self.simulate(0,f'local_owned={int(owned)};remote_owned={int(owned)};s_command={{{origin},18\'d0,28\'d1,48\'d0}};s_command_valid=1;'+r'''
#1;if(s_command_ready || m_local_command_valid || m_remote_command_valid)$fatal(1,"bad command escaped");
repeat(4)@(negedge clk);if(!fault || fault_code!=8'hc1 || dut.count)$fatal(1,"origin not quarantined");
''')
    def test_wrong_payload_length_never_releases_credit(self):
        for mode in [0,1]:
            self.simulate(mode,r'''
command(2,65);
if(MODE)begin s_local_valid=1;s_local_keep=1;s_local_last=1;end
else begin s_valid=1;s_keep=1;s_last=1;end
#1;if(m_valid || m_local_valid || s_ready || s_local_ready)$fatal(1,"early EOF escaped");
repeat(4)@(negedge clk);if(!fault || fault_code!=8'hc2 || dut.count!=1 || !busy)$fatal(1,"bad EOF lost ownership");
'''.replace('MODE',str(mode)))
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_MEMORY_ORIGIN_REPORT'):
            result=dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),
                simulations=sum(map(len,cls.reports.values())),tests=cls.reports,hardware_verified=False)
            with Path(name).open('x')as f:f.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':unittest.main()
