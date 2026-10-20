# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full native real owned HLS stage and actual trusted SQC route binding.

Atomic RX still disabled. Network/host/MAC pins/peer remain modeled. New
bootstrap orders actual SQC creation BEFORE route open, like kernel verbs.
Unrelated earlier unsafe Ethernet re-COMMIT test is not repeated; all actual
WR/MR/DMA/HLS/MAC/CQ ownership assertions remain.
"""
import json
from pathlib import Path
import sys
import native_immediate_request_fixture as old
import check_immediate_native_elaboration as elaboration
import derive_atomic_native_owned_stage as stage

ROOT=stage.ROOT
digest=elaboration.delivery.digest
once=stage.once


def sources(project,immediate_report,owned_report,directory):
    src,data,before,_,_=elaboration.sources(project,immediate_report,directory)
    for original,text in stage.derive().items():
        name='rocev2_shared_protected_responder.v'if original==stage.authority.base.responder.ORIGINAL else original.name
        p=directory/name
        if not p.exists():
            if src.count(original)!=1:raise ValueError('one actual SQC input required')
            src.remove(original);src.append(p)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    info=json.loads(immediate_report.read_text())
    raw=ROOT/info['directory']/'project/solution1/syn/verilog'
    old_rtl={raw/n for n in info['generated_sha256']if n.endswith('.v')}
    if not old_rtl.issubset(src):raise ValueError('actual Immediate raw selection changed')
    src=[p for p in src if p not in old_rtl]
    data=[p for p in data if p.parent!=raw]
    hls=json.loads(owned_report.read_text())
    if not hls.get('pass_test')or hls.get('HLS_top')!='rocev2_native_atomic_owned_top':raise ValueError('matched owned raw required')
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
    for name,sha in hls['generated_sha256'].items():
        if digest(raw/name)!=sha:raise ValueError('actual owned raw changed')
    src+=[raw/n for n in hls['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in hls['generated_sha256']if n.endswith('.dat')]
    src+=stage.EXTRA
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,owned_report]})
    return list(dict.fromkeys(src)),data,before


def bench():
    t=old.case()
    connections=[];declarations=[]
    for direction,width,name in stage.authority.ROOT_PORTS:
        if direction=='input':value="1'b0" # No Atomic RX admitted in this stage.
        else:
            value='p_'+name;declarations.append('wire '+(width+' 'if width else'')+value+';')
        connections.append('.'+name+'('+value+')')
    t=once(t,'dut(.clk(clk),','dut('+','.join(connections)+',.clk(clk),')
    t=once(t,'integer runtime_native_opcode=2,request_event_file,request_word;',
        '\n'.join(declarations)+'\ninteger runtime_native_opcode=2,request_event_file,request_word;')
    # Real kernel verbs creates SQC before opening the RX route. Preserve the
    # real command and reply/proof assertions, only move its bootstrap order.
    t=once(t,'sq_command(1,0,0,7,0);','// SQC already created before opening RX route.')
    t=once(t,' host_api(6,100,0,0,17,0,0,0,0,0);',
        ' sq_command(1,0,0,7,0);\n host_api(6,100,0,0,17,0,0,0,0,0);\n'
        " if(!p_atomic_admission_valid || !p_atomic_bound_valid || p_atomic_bound_qpn!==2 || p_atomic_bound_pd!==17 ||\n"
        " p_atomic_bound_epoch!==64'h9123456700000001 || p_atomic_bound_cookie!==64'hfedcba9889abcdef || p_atomic_binding_fault)\n"
        '  $fatal(1,"actual native route not bound to actual SQC owner epoch/cookie/PD");')
    first=t.index(' // Stage changes are harmless while running.')
    last=t.index("\nread_reg(24'h402000",first)
    t=t[:first]+'\n // Unrelated unsafe Ethernet re-COMMIT case remains in the unchanged baseline, not this stage.\n'+t[last:]
    first=t.index('host_api(8,401,0,0,0,0,0,0,0,2);')
    last=t.index('read_reg(AS02_CTL_FEATURES,sq_value);',first)
    t=t[:first]+'// No pre-SQC STOP/reconfiguration: real SQC precedes RX route open.\n'+t[last:]
    t=once(t,'$display("NATIVE_RNIC_RESULT ',r'''
 $display("ATOMIC_NATIVE_OWNED_STAGE {\"pass_test\":true,\"actual_owned_HLS\":true,\"actual_SQC_binding\":true,\"Atomic_RX_selected\":false,\"physical_host_MAC_peer_models\":true}");
 $display("NATIVE_RNIC_RESULT ''')
    if 'force 'in t:raise ValueError('no internal force')
    return t
