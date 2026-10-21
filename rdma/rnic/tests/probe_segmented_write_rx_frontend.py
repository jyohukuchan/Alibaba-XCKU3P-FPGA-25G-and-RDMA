#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual IPv4/ICRC -> parsed-frame -> remote MR -> late-RQ -> owned replay.

Replay checks every unchanged IP/BTH/RETH/payload/pad/ICRC byte against
independent authored input, under stalls. MR and RQ are actual RTL, not
reply agents. Trusted management/context, posted admission, downstream
backend/HLS/MAC/CQ certificates remain MODELS. No full-native, payload-DMA,
generated new HLS, Linux, timing or physical qualification is claimed.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import probe_remote_write_mr_notice as prior

ROOT=prior.ROOT;digest=prior.digest;once=prior.queue.once
sys.path.insert(0,str(ROOT/'rdma/host'))
from rocev2_wire import icrc_ipv4,internet_checksum

FRONT=ROOT/'rdma/rnic/rtl/rocev2_segmented_write_rx_frontend.v'
AXIS=ROOT/'external/corundum/fpga/lib/eth/lib/axis/rtl'
ICRC=ROOT/'rdma/rtl/rocev2_ipv4_icrc.v'
LFSR=ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v'
# Case2 remains the separate 1MiB metadata test, not a newly claimed raw or
# native1MiB transfer. Raw26 cannot inject a private monotonic tag from wire.
# New46 checks an actual FIRST with1MiB RETH extent then safe cancellation;
# new47 presents correct-token proof before replay EOF;49 corrupts ICRC.
MODES=[i for i in range(46)if i not in [2,26]]+[46,47,49]


def geometry(mode):
    total=8192 if mode==3 else 4097 if mode==5 else 4096 if mode==11 else 1048577 if mode==12 else 1048576 if mode==46 else 8193
    return total,mode in [1,3,4,5,33,36]


def frame(mode,opcode,off,count,psn):
    total,imm=geometry(mode);first=opcode==6;notify=opcode==9
    va=(0xffffffffffffedef if mode==5 else 0xfedcba9876543000)+0x210
    key=8 if mode==8 else 0x80000009 if mode==10 else 0x80000008
    pad=(-count)&3;dest=7
    if first:
        if mode==14:pad=1
        if mode==16:dest=0x800007
        if mode==17:psn=(psn+1)&0xffffff
        if mode==20:key=0
        if mode==21:va=0xfffffffffffffff0
    bth=bytes([opcode,0x40|(pad<<4)])+b'\xff\xff\x00'+dest.to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
    reth=struct.pack('!QII',va,key,total)if first and mode!=19 else b''
    immediate=struct.pack('!I',0x89abcdef)if notify else b''
    data=bytes((((off+i)*113)^((off+i)>>8)^0xb7)&255 for i in range(count))
    padding=bytes((-count)&3)
    if mode==15 and first:padding+=bytes(4)
    body=bth+reth+immediate+data+padding
    size=20+8+len(body)+4
    ip=bytearray(struct.pack('!BBHHHBBHII',0x45,0,size,1,0x4000,64,17,0,0xc6120b01,0xc6120b02))
    ip[10:12]=internet_checksum(ip).to_bytes(2,'big')
    packet=bytes(ip)+struct.pack('!HHHH',49152,4791,size-20,0)+body+bytes(4)
    packet=packet[:-4]+icrc_ipv4(packet)
    if mode==49:packet=packet[:-1]+bytes([packet[-1]^1])
    return packet


def images(mode):
    total,imm=geometry(mode)
    planned=[(6,0,4095 if mode==13 else 4096,0xfffffe)]
    if mode in range(6,22)or mode in [27,28,29,31,34,35,37,39,40,41,42,43,44,45,46,47,49]:
        return [frame(mode,*v)for v in planned]
    if 22<=mode<=25:
        planned.append((8 if mode==23 else 6 if mode==24 else 12 if mode==25 else 7,4096,1 if mode==23 else 4096,0 if mode==22 else 0xffffff))
    else:
        for off in range(4096,total,4096):
            n=min(4096,total-off);last=off+n==total
            planned.append((9 if last and imm else 8 if last else 7,off,n,(0xfffffe+off//4096)&0xffffff))
            if mode==4 and last:planned.append(planned[-1])
    return [frame(mode,*v)for v in planned]


RAW=r'''
parameter [15:0] TAG_INIT=0;
reg [127:0] raw_data=0;reg [15:0] raw_keep=0;
reg raw_valid=0,raw_last=0;
wire raw_ready,checked_valid,checked_ready,checked_last;
wire [127:0] checked_data,output_data;wire [15:0] checked_keep,output_keep;
wire output_valid,output_last;
// Drive boundary READY away from the active clock edge. Deriving it from
// a blocking posedge scoreboard counter races the real register slice.
reg output_ready=0;
always @(negedge clk)output_ready=(cycle%7)!=0;
wire crc_good,crc_bad,crc_overflow;
wire [355:0] native_context={4'd7,48'h020000000001,48'h020000000002,
 32'hc6120b01,32'hc6120b02,24'd196,64'h8000000000000001,trusted_epoch,trusted_pd,trusted_qpn};
assign s_packet_ready=checked_ready;
rocev2_ipv4_icrc #(.TX_MODE(0)) actual_integrity(
 .clk(clk),.rst(rst),.s_axis_tdata(raw_data),.s_axis_tkeep(raw_keep),.s_axis_tvalid(raw_valid),
 .s_axis_tready(raw_ready),.s_axis_tlast(raw_last),.s_axis_tuser(1'b0),
 .m_axis_tdata(checked_data),.m_axis_tkeep(checked_keep),.m_axis_tvalid(checked_valid),
 .m_axis_tready(checked_ready),.m_axis_tlast(checked_last),
 .status_good_frame(crc_good),.status_bad_frame(crc_bad),.status_overflow(crc_overflow));
reg [144:0] input_words[0:4095];reg [4095:0] image_path;
integer input_count=0,input_index=0,current_start=0,current_words=0;
integer replay_start=0,replay_words=0,replay_index=0,replayed_frames=0,replayed_bytes=0;
integer crc_good_count=0,crc_bad_count=0;
reg replay_owned=0,output_complete=0,output_stalled=0;
reg [144:0] stalled_output;
always @(posedge clk)if(!rst)begin
 if(crc_good)crc_good_count=crc_good_count+1;
 if(crc_bad)crc_bad_count=crc_bad_count+1;
 if(crc_overflow)$fatal(1,"real checker overflow, never a fake accepted frame");
 if(m_packet_valid && m_packet_ready)begin
  if(replay_owned)$fatal(1,"new packet stole replay owner");
  replay_start=current_start;replay_words=current_words;replay_index=0;replay_owned=1;output_complete=0;
 end
 if(output_stalled && (!output_valid || {output_last,output_keep,output_data}!==stalled_output))
  $fatal(1,"actual registered replay changed under backpressure");
 output_stalled=output_valid && !output_ready;stalled_output={output_last,output_keep,output_data};
 if(output_valid && output_ready)begin
  if(!replay_owned || replay_index>=replay_words ||
     {output_last,output_keep,output_data}!==input_words[replay_start+replay_index])
   $fatal(1,"independent whole raw-frame byte/mask/EOF oracle");
  for(integer lane=0;lane<16;lane=lane+1)if(output_keep[lane])replayed_bytes=replayed_bytes+1;
  replay_index=replay_index+1;
  if(output_last)begin
   if(replay_index!=replay_words)$fatal(1,"short/duplicated actual replay");
   replay_owned=0;output_complete=1;replayed_frames=replayed_frames+1;
  end
 end
end
'''


def bench():
    text=prior.bench(prior.GUARD.read_text(),prior.queue.derive())
    special=dict(trusted_context='native_context',s_axis_tdata='checked_data',s_axis_tkeep='checked_keep',
        s_axis_tvalid='checked_valid',s_axis_tready='checked_ready',s_axis_tlast='checked_last',
        m_axis_tdata='output_data',m_axis_tkeep='output_keep',m_axis_tvalid='output_valid',
        m_axis_tready='output_ready',m_axis_tlast='output_last')
    ports=prior.ports(FRONT.read_text())
    instance='rocev2_segmented_write_rx_frontend #(.INITIAL_MESSAGE_COOKIE(COOKIE_INIT),.INITIAL_PACKET_TAG(TAG_INIT)) dut(\n'
    instance+=',\n'.join('.'+n+'('+special.get(n,n)+')'for _,_,n in ports)+'\n);'
    text=once(text,'rocev2_remote_write_message_guard #(.INITIAL_MESSAGE_COOKIE(COOKIE_INIT)) dut(.*);',RAW+'\n'+instance)
    # Separate new checked-frame fixture: same independent token/MR/RQ/
    # lifetime assertions, original10s/4ns/100000 cycles. Per-frame polling
    # includes full checker/replay latency rather than metadata-only latency.
    text=once(text,'while(!m_packet_valid && i<100)','while(!m_packet_valid && i<4000)')
    text=once(text,'while(!m_reject_valid && i<100)','while(!m_reject_valid && i<4000)')
    text=once(text,'m_reject_qpn!==7','m_reject_qpn!==(mode==16 ? 24\'h800007:24\'d7)')
    text=once(text,'trusted_expected_psn=cur_psn;s_packet_valid=1;\n @(posedge clk);if(!s_packet_ready)$fatal(1,"metadata ready under trusted fixed QP");\n @(negedge clk);s_packet_valid=0;',r'''
 trusted_expected_psn=cur_psn;s_packet_valid=0;
 current_start=input_index;current_words=0;
 begin: send_raw_frame
  reg last_word;
  last_word=0;
  while(!last_word)begin
   if(input_index>=input_count)$fatal(1,"authored raw frame image exhausted");
   {raw_last,raw_keep,raw_data}=input_words[input_index];raw_valid=1;
   @(posedge clk);while(!raw_ready)@(posedge clk);
   @(negedge clk);last_word=raw_last;input_index=input_index+1;current_words=current_words+1;
  end
 end
 raw_valid=0;
 // Return at the same public authorization boundary as the earlier
 // metadata-only producer. CRC buffering/replay is NOT MR reaction time.
 // Keep every original proof/fault assertion and its five-cycle bound.
 if(mode!=49)begin
  i=0;while(!m_mr_valid && !m_reject_valid && !fault && !m_packet_valid && i<4000)begin tick;i=i+1;end
  if(!m_mr_valid && !m_reject_valid && !fault && !m_packet_valid)
   $fatal(1,"checked frame did not reach actual authorization boundary");
 end''')
    a=text.index('task wait_grant;');b=text.index('endtask',a)
    text=text[:b]+r'''
 if(mode!=47)begin
  i=0;while(!output_complete && i<4000)begin tick;good;i=i+1;end
  if(!output_complete || replay_owned)$fatal(1,"actual full-frame replay before execution receipt");
 end
'''+text[b:]
    text=once(text,'if(!$value$plusargs("MODE=%d",mode))mode=0;',r'''
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 if(!$value$plusargs("IMAGE=%s",image_path) || !$value$plusargs("COUNT=%d",input_count) ||
    input_count<=0 || input_count>4096)$fatal(1,"exact bounded authored image required");
 $readmemh(image_path,input_words,0,input_count-1);''')
    text=once(text,'total=mode==2 ? 1048576:','total=mode==46 ? 1048576:mode==2 ? 1048576:')
    text=once(text,'if(mode==39)begin',r'''
 if(mode==49)begin
  emit_packet(6,0,4096,24'hfffffe,1);repeat(1000)tick;good;
  if(crc_bad_count!=1 || crc_good_count || queries || grants || m_reject_valid || output_valid || message_active)
   $fatal(1,"bad actual ICRC must never reach parsed MR/owner/replay");
 end else if(mode==39)begin''')
    text=once(text,'if(mode==28 || mode==29 || mode>=41 && mode<=44)',
        'if(mode==47 || mode==28 || mode==29 || mode>=41 && mode<=44)')
    text=once(text,'else if(mode==34 || mode==35)begin','else if(mode==46 || mode==34 || mode==35)begin')
    text=once(text,' $display("REMOTE_WRITE_MR_RESULT',r'''
 $display("RAW_WRITE_REPLAY_RESULT {\"mode\":%0d,\"CRC_good\":%0d,\"CRC_bad\":%0d,\"replayed_frames\":%0d,\"replayed_bytes\":%0d}",
  mode,crc_good_count,crc_bad_count,replayed_frames,replayed_bytes);
 $display("REMOTE_WRITE_MR_RESULT''')
    return text


def compiletime_lfsr():
    """Memoize the original constant-function matrix once per width.

    Simulation-only copy. No function, XOR, parameter, port, polynomial,
    hardware source, checker, assertion or deadline is changed. The original
    function is retained byte-for-byte. Its index-independent matrix prefix
    runs once; its unchanged selection suffix fills all constant indices.
    Every actual XOR/output and original function can reconstruct exactly.
    """
    original=LFSR.read_text()
    start=original.index('function [LFSR_WIDTH+DATA_WIDTH-1:0] lfsr_mask(')
    end=original.index('endfunction',start)+len('endfunction');function=original[start:end]
    sibling=once(function,'function [LFSR_WIDTH+DATA_WIDTH-1:0] lfsr_mask(input [31:0] index);',
        'function [(LFSR_WIDTH+DATA_WIDTH)*(LFSR_WIDTH+DATA_WIDTH)-1:0] all_lfsr_masks(input [31:0] unused);\n    integer index;')
    sibling=once(sibling,'        // reverse bits if selected',
        '        for(index=0;index<LFSR_WIDTH+DATA_WIDTH;index=index+1)begin\n        // reverse bits if selected')
    sibling=once(sibling,'        lfsr_mask = {data_val, state_val};',
        '        all_lfsr_masks[index*(LFSR_WIDTH+DATA_WIDTH)+:(LFSR_WIDTH+DATA_WIDTH)] = {data_val, state_val};\n        end')
    addition='\n'+sibling+'\nlocalparam [(LFSR_WIDTH+DATA_WIDTH)*(LFSR_WIDTH+DATA_WIDTH)-1:0] constant_masks = all_lfsr_masks(0);\n'
    result=original[:end]+addition+original[end:]
    for index in ['n','n+LFSR_WIDTH']:
        old='wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = lfsr_mask('+index+');'
        new='wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = constant_masks[('+index+')*(LFSR_WIDTH+DATA_WIDTH)+:(LFSR_WIDTH+DATA_WIDTH)];'
        if result.count(old)!=2:raise ValueError('both original XOR styles require the same exact mask')
        result=result.replace(old,new)
    reconstructed=once(result,addition,'')
    for index in ['n','n+LFSR_WIDTH']:
        reconstructed=reconstructed.replace(
            'wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = constant_masks[('+index+')*(LFSR_WIDTH+DATA_WIDTH)+:(LFSR_WIDTH+DATA_WIDTH)];',
            'wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = lfsr_mask('+index+');')
    if reconstructed!=original:raise ValueError('original complete LFSR must reconstruct byte-for-byte')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-rx-front-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-write-rx-front-',dir='/dev/shm'))
    sources=[FRONT,prior.GUARD,prior.MR,ICRC,AXIS/'axis_register.v',AXIS/'axis_fifo.v',LFSR]
    authored=sources+[Path(__file__).resolve(),Path(prior.__file__).resolve(),prior.BENCH,
        Path(prior.queue.__file__).resolve(),Path(prior.queue.parent.__file__).resolve(),prior.queue.SOURCE,
        ROOT/'rdma/host/rocev2_wire.py']
    before={str(n.relative_to(ROOT)):digest(n)for n in authored}
    for n in sources:shutil.copy2(n,run/n.name)
    (run/(prior.queue.NAME+'.v')).write_text(prior.queue.derive());(run/'tb.v').write_text(bench())
    (run/'lfsr_const_masks.v').write_text(compiletime_lfsr())
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},
        planned_modes=MODES,case_limit_seconds=10,compile_limit_seconds=10,clock_ns=4,cycle_limit=100000,
        actual_IPv4_ICRC=True,actual_remote_MR=True,actual_RQ=True,actual_registered_owned_replay=True,
        bytes_compared_to_authored_input=True,all_backend_HLS_MAC_CQ_certificate_producers_modeled=True,
        actual_generated_new_HLS=False,full_native_integration=False,payload_DMA_executed=False,
        full_raw_or_native_1MiB_transfer=False,hardware_verified=False,
        LFSR_simulation_only_constant_function_evaluation_at_compile_time=True,
        original_vendor_LFSR_and_all_actual_XOR_functions_parameters_unchanged=True)
    try:
        result['compile_commands']=[]
        for name,overrides in [('normal',[]),('cookie',["-Ptb.COOKIE_INIT=64'hffffffffffffffff"]),('tag',["-Ptb.TAG_INIT=16'hffff"])]:
            command=['iverilog','-g2012','-s','tb',*overrides,'-o',str(ram/name),str(run/'tb.v'),
                *[str(run/('lfsr_const_masks.v'if n==LFSR else n.name))for n in sources],str(run/(prior.queue.NAME+'.v'))]
            result['compile_commands'].append(command);start=time.monotonic()
            c=subprocess.run(command,capture_output=True,text=True,timeout=10)
            (run/(name+'-compile.log')).write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError('actual frontend compilation failed:'+str(run/(name+'-compile.log')))
        for mode in MODES:
            frames=images(mode);words=[]
            for data in frames:
                for off in range(0,len(data),16):
                    chunk=data[off:off+16]
                    words.append(int.from_bytes(chunk.ljust(16,b'\0'),'little')|(((1<<len(chunk))-1)<<128)|((off+16>=len(data))<<144))
            image=run/(str(mode)+'-input.hex');image.write_text(''.join(f'{v:037x}\n'for v in words))
            executable='cookie'if mode==37 else'tag'if mode==18 else'normal';start=time.monotonic()
            try:c=subprocess.run(['vvp',str(ram/executable),'+MODE='+str(mode),'+IMAGE='+str(image),'+COUNT='+str(len(words))],capture_output=True,text=True,timeout=10)
            except subprocess.TimeoutExpired as e:
                (run/(str(mode)+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b''));result['tests'][str(mode)]=dict(exit=None,timed_out=True,seconds=time.monotonic()-start);raise
            (run/(str(mode)+'.log')).write_text(c.stdout+c.stderr);t=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][str(mode)]=t
            if c.returncode:raise ValueError('actual checked-frame assertion failed:'+str(run/(str(mode)+'.log')))
            for label,key in [('REMOTE_WRITE_MR_RESULT','protection'),('RAW_WRITE_REPLAY_RESULT','replay')]:
                rows=[json.loads(l.split(' ',1)[1])for l in c.stdout.splitlines()if l.startswith(label+' ')]
                if len(rows)!=1:raise ValueError('missing actual RTL assertion summary:'+label)
                t[key]=rows[0]
            s=t['protection'];raw=t['replay']
            if mode==46:prior.verify(34,dict(s,mode=34))
            elif mode==47:
                if s['fault']!=1 or s['completed_packets']or s['completed_messages']or not s['message_active']:raise ValueError('premature EOF proof cannot advance actual frontend')
            elif mode==49:
                if raw['CRC_bad']!=1 or raw['CRC_good']or raw['replayed_frames']or s['MR_queries']or s['grants']:raise ValueError('real ICRC rejection before MR')
            else:prior.verify(mode,s)
            if mode in [0,1,3,4,5,38]:
                wanted=frames[:-1]if mode==4 else frames
                if raw['replayed_frames']!=len(wanted)or raw['replayed_bytes']!=sum(map(len,wanted)):raise ValueError('independent complete authorized replay count')
                t['every_input_byte_mask_EOF_unchanged']=True
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during actual execution')
        result.update(pass_test=True,source_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),maximum_seconds=max(v['seconds']for v in result['tests'].values()),full_native_or_physical=False)))


if __name__=='__main__':main()
