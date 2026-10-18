#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Two actual combined-app READ runs, same QP/PSNs, different source data.

An old-run READ FIRST is queued behind a backpressured ordinary host frame.
Release it only after the next run transmits: it must be discarded by the
run-generation router, while host data and the new READ remain intact.
No internal force, native RNIC, physical PCIe, or hardware access.
"""
import argparse
import hashlib
import json
from pathlib import Path

import probe_rw_read as base
import rw_sim

ROOT=rw_sim.ROOT
replace=base.replace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--wall-timeout',type=int,default=1200)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('select a new report')
    args.message_bytes=4097;args.count=1;args.initial_psn=0xFFFFFE;args.read_window=1
    size=args.message_bytes;stride=(size+63)&~63;extent=stride+64;word_count=extent//4
    payloads=[hashlib.shake_256(f'warm-rw-read/run{i}/same-psn'.encode()).digest(size) for i in (1,2)]
    expected=[];prefill=[];inputs=[];after=[]
    for run,payload in enumerate(payloads,1):
        want=bytearray(b'\xa5'*extent);want[:size]=payload;expected.append(want)
        initial=bytearray(want);initial[:size]=bytes(b^255 for b in payload);prefill.append(initial)
        frames=base.read_wire.responses(payload,initial_psn=args.initial_psn,source_ip='198.18.11.1',
            destination_ip='198.18.11.2',destination_qpn=2,msn=1)
        for frame in frames:
            words=base.old.words(frame);inputs.extend(words);after.extend([run]*len(words))
        if run==1:
            host=bytes(range(12))+b'\x08\x06'+bytes(range(46))
            # Queue only the old FIRST. If admitted after run2 starts, the
            # old4096bytes could be mixed with the new final byte; byte-exact
            # nonce readback would detect that, even with identical QP/PSNs.
            for frame in (host,frames[0]):
                words=base.old.words(frame);inputs.extend(words);after.extend([1]*len(words))
    tb=base.bench(args,word_count,len(inputs),2)
    display=next(line for line in tb.splitlines() if '$display("RESULT ' in line)
    operation=tb[tb.index(" read_reg(4,32'h20000,0);"):tb.index(display)]
    second=operation
    second=replace(second,"read_reg(24'h130,1,0)","read_reg(24'h130,2,0)")
    second=replace(second,"read_reg(24'hc0,1,0)","read_reg(24'hc0,2,0)")
    second=replace(second,"read_reg(24'hc4,1,0)","read_reg(24'hc4,2,0)")
    second=replace(second,'guard_admitted!=1 || guard_completed!=1','guard_admitted!=2 || guard_completed!=2')
    second=replace(second,'if(net_frames!=1 || ack_events!=1','if(net_frames!=2 || ack_events!=2')
    insertion=r'''
 write_reg(8,2,1,0,0);
 for(ram_index=0;ram_index<RAM_WORDS;ram_index=ram_index+1) begin
  prefill_words[ram_index]=prefill_second[ram_index];expected_words[ram_index]=expected_second[ram_index];
 end
'''.replace('RAM_WORDS',str(word_count))
    ending=r'''
 if(app.endpoint.ingress.stale_frame_count!=1 || host_frames!=1 || host_index!=4)
  $fatal(1,"old-run/host isolation missing stale=%0d host=%0d words=%0d",app.endpoint.ingress.stale_frame_count,host_frames,host_index);
 read_reg(24'hc8,1,0);
 $display("WARM_RESULT stale=1 runs=2 host_frames=1 same_psn=1 distinct_data=1");
'''
    tb=replace(tb,display,insertion+second+ending+display)
    tb=replace(tb,'reg output_ready=0,tx_allow=0;',r'''
reg output_ready=0,tx_allow=0,host_allow=0;
wire [255:0] host_data;wire [31:0] host_keep;wire [1:0] host_valid,host_last;
reg [145:0] host_expected[0:3];integer host_index=0,host_frames=0;
''')
    tb=replace(tb,".m_axis_sync_rx_tready(2'b11)",".m_axis_sync_rx_tready({host_allow,1'b1})")
    for name,value in [('tdata','host_data'),('tkeep','host_keep'),('tvalid','host_valid'),('tlast','host_last')]:
        tb=replace(tb,f'.m_axis_sync_rx_{name}()',f'.m_axis_sync_rx_{name}({value})')
    tb=replace(tb,' $readmemh("expected.hex",expected_words);',
        ' $readmemh("expected.hex",expected_words);\n $readmemh("prefill2.hex",prefill_second);\n'
        ' $readmemh("expected2.hex",expected_second);\n $readmemh("host.hex",host_expected);')
    tb=replace(tb,'integer ram_index,early_completion_events=0,observed_read_completions=0;',
        f'reg [31:0] prefill_second[0:{word_count-1}],expected_second[0:{word_count-1}];\n'
        'integer ram_index,early_completion_events=0,observed_read_completions=0;')
    tb=replace(tb,' if(ack_valid && ack_ready) begin\n  if(app.endpoint.control.capture_committed',
        ' if(app.endpoint.control.start) observed_read_completions=0;\n'
        ' if(ack_valid && ack_ready) begin\n  if(app.endpoint.control.capture_committed')
    extra=r'''
always @(negedge clk) if(!rst && net_frames>=2) host_allow=1;
always @(posedge clk) if(!rst && host_valid[1] && host_allow) begin
 if(host_index>=4 || {host_last[1],host_keep[31:16],host_data[255:128]}!==host_expected[host_index][144:0])
  $fatal(1,"backpressured ordinary host frame changed/lost");
 host_index=host_index+1;if(host_last[1]) host_frames=host_frames+1;
end
'''
    tb=replace(tb,'\nendmodule\n','\n'+extra+'\nendmodule\n')
    fixtures={'acks.hex':inputs,'ack_after.hex':after,'host.hex':base.old.words(host)}
    for name,data in [('prefill.hex',prefill[0]),('expected.hex',expected[0]),
                      ('prefill2.hex',prefill[1]),('expected2.hex',expected[1])]:
        fixtures[name]=[int.from_bytes(data[i:i+4],'little') for i in range(0,extent,4)]
    output,identity=rw_sim.simulate(tb,fixtures,args.hls_build,args.wall_timeout)
    print(output,flush=True)
    frames=rw_sim.ethernet_frames(output)
    if len(frames)!=2 or frames[0]!=frames[1]:raise ValueError('warm run did not reuse exact READ request/QP/PSN')
    for frame in frames:
        decoded=base.read_wire.decode(frame)
        if decoded['psn']!=0xFFFFFE or decoded['read_bytes']!=size:raise ValueError('wrong warm READ metadata')
    if output.count('WARM_RESULT stale=1 runs=2 host_frames=1 same_psn=1 distinct_data=1')!=1:
        raise ValueError('missing old-run isolation evidence')
    rows=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    if len(rows)!=1 or rows[0]['wire_read_requests']!=2 or rows[0]['success_read_completions']!=2:
        raise ValueError('warm READ completion count differs')
    deps=[Path(__file__),Path(base.__file__),Path(rw_sim.__file__),Path(base.old.__file__),
        Path(base.app_boundary.__file__),Path(base.read_wire.__file__),ROOT / 'rdma/tests/test_control_rtl.py',
        ROOT / 'rdma/tests/test_icrc_rtl.py',ROOT / 'rdma/host/rocev2_wire.py']
    identity['source_sha256'].update({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in deps})
    report=dict(scope='Actual combined RW app/HLS warm READ and queued stale-response RTL; not hardware',
        pass_test=True,hardware_verified=False,**rows[0],**identity,warm_runs=2,message_bytes=size,message_count_per_run=1,
        same_qp_and_psn_reused=True,distinct_payloads=True,stale_read_first_discarded=1,
        host_frame_preserved_under_backpressure=True,host_bar_readback_bytes_verified=size*2,
        untouched_sentinel_bytes_verified=(extent-size)*2,
        payload_sha256=[hashlib.sha256(p).hexdigest() for p in payloads],physical_mac_completion_modeled=True,
        physical_mac_drain_verified=False)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
