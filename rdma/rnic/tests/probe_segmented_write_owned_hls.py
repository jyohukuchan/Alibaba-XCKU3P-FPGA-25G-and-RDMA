#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual typed-WRITE EOF/ACK/MSN/PSN consumers plus all65 prior modes.

Full protected424 owner is modeled at the native/HLS boundary; receipts
are from actual HLS consumers and the actual same PSN table, not injected
certificate bits. Native MR/DMA/fence/MAC/CQ/Linux/physical proof remains.
Original full payload/wire/whole-RQ oracles and30s/600s/8QP/2000 gates stay.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_write_receive_hls as parent

ROOT=parent.ROOT;once=parent.once

HELPERS=r'''
static as02WriteOwner write_owner(unsigned sequence,unsigned total,unsigned offset,
    unsigned psn,unsigned first_psn,unsigned tag) {
    as02WriteOwner o;auto& t=o.token;t=0;
    t(423,400)=2;t(399,384)=17;t(383,320)=0x9123456700000001ULL;
    t(319,256)=0xfedcba9876543210ULL+sequence;t(255,224)=0x81234567;
    t(223,160)=0xe23456789abcdef0ULL;t(159,128)=total;t(127,104)=first_psn;
    t(103,72)=offset;t(71,40)=std::min(4096U,total-offset);t(39,16)=psn;t(15,0)=tag;
    assert(as02_write_owner_valid(o));return o;
}
template<int I> static void take_write_receipt(Harness<I>& h,as02WriteOwner o,unsigned msn) {
    assert(!h.write_fault && h.write_done.size()==1);auto d=h.write_done.read();
    assert(!d.error && d.proof.owner.token==o.token && d.proof.msn==msn);
}
'''


def write_owned_harness():
    t=parent.write_receive_harness()
    t=once(t,'hls::stream<as02WriteNotify> write_notify;',r'''
    hls::stream<as02WriteNotify> write_notify;
    hls::stream<as02WriteOwner> write_owners;
    hls::stream<as02WriteProof> write_data,write_ack;
    hls::stream<ap_uint<24>> write_state_req,write_dummy_req;
    hls::stream<ap_uint<56>> write_state_rsp,write_dummy_rsp;
    hls::stream<as02WriteDone> write_done;
    ap_uint<1> write_fault=0;bool write_table_enabled=true,write_join_enabled=true;''')
    t=once(t,'exh_words,recv_ack,zero_tx);','exh_words,recv_ack,write_ack,zero_tx);')
    t=once(t,'atomic_commit,recv_owners,write_notify,recv_fault,',
        'atomic_commit,recv_owners,write_owners,write_notify,recv_fault,')
    t=once(t,'memory,recv_data,read_consumed,pf,zero_data);',
        'memory,recv_data,write_data,read_consumed,pf,zero_data);')
    t=once(t,'recv_state_req,recv_state_rsp,state_req,state_rsp);',
        'recv_state_req,recv_state_rsp,state_req,state_rsp,\n'
        '            write_table_enabled ? write_state_req:write_dummy_req,write_table_enabled ? write_state_rsp:write_dummy_rsp);\n'
        '        if(write_join_enabled)as02_write_packet_retire_join<I>(write_data,write_ack,write_state_req,write_state_rsp,write_done,write_fault);')
    return t


def write_owned_prior():
    t=(ROOT/'rdma/rnic/hls/test_segmented_write_receive.cpp').read_text()
    t=once(t,'static const unsigned long long WRITE_VA=',HELPERS+'\nstatic const unsigned long long WRITE_VA=')
    t=once(t,'auto b=write_packet(imm,total,offset,psn,value);e.input(b,b.size()+12);',
        'auto w=write_owner(seq,total,offset,psn,initial,packets+1);e.h.write_owners.write(w);\n'
        '            auto b=write_packet(imm,total,offset,psn,value);e.input(b,b.size()+12);')
    t=once(t,'e.h.recv_owners.write(rq);\n            }\n            if(imm && last)',
        'assert(e.h.write_owners.size()==1);e.h.recv_owners.write(rq);\n            }\n            if(imm && last)')
    t=once(t,'            if(imm && last) {\n                assert(e.packets.size()==1);',r'''
            assert(e.h.write_done.size()==1 && !e.h.write_fault);auto wd=e.h.write_done.read();
            assert(!wd.error && wd.proof.owner.token==w.token && wd.proof.msn==(last ? seq:seq-1));
            std::cout<<std::dec<<"WRITE_PACKET_RECEIPT "<<total<<" "<<offset<<" "<<psn<<" "<<unsigned(wd.proof.msn)
                <<" "<<wd.proof.owner.token.to_string(16)<<std::endl;
            if(imm && last) {
                assert(e.packets.size()==1);''')
    t=once(t,'    std::cout<<std::dec<<"WRITE_RECEIVE_HLS',r'''
    std::cout<<std::dec<<"WRITE_PACKET_HLS {\"pass_test\":true,\"packets\":"<<packets
        <<",\"full424_owner\":true,\"actual_payload_EOF_ACK_MSN_same_PSN_table\":true,\"max_bytes\":1048576,"
        "\"RQ_not_remote_packet_owner\":true,\"native_backend_MAC_CQ\":false}"<<std::endl;
    std::cout<<std::dec<<"WRITE_RECEIVE_HLS''')
    t=once(t,'        e.input(first,first.size()+12);',
        '        e.h.write_owners.write(write_owner(1,8193,0,psn,0xfffffe,1));\n        e.input(first,first.size()+12);')
    t=once(t,'        psn=0xffffff;b=write_packet',
        '        take_write_receipt(e.h,write_owner(1,8193,0,0xfffffe,0xfffffe,1),0);\n        psn=0xffffff;b=write_packet')
    t=once(t,'            e.input(middle,middle.size()+12);',
        '            e.h.write_owners.write(write_owner(1,8193,4096,psn,0xfffffe,2));\n            e.input(middle,middle.size()+12);')
    t=once(t,'            psn=0;b=write_packet',
        '            take_write_receipt(e.h,write_owner(1,8193,4096,0xffffff,0xfffffe,2),0);\n            psn=0;b=write_packet')
    t=once(t,'    e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);',
        '    unsigned off=continuation ? (kind==13 || kind==14 || kind==15 || kind==16 ? 4096:8192):0;\n'
        '    e.h.write_owners.write(write_owner(1,8193,off,psn,0xfffffe,off/4096+1));\n'
        '    e.input(b,b.size()+12);e.h.dest.write(196);e.steps(240);\n'
        '    assert(e.h.write_done.empty());')
    return once(t,'int main(int argc,char **argv) {','int preceding_write_receive_main(int argc,char **argv) {')


def verify_packet_receipts(output):
    expected=[];psn=0xfffffe;tag=0
    for seq,total in enumerate([4097,8192,8193,12289,65537,1048576],1):
        first=psn
        for off in range(0,total,4096):
            count=min(4096,total-off);tag+=1;msn=seq if off+count==total else seq-1
            token=0
            for width,value in [(24,2),(16,17),(64,0x9123456700000001),(64,0xfedcba9876543210+seq),
                (32,0x81234567),(64,0xe23456789abcdef0),(32,total),(24,first),(32,off),(32,count),(24,psn),(16,tag)]:
                token=(token<<width)|value
            expected.append((total,off,psn,msn,token));psn=(psn+1)&0xffffff
    rows=[]
    for line in output.splitlines():
        if line.startswith('WRITE_PACKET_RECEIPT '):
            _,total,off,psn,msn,token=line.split();rows.append((*map(int,[total,off,psn,msn]),int(token,16)))
    if rows!=expected:raise ValueError('independent every full424 token/extent/PSN/MSN/tag/cookie oracle mismatch')
    return dict(packets=284,full424_identity=True,actual_EOF_ACK_MSN_and_same_table=True,metadata_MR_backend_MAC_CQ_not_proved=True)


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'from probe_segmented_write_receive_hls import write_receive_harness,verify_write_receive',
        'from probe_segmented_write_receive_hls import verify_write_receive\n'
        'from probe_segmented_write_owned_hls import write_owned_harness,write_owned_prior,verify_packet_receipts')
    t=once(t,"info.get('HLS_top')!='rocev2_native_segmented_write_receive_top'", "info.get('HLS_top')!='rocev2_native_segmented_write_owned_top'")
    t=once(t,"prefix='segmented-write-receive-hls-'","prefix='segmented-write-owned-hls-'")
    t=once(t,"prefix='as02-segmented-write-receive-hls-'","prefix='as02-segmented-write-owned-hls-'")
    t=once(t,'write_text(write_receive_harness())','write_text(write_owned_harness())')
    t=once(t,"shutil.copy2(hls/'test_segmented_write_receive.cpp',run/'test.cpp')",
        "(run/'write_prior.cpp').write_text(write_owned_prior())\n    shutil.copy2(hls/'test_segmented_write_owned.cpp',run/'test.cpp')")
    t=once(t,"['segmented_write_receive','segmented_receive'","['segmented_write_owned','segmented_write_receive','segmented_receive'")
    t=once(t,"ROOT/'rdma/rnic/tests/probe_segmented_write_receive_hls.py',",
        "ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',ROOT/'rdma/rnic/tests/probe_segmented_write_receive_hls.py',")
    t=once(t,"*['write-rx-bad'+str(i)for i in range(19)]]:",
        "*['write-rx-bad'+str(i)for i in range(19)],'write-owned-hold',*['write-owned-bad'+str(i)for i in range(21)]]:")
    t=once(t,"item['independent_write_receive_oracles']=verify_write_receive(r.stdout,mode=='write-rx-imm');markers=['WRITE_RECEIVE_HLS']",
        "item['independent_write_receive_oracles']=verify_write_receive(r.stdout,mode=='write-rx-imm');item['independent_write_packet_oracles']=verify_packet_receipts(r.stdout);markers=['WRITE_RECEIVE_HLS','WRITE_PACKET_HLS']")
    t=once(t,"            elif mode.startswith('write-rx-bad'):",
        "            elif mode=='write-owned-hold':\n                markers=['WRITE_PACKET_HOLD']\n"
        "            elif mode.startswith('write-owned-bad'):\n"
        "                if 'WRITE_PACKET_NEGATIVE '+mode[15:]not in r.stdout:raise ValueError('actual WRITE typed-owner negative missing')\n"
        "                markers=[]\n"
        "            elif mode.startswith('write-rx-bad'):")
    t=once(t,"if len(report['tests'])!=65:raise ValueError('all44 old plus2 new actual WRITE modes and19 negatives required')",
        "if len(report['tests'])!=87:raise ValueError('all65 prior exact modes and22 actual typed-WRITE cases required')")
    t=once(t,'segmented_WRITE_Immediate_RX=True,all44_prior_modes_retained=True,',
        'segmented_WRITE_Immediate_RX=True,typed424_remote_write_owner=True,actual456_write_packet_receipt=True,all65_prior_modes_retained=True,all44_prior_modes_retained=True,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-owned-hls-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
