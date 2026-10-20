# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native SQ/MR/RX/executor/PCIe/fence + production issued/lifetime join.

TX is a replay of retained actual-HLS READ bytes, NOT a live HLS core here.
HLS extraction/commands, physical host/link, MAC proof/transport drain and
final CQ publication/commit are MODELS. No real kernel/provider/board CQ.
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

import test_native_response_guard_rtl as native
import test_wqe_lifetime_rtl as lifetime

ROOT=native.ROOT
TRACE=ROOT/'results/2026-10-18/rocev2-rnic-native-read-hls-replay-003.json'


def make_tb(words):
    once=native.native.memory.sq.once;tb=native.make_tb(words)
    tb=once(tb,'m_hls_sq_tready=1;@(posedge clk);@(negedge clk);m_hls_sq_tready=0;',r'''
// The actual lifetime owner is captured BEFORE the modeled HLS SQ handoff.
lf_s_owner_valid=1;@(posedge clk);if(!lf_s_owner_ready)$fatal(1,"native lifetime capture");
@(negedge clk);lf_s_owner_valid=0;
if(completion_queue_guard!==8'h04 || !lf_busy || lf_m_cq_valid)$fatal(1,"native full-WR owner gap before SQ");
m_hls_sq_tready=1;@(posedge clk);@(negedge clk);m_hls_sq_tready=0;
lf_transmit_request();
payload_deadline=cycle+1000;while(!lf_response_admission_ready)begin if(cycle>payload_deadline)$fatal(1,"hardware issued PSN/expectation deadline");@(negedge clk);end
if(lf_m_expect_psn!=24'hfffffe || lf_m_expect_context!==e_m_memory_event_context)$fatal(1,"hardware issued full-WR context mismatch");
''')
    start=tb.index('rg_s_expect_valid=1;@(posedge clk);')
    end=tb.index('response_send(0);',start)
    tb=tb[:start]+'// Expected peer/context/PSN now come from actual lifetime RTL.\n'+tb[end:]
    # The real response event is consumed by the real join. The join keeps its
    # own full-WR guard, rather than requiring the earlier wire stage to stall.
    tb=once(tb,'while(!rg_m_response_event_valid)',"while(!lf_proof_flags[3])")
    start=tb.index('// Explicit downstream wire/CQ MODEL takes memory owner BEFORE its ready.')
    end=tb.index('collect_native(8,405,0,0,2);',start)
    tb=tb[:start]+r'''
// HLS ACK can be early; it is a MODEL here and never completes memory/CQ.
lf_s_hls_ack=40'h07fffff004;lf_s_hls_ack_valid=1;
@(posedge clk);if(!lf_s_hls_ack_ready)$fatal(1,"native HLS ACK model binding");@(negedge clk);lf_s_hls_ack_valid=0;
repeat(11)begin @(negedge clk);if(lf_m_cq_valid || !lf_busy || completion_queue_guard!==8'h04 || quiet || config_safe)$fatal(1,"ACK alone completed native WR");end
lf_allow_memory=1;@(posedge clk);if(!e_m_memory_event_ready)$fatal(1,"actual memory event join");
@(negedge clk);lf_allow_memory=0;
repeat(11)begin @(negedge clk);if(e_busy || executor_queue_guard || !lf_proof_flags[2] ||
 !lf_busy || completion_queue_guard!==8'h04 || lf_m_cq_valid || quiet || config_safe)$fatal(1,"memory visibility mistaken for MAC/CQ commit");end
if(wire_queue_guard || rg_busy || !lf_proof_flags[3] || !dut.memory_drained)$fatal(1,"real response/memory drain evidence absent");
// MAC receipt and transport drain are explicit MODELS until real parent/HLS
// completion correlation is implemented. Never default-success callbacks.
lf_s_mac_context=e_m_memory_event_context;lf_s_mac_error=0;lf_s_mac_valid=1;
@(posedge clk);if(!lf_s_mac_ready)$fatal(1,"modeled MAC receipt ownership");@(negedge clk);lf_s_mac_valid=0;
repeat(11)begin @(negedge clk);if(lf_m_cq_valid || quiet || config_safe || completion_queue_guard!==8'h04)$fatal(1,"MAC substituted for transport drain");end
lf_transport_drained=1;payload_deadline=cycle+1000;
while(!lf_m_cq_valid)begin if(cycle>payload_deadline)$fatal(1,"joined native CQ ticket deadline");@(negedge clk);end
repeat(13)begin @(negedge clk);if(lf_m_cq_context!==e_m_memory_event_context || completion_queue_guard!==8'h04 ||
 !lf_busy || lf_committed_count || quiet || config_safe || !control_busy)$fatal(1,"CQ ticket released native MR/QP");end
lf_m_cq_ready=1;@(posedge clk);@(negedge clk);lf_m_cq_ready=0;
repeat(17)begin @(negedge clk);if(!lf_busy || lf_committed_count || completion_queue_guard!==8'h04 || quiet || config_safe)$fatal(1,"ticket acceptance became actual CQ commit");end
// Final actual CQ publisher is still a MODEL. Its exact full owner+current
// real memory drain are required before the RTL can release the native guard.
lf_s_cq_commit_context=e_m_memory_event_context;lf_s_cq_commit_error=0;lf_s_cq_commit_valid=1;
@(posedge clk);if(!lf_s_cq_commit_ready)$fatal(1,"native exact CQ commit");@(negedge clk);lf_s_cq_commit_valid=0;
if(lf_busy || completion_queue_guard || lf_committed_count!=1 || lf_fault)$fatal(1,"native final lifetime release");
'''+tb[end:]
    # Real hardware, not the old ad-hoc guards/readies, now owns these ports.
    for name in ['completion_queue_guard','e_m_memory_event_ready','rg_m_response_event_ready']:
        tb,n=re.subn(r'\breg (\[[^]]+\]\s+)?'+name+r'=0;',lambda m:'wire '+(m[1]or'')+name+';',tb)
        if n!=1:raise ValueError('old modeled ownership declaration changed '+name)
        if re.search(r'\b'+name+r'\s*(?:<=|=(?!=))',tb):raise ValueError('old modeled lifetime driver survived '+name)
    for name,target in [('s_expect_context','lf_m_expect_context'),('s_expect_local_ip','lf_m_expect_local_ip'),
        ('s_expect_peer_ip','lf_m_expect_peer_ip'),('s_expect_psn','lf_m_expect_psn'),
        ('s_expect_valid','lf_m_expect_valid'),('s_expect_ready','lf_m_expect_ready')]:
        pattern=r'\.'+name+r'\([^()]*\)';tb,n=re.subn(pattern,f'.{name}({target})',tb)
        if n!=1:raise ValueError('protected expectation wiring changed '+name)
    mapping=dict(clk='clk',rst='rst',enable="1'b1",s_owner_context='e_m_memory_event_context',
        s_owner_local_ip="32'hc6120b02",s_owner_peer_ip="32'hc6120b01",s_owner_peer_qpn="24'd196",
        s_memory_context='e_m_memory_event_context',s_memory_error='e_m_memory_event_error',
        s_memory_valid='e_m_memory_event_valid && lf_allow_memory',
        s_response_context='rg_m_response_event_context',s_response_psn='rg_m_response_event_psn',
        s_response_opcode='rg_m_response_event_opcode',s_response_syndrome='rg_m_response_event_syndrome',
        s_response_valid='rg_m_response_event_valid',s_response_ready='rg_m_response_event_ready',
        memory_drained='dut.memory_drained',queue_guard='completion_queue_guard',m_expect_ready='lf_m_expect_ready')
    h=lifetime.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h,re.M)
    declarations=[];connections=[]
    for direction,width,name in ports:
        target=mapping.get(name,'lf_'+name);connections.append(f'.{name}({target})')
        if name not in mapping:declarations.append(('reg 'if direction=='input'else'wire ')+(width or'')+target+('=0;'if direction=='input'else';'))
    block='\n'.join(declarations)+'\n'+r'''
wire lf_m_expect_ready;
reg lf_allow_memory=0;reg [127:0] lf_request[0:3];integer lf_i;
initial $readmemh("issued.hex",lf_request);
assign e_m_memory_event_ready=lf_s_memory_ready && lf_allow_memory;
task lf_transmit_request;
 begin
  for(lf_i=0;lf_i<4;lf_i=lf_i+1)begin
   @(negedge clk);lf_s_tx_data=lf_request[lf_i];lf_s_tx_keep=lf_i==3 ? 16'h0fff : 16'hffff;
   lf_s_tx_last=lf_i==3;lf_s_tx_user=0;lf_s_tx_valid=1;lf_s_tx_ready=0;
   repeat(7)@(negedge clk);lf_s_tx_ready=1;@(posedge clk);@(negedge clk);lf_s_tx_valid=0;lf_s_tx_ready=0;
  end
 end
endtask
always @(posedge clk)if(!rst && lf_fault)$fatal(1,"actual native lifetime fault%h",lf_fault_code);
'''
    block+='\nrocev2_wqe_lifetime full_WR('+',\n'.join(connections)+');\n'
    tb=once(tb,'rocev2_wqe_memory_executor executor(',block+'\nrocev2_wqe_memory_executor executor(')
    return f'`include "{lifetime.RTL}"\n'+tb


class NativeLifetimeTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):native.native.shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def test_actual_native_proofs_keep_MR_QP_until_exact_CQ_commit_not_ACK_or_memory(self):
        record=json.loads(TRACE.read_text());self.assertTrue(record['pass_test']);pkt=bytes.fromhex(record['request_packet_hex']);self.assertEqual(len(pkt),60)
        words=native.native.memory.sq.local.fixture.packet();tb=make_tb(words)
        paths=native.native.sq.input_paths(tb)+[Path(__file__).resolve(),Path(native.__file__).resolve(),Path(native.native.__file__).resolve(),
            Path(native.native.memory.__file__).resolve(),Path(native.native.executor.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(native.response.__file__).resolve(),
            Path(native.response.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',Path(lifetime.__file__).resolve(),lifetime.RTL,TRACE]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        records=[bytes.fromhex(v)for v in record['actual_C_UBSan_WQE_records']]
        for i,data in enumerate(records):
            w=native.native.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,remote_key=0,opcode=2,flags=1,length=65)
            encoded=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(encoded,C.byref(w)),0)
            self.assertEqual(bytes(encoded),data);self.assertEqual(data,native.native.shared.codec.oracle(w))
        # Reuse the independently verified real-HLS case's exact peer bytes,
        # so even this modeled extraction uses the SAME179/d3payload as the
        # retained native PCIe oracle (not the separate131/5aunit pattern).
        bad,good=[bytes.fromhex(v)for v in record['protected_input_packets_hex']]
        self.assertEqual([len(bad),len(good)],[116,116])
        self.assertEqual(good[44:109],bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65)))
        frames=[int.from_bytes(p[n:n+16].ljust(16,b'\0'),'little')for p in [bad,good]for n in range(0,len(p),16)]
        with tempfile.TemporaryDirectory(prefix='as02-native-lifetime-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(native.native.shared.protected.stub_source())
            for name,values in {'input.hex':words,'records.hex':[int.from_bytes(v,'little')for v in records],
                'response.hex':frames,'issued.hex':[int.from_bytes(pkt[n:n+16].ljust(16,b'\0'),'little')for n in range(0,60,16)]}.items():
                (p/name).write_text(''.join(f'{v:x}\n'for v in values))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),*map(str,native.native.memory.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text();names=['rocev2_wqe_lifetime','rocev2_wqe_response_guard','rocev2_wqe_memory_executor',
                'rocev2_mr_table','rocev2_mr_page_table','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names};self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[23:])for l in r.stdout.splitlines()if l.startswith('NATIVE_EXECUTOR_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual([rows[0][n]for n in ['physical_descriptors','read_tlps','write_tlps','fences']],[4,2,2,1])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            actual_elaborated_module_counts=counts,actual_hardware_issued_expectation_and_native_lifetime_join=True,
            live_HLS_TX_RX_MAC_CQ=False,TX_input_is_actual_HLS_trace_replay=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_LIFETIME_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==1,methods=len(cls.reports),tests=cls.reports,
                actual_native_MR_RX_memory_fence_lifetime_proof_join=True,
                HLS_MAC_transport_drain_CQ_are_models=True,actual_native_WR_CQ_runtime=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
