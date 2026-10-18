#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual combined app: invalid READ range -> CLEAR -> successful READ.

The real generated HLS/RTL is used, not the host-tool register model. The
remote RNIC, AXI-Lite host and physical MAC completion remain simulations.
"""
import argparse
import hashlib
import json
from pathlib import Path

import probe_rw_read as base

ROOT=base.ROOT


def bench(args,words,input_words,packets):
    tb=base.bench(args,words,input_words,packets)
    prelude=r'''
 recovery_probe_active=1;
 read_reg(24'h130,0,0);
 write_reg(24'h78,REQUIRED_BYTES-1,15,0,0);write_reg(24'h7c,0,15,0,0);
 write_reg(8,1,1,0,0);
 wait(done || failed);repeat(8) @(negedge clk);
 read_reg(12,32'h8bc,0);read_reg(16,1,0);read_reg(20,0,0);read_reg(24,0,0);
 read_reg(24'h110,0,0);read_reg(24'h114,0,0);read_reg(24'h118,0,0);read_reg(24'h11c,0,0);
 read_reg(24'h120,0,0);read_reg(24'h124,0,0);read_reg(24'h12c,6,0);read_reg(24'h130,1,0);
 read_reg(24'hc0,0,0);read_reg(24'hc4,0,0);read_reg(24'hcc,0,0);read_reg(56,0,0);
 if(net_frames!=0 || ack_events!=0 || guard_admitted!=0 || guard_completed!=0)
  $fatal(1,"invalid range issued transport traffic");
 write_reg(8,2,1,0,0);repeat(8) @(negedge clk);
 read_reg(12,32'hb8,0);read_reg(24'h130,1,0);read_reg(24'hc0,0,0);read_reg(24'hc4,0,0);
 for(ram_index=0;ram_index<RAM_WORDS;ram_index=ram_index+1)
  read_reg(24'h10000+ram_index*4,prefill_words[ram_index],0);
 write_reg(24'h78,REQUIRED_BYTES,15,0,0);read_reg(24'h78,REQUIRED_BYTES,0);
 recovery_probe_active=0;
 write_reg(8,1,1,0,0);
'''.replace('REQUIRED_BYTES',str(args.message_bytes*args.count)).replace('RAM_WORDS',str(words))
    tb=base.replace(tb,' write_reg(8,1,1,0,0);\n',prelude)
    tb=base.replace(tb,"read_reg(24'h130,1,0);\n for(ram_index=0;", "read_reg(24'h130,2,0);\n for(ram_index=0;")
    extra=r'''
reg recovery_probe_active=0;
integer invalid_probe_cycles=0,post_boot_global_resets=0;
always @(posedge rst) if(!boot_phase) post_boot_global_resets=post_boot_global_resets+1;
always @(posedge clk) if(!rst && recovery_probe_active) begin
 invalid_probe_cycles=invalid_probe_cycles+1;
 if(app.endpoint.qv || app.endpoint.cv || app.endpoint.sv || output_valid || model_mac_cpl)
  $fatal(1,"invalid advertised extent released QP/connection/SQ/network valid");
end
'''
    tb=base.replace(tb,'\nendmodule\n','\n'+extra+'\nendmodule\n')
    tb=base.replace(tb,' $finish;\n',r'''
 if(invalid_probe_cycles==0 || post_boot_global_resets!=0) $fatal(1,"missing probe or unexpected global reset");
 $display("RECOVERY {\"invalid_probe_cycles\":%0d,\"post_boot_global_resets\":%0d,\"invalid_qp_conn_sq_network_valid_cycles\":0,\"configuration_error_code\":1,\"final_generation\":2}",invalid_probe_cycles,post_boot_global_resets);
 $finish;
''')
    return tb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--message-bytes',type=int,default=65)
    parser.add_argument('--count',type=int,default=3)
    parser.add_argument('--initial-psn',type=lambda s:int(s,0),default=0xFFFFFE)
    parser.add_argument('--read-window',type=int,default=1)
    parser.add_argument('--wall-timeout',type=int,default=900)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();stride=(args.message_bytes+63)&~63;allocation=stride*args.count
    if args.report.exists() or not 1<=args.message_bytes<=65536 or not 1<=args.count<=4096 or \
        allocation>262144 or not 1<=args.read_window<=32 or not 0<=args.initial_psn<=0xFFFFFF:
        parser.error('new report and bounded READ configuration required')
    total=args.message_bytes*args.count
    payload=hashlib.shake_256(f'combined-rw-error-recovery/{args.message_bytes}/{args.count}/1'.encode()).digest(total)
    extent=min(262144,allocation+64);expected=bytearray(b'\xa5'*extent);prefill=bytearray(expected)
    inputs=[];after=[];packets=0;packets_per_op=(args.message_bytes+4095)//4096
    for index in range(args.count):
        part=payload[index*args.message_bytes:(index+1)*args.message_bytes];start=index*stride
        expected[start:start+args.message_bytes]=part
        prefill[start:start+args.message_bytes]=bytes(b^255 for b in part)
        frames=base.read_wire.responses(part,initial_psn=(args.initial_psn+index*packets_per_op)&0xFFFFFF,
            source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=2,msn=index+1)
        packets+=len(frames)
        for frame in frames:
            values=base.old.words(frame);inputs.extend(values);after.extend([index+1]*len(values))
    fixtures={'acks.hex':inputs,'ack_after.hex':after}
    for name,data in (('prefill.hex',prefill),('expected.hex',expected)):
        fixtures[name]=[int.from_bytes(data[i:i+4],'little') for i in range(0,extent,4)]
    output,identity=base.rw_sim.simulate(bench(args,extent//4,len(inputs),packets),fixtures,args.hls_build,args.wall_timeout)
    print(output,flush=True)
    frames=base.rw_sim.ethernet_frames(output)
    if len(frames)!=args.count:raise ValueError('invalid/valid sequence emitted wrong number of READ requests')
    for index,frame in enumerate(frames):
        decoded=base.read_wire.decode(frame)
        wanted=dict(opcode=base.read_wire.REQUEST,destination_qpn=0xABCDEF,
            psn=(args.initial_psn+index*packets_per_op)&0xFFFFFF,
            remote_address=0xFEDCBA9876543210+index*args.message_bytes,rkey=0xFEDCBA98,
            read_bytes=args.message_bytes,source_ip='198.18.11.2',destination_ip='198.18.11.1')
        if frame[:14]!=bytes.fromhex('b8830367c5d08af3fbb975310800') or any(decoded[k]!=v for k,v in wanted.items()):
            raise ValueError('READ request bytes/metadata differ after recovery')
    rows=[json.loads(s[7:]) for s in output.splitlines() if s.startswith('RESULT ')]
    recovery=[json.loads(s[9:]) for s in output.splitlines() if s.startswith('RECOVERY ')]
    if len(rows)!=1 or len(recovery)!=1 or rows[0]['wire_read_requests']!=args.count or \
        rows[0]['success_read_completions']!=args.count or recovery[0]['invalid_probe_cycles']<=0 or \
        recovery[0]['post_boot_global_resets']!=0:raise ValueError('missing successful error/recovery evidence')
    deps=[Path(__file__),Path(base.__file__),Path(base.rw_sim.__file__),Path(base.old.__file__),
        Path(base.app_boundary.__file__),Path(base.read_wire.__file__),ROOT / 'rdma/tests/test_control_rtl.py',
        ROOT / 'rdma/host/rocev2_wire.py',ROOT / 'rdma/tests/test_icrc_rtl.py']
    identity['source_sha256'].update({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in deps})
    result=dict(scope='Actual combined RW app/generated HLS error/CLEAR/READ RTL; no hardware',hardware_verified=False,
        pass_test=True,**identity,**rows[0],**recovery[0],message_bytes=args.message_bytes,message_count=args.count,
        initial_psn=args.initial_psn,read_window=args.read_window,response_packets=packets,
        advertised_remote_bytes_during_error=total-1,required_remote_bytes=total,source_range_restored=True,
        clear_without_global_reset=True,all_prefill_bytes_preserved_across_error_clear=True,
        prefill_bytes_verified=extent,all_request_bytes_checked=True,host_bar_readback_bytes_verified=total,
        untouched_sentinel_bytes_verified=extent-total,protected_ram_used=True,version2_bar_used=True,
        physical_mac_completion_modeled=True,native_read_verified=False,payload_sha256=hashlib.sha256(payload).hexdigest())
    with args.report.open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
