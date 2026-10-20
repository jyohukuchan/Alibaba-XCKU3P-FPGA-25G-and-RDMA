#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite actual IPv4 PSN-sequence NAK -> four per-WR-key replays, four-state.

Original four different keys on one QP, including0, then actual input ACK/NAK
with syndrome0x60. No internal forcing/shortened timer/metadata substitution.
Source memory and peer are models. This is not native DMA, general recovery,
RNR/timeout/congestion coverage, peer completion or standard verbs proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import probe_wrkey_wire as base
from wrkey_delivery_sim import ROOT, simulate, digest


def once(text, old, new):
    if text.count(old) != 1: raise ValueError('unreviewed wire bench dependency: '+old)
    return text.replace(old, new, 1)


def make_tb(write, peer_words):
    text = base.TB.replace('WRITE_VALUE', str(int(write)))
    text = once(text, 'reg [31:0] key=0;', '''reg [31:0] key=0;
reg [127:0] ip_data=0;reg [15:0] ip_keep=0;
reg ip_valid=0,ip_last=0;wire ip_ready;
reg [144:0] peer[0:PEER_LAST];integer peer_index=0;'''.replace('PEER_LAST', str(peer_words-1)))
    text = once(text, '.s_axis_rx_tdata(128\'d0),.s_axis_rx_tkeep(16\'d0),.s_axis_rx_tvalid(1\'b0),.s_axis_rx_tready(),.s_axis_rx_tlast(1\'b0),.s_axis_rx_tuser(1\'b0),',
        '.s_axis_rx_tdata(ip_data),.s_axis_rx_tkeep(ip_keep),.s_axis_rx_tvalid(ip_valid),.s_axis_rx_tready(ip_ready),.s_axis_rx_tlast(ip_last),.s_axis_rx_tuser(1\'b0),')
    text = once(text, 'integer cycle=0,issued=0,frames=0,commands=0,read_frames=0,offset=0,source_id=0;',
        'integer cycle=0,issued=0,frames=0,commands=0,read_frames=0,offset=0,source_id=0,tx_end=0,expected_source=0;')
    text = once(text, '$readmemh("sq.hex",requests);$readmemh("keys.hex",keys);',
        '$readmemh("sq.hex",requests);$readmemh("keys.hex",keys);$readmemh("peer.hex",peer);')
    text = once(text, ' mr=cycle>2500 && rng[2:0]!=0;', ''' if(!ip_valid && frames>=4 && cycle>tx_end+32 && peer_index<PEER_WORDS)begin
  {ip_last,ip_keep,ip_data}=peer[peer_index];ip_valid=1;
 end
 mr=cycle>2500 && rng[2:0]!=0;'''.replace('PEER_WORDS', str(peer_words)))
    text = once(text, ' if(sqv&&sqr)begin issued=issued+1;sqv<=0;end',
        ' if(sqv&&sqr)begin issued=issued+1;sqv<=0;end\n if(ip_valid&&ip_ready)begin peer_index=peer_index+1;ip_valid<=0;end')
    text = once(text, '''  if(!WRITE || active || commands>=4 || rc[47:0]!==48'h4000+commands*256 ||
     rc[75:48]!==28'd65 || rc[93:84]!==10'd2 || rc[79]!==((commands&1)!=0))''',
        '''  expected_source=commands%4;
  if(!WRITE || active || commands>=8 || rc[47:0]!==48'h4000+expected_source*256 ||
     rc[75:48]!==28'd65 || rc[93:84]!==10'd2 || rc[79]!==((expected_source&1)!=0) ||
     rc[78]!==((commands>=4)!=0) || rc[83:80]!==4'd0)''')
    text = once(text, '  source_id=commands;commands=commands+1;offset=0;active<=1;',
        '  source_id=expected_source;commands=commands+1;offset=0;active<=1;')
    text = once(text, 'if(tl)frames=frames+1;', 'if(tl)begin frames=frames+1;tx_end=cycle;end ')
    text = once(text, ' if(overflow!==0 || psndrop!==0 || retrans!==0 || rxbad!==0 || txbad!==0 || rxgood!==0)',
        ' if(overflow!==0 || psndrop!==0 || (^retrans)===1\'bx || retrans>4 || rxbad!==0 || txbad!==0 || (^rxgood)===1\'bx || rxgood>1)')
    text = once(text, ' if(issued==4 && frames==4 && txgood==4 && commands==WRITE*4 && read_frames==WRITE*4 && !active)',
        ' if(issued==4 && frames==8 && txgood==8 && commands==WRITE*8 && read_frames==WRITE*8 && !active && peer_index==PEER_WORDS && rxgood==1 && retrans==4)'.replace('PEER_WORDS', str(peer_words)))
    return text


def nak_packet():
    bth = bytes([0x11,0,0xff,0xff,0])+int(2).to_bytes(3,'big')+b'\0'+int(0xfffffe).to_bytes(3,'big')
    aeth = bytes.fromhex('60000001')
    ip = bytearray(struct.pack('!BBHHHBBH4s4s',0x45,0,48,0,0x4000,64,17,0,
                               bytes([198,18,11,1]),bytes([198,18,11,2])))
    ip[10:12] = struct.pack('!H',base.internet_checksum(ip))
    packet = bytes(ip)+struct.pack('!HHHH',4791,4791,28,0)+bth+aeth+b'\0'*4
    return packet[:-4]+base.icrc_ipv4(packet)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--operation',choices=['read','write'],required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve previous evidence')
    write=args.operation=='write';opcode=10 if write else 12
    packet=nak_packet()
    peer=[int.from_bytes(packet[i:i+16].ljust(16,b'\0'),'little')|
          (((1<<len(packet[i:i+16]))-1)<<128)|((i+16>=len(packet))<<144)
          for i in range(0,len(packet),16)]
    sq=[(0xdeadbeef<<208)|(65<<176)|(base.REMOTE[n]<<112)|((0x4000+n*256)<<48)|
        (1<<43)|((n&1)<<42)|(2<<32)|opcode for n in range(4)]
    own={str(p.relative_to(ROOT)):digest(p) for p in
         [Path(__file__).resolve(),Path(base.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']}
    tb=make_tb(write,len(peer))
    output,identity=simulate(tb,{'sq.hex':sq,'keys.hex':base.KEYS,'peer.hex':peer},args.hls_build)
    print(output,end='',flush=True)
    actual=base.packets(output)
    if len(actual)!=8:raise ValueError('expected four original and four real NAK replays')
    checked=[]
    for index,p in enumerate(actual):
        n=index%4;padding=3 if write else 0
        payload=bytes(((i*131)^(i>>8)^n^0x5a)&255 for i in range(65)) if write else b''
        if (len(p)!=(128 if write else 60) or p[0]!=0x45 or p[9]!=17 or
            int.from_bytes(p[2:4],'big')!=len(p) or base.internet_checksum(p[:20])!=0 or
            p[12:16]!=bytes([198,18,11,2]) or p[16:20]!=bytes([198,18,11,1]) or
            int.from_bytes(p[22:24],'big')!=4791 or int.from_bytes(p[24:26],'big')!=len(p)-20 or
            p[28]!=opcode or (p[29]>>4)&3!=padding or
            int.from_bytes(p[33:36],'big')!=196 or int.from_bytes(p[37:40],'big')!=((0xfffffe+n)&0xffffff) or
            int.from_bytes(p[40:48],'big')!=base.REMOTE[n] or
            int.from_bytes(p[48:52],'big')!=base.KEYS[n] or int.from_bytes(p[52:56],'big')!=65 or
            p[56:-4]!=payload+b'\0'*padding or p[-4:]!=base.icrc_ipv4(p)):
            raise ValueError('NAK replay changed key/PSN/address/payload/integrity index'+str(index))
        checked.append(dict(index=index,original_WR=n,replay=index>=4,rkey=f'0x{base.KEYS[n]:08x}',
            psn=f'0x{((0xfffffe+n)&0xffffff):06x}',sha256=hashlib.sha256(p).hexdigest(),hex=p.hex()))
    results=[json.loads(s[7:]) for s in output.splitlines() if s.startswith('RESULT ')]
    if len(results)!=1:raise ValueError('missing finite RTL result')
    if own!={n:digest(ROOT/n) for n in own}:raise ValueError('test source changed')
    identity['source_sha256'].update(own)
    report=dict(scope=__doc__,pass_test=True,operation=args.operation,**identity,**results[0],
        generated_testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
        peer_NAK_IP_hex=packet.hex(),peer_NAK_ICRC_valid=packet[-4:]==base.icrc_ipv4(packet),
        actual_wire_NAK_frames=1,actual_transport_retransmissions=4,original_WRs=4,
        zero_key_and_full_keys_PSN_addresses_payload_ICRC_preserved=True,
        initial_and_retry_host_selectors_verified=write,wire_payload_bytes_checked=520 if write else 0,
        packets=checked,physical_memory_and_peer_models=True,
        native_hardware_verified=False,hardware_verified=False,standard_verbs_implemented=False,
        general_recovery_RNR_timeout_congestion_verified=False)
    with args.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ['source_sha256','packets']},indent=2))


if __name__=='__main__':main()
