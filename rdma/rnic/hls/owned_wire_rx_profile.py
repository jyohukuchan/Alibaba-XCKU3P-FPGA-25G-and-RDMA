#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual BTH/EXH byte parsing -> same-table lookup -> retained raw RX token.

Not native packet/connection authentication, effectful RX IBH/EXH execution,
memory placement/CQ or whole-core retirement. Original candidates untouched.
"""
import importlib.util
from pathlib import Path
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
base=module('rx_lookup',Path(__file__).with_name('owned_rx_lookup_profile.py'))
lex=module('wire_tx',Path(__file__).with_name('owned_wire_tx_profile.py'))
ROOT=base.ROOT;BASE=base.BASE;META=base.META;TIMER=base.TIMER;TOP=base.TOP
CPP=lex.CPP;HPP=lex.HPP;once=base.once
derive_timer=base.derive_timer

def derive_query_decoder():
    # Preserve every original field/reserved-bit guard. Only replace the
    # FIFO-read source with an actual elastic full320-bit capture register.
    s=once(base.DECODE,'''    if(!in.empty() && !out.full()) {
        ap_uint<320> r=in.read();as02RxLookupQuery q;''',r'''    static bool have=false;static ap_uint<320> held=0;
    if(have && !out.full()) {
        ap_uint<320> r=held;as02RxLookupQuery q;''')
    s=once(s,'q.bad=r(319,298)!=0;out.write(q);','q.bad=r(319,298)!=0;out.write(q);have=false;')
    s=once(s,'    }\n}\n','    }\n    if(!have && !in.empty()) {held=in.read();have=true;}\n}\n')
    return s

def derive(original):
    # Keep the real tables/process; only register the first-record epoch
    # selection before later chain comparisons. All original guards remain.
    s=base.derive(original)
    s=once(s,'RX_CHECK,RX_RANGE,RX_MATCH','RX_CHECK,RX_EPOCH,RX_CHAIN,RX_RANGE,RX_MATCH')
    s=once(s,'''        if(lookup_walked==0) {
            lookup_epoch=meta.lease(183,120);
            if(lookup_epoch!=rx_query.epoch) {lookup_walked=1;lookup_status=3;state=RX_RESULT;break;}
        }
        if(meta.lease(183,120)!=lookup_epoch''',r'''        if(lookup_walked==0)lookup_epoch=meta.lease(183,120);
        state=RX_EPOCH;break;
    case RX_EPOCH:
        if(lookup_walked==0 && lookup_epoch!=rx_query.epoch) {
            lookup_walked=1;lookup_status=3;state=RX_RESULT;break;
        }
        state=RX_CHAIN;break;
    case RX_CHAIN:
        if(meta.lease(183,120)!=lookup_epoch''')
    return s

TYPES=r'''
struct as02RxWireIbh {
    ibhMeta normal;ap_uint<96> raw=0;
    as02RxWireIbh() {}
    as02RxWireIbh(ibhMeta n,ap_uint<96> r):normal(n),raw(r) {}
};
inline as02RxWireExhMeta as02_rx_aeth_meta(bool nak,ap_uint<8> syndrome) {
    as02RxWireExhMeta m(nak);m.syndrome=syndrome;m.has_aeth=true;return m;
}
'''

INGRESS=r'''
// Descriptor320:QPN23:0/epoch87:24/length103:88/admitted104/marker105 /
// marker-owner273:106/expectedPKey289:274/reserved319:290. The admission bit
// and epoch are TRUSTED CALLER inputs, NOT proof of real ICRC/peer/native auth.
// Exact canonical keep decode: all256 patterns retain the original validity
// rule. Avoid eight serial32-bit conditional increments in a one-beat path.
inline ap_uint<4> as02_rx_wire_keep_bytes(ap_uint<8> keep) {
#pragma HLS inline
    switch(keep.to_uint()) {
    case 1:return 1;case 3:return 2;case 7:return 3;case 15:return 4;
    case 31:return 5;case 63:return 6;case 127:return 7;case 255:return 8;
    default:return 0;
    }
}
// A genuine II1 dataflow stage, not an extra serialized per-body-beat state.
// No side effects/packet authorization; exact bytes stay with decode fields.
void as02_rx_wire_decode(stream<ap_uint<80>>& packets,stream<ap_uint<96>>& decoded) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!packets.empty() && !decoded.full()) {
        ap_uint<80> r=packets.read();ap_uint<96> d=0;d(79,0)=r;
        d(83,80)=as02_rx_wire_keep_bytes(r(71,64));
        ap_uint<8> opcode=r(7,0);ibOpCode op=static_cast<ibOpCode>(opcode.to_uint());
        d(88,84)=checkIfAethHeader(op)?16:(checkIfRethHeader(op)?28:12);
        d[89]=opcode>RC_ACK;decoded.write(d);
    }
}
void as02_rx_wire_ingress(stream<ap_uint<320>>& descriptors,stream<ap_uint<96>>& packets,
    stream<ap_uint<320>>& begins,stream<ap_uint<128>>& annotated,
    stream<ap_uint<320>>& completed,ap_uint<32>& fault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum State {LOAD,CHECK,DISPATCH,COLLECT,WAIT,RECEIPT_CHECK};static State state=LOAD;
    static ap_uint<320> descriptor=0,receipt=0;static ap_uint<17> count=0;
    static ap_uint<32> error=0;static bool quarantined=false;
    fault=error;if(quarantined)return;
    if(state==LOAD) {
        if(!descriptors.empty()) {
            descriptor=descriptors.read();count=0;state=CHECK;
        }
    } else if(state==CHECK) {
        if(descriptor(319,290)!=0) {error=40;quarantined=true;return;}
        if(descriptor[105]) {
            ap_uint<168> owner=descriptor(273,106);
            if(descriptor(104,0)!=0 || descriptor(289,274)!=0 || owner(15,0)>=MAX_QPS ||
                owner(103,40)==0 || owner(167,104)==0) {error=40;quarantined=true;return;}
        } else {
            if(!descriptor[104] || descriptor(23,0)>=MAX_QPS || descriptor(87,24)==0 ||
                descriptor(103,88)<12 || descriptor(273,106)!=0) {error=40;quarantined=true;return;}
        }
        state=DISPATCH;
    } else if(state==DISPATCH) {
        begins.write(descriptor);state=descriptor[105]?WAIT:COLLECT;
    } else if(state==COLLECT) {
        if(!packets.empty() && !annotated.full()) {
            ap_uint<96> d=packets.read();ap_uint<4> bytes=d(83,80);
            ap_uint<17> total=count+ap_uint<17>(bytes);
            ap_uint<128> a=0;a(95,0)=d;a(112,96)=total;a[113]=count==0;
            annotated.write(a);count=total;if(d[72])state=WAIT;
        }
    } else if(state==WAIT) {
        if(!completed.empty()) {receipt=completed.read();state=RECEIPT_CHECK;}
    } else {
        if(receipt!=descriptor) {error=41;quarantined=true;return;}
        state=LOAD;
    }
}

// Only private actual count annotations enter. Guard evaluation is DATA, not
// a conditional write/retirement. The following commit task enforces it.
void as02_rx_wire_frame_check(stream<ap_uint<320>>& begins,stream<ap_uint<128>>& annotated,
    stream<ap_uint<320>>& checked_begins,stream<ap_uint<128>>& checked) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static bool collecting=false,have=false;static ap_uint<320> descriptor=0;
    static ap_uint<128> saved=0;
    // One genuine elastic register separates validation from FIFO output.
    // Pop and replace in the same cycle; stalls never overwrite a saved beat.
    if(have && !checked.full()) {checked.write(saved);have=false;}
    if(!collecting) {
        if(!have && !begins.empty()) {
            descriptor=begins.read();checked_begins.write(descriptor);collecting=!descriptor[105];
        }
    } else if(!have && !annotated.empty()) {
        ap_uint<128> a=annotated.read();ap_uint<96> d=a(95,0);ap_uint<80> r=d(79,0);
        net_axis<64> w;w.data=r(63,0);w.keep=r(71,64);w.last=r[72];
        ap_uint<8> keep=w.keep;ap_uint<4> bytes=d(83,80);ap_uint<17> total=a(112,96);
        bool bad=a(127,114)!=0 || d(95,90)!=0 || r(79,73)!=0 || bytes==0 || (!w.last && keep!=255) ||
            total>descriptor(103,88) || total>65535 || (!w.last && total==descriptor(103,88)) ||
            (w.last && total!=descriptor(103,88)) ||
            (a[113] && (d[89] || descriptor(103,88)<d(88,84)));
        a[114]=bad;saved=a;have=true;if(w.last)collecting=false;
    }
}

void as02_rx_wire_frame_commit(stream<ap_uint<320>>& begins,stream<ap_uint<128>>& checked,
    stream<net_axis<64>>& retained,stream<ap_uint<320>>& commands,ap_uint<32>& fault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum State {LOAD,COLLECT,EMIT};static State state=LOAD;static ap_uint<320> descriptor=0;
    static ap_uint<32> error=0;static bool quarantined=false;fault=error;if(quarantined)return;
    if(state==LOAD) {
        if(!begins.empty()) {descriptor=begins.read();state=descriptor[105]?EMIT:COLLECT;}
    } else if(state==COLLECT) {
        if(!checked.empty() && !retained.full()) {
            ap_uint<128> a=checked.read();
            if(a[114] || a(127,115)!=0) {error=40;quarantined=true;return;}
            net_axis<64> w;w.data=a(63,0);w.keep=a(71,64);w.last=a[72];retained.write(w);
            if(w.last)state=EMIT;
        }
    } else {commands.write(descriptor);state=LOAD;}
}

void as02_rx_wire_release(stream<ap_uint<320>>& commands,stream<net_axis<64>>& retained,
    stream<ap_uint<320>>& front_commands,stream<net_axis<64>>& parser_input) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static bool body=false;
    if(!body) {
        if(!commands.empty()) {ap_uint<320> c=commands.read();front_commands.write(c);body=!c[105];}
    } else if(!retained.empty()) {
        net_axis<64> w=retained.read();parser_input.write(w);if(w.last)body=false;
    }
}
'''

FRONT=r'''
// Token1024: lookup447:0/rawBTH543:448/rawEXH671:544/numPkg693:672 /
// original-isNAK694/REMOTE_RAW695/descriptor1015:696/reserved1023:1016.
// UNIQUE means identity ONLY. Native consumer must retain the real WR/MR
// lifetime before accepting; token/body handoff is NOT memory/CQ retirement.
void as02_rx_wire_front(stream<ap_uint<320>>& commands,stream<as02RxWireIbh>& ibhs,
    stream<as02RxWireExhMeta>& exhs,stream<ExHeader<64>>& headers,
    stream<net_axis<64>>& raw_body,stream<ap_uint<1>>& parser_ends,
    stream<ap_uint<320>>& queries,stream<ap_uint<448>>& bindings,stream<ap_uint<448>>& lookup_accepts,
    stream<ap_uint<1024>>& meta,stream<ap_uint<80>>& body,
    stream<ap_uint<1024>>& meta_accepts,stream<ap_uint<1024>>& body_accepts,stream<ap_uint<192>>& resumes,
    stream<ap_uint<320>>& completed,ap_uint<32>& fault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum State {LOAD,HEADERS,HEADER_CHECK,HEADER_CLASSIFY,QUERY_BUILD,REMOTE_BUILD,
        QUERY,RESPONSE,CHECK,CHECK_RESULT,BUILD,META,ACCEPT,CHECK_ACCEPT,
        LOOKUP_ACCEPT,BODY,END,BODY_ACCEPT,CHECK_BODY_ACCEPT,DONE,MARKER,MARKER_RESUME};
    static State state=LOAD;static ap_uint<320> descriptor=0,query=0;
    static ap_uint<448> binding=0;static ap_uint<1024> token=0,receipt=0;
    static as02RxWireIbh ibh;static as02RxWireExhMeta exh;static ExHeader<64> header;
    static bool local=false,no_body=false,discard=false;
    static ap_uint<4> binding_invalid=0;
    static ap_uint<32> error=0;fault=error;if(error)return;
    switch(state) {
    case LOAD:
        if(!commands.empty()) {descriptor=commands.read();state=descriptor[105]?MARKER:HEADERS;}
        break;
    case HEADERS:
        if(!ibhs.empty() && !exhs.empty() && !headers.empty()) {
            ibh=ibhs.read();exh=exhs.read();header=headers.read();
            state=HEADER_CHECK;
        }
        break;
    case HEADER_CHECK:
        if(ibh.normal.dest_qp!=descriptor(23,0) || ibh.normal.partition_key!=descriptor(289,274) ||
            (ibh.raw(15,8)&15)!=0 || (ibh.raw(39,32)&63)!=0 || (ibh.raw(71,64)&127)!=0 ||
            exh.has_aeth!=checkIfAethHeader(ibh.normal.op_code)) {error=42;break;}
        state=HEADER_CLASSIFY;break;
    case HEADER_CLASSIFY:
        local=checkIfResponse(ibh.normal.op_code);
        no_body=ibh.normal.op_code==RC_ACK || (checkIfRethHeader(ibh.normal.op_code) && descriptor(103,88)==28);
        discard=false;state=local?QUERY_BUILD:REMOTE_BUILD;break;
    case QUERY_BUILD:
        query=0;query(23,0)=ibh.normal.dest_qp;query(47,24)=ibh.normal.psn;
        query(55,48)=static_cast<unsigned>(ibh.normal.op_code);query(119,56)=descriptor(87,24);
        query(127,120)=exh.syndrome;query[128]=exh.has_aeth;state=QUERY;break;
    case REMOTE_BUILD:
        binding=0;binding(271,248)=ibh.normal.dest_qp;binding(295,272)=ibh.normal.psn;
        binding(303,296)=static_cast<unsigned>(ibh.normal.op_code);binding(367,304)=descriptor(87,24);
        binding(399,392)=255;binding(419,412)=exh.syndrome;binding[420]=exh.has_aeth;state=BUILD;break;
    case QUERY:queries.write(query);state=RESPONSE;break;
    case RESPONSE:if(!bindings.empty()) {binding=bindings.read();state=CHECK;}break;
    case CHECK: {
        ap_uint<8> status=binding(399,392);ap_uint<248> lease=binding(247,0);
        binding_invalid[0]=!binding[422] || binding(447,423)!=0 || binding(411,400)>META_TABLE_SIZE || status>3;
        binding_invalid[1]=binding(271,248)!=query(23,0) ||
            binding(295,272)!=query(47,24) || binding(303,296)!=query(55,48) ||
            binding(367,304)!=query(119,56) || binding(419,412)!=query(127,120) ||
            binding[420]!=query[128];
        binding_invalid[2]=status==0 && (!as02_timer_lease_valid(lease) || lease(95,80)!=query(23,0) || lease(183,120)!=query(119,56));
        binding_invalid[3]=status!=0 && (lease!=0 || binding(391,368)!=0 || binding[421]);
        state=CHECK_RESULT;break;
    }
    case CHECK_RESULT:
        if(binding_invalid!=0) {error=43;break;}
        discard=binding(399,392)!=0 || (exh.has_aeth && exh.syndrome(7,5)!=0);
        state=BUILD;break;
    case BUILD:
        token=0;token(447,0)=binding;token(543,448)=ibh.raw;
        if(exh.has_aeth || checkIfRethHeader(ibh.normal.op_code))token(671,544)=header.getRawHeader();
        token(693,672)=exh.numPkg;token[694]=exh.isNak;token[695]=!local;token(1015,696)=descriptor;
        state=META;break;
    case META:meta.write(token);state=ACCEPT;break;
    case ACCEPT:if(!meta_accepts.empty()) {receipt=meta_accepts.read();state=CHECK_ACCEPT;}break;
    case CHECK_ACCEPT:
        if(receipt!=token) {error=44;break;}
        state=local?LOOKUP_ACCEPT:(no_body?END:BODY);break;
    case LOOKUP_ACCEPT:
        lookup_accepts.write(binding);state=no_body?END:BODY;break;
    case BODY:
        if(!raw_body.empty() && (discard || !body.full())) {
            net_axis<64> w=raw_body.read();
            if(!discard) {ap_uint<80> r=0;r(63,0)=w.data;r(71,64)=w.keep;r[72]=w.last;body.write(r);}
            if(w.last)state=END;
        }
        break;
    case END:
        if(!parser_ends.empty()) {
            if(parser_ends.read()!=1) {error=45;break;}
            state=(no_body || discard)?DONE:BODY_ACCEPT;
        }
        break;
    case BODY_ACCEPT:if(!body_accepts.empty()) {receipt=body_accepts.read();state=CHECK_BODY_ACCEPT;}break;
    case CHECK_BODY_ACCEPT:
        if(receipt!=token) {error=46;break;}
        state=DONE;break;
    case DONE:completed.write(descriptor);state=LOAD;break;
    case MARKER:
        query=0;query[129]=1;query(297,130)=descriptor(273,106);
        queries.write(query);state=MARKER_RESUME;break;
    case MARKER_RESUME:
        if(!resumes.empty()) {
            ap_uint<192> r=resumes.read();
            if(r(191,168)!=0 || r(167,0)!=descriptor(273,106)) {error=47;break;}
            state=DONE;
        }
        break;
    }
}
'''

def wire_header(cpp,hpp):
    license=cpp[:cpp.index('#include')]
    a,_,b=lex.source_block(hpp,'struct exhMeta\n')
    types=hpp[a:b+1].replace('exhMeta','as02RxWireExhMeta')
    at=types.index('{')
    types=types[:at+1]+'\n    ap_uint<8> syndrome=0;bool has_aeth=false;'+types[at+1:]
    ibh=lex.function(cpp,'rx_process_ibh').replace('void rx_process_ibh(','void as02_rx_wire_process_ibh(')
    ibh=once(ibh,'stream<ibhMeta>& metaOut,','stream<as02RxWireIbh>& metaOut,')
    constructor='ibhMeta(bth.getOpCode(), bth.getPartitionKey(), bth.getDstQP(), bth.getPsn(), true)'
    ibh=once(ibh,'metaOut.write('+constructor+');','metaOut.write(as02RxWireIbh('+constructor+',bth.getRawHeader()));')
    exh=lex.function(cpp,'rx_process_exh').replace('void rx_process_exh(','void as02_rx_wire_process_exh(')
    exh=once(exh,'void as02_rx_wire_process_exh(\n','void as02_rx_wire_process_exh(\n    stream<ap_uint<1>>& completed,\n')
    exh=exh.replace('stream<exhMeta>&','stream<as02RxWireExhMeta>&').replace('exhMeta(','as02RxWireExhMeta(')
    exh=once(exh,'as02RxWireExhMeta(ackHeader.isNAK())','as02_rx_aeth_meta(ackHeader.isNAK(),ackHeader.getSyndrome())')
    anchor='if (currWord.last)\n\t\t\t{'
    if exh.count(anchor)!=3:raise ValueError('all three actual parser packet-end sites required')
    exh=exh.replace(anchor,anchor+'\n                completed.write(1);')
    return license+'''#pragma once
#include "ib_transport_protocol.hpp"
#include "ib_utils.cpp"
#include "owned_timer.hpp"
'''+types+'\n'+TYPES+'\n'+ibh+'\n'+exh+'\n'+INGRESS+'\n'+FRONT+'\n'

def derive_top(original):
    s=base.derive_top(original).replace('as02_owned_rx_lookup_top','as02_owned_wire_rx_top')
    s=once(s,base.DECODE.strip(),derive_query_decoder().strip())
    s=once(s,'#include "ib_transport_protocol/owned_timer.hpp"',
        '#include "ib_transport_protocol/owned_timer.hpp"\n#include "ib_transport_protocol/owned_wire_rx.hpp"')
    s=once(s,'hls::stream<ap_uint<320>>& s_rx_query,hls::stream<ap_uint<448>>& m_rx_binding,hls::stream<ap_uint<448>>& s_rx_accept,',r'''
    hls::stream<ap_uint<320>>& s_rx_descriptor,hls::stream<ap_uint<80>>& s_rx_packet,
    hls::stream<ap_uint<1024>>& m_rx_meta,hls::stream<ap_uint<80>>& m_rx_body,
    hls::stream<ap_uint<1024>>& s_meta_accept,hls::stream<ap_uint<1024>>& s_body_accept,hls::stream<ap_uint<192>>& s_rx_resume,
    ap_uint<32>& rx_ingress_fault,ap_uint<32>& rx_front_fault,ap_uint<32>& rx_frame_fault,ap_uint<32>& rx_parser_words,''')
    s=once(s,'#pragma HLS interface axis register port=s_rx_query\n#pragma HLS interface axis register port=m_rx_binding\n#pragma HLS interface axis register port=s_rx_accept',r'''#pragma HLS interface axis register port=s_rx_descriptor
#pragma HLS interface axis register port=s_rx_packet
#pragma HLS interface axis register port=m_rx_meta
#pragma HLS interface axis register port=m_rx_body
#pragma HLS interface axis register port=s_meta_accept
#pragma HLS interface axis register port=s_body_accept
#pragma HLS interface axis register port=s_rx_resume
#pragma HLS interface ap_none port=rx_ingress_fault
#pragma HLS interface ap_none port=rx_front_fault
#pragma HLS interface ap_none port=rx_frame_fault
#pragma HLS interface ap_none port=rx_parser_words''')
    s=once(s,'    as02_rx_lookup_decode(s_rx_query,rx_queries);',r'''
    static stream<ap_uint<320>> wire_queries("wire_queries"),commands("commands"),front_commands("front_commands"),completed("completed");
    static stream<ap_uint<448>> wire_bindings("wire_bindings"),wire_accepts("wire_accepts");
    static stream<ap_uint<96>> decoded_packets("decoded_packets");
    static stream<ap_uint<128>> annotated_packets("annotated_packets"),checked_packets("checked_packets");
    static stream<ap_uint<320>> frame_begins("frame_begins"),checked_begins("checked_begins");
    static stream<net_axis<64>> retained("retained"),parser_input("parser_input"),bth_words("bth_words"),shifted("shifted"),raw_body("raw_body");
    static stream<as02RxWireIbh> parsed_bth("parsed_bth");
    static stream<as02RxWireExhMeta> parsed_exh("parsed_exh");
    static stream<ExHeader<64>> exh_headers("exh_headers");
    static stream<ibOpCode> opcodes("opcodes");static stream<ap_uint<1>> parser_ends("parser_ends");
#pragma HLS stream variable=retained depth=8192
#pragma HLS stream variable=decoded_packets depth=2
#pragma HLS stream variable=annotated_packets depth=2
#pragma HLS stream variable=checked_packets depth=2
#pragma HLS stream variable=frame_begins depth=2
#pragma HLS stream variable=checked_begins depth=2
#pragma HLS stream variable=wire_queries depth=2
#pragma HLS stream variable=wire_bindings depth=2
#pragma HLS stream variable=wire_accepts depth=2
#pragma HLS stream variable=commands depth=2
#pragma HLS stream variable=front_commands depth=2
#pragma HLS stream variable=completed depth=2
#pragma HLS stream variable=parser_input depth=2
#pragma HLS stream variable=bth_words depth=2
#pragma HLS stream variable=shifted depth=2
#pragma HLS stream variable=raw_body depth=2
#pragma HLS stream variable=parsed_bth depth=2
#pragma HLS stream variable=parsed_exh depth=2
#pragma HLS stream variable=exh_headers depth=2
#pragma HLS stream variable=opcodes depth=2
#pragma HLS stream variable=parser_ends depth=2
#pragma HLS aggregate variable=retained compact=bit
#pragma HLS aggregate variable=parser_input compact=bit
#pragma HLS aggregate variable=bth_words compact=bit
#pragma HLS aggregate variable=shifted compact=bit
#pragma HLS aggregate variable=raw_body compact=bit
#pragma HLS aggregate variable=parsed_bth compact=bit
#pragma HLS aggregate variable=parsed_exh compact=bit
#pragma HLS aggregate variable=exh_headers compact=bit
    as02_rx_wire_decode(s_rx_packet,decoded_packets);
    as02_rx_wire_ingress(s_rx_descriptor,decoded_packets,frame_begins,annotated_packets,completed,rx_ingress_fault);
    as02_rx_wire_frame_check(frame_begins,annotated_packets,checked_begins,checked_packets);
    as02_rx_wire_frame_commit(checked_begins,checked_packets,retained,commands,rx_frame_fault);
    as02_rx_wire_release(commands,retained,front_commands,parser_input);
    as02_rx_wire_process_ibh<64,58>(parser_input,parsed_bth,opcodes,bth_words,rx_parser_words);
    rshiftWordByOctet<net_axis<64>,64,11,58>(4,bth_words,shifted);
    as02_rx_wire_process_exh<64,58>(parser_ends,shifted,opcodes,parsed_exh,exh_headers,raw_body);
    as02_rx_wire_front(front_commands,parsed_bth,parsed_exh,exh_headers,raw_body,parser_ends,
        wire_queries,wire_bindings,wire_accepts,m_rx_meta,m_rx_body,s_meta_accept,s_body_accept,s_rx_resume,completed,rx_front_fault);
    as02_rx_lookup_decode(wire_queries,rx_queries);''')
    s=once(s,'rx_queries,m_rx_binding,s_rx_accept,pool_credit','rx_queries,wire_bindings,wire_accepts,pool_credit')
    return s

def derive_wrapper(original):
    s=base.derive_wrapper(original)
    s=once(s,'module rocev2_owned_rx_lookup(','module rocev2_owned_wire_rx(')
    s=once(s,''' input wire [319:0] s_rx_query_data,input wire s_rx_query_valid,output wire s_rx_query_ready,
 output wire [447:0] m_rx_binding_data,output wire m_rx_binding_valid,input wire m_rx_binding_ready,''',r''' input wire [319:0] s_rx_descriptor_data,input wire s_rx_descriptor_valid,output wire s_rx_descriptor_ready,
 input wire [79:0] s_rx_packet_data,input wire s_rx_packet_valid,output wire s_rx_packet_ready,
 output wire [1023:0] m_rx_meta_data,output wire m_rx_meta_valid,input wire m_rx_meta_ready,
 output wire [79:0] m_rx_body_data,output wire m_rx_body_valid,input wire m_rx_body_ready,''')
    s=once(s,'''wire [447:0] raw_binding;wire raw_binding_valid,raw_binding_ready,lookup_ack_ready;
reg [447:0] lookup_ack=0;reg lookup_ack_valid=0;
wire lookup_room=!lookup_ack_valid || lookup_ack_ready;
assign m_rx_binding_data=raw_binding;
assign m_rx_binding_valid=raw_binding_valid && lookup_room;
assign raw_binding_ready=m_rx_binding_ready && lookup_room;''',r'''
wire [1023:0] raw_meta;wire raw_meta_valid,raw_meta_ready,meta_ack_ready,body_ack_ready;
wire [79:0] raw_body;wire raw_body_valid,raw_body_ready;
reg [1023:0] meta_ack=0,body_ack=0,body_owner=0;
reg meta_ack_valid=0,body_ack_valid=0,body_active=0;
wire rx_resume_ready;reg rx_resume_valid=0;reg [191:0] rx_resume=0;
wire [31:0] rx_ingress_fault,rx_front_fault,rx_frame_fault,rx_parser_words;
wire [7:0] rx_op=raw_meta[303:296];
wire [15:0] rx_length=raw_meta[799:784];
wire rx_no_body=rx_op==17 || ((rx_op==6 || rx_op==10 || rx_op==12) && rx_length==28);
wire rx_discard=!raw_meta[695] && (raw_meta[399:392]!=0 || (raw_meta[420] && raw_meta[419:417]!=0));
assign m_rx_meta_data=raw_meta;
assign m_rx_meta_valid=raw_meta_valid && !meta_ack_valid && !body_active;
assign raw_meta_ready=m_rx_meta_ready && !meta_ack_valid && !body_active;
assign m_rx_body_data=raw_body;
assign m_rx_body_valid=raw_body_valid && body_active && !body_ack_valid;
assign raw_body_ready=m_rx_body_ready && body_active && !body_ack_valid;''')
    s=once(s,"assign fault=process_fault!=0?process_fault:(receipt_fault?32'h100:32'd0);",r'''assign fault=process_fault!=0?process_fault:
 (rx_ingress_fault!=0?(32'h1000|rx_ingress_fault):
 (rx_front_fault!=0?(32'h2000|rx_front_fault):
 (rx_frame_fault!=0?(32'h3000|rx_frame_fault):(receipt_fault?32'h100:32'd0))));''')
    s=once(s,'assign m_fence_valid=raw_fence_valid&&!fence_ack_valid;',
        'assign m_fence_valid=raw_fence_valid&&!fence_ack_valid&&!rx_resume_valid;')
    s=once(s,'assign raw_fence_ready=m_fence_ready&&!fence_ack_valid;',
        'assign raw_fence_ready=m_fence_ready&&!fence_ack_valid&&!rx_resume_valid;')
    s=once(s,'  lookup_ack_valid<=0;lookup_ack<=0;',r'''  meta_ack_valid<=0;body_ack_valid<=0;body_active<=0;rx_resume_valid<=0;
  meta_ack<=0;body_ack<=0;body_owner<=0;rx_resume<=0;''')
    s=once(s,'''  if(lookup_ack_valid && lookup_ack_ready)lookup_ack_valid<=0;
  if(m_rx_binding_valid && m_rx_binding_ready)begin
   lookup_ack<=m_rx_binding_data;lookup_ack_valid<=1;
  end''',r'''  if(meta_ack_valid && meta_ack_ready)meta_ack_valid<=0;
  if(body_ack_valid && body_ack_ready)body_ack_valid<=0;
  if(rx_resume_valid && rx_resume_ready)rx_resume_valid<=0;
  if(m_rx_meta_valid && m_rx_meta_ready)begin
   meta_ack<=m_rx_meta_data;meta_ack_valid<=1;body_owner<=m_rx_meta_data;
   body_active<=!rx_no_body && !rx_discard;
   if(m_rx_meta_data[1023:1016]!==8'd0)receipt_fault<=1;
  end
  if(m_rx_body_valid && m_rx_body_ready && m_rx_body_data[72])begin
   body_ack<=body_owner;body_ack_valid<=1;body_active<=0;
  end''')
    s=once(s,"   fence_ack<={24'd0,raw_fence[167:0]};fence_ack_valid<=1;",r'''   fence_ack<={24'd0,raw_fence[167:0]};fence_ack_valid<=1;
   rx_resume<={24'd0,raw_fence[167:0]};rx_resume_valid<=1;''')
    s=once(s,'''as02_owned_rx_lookup_top process_and_tables(
 .s_rx_query_TDATA(s_rx_query_data),.s_rx_query_TVALID(s_rx_query_valid),.s_rx_query_TREADY(s_rx_query_ready),
 .m_rx_binding_TDATA(raw_binding),.m_rx_binding_TVALID(raw_binding_valid),.m_rx_binding_TREADY(raw_binding_ready),
 .s_rx_accept_TDATA(lookup_ack),.s_rx_accept_TVALID(lookup_ack_valid),.s_rx_accept_TREADY(lookup_ack_ready),''',r'''as02_owned_wire_rx_top process_and_tables(
 .s_rx_descriptor_TDATA(s_rx_descriptor_data),.s_rx_descriptor_TVALID(s_rx_descriptor_valid),.s_rx_descriptor_TREADY(s_rx_descriptor_ready),
 .s_rx_packet_TDATA(s_rx_packet_data),.s_rx_packet_TVALID(s_rx_packet_valid),.s_rx_packet_TREADY(s_rx_packet_ready),
 .m_rx_meta_TDATA(raw_meta),.m_rx_meta_TVALID(raw_meta_valid),.m_rx_meta_TREADY(raw_meta_ready),
 .m_rx_body_TDATA(raw_body),.m_rx_body_TVALID(raw_body_valid),.m_rx_body_TREADY(raw_body_ready),
 .s_meta_accept_TDATA(meta_ack),.s_meta_accept_TVALID(meta_ack_valid),.s_meta_accept_TREADY(meta_ack_ready),
 .s_body_accept_TDATA(body_ack),.s_body_accept_TVALID(body_ack_valid),.s_body_accept_TREADY(body_ack_ready),
 .s_rx_resume_TDATA(rx_resume),.s_rx_resume_TVALID(rx_resume_valid),.s_rx_resume_TREADY(rx_resume_ready),
 .rx_ingress_fault(rx_ingress_fault),.rx_front_fault(rx_front_fault),.rx_frame_fault(rx_frame_fault),.rx_parser_words(rx_parser_words),''')
    s=once(s,'.pool_fault_in(pool_fault|receipt_fault)',
        '.pool_fault_in(pool_fault|receipt_fault|(rx_ingress_fault!=0)|(rx_front_fault!=0)|(rx_frame_fault!=0))')
    s=once(s,'// Same real tables/pool with RX lookup.',
        '// Actual BTH/EXH bytes and full-syndrome parser joined to same tables/pool.\n// No effectful RX FSM, native auth, memory placement/CQ or whole-core drain.\n// Same real tables/pool with RX lookup.')
    return s
