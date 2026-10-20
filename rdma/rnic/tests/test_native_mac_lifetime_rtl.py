# SPDX-License-Identifier: BSD-2-Clause-Views
"""Native SQ/MR/PCIe/fence/protected RX + real shared-MAC owner/lifetime RTL.

READ IP is retained real-HLS trace replay; HLS extraction/ACK/drain, physical
MAC/host/link and actual CQ publisher are MODELS. Real Ethernet framing, native
role arbitration, external tag receipt correlation and wire-tail holding are
NOW connected RTL, not a copied full-context MAC proof. No hardware/verbs.
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

import test_native_lifetime_rtl as old
import test_wqe_mac_tx_rtl as mac

ROOT=old.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_tx_lifetime.v'


def make_tb(words):
    once=old.native.native.memory.sq.once;tb=old.make_tb(words)
    # Keep the SAME real native endpoint and all original memory/STOP/retire/
    # sentinel assertions; interpose the production role mapper on its ACTUAL
    # Ethernet output/completion path rather than replace them with constants.
    ports=dict(m_axis_mac_tx_tdata='native_tx_data',m_axis_mac_tx_tkeep='native_tx_keep',
        m_axis_mac_tx_tvalid='native_tx_valid',m_axis_mac_tx_tready='native_tx_ready',
        m_axis_mac_tx_tlast='native_tx_last',m_axis_mac_tx_tuser='native_tx_user',
        s_axis_mac_cpl_tag='native_cpl_tag',s_axis_mac_cpl_ts='native_cpl_ts',
        s_axis_mac_cpl_valid='native_cpl_valid',s_axis_mac_cpl_ready='native_cpl_ready')
    for name,target in ports.items():
        tb,n=re.subn(r'\.'+name+r'\([^()]*\)',f'.{name}({target})',tb)
        if n!=1:raise ValueError('native MAC path changed '+name)
    for name in ['lf_s_mac_context','lf_s_mac_error','lf_s_mac_valid','lf_s_mac_ready']:
        tb,n=re.subn(r'^(?:reg|wire) (?:\[[^]]+\] )?'+name+r'(?:=0)?;\n','',tb,flags=re.M)
        if n!=1:raise ValueError('old MAC model declaration changed '+name)
    tb=once(tb,'reg lf_s_tx_ready=0;','wire lf_s_tx_ready;')
    start=tb.index('task lf_transmit_request;');end=tb.index('endtask',start)+len('endtask')
    tb=tb[:start]+r'''
task lf_transmit_request;
 begin
  for(lf_i=0;lf_i<4;lf_i=lf_i+1)begin
   @(negedge clk);lf_s_tx_data=lf_request[lf_i];lf_s_tx_keep=lf_i==3 ? 16'h0fff : 16'hffff;
   lf_s_tx_last=lf_i==3;lf_s_tx_user=0;lf_s_tx_valid=1;
   @(posedge clk);while(!lf_s_tx_ready)@(posedge clk);
   @(negedge clk);lf_s_tx_valid=0;
  end
 end
endtask'''+tb[end:]
    tb=once(tb,'lf_transmit_request();','fork lf_transmit_request();native_host_frame();join')
    start=tb.index('// MAC receipt and transport drain are explicit MODELS until real parent/HLS')
    end=tb.index('lf_transport_drained=1;',start)
    tb=tb[:start]+r'''
// The REAL framer/tag mapper accepted a receipt from the EXPLICIT physical
// MAC pin model. Its full owner is recovered internally; no test context copy.
payload_deadline=cycle+1500;
while(!lf_proof_flags[5] || !mt_local_tx_drained)begin
 if(cycle>payload_deadline || mt_frame_count!=1 || mt_receipt_count!=1 || lf_fault)
  $fatal(1,"real native MAC/tag/tail proof deadline");@(negedge clk);
end
if(mt_mac_proof_count!=1 || lf_m_cq_valid || completion_queue_guard!==8'h04 || quiet || config_safe)
 $fatal(1,"actual MAC receipt substituted for HLS drain/CQ commit");
if(host_tx_frames!=1 || host_cpl_frames!=1 || mac_host_cpls!=1)
 $fatal(1,"actual native host traffic/completion was stolen by local WR");
// This remaining drain is the HLS-only MODEL, not MAC completion/quiescence.
'''+tb[end:]
    start=tb.index('rocev2_wqe_lifetime full_WR(');end=tb.index(');',start)+2
    old_connections=dict(re.findall(r'\.(\w+)\(([^()]*)\)',tb[start:end]))
    # Every common proof/expectation/CQ port keeps its original connection.
    mapping={n:v.rstrip(',')for n,v in old_connections.items()}
    for n in ['s_tx_data','s_tx_keep','s_tx_last','s_tx_user','s_tx_valid','s_tx_ready',
              's_mac_context','s_mac_error','s_mac_valid','s_mac_ready','transport_drained']:
        mapping.pop(n)
    mapping.update(parent_fault='actual_parent_fault',s_owner_local_mac="48'h8af3fbb97531",s_owner_peer_mac="48'hb8830367c5d0",
        s_axis_ip_tdata='lf_s_tx_data',s_axis_ip_tkeep='lf_s_tx_keep',s_axis_ip_tvalid='lf_s_tx_valid',
        s_axis_ip_tready='lf_s_tx_ready',s_axis_ip_tlast='lf_s_tx_last',s_axis_ip_tuser='lf_s_tx_user',
        s_axis_native_tdata='native_tx_data',s_axis_native_tkeep='native_tx_keep',s_axis_native_tvalid='native_tx_valid',
        s_axis_native_tready='native_tx_ready',s_axis_native_tlast='native_tx_last',s_axis_native_tuser='native_tx_user',
        m_axis_mac_tdata='mac_tx_data',m_axis_mac_tkeep='mac_tx_keep',m_axis_mac_tvalid='mac_tx_valid',
        m_axis_mac_tready='tr',m_axis_mac_tlast='mac_tx_last',m_axis_mac_tuser='mac_tx_user',
        s_mac_cpl_tag='s_axis_mac_cpl_tag',s_mac_cpl_ts='s_axis_mac_cpl_ts',s_mac_cpl_valid='s_axis_mac_cpl_valid',s_mac_cpl_ready='s_axis_mac_cpl_ready',
        m_native_cpl_tag='native_cpl_tag',m_native_cpl_ts='native_cpl_ts',m_native_cpl_valid='native_cpl_valid',m_native_cpl_ready='native_cpl_ready',
        hls_transport_drained='lf_transport_drained')
    h=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)\s*,?$',h,re.M)
    declarations=[];connections=[]
    for direction,width,name in ports:
        target=mapping.get(name,'mt_'+name);connections.append(f'.{name}({target})')
        if name not in mapping:
            if direction=='input':raise ValueError('unbound production input '+name)
            declarations.append('wire '+(width or'').replace('TX_TAG_WIDTH','16')+target+';')
    block=r'''
wire [127:0] native_tx_data;wire [15:0] native_tx_keep;wire native_tx_valid,native_tx_ready,native_tx_last;
wire [16:0] native_tx_user;wire [15:0] native_cpl_tag;wire [95:0] native_cpl_ts;wire native_cpl_valid,native_cpl_ready;
reg [127:0] native_host_words[0:3];integer native_host_i;
initial $readmemh("host.hex",native_host_words);
task native_host_frame;
 begin
  for(native_host_i=0;native_host_i<4;native_host_i=native_host_i+1)begin
   @(negedge clk);s_axis_host_tx_tdata=native_host_words[native_host_i];s_axis_host_tx_tkeep=native_host_i==3 ? 16'h0fff : 16'hffff;
   s_axis_host_tx_tlast=native_host_i==3;s_axis_host_tx_tuser={16'h9234,1'b0};s_axis_host_tx_tvalid=1;
   @(posedge clk);while(!s_axis_host_tx_tready)@(posedge clk);
  end
  @(negedge clk);s_axis_host_tx_tvalid=0;
 end
endtask
'''+ '\n'.join(declarations)+'\nrocev2_wqe_tx_lifetime full_WR('+',\n'.join(connections)+');'
    tb=tb[:start]+block+tb[end:]
    tb=once(tb,'else if(mac_tx_user[16:1]!=16\'h4000) $fatal(1,"unexpected legacy TX in responder-only phase");',r'''
else if((mac_tx_user[16:1]&16'he000)==16'h2000)
 $display("OWNED_MAC %032h %04h %b %04h",mac_tx_data,mac_tx_keep,mac_tx_last,mac_tx_user[16:1]);
else if(mac_tx_user[16:1]!=16'h4000)$fatal(1,"unowned native role");''')
    tb=once(tb,'if(lf_busy || completion_queue_guard || lf_committed_count!=1 || lf_fault)',
        'if(lf_busy || completion_queue_guard || lf_committed_count!=1 || lf_fault || mt_mac_proof_count!=1 || mt_frame_count!=1 || mt_receipt_count!=1 || !mt_local_tx_drained)')
    return f'`include "{mac.RTL}"\n`include "{RTL}"\n'+tb


class NativeMACLifetimeTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):old.native.native.shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def test_actual_native_MAC_role_receipt_and_tail_join_protected_DMA_until_CQ_commit(self):
        trace=old.TRACE;self.assertEqual(hashlib.sha256(trace.read_bytes()).hexdigest(),
            'd475a673fcc89c28245bd8cb148b2a2ef80b15f05d212be7301eb0cb929ca4d7')
        r0=json.loads(trace.read_text());self.assertTrue(r0['pass_test']);pkt=bytes.fromhex(r0['request_packet_hex'])
        self.assertEqual(len(pkt),60)
        records=[bytes.fromhex(v)for v in r0['actual_C_UBSan_WQE_records']]
        for i,data in enumerate(records):
            w=old.native.native.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,remote_key=0,opcode=2,flags=1,length=65)
            encoded=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(encoded,C.byref(w)),0)
            self.assertEqual(bytes(encoded),data);self.assertEqual(data,old.native.native.shared.codec.oracle(w))
        words=old.native.native.memory.sq.local.fixture.packet();tb=make_tb(words)
        paths=old.native.native.sq.input_paths(tb)+mac.SOURCES+[RTL,Path(__file__).resolve(),Path(mac.__file__).resolve(),
            Path(old.__file__).resolve(),Path(old.native.__file__).resolve(),Path(old.native.native.__file__).resolve(),
            Path(old.native.native.memory.__file__).resolve(),Path(old.native.native.executor.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(old.native.response.__file__).resolve(),
            Path(old.native.response.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',Path(old.lifetime.__file__).resolve(),old.lifetime.RTL,trace]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        frames=[bytes.fromhex(v)for v in r0['protected_input_packets_hex']]
        host=bytes.fromhex('b8830367c5d08af3fbb9753188b5')+bytes(((i*29)^0xa6)&255 for i in range(46))
        with tempfile.TemporaryDirectory(prefix='as02-native-mac-life-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(old.native.native.shared.protected.stub_source())
            values={'input.hex':words,'records.hex':[int.from_bytes(v,'little')for v in records],
                'response.hex':[int.from_bytes(v[n:n+16].ljust(16,b'\0'),'little')for v in frames for n in range(0,len(v),16)],
                'issued.hex':[int.from_bytes(pkt[n:n+16].ljust(16,b'\0'),'little')for n in range(0,60,16)],
                'host.hex':[int.from_bytes(host[n:n+16].ljust(16,b'\0'),'little')for n in range(0,60,16)]}
            for name,data in values.items():(p/name).write_text(''.join(f'{v:x}\n'for v in data))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),
                *map(str,old.native.native.memory.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text()
            names=['rocev2_wqe_tx_lifetime','rocev2_wqe_mac_tx','rocev2_wqe_lifetime','rocev2_wqe_response_guard',
                'rocev2_wqe_memory_executor','rocev2_mr_table','rocev2_mr_page_table','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[len('NATIVE_EXECUTOR_RESULT '):])for l in r.stdout.splitlines()if l.startswith('NATIVE_EXECUTOR_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual([rows[0][n]for n in ['physical_descriptors','read_tlps','write_tlps','fences']],[4,2,2,1])
            output=[l.split()for l in r.stdout.splitlines()if l.startswith('OWNED_MAC ')]
            actual=b''.join(bytes(b for i,b in enumerate(int(line[1],16).to_bytes(16,'little'))if int(line[2],16)>>i&1)for line in output)
            self.assertEqual(actual,bytes.fromhex('b8830367c5d08af3fbb975310800')+pkt)
            self.assertEqual([line[3]for line in output],['0']*4+['1']);self.assertEqual({line[4]for line in output},{'2001'})
            output=[l.split()for l in r.stdout.splitlines()if l.startswith('HOST_TX ')]
            actual=b''.join(bytes(b for i,b in enumerate(int(line[1],16).to_bytes(16,'little'))if int(line[2],16)>>i&1)for line in output)
            self.assertEqual(actual,host);self.assertEqual({line[4]for line in output},{'12468'})
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            actual_elaborated_module_counts=counts,actual_MAC_framing_tag_receipt_lifetime_proof=True,
            HLS_TX_is_trace_replay=True,HLS_ACK_extraction_drain_physical_MAC_pins_CQ_are_models=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_MAC_LIFETIME_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==1,methods=len(cls.reports),tests=cls.reports,
                real_native_MAC_role_mapper_and_lifetime=True,physical_MAC_HLS_extraction_ACK_drain_CQ_are_models=True,
                actual_native_WR_CQ_runtime=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
