# SPDX-License-Identifier: BSD-2-Clause-Views
"""New actual segmented HLS + shared physical command nonce in native graph.

Keep all previous guards/ABIs/default sources. Large-WR source dispatcher,
per-packet wire lifetime, whole-WR CQ and large admission are still OPEN;
this intermediate graph does not advertise native1MiB/multi-SGE support.
"""
import derive_zero_service_native as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;connect=parent.connect
helpers=parent.helpers.rx
EXTRA=parent.EXTRA+[RTL/'rocev2_memory_command_nonce.v']


def paged(t):
    pairs=[('s_command_'+n,'nonce_command_'+n)for n in ['write','offset','length','key','tag','valid','ready']]
    pairs +=[('m_status_'+n,'nonce_status_'+n)for n in ['tag','error','valid','ready']]
    pairs +=[('idle','raw_backend_idle'),('dma_drained','raw_backend_drained'),
             ('fault','raw_backend_fault'),('fault_code','raw_backend_fault_code')]
    for port,signal in pairs:
        old_signal='backend_command_'+port[len('s_command_'):] if port.startswith('s_command_') else \
            'backend_status_'+port[len('m_status_'):] if port.startswith('m_status_') else \
            dict(idle='backend_idle',dma_drained='backend_drained',fault='backend_fault',fault_code='backend_fault_code')[port]
        # Existing ports must be REPLACED, not appended by the new-port helper.
        t=once(t,'.'+port+'('+old_signal+')','.'+port+'('+signal+')')
    t=once(t,'.cfg_quiescent(guard_quiescent && !guard_fault),',
        '.cfg_quiescent(guard_quiescent && !guard_fault && !memory_nonce_guard),')
    t=once(t,'.cfg_valid(cfg_page_valid && cfg_admission_pause && guard_mr_ready && !cfg_mr_valid && !cfg_qp_valid && !fault),',
        '.cfg_valid(cfg_page_valid && cfg_admission_pause && guard_mr_ready && !cfg_mr_valid && !cfg_qp_valid && !fault && !memory_nonce_guard),')
    t=once(t,'wire configuration_allowed=cfg_admission_pause && backend_idle && backend_page_ready && !fault && !rst;',
        'wire configuration_allowed=cfg_admission_pause && backend_idle && backend_page_ready && !memory_nonce_guard && !fault && !rst;')
    t=once(t,'assign cfg_page_ready=backend_page_ready && cfg_admission_pause && guard_mr_ready &&',
        'assign cfg_page_ready=backend_page_ready && cfg_admission_pause && guard_mr_ready && !memory_nonce_guard &&')
    t=once(t,'assign memory_drained=backend_drained && backend_idle &&',
        'assign memory_drained=backend_drained && backend_idle && !memory_nonce_guard &&')
    t=once(t,'assign atomic_backend_idle=backend_drained && backend_idle &&',
        'assign atomic_backend_idle=backend_drained && backend_idle && !memory_nonce_guard &&')
    logic=r'''
wire nonce_command_write,nonce_command_valid,nonce_command_ready;
wire [63:0] nonce_command_offset;wire [31:0] nonce_command_length,nonce_command_key;
wire [15:0] nonce_command_tag,nonce_status_tag;wire [7:0] nonce_status_error;
wire nonce_status_valid,nonce_status_ready;
wire raw_backend_idle,raw_backend_drained,raw_backend_fault;wire [7:0] raw_backend_fault_code;
wire memory_nonce_busy,memory_nonce_guard,memory_nonce_fault,memory_nonce_exhausted;
wire [7:0] memory_nonce_fault_code;
assign backend_idle=raw_backend_idle && !memory_nonce_busy;
assign backend_drained=raw_backend_drained && !memory_nonce_busy;
assign backend_fault=raw_backend_fault || memory_nonce_fault;
assign backend_fault_code=memory_nonce_fault ? 8'h7e:raw_backend_fault_code;
'''
    p=dict(clk='clk',rst='rst',enable='!guard_fault && !raw_backend_fault',
        parent_fault='guard_fault || raw_backend_fault || memory_mux_fault || atomic_memory_fault',
        busy='memory_nonce_busy',configuration_guard='memory_nonce_guard',exhausted='memory_nonce_exhausted',
        fault='memory_nonce_fault',fault_code='memory_nonce_fault_code',command_count='',status_count='',retired_count='')
    for n in ['write','offset','length','key','tag','valid','ready']:
        p['s_command_'+n]='backend_command_'+n;p['m_command_'+n]='nonce_command_'+n
    for n in ['tag','error','valid','ready']:
        p['s_status_'+n]='nonce_status_'+n;p['m_status_'+n]='backend_status_'+n
    logic+=helpers.instance(RTL/'rocev2_memory_command_nonce.v','memory_nonce',p)
    return once(t,'rocev2_paged_memory_backend #(',logic+'\nrocev2_paged_memory_backend #(')


def derive():
    out=parent.derive()
    p=RTL/'rocev2_paged_responder.v';out[p]=paged(out[p])
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v'
    out[p]=once(out[p],'rocev2_native_zero_service_top transport (',
        'rocev2_native_segmented_request_top transport (')
    return out
