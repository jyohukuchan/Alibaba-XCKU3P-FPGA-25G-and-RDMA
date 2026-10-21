#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual MR controller/MR/PTE and exact accepted-route observer/MSN logic.

Decoded host commands, QP apply/quiescence/parent drain are explicit models.
No SQC identity is supplied and no WR is issued: this isolates real accepted
configuration semantics, not native DMA/HLS/CQ or physical execution. Keep
the old failing native model; reproduce its route-erasure fault independently.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import test_mr_control_rtl as legacy
import probe_atomic_responder as helper

ROOT=legacy.ROOT;digest=helper.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_route as source


def observer(generated):
    t=generated[source.RTL/'rocev2_controlled_responder.v']
    start=t.index('reg tx_route_valid=0;')
    return t[start:t.index('\nrocev2_atomic_qp_binding ',start)]


TASKS=r'''
reg allow_qp=1;
reg [2:0] expected_reply_slot=0;
reg [23:0] applied_tx_psn=0;integer tx_only_commands=0,mutation_index=0;
always @(posedge clk)if(!rst && cfg_qp_valid && cfg_qp_ready)begin
 applied_tx_psn<=cfg_tx_psn;
 if(cfg_qp_tx_only)begin
  if({cfg_peer_qp_number,cfg_local_ip,cfg_peer_ip,cfg_rx_psn}!==112'd0)
   $fatal(1,"actual accepted QP_TX did not require empty route fields");
  tx_only_commands<=tx_only_commands+1;
 end
end
task txonly;input [15:0] pd;input [2:0] qpn;input integer mutation;
 begin
  @(negedge clk);s_command=9;s_sequence=next_sequence;next_sequence=next_sequence+1;
  s_cookie=403;s_slot=0;s_key=0;s_pd=pd;s_virtual_address=0;s_length=0;s_access=0;
  s_first_offset=0;s_page_index=0;s_dma_page=0;s_qp_number=qpn;s_peer_qp_number=0;
  s_local_ip=0;s_peer_ip=0;s_rx_psn=0;s_tx_psn=24'h89abcd;
  case(mutation)
   1:s_key=8;2:s_virtual_address=1;3:s_length=1;4:s_access=1;
   5:s_first_offset=1;6:s_page_index=1;7:s_dma_page=4096;
   8:s_peer_qp_number=196;9:s_local_ip=32'hc6120b02;10:s_peer_ip=32'hc6120b01;
   11:s_rx_psn=1;12:s_slot=1;
  endcase
  s_valid=1;@(posedge clk);while(!s_ready)@(posedge clk);
  @(negedge clk);s_valid=0;commands=commands+1;
 end
endtask
task route_ok;
 begin
  repeat(5)@(negedge clk);#1;
  if(msn_route_valid!==1 || msn_route_qpn!==2 || msn_route_peer_qpn!==196 ||
   msn_route_local_ip!==32'hc6120b02 || msn_route_peer_ip!==32'hc6120b01 ||
   p_fault || p_configuration_guard || p_queue_guard)
   $fatal(1,"accepted effective route changed or false MSN quarantine");
 end
endtask
'''


def bench(scenario):
    generated=(source.parent if scenario==0 else source).derive()
    raw=legacy.RTL.read_text().split('\n);',1)[0]
    driven=set('cfg_mr_ready cfg_mr_response_error cfg_mr_response_key cfg_mr_response_valid '
        'cfg_page_ready cfg_page_response_error cfg_page_response_key cfg_page_response_valid '
        'endpoint_quiescent cfg_qp_ready'.split())
    decl=[]
    for direction,width,name in re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',raw):
        reg=direction=='input'and name not in driven
        decl.append(('reg 'if reg else'wire ')+(width or'')+name+('=0;'if reg else';'))
    pred=helper.instance(source.RTL/'rocev2_expected_remote_msn.v','predictor','p_',dict(
        clk='clk',rst='rst',parent_fault="1'b0",route_valid='msn_route_valid',route_qpn='msn_route_qpn',
        route_peer_qpn='msn_route_peer_qpn',route_local_ip='msn_route_local_ip',route_peer_ip='msn_route_peer_ip',
        s_query_valid="1'b0",s_query_cookie="64'd0",s_query_epoch="64'd0",s_query_pd="16'd0"))
    t=legacy.TB[:legacy.TB.index('initial begin\n #1 rst=1;')]
    t=source.once(t,'rocev2_mr_control ctrl(.*);','rocev2_mr_control #(.QP_TX_ENABLE(1)) ctrl(.*);')
    t=source.once(t,'assign cfg_qp_ready=quiet && !qp_pending;',
        "assign cfg_qp_ready=quiet && !qp_pending && allow_qp && p_configuration_guard===1'b0;")
    t=source.once(t,'m_slot!==0','m_slot!==expected_reply_slot')
    extra='localparam MAX_QPS=8;\nwire msn_route_valid;wire [23:0] msn_route_qpn,msn_route_peer_qpn;\n'
    extra+='wire [31:0] msn_route_local_ip,msn_route_peer_ip;\n'+pred+observer(generated)+TASKS
    t=t.replace('// PORTS','\n'.join(decl)+'\n'+extra)
    body=r'''
initial begin
 rst=1;parent_dma_drained=1;repeat(5)@(negedge clk);rst=0;
 seed(0);
 // BODY
 if(fatal || building || active || p_message_count || p_retired_count || p_busy && !p_fault)
  $fatal(1,"isolated config test invented work or changed controller state");
 $display("CONFIG_ROUTE_RESULT {\"scenario\":%0d,\"actual_QP_configs\":%0d,\"actual_QP_TX_configs\":%0d,\"MSN_fault\":%0d,\"MSN_fault_code\":%0d,\"observed_peer\":%0d,\"applied_TX_PSN\":%0d}",
  SCENARIO,qp_commands,tx_only_commands,p_fault,p_fault_code,msn_route_peer_qpn,applied_tx_psn);
 $finish;
end
endmodule
'''.replace('SCENARIO',str(scenario))
    setup="submit(6,100,0,0,0);response(6,100,0,0,0);route_ok();\n"
    if scenario in (0,1):
        code=setup+"txonly(17,2,0);response(9,403,0,0,0);\n"
        if scenario==0:
            code+=r'''
repeat(5)@(negedge clk);
if(tx_only_commands!=1 || msn_route_valid!==1 || msn_route_peer_qpn!==0 ||
 msn_route_local_ip!==0 || msn_route_peer_ip!==0 || !p_fault || p_fault_code!==8'ha2 || p_queue_guard!==255)
 $fatal(1,"old actual accepted QP_TX route-erasure fault not reproduced");
'''
        else:code+='route_ok();if(tx_only_commands!=1 || applied_tx_psn!==24\'h89abcd)$fatal(1,"TX PSN update not accepted");\n'
    elif scenario==2:
        code="txonly(17,2,0);response(9,403,0,8'he2,0);\n"
        code+="if(qp_commands || tx_only_commands || msn_route_valid || p_fault)$fatal(1,\"QP_TX invented missing route\");\n"
    elif scenario==3:
        code=setup+"txonly(18,2,0);response(9,403,0,8'he2,0);route_ok();\n"
        code+="txonly(17,3,0);response(9,403,0,8'he2,0);route_ok();\n"
        code+="for(mutation_index=1;mutation_index<=12;mutation_index=mutation_index+1)begin expected_reply_slot=mutation_index==12 ? 1:0;txonly(17,2,mutation_index);response(9,403,0,8'he4,0);route_ok();end\n"
        code+="if(qp_commands!=1 || tx_only_commands)$fatal(1,\"invalid QP_TX reached observer\");\n"
    elif scenario==4:
        code=setup+"allow_qp=0;txonly(17,2,0);while(!cfg_qp_valid)@(negedge clk);\n"
        code+='repeat(20)begin route_ok();if(qp_commands!=1 || tx_only_commands || m_valid)$fatal(1,"unaccepted QP_TX observed");end\n'
        code+='allow_qp=1;response(9,403,0,0,0);route_ok();\n'
    elif scenario==5:
        code=setup+"submit(6,101,0,0,0);response(6,101,0,0,0);route_ok();\n"
        code+='txonly(17,2,0);response(9,403,0,0,0);route_ok();\n'
        code+='@(negedge clk);rst=1;repeat(5)@(negedge clk);rst=0;repeat(5)@(negedge clk);\n'
        code+='if(msn_route_valid || p_fault || p_queue_guard || qp_configured)$fatal(1,"reset retained stale accepted route");\n'
    else:raise ValueError('unknown config route case')
    return t+body.replace('// BODY',code)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    run=Path(tempfile.mkdtemp(prefix='read-config-route-',dir=ROOT/'rdma/rnic/build'))
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys([
        Path(__file__).resolve(),Path(legacy.__file__).resolve(),Path(helper.__file__).resolve(),
        *legacy.SOURCES,*source.RTL.glob('*.v'),*list((ROOT/'rdma/rnic/fpga').glob('*.py'))])}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),four_state=True,
        actual_MR_controller=True,actual_MR_and_PTE=True,exact_native_route_observer=True,
        actual_MSN_predictor=True,SQC_identity_supplied=False,WRs_issued=0,native_runtime=False,
        HLS_QP_apply_modeled=True,hardware_verified=False,simulation_limit_seconds=10,
        source_sha256=before,tests={})
    try:
        prior=source.parent.derive();new=source.derive()
        if {q.name for q in new if new[q]!=prior[q]}!={'rocev2_controlled_responder.v'}:
            raise ValueError('only accepted-route observer may change')
        for n in range(6):
            case=run/str(n);case.mkdir();(case/'tb.v').write_text(bench(n))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(case/'test.vvp'),str(case/'tb.v'),
                *map(str,legacy.SOURCES),str(source.RTL/'rocev2_expected_remote_msn.v')],capture_output=True,text=True,timeout=30)
            (case/'compile.log').write_text(c.stdout+c.stderr)
            if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):
                raise ValueError('config route compile/width failure:'+str(n))
            start=time.monotonic();r=subprocess.run(['vvp',str(case/'test.vvp')],capture_output=True,text=True,timeout=10)
            output=r.stdout+r.stderr;(case/'simulation.log').write_text(output)
            item=dict(seconds=time.monotonic()-start,exit=r.returncode,pass_test=False);report['tests'][str(n)]=item
            if r.returncode or 'FATAL:'in output or 'ERROR:'in output:raise ValueError('config route runtime failed:'+str(n))
            rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('CONFIG_ROUTE_RESULT ')]
            if len(rows)!=1:raise ValueError('actual config observation missing')
            item.update(pass_test=True,summary=rows[0],baseline_fault_reproduction=n==0)
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True,cases=6,old_native_failure_preserved=True,
            accepted_TX_only_preserves_effective_route=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.rglob('*')if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=6,directory=report['directory'])))


if __name__=='__main__':main()
