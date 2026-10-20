# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE complete matched128-byte native Atomic requester/responder candidate.

Replace the full existing native graph, never add a second MR/HLS/PSN domain.
Request748/SQ408/core816; posted receive620 and owned service ABI unchanged.
Actual SQC/RQC ring stride128 and CQ operands use explicit new feature bits;
old exact-feature kernel negotiators MUST refuse this unmatched profile.
Not a default/physical/standard-API selection or timing/drain relaxation.
"""
import re
import derive_atomic_native as base
import derive_atomic128_admission as admission
import derive_atomic128_response as response
import derive_atomic128_executor as executor
import derive_atomic128_lifetime as lifetime
import derive_atomic_request_bridge as bridge

ROOT=base.ROOT;RTL=base.RTL;once=base.once
CQ=RTL/'rocev2_cq_mmio.v';ROUTER=RTL/'rocev2_duplex_tx_router.v'
EXTRA=base.EXTRA


def original_names(t):return re.sub(r'\brocev2_atomic128_(\w+)\b',r'rocev2_\1',t)


def width(t,name,old,new):
    pattern=r'\['+str(old)+r':0\](\s+)'+re.escape(name)+r'\b'
    found=list(re.finditer(pattern,t))
    if len(found)>1:raise ValueError('ambiguous declaration '+name)
    if found:t=re.sub(pattern,'['+str(new)+r':0]\1'+name,t)
    return t


def common(t):
    for n in ['s_local_owner_context','s_local_retire_context','m_cq_context','s_cq_commit_context','m_executor_context']:
        t=width(t,n,619,747)
    for n in ['m_request_done_data','h_request_done_data']:t=width(t,n,687,815)
    for n in ['s_local_sq_tdata','m_hls_sq_tdata','sq_m_hls_sq_tdata']:t=width(t,n,279,407)
    return t


def sq(t):
    t=once(t,'    output wire [31:0] m_work_immediate,',
        '    output wire [31:0] m_work_immediate,\n'
        '    output wire [63:0] m_work_compare,m_work_swap_add,')
    t=once(t,'wire [31:0] rq_work_immediate;',
        'wire [31:0] rq_work_immediate;\nwire [63:0] rq_work_compare,rq_work_swap_add;')
    t=once(t,'wire [619:0] bridge_work_context={m_work_immediate,',
        'wire [747:0] bridge_work_context={m_work_swap_add,m_work_compare,m_work_immediate,')
    t=once(t,'assign m_recv_post_context=SEPARATE_RQ_ENABLE ? rq_work_context : bridge_work_context;',
        'assign m_recv_post_context=SEPARATE_RQ_ENABLE ? rq_work_context : bridge_work_context[619:0];')
    t=once(t,'wire [511:0] sq_m_result_data;','wire [1023:0] sq_m_result_data;')
    t=once(t,' .m_work_immediate(m_work_immediate),',
        ' .m_work_immediate(m_work_immediate),.m_work_compare(m_work_compare),.m_work_swap_add(m_work_swap_add),')
    t=once(t,' .m_work_immediate(rq_work_immediate),',
        ' .m_work_immediate(rq_work_immediate),.m_work_compare(rq_work_compare),.m_work_swap_add(rq_work_swap_add),')
    return once(t,'assign rq_work_remote_key=0;assign rq_work_immediate=0;',
        'assign rq_work_remote_key=0;assign rq_work_immediate=0;assign rq_work_compare=0;assign rq_work_swap_add=0;')


def shared(t):
    t=width(t,'owner',619,747)
    t=once(t,'wire owner_ok=',
        'wire atomic_local=opcode==7 || opcode==8;\n'
        'wire local_operands_ok=atomic_local ? (length==8 && remote_address[2:0]==0 &&\n'
        '    (opcode!=8 || s_local_owner_context[683:620]==0)) : s_local_owner_context[747:620]==0;\n'
        'wire owner_ok=local_operands_ok &&')
    t=once(t,'(opcode==1 || opcode==2 || opcode==6 || ((opcode==3 || opcode==5) && remote_address==0 && remote_key==0))',
        '(atomic_local || opcode==1 || opcode==2 || opcode==6 || ((opcode==3 || opcode==5) && remote_address==0 && remote_key==0))')
    t=once(t,"wire [7:0] request_opcode=owner[339:324]==1 ? 8'h0a :",
        "wire [7:0] request_opcode=owner[339:324]==7 ? 8'h13 : owner[339:324]==8 ? 8'h14 : owner[339:324]==1 ? 8'h0a :")
    for a,b in [('619:0','747:0'),('687:676','815:804'),('675:668','803:796'),('667:644','795:772'),('643:620','771:748')]:
        t=once(t,'m_request_done_data['+a+']','m_request_done_data['+b+']')
    t=once(t,"wire [279:0] expected_sq={7'd0,owner[619:588],",
        "wire [407:0] expected_sq={owner[747:684],owner[683:620],7'd0,owner[619:588],")
    t=once(t,'(saved_opcode==1 ? 32\'d10 : saved_opcode==2 ? 32\'d12 :',
        "(saved_opcode==7 ? 32'd19 : saved_opcode==8 ? 32'd20 : saved_opcode==1 ? 32'd10 : saved_opcode==2 ? 32'd12 :")
    return once(t,'rocev2_atomic_native_integrity_transport #(','rocev2_atomic_request_integrity_transport #(')


def root(t):
    t=once(t,'wire [619:0] rq_held_context,rq_ticket_context,local_cq_context;',
        'wire [619:0] rq_held_context,rq_ticket_context;\nwire [747:0] local_cq_context;')
    for n in ['sq_m_executor_context','ex_m_memory_event_context','tx_m_expect_context','rx_m_read_response_context',
              'rx_m_response_event_context','cq_commit_context','rx_control_context']:
        t=width(t,n,619,747)
    # cq_commit_context,cq_retire_context share ONE declaration; both widen.
    if 'wire [747:0] cq_commit_context,cq_retire_context;'not in t:raise ValueError('CQ context declaration changed')
    t=once(t,'assign m_cq_context=rq_ticket_valid ? rq_ticket_context : local_cq_context;',
        "assign m_cq_context=rq_ticket_valid ? {128'd0,rq_ticket_context} : local_cq_context;")
    for a,b in [('.s_commit_context(cq_commit_context),','.s_commit_context(cq_commit_context[619:0]),'),
                ('.s_retire_context(cq_retire_context),','.s_retire_context(cq_retire_context[619:0]),')]:
        # Receive queue/ACK/HLS retire inputs keep their COMPLETE620-bit ABI.
        count=t.count(a)
        if not count:raise ValueError('receive commit/retire connection changed '+a)
        t=t.replace(a,b)
    t=once(t,'.s_recv_retire_context(cq_retire_context),',
        '.s_recv_retire_context(cq_retire_context[619:0]),')
    # The separately named local requester retire input retains all748 bits.
    if t.count('.s_local_retire_context(cq_retire_context),')!=1:
        raise ValueError('full local requester retirement connection changed')
    t=once(t,'    output wire [31:0] m_work_immediate,',
        '    output wire [31:0] m_work_immediate,\n    output wire [63:0] m_work_compare,m_work_swap_add,')
    return once(t,'.m_work_immediate(m_work_immediate),',
        '.m_work_immediate(m_work_immediate),.m_work_compare(m_work_compare),.m_work_swap_add(m_work_swap_add),')


def sq_control(t):
    t=once(t,'((65\'d1<<stage[10])<<6)',"((65'd1<<stage[10])<<7)")
    t=once(t,'sd[5:0]!==0','sd[6:0]!==0')
    t=once(t,'ra==12 || ra==28 ||','ra==12 || ra==28 || ra==32 ||')
    t=once(t,"8:rd=(RECV_CANCEL_ENABLE ? 32'h3:32'h1) | (IMMEDIATE_ENABLE ? 32'h4:0);",
        "8:rd=(RECV_CANCEL_ENABLE ? 32'h3:32'h1) | 32'hc;\n    32:rd=128;")
    return once(t,'initial begin if(ADDR_WIDTH!=12 || MAX_QPS!=8)',
        'initial if(!IMMEDIATE_ENABLE)$fatal(1,"matched128-byte Immediate-header profile required");\n'
        'initial begin if(ADDR_WIDTH!=12 || MAX_QPS!=8)')


def cq():
    t=CQ.read_text();old='[587+32*IMMEDIATE_ENABLE:0]'
    if t.count(old)!=4:raise ValueError('CQ owner geometry changed')
    t=t.replace(old,'[747:0]')
    t=once(t,'wire ticket_ok=owner_ok &&',
        'wire atomic_ticket=incoming_opcode==7 || incoming_opcode==8;\n'
        'wire extension_ok=atomic_ticket ? (s_ticket_context[307:276]==8 && s_ticket_context[54:52]==0 &&\n'
        '    (incoming_opcode!=8 || s_ticket_context[683:620]==0)):s_ticket_context[747:620]==0;\n'
        'wire ticket_ok=owner_ok && extension_ok &&')
    t=once(t,'(incoming_opcode==1 || incoming_opcode==2 ||',
        '(atomic_ticket || incoming_opcode==1 || incoming_opcode==2 ||')
    t=once(t,'IMMEDIATE_ENABLE && (ra==12\'h03c || ra==12\'h090);',
        "IMMEDIATE_ENABLE && (ra==12'h03c || ra==12'h090) ||\n"
        "    ra==12'h094 || ra==12'h098 || (ra>=12'h0a0 && ra<=12'h0ac);")
    t=once(t,"rd=({20'd0,owner_context}>>", "rd=({20'd0,owner_context[619:0]}>>")
    t=once(t,'8:rd=IMMEDIATE_ENABLE ? 7 : MESSAGE_ENABLE ? 3 : 1;',
        "8:rd=15;\n    12'h094:rd=748;\n    12'h098:rd=12'h0a0;\n"
        "    12'h0a0:rd=state==VISIBLE ? owner_context[651:620]:0;\n"
        "    12'h0a4:rd=state==VISIBLE ? owner_context[683:652]:0;\n"
        "    12'h0a8:rd=state==VISIBLE ? owner_context[715:684]:0;\n"
        "    12'h0ac:rd=state==VISIBLE ? owner_context[747:716]:0;")
    return once(t,'initial if((IMMEDIATE_ENABLE',
        'initial if(!IMMEDIATE_ENABLE || !MESSAGE_ENABLE)$fatal(1,"matched128-byte CQ profile required");\ninitial if((IMMEDIATE_ENABLE')


def derive():
    out=base.derive()
    for p in list(out):out[p]=common(out[p])
    p=RTL/'rocev2_native_sq_endpoint.v';out[p]=sq(out[p])
    p=RTL/'rocev2_native_rnic_endpoint.v';out[p]=root(out[p])
    p=base.rx.stage.authority.base.duplex.ORIGINAL;out[p]=shared(out[p])
    for p,t in {**admission.fetch.derive(),**admission.derive(),**lifetime.derive(),
                response.SOURCE:response.derive(),executor.SOURCE:executor.derive()}.items():out[p]=original_names(t)
    p=base.rx.stage.authority.lookup.SOURCE;out[p]=sq_control(out[p])
    out[CQ]=cq();out[ROUTER]=once(ROUTER.read_text(),"wire request=opcode<=8'h0c;",
        "wire request=opcode<=8'h0c || opcode==8'h13 || opcode==8'h14;")
    out[base.rx.stage.authority.base.duplex.bridge.legacy.BRIDGE]=bridge.derive()
    return out
