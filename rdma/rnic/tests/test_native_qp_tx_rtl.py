# SPDX-License-Identifier: BSD-2-Clause-Views
"""TX-only QP mailbox through the actual native RNIC ancestry and READ path.

HLS including actual-state readback is an EXPLICIT MODEL here; the real HLS
C++ consumers are tested separately. No generated-new-HLS/board claim.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import test_native_rnic_rtl as main

ROOT=main.ROOT
PSN=0x89abcd

def model(write=False):
    text=main.core_model(write)
    text=text.replace('module rocev2_integrity_transport #','module rocev2_qptx_integrity_transport #')
    text=text.replace('parameter LEGACY_QP_KEY=1',
        'parameter LEGACY_QP_KEY=1,parameter EXTERNAL_REPLAY_ENABLE=0,parameter RNR_ENABLE=0,parameter RECV_RETIRE_ENABLE=0')
    text=text.replace('input wire [31:0] s_axis_sq_rkey',
        'input wire [31:0] s_axis_sq_rkey,\noutput wire [79:0] m_axis_qp_apply_tdata,\n'
        'output wire m_axis_qp_apply_tvalid,input wire m_axis_qp_apply_tready,\n'
        'input wire [55:0] s_rnr_event_tdata,input wire s_rnr_event_tvalid,\n'
        'output wire s_rnr_event_tready,output wire rnr_fault,\n'
        'input wire [647:0] s_recv_owner_tdata,input wire s_recv_owner_tvalid,output wire s_recv_owner_tready,\n'
        'output wire [679:0] m_recv_done_tdata,output wire m_recv_done_tvalid,input wire m_recv_done_tready,output wire recv_fault')
    text=text.replace("40'h07fffff004",f"40'h{(PSN<<11)|4:x}")
    text=text.replace('initial $readmemh',r'''
// Compatibility model for the old QP path ONLY. Real RNR requires generated
// matched HLS, never a modeled wire packet or fake core-drain certificate.
initial if(RNR_ENABLE)$fatal(1,"use actual generated HLS for wire RNR");
initial if(RECV_RETIRE_ENABLE)$fatal(1,"use actual generated HLS for receive receipts");
assign s_rnr_event_tready=0;assign rnr_fault=0;
assign s_recv_owner_tready=0;assign m_recv_done_tdata=0;assign m_recv_done_tvalid=0;assign recv_fault=0;
reg [23:0] model_rx_psn=0,model_tx_psn=0,model_qpn=0;
reg [7:0] model_flags=0;
reg model_pending=0;
assign m_axis_qp_apply_tdata={model_flags,model_rx_psn,model_tx_psn,model_qpn};
assign m_axis_qp_apply_tvalid=model_pending && tb.qp_model_allow;
always @(posedge clk)begin
 if(rst)begin model_pending<=0;model_rx_psn<=0;model_tx_psn<=0;model_qpn<=0;model_flags<=0;end
 else begin
  if(m_axis_qp_apply_tvalid && m_axis_qp_apply_tready)model_pending<=0;
  if(s_axis_qp_tvalid && s_axis_qp_tready)begin
   if(model_pending)$fatal(1,"test model received overlapping QP configs");
   model_pending<=1;model_qpn<=s_axis_qp_tdata[55:32];model_tx_psn<=s_axis_qp_tdata[79:56];
   if(s_axis_qp_tdata[151:104]==48'h415332545850)model_flags<=3;
   else begin model_flags<=1;model_rx_psn<=s_axis_qp_tdata[103:80];end
  end
 end
end
initial $readmemh''')
    return text

def case(write=False):
    tb,words=main.bench(write)
    tb=main.sq.once(tb,'rocev2_native_rnic_endpoint dut(',
        'rocev2_native_rnic_endpoint #(.QP_TX_ENABLE(1)) dut(')
    tb=main.sq.once(tb,'reg [144:0] stimulus','reg qp_model_allow=1;\nreg [144:0] stimulus')
    injection=r'''
read_reg(AS02_CTL_FEATURES,sq_value);if(sq_value!==3)$fatal(1,"new QP TX capability missing");
host_stage(9,403,0,0,17,0,0,0);
for(host_i=4;host_i<21;host_i=host_i+1)host_words[host_i]=0;
host_words[6]=17;host_words[15]=2;host_words[20]=24'h89abcd;
for(host_i=0;host_i<21;host_i=host_i+1)write_reg(AS02_CTL_STAGE+host_i*4,host_words[host_i],15,0,1);
qp_model_allow=0;write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(23)begin @(negedge clk);if(!control_busy || quiet || config_safe)$fatal(1,"QP TX returned before real apply");end
read_reg(AS02_CTL_STATUS,sq_value);if(sq_value&AS02_ST_REPLY)$fatal(1,"fabricated state apply reply");
qp_model_allow=1;collect_native(9,403,0,0,0);
if(observed_local_hls_local_ip!==32'hc6120b02 || observed_local_hls_peer_ip!==32'hc6120b01 ||
 observed_local_hls_peer_qpn!==196)$fatal(1,"TX-only config erased the live RX/route context");
enable=1;sq_command(2,1,0,0,0);
'''
    tb=main.sq.once(tb,'enable=1;sq_command(2,1,0,0,0);',injection)
    n=len(main.sq.local.fixture.packet())
    reply=bytearray(main.response.packet(write=write,mig=1,qpn=2,psn=PSN))
    if not write:reply[44:109]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65))
    frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+main.response.repair(reply)
    words=words[:n]+[int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little')|
        (((1<<min(16,len(frame)-i))-1)<<128)|((i+16>=len(frame))<<144)for i in range(0,len(frame),16)]
    request=bytearray(main.request(write));request[37:40]=PSN.to_bytes(3,'big');request=main.response.repair(request)
    records=[]
    for i in range(2):
        w=main.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
            local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
            remote_key=0,opcode=1 if write else 2,flags=1,length=65)
        records.append(main.shared.codec.oracle(w))
    return tb,words,records,request

class NativeQPTXTests(unittest.TestCase):
    def test_native_QP_TX_waits_for_apply_preserves_route_then_READ_uses_new_PSN(self):
        tb,words,records,request=case()
        sources=list(dict.fromkeys([*main.original.input_paths(tb),main.TOP,*main.EXTRA,
            Path(main.__file__).resolve(),Path(main.derive.__file__).resolve(),main.derive.ORIGINAL,Path(__file__).resolve()]))
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources}
        with tempfile.TemporaryDirectory(prefix='as02-native-qp-tx-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            (p/'legacy.v').write_text(main.core_model(False));(p/'new.v').write_text(model())
            (p/'shared.v').write_text(main.derive.derive(main.derive.ORIGINAL.read_text()))
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
            (p/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
            (p/'request.hex').write_text(''.join(f'{v:x}\n'for v in main.octets(request)))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'legacy.v'),str(p/'new.v'),
                str(p/'shared.v'),str(main.TOP),*map(str,main.EXTRA),*map(str,main.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            hierarchy=(p/'test.vvp').read_text()
            counts={name:len(re.findall(r'\.scope module, "[^\"]+" "'+name+r'"',hierarchy))for name in
                ['rocev2_qptx_integrity_transport','rocev2_mr_table','rocev2_mr_page_table','rocev2_wqe_memory_executor']}
            self.assertTrue(all(n==1 for n in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertEqual(rows[0]['proof_flags'],63)
            self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
            if name:=os.environ.get('AS02_RNIC_QP_TX_RTL_REPORT'):
                report=dict(scope=__doc__,pass_test=True,source_sha256=before,source_unchanged=True,
                    summary=rows[0],actual_main_QP_TX_command=True,TX_PSN=PSN,RX_route_preserved=True,
                    configuration_waited_for_modeled_apply=True,actual_module_counts=counts,
                    HLS_state_apply_model=True,generated_new_HLS=False,hardware_verified=False)
                with (ROOT/name).open('x')as f:f.write(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':unittest.main()
