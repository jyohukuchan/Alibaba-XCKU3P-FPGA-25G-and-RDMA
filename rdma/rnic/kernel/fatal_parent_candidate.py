# SPDX-License-Identifier: BSD-2-Clause-Views
"""Derive optional actual parent FEC bootstrap/polling on qualified kernel73.

Default parent/driver/layout/parameters remain untouched. A successful logical
poll stop NEVER closes the attachment: native whole-device STOP/reference
retirement is still missing, so the real graph close retains the full lease.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import audit_segmented_receive as binding
from segmented_write_payload_native_fixture import once

ROOT=binding.ROOT;digest=binding.digest
PARENT='fatal-verbs-kernel-build-001'
EXTRA=['fatal_parent.c','fatal_parent.h']


def derive(graph,header,mqnic,makefile):
    header=once(header,'#include "sq_hw.h"','#include "sq_hw.h"\n#include "fatal_parent.h"')
    header=once(header,'    size_t application_bytes;','    size_t application_bytes;\n    bool fatal_events;')
    header=once(header,'    struct as02_qp_hw qp;','    struct as02_qp_hw qp;\n    struct as02_fatal_parent fatal;')
    header=once(header,'int as02_native_graph_close(struct as02_native_graph **handle);',
        'int as02_native_graph_close(struct as02_native_graph **handle);\n'
        '/* Logical polling stop only; never permits graph/BAR/ref release. */\n'
        'int as02_native_graph_stop_fatal_polling(struct as02_native_graph *);')
    graph=once(graph,'    if(readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ID)',
        '    if(b->fatal_events){ret=as02_fatal_parent_check(bar+AS02_NATIVE_FATAL_BASE,AS02_NATIVE_FATAL_BYTES);if(ret)goto failed;}\n'
        '    if(readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ID)')
    anchor='    ret=as02_device_publish(g->device,g->parent,g->netdev,bar+AS02_NATIVE_ETH_BASE,AS02_NATIVE_ETH_BYTES);'
    graph=once(graph,anchor,
        '    if(b->fatal_events){ret=as02_fatal_parent_bind(&g->fatal,g->device,bar+AS02_NATIVE_FATAL_BASE,AS02_NATIVE_FATAL_BYTES);if(ret)goto failed;}\n'+anchor)
    graph=once(graph,anchor+'\n    if(ret)goto failed;\n    return 0;',
        anchor+'\n    if(ret)goto failed;\n'
        '    if(b->fatal_events){ret=as02_fatal_parent_start(&g->fatal);if(ret)goto failed;}\n    return 0;')
    anchor='    if(uncertain(g) || g->queues.queue_count || g->mrs.mapping_count){ret=-EBUSY;goto out;}'
    graph=once(graph,anchor,
        '    /* An attached FEC graph still owns BAR/device/storage, even after\n'
        '     * polling stops. No empty/idle/ACK-based lifetime release. */\n'
        '    if(g->fatal.initialized){ret=-EBUSY;goto out;}\n'+anchor)
    graph=once(graph,'EXPORT_SYMBOL_GPL(as02_native_lease_init);',
        'int as02_native_graph_stop_fatal_polling(struct as02_native_graph *g)\n'
        '{\n    if(!g || !g->fatal.initialized)return -EINVAL;\n'
        '    /* No graph/lease lock across cancellation/handler completion. */\n'
        '    return as02_fatal_parent_stop(&g->fatal);\n}\n'
        'EXPORT_SYMBOL_GPL(as02_native_graph_stop_fatal_polling);\nEXPORT_SYMBOL_GPL(as02_native_lease_init);')
    mqnic=once(mqnic,'static bool enable_native_attach;',
        'static bool enable_fatal_events;\nmodule_param(enable_fatal_events, bool, 0400);\n'
        'MODULE_PARM_DESC(enable_fatal_events, "Explicit reviewed FEC-native graph only; adds retained polling ownership, not safe unbind/STOP proof");\n'
        'static bool enable_native_attach;')
    mqnic=once(mqnic,'    b.application_bar=parent->app_hw_addr;',
        '    b.fatal_events=enable_fatal_events;\n    b.application_bar=parent->app_hw_addr;')
    makefile=once(makefile,'fatal_io.o fatal_verbs.o verbs.o','fatal_io.o fatal_verbs.o fatal_parent.o verbs.o')
    return graph,header,mqnic,makefile


def inputs():
    names=[PARENT,'fatal-verbs-diagnostics-001','fatal-event-native-full-001',
        'fatal-event-native-runtime-diagnostics-001','fatal-event-native-software-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    parent,software,native,runtime,coupling=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or len(native['tests'])!=40 or \
       parent['actual_total_inputs']!=73 or parent['private_identity']!=[131071,511,13,63,8]or coupling['live_Linux_FPGA_coupling']:
        raise ValueError('actual FEC-native40/AXI proof and matching full kernel73/callback220/source qualification required')
    base=ROOT/parent['directory'];files={str(Path(n).relative_to(Path(parent['directory']))):(ROOT/n).read_text()for n in parent['derived_sha256']}
    before={n:digest(ROOT/n)for n in parent['derived_sha256']}
    files['native_graph.c'],files['native_graph.h'],files['mqnic_graph.c'],files['Makefile']=derive(
        files['native_graph.c'],files['native_graph.h'],files['mqnic_graph.c'],files['Makefile'])
    for n in EXTRA:
        p=ROOT/'rdma/rnic/kernel'/n
        if n in files:raise ValueError('new parent files cannot overwrite qualified input')
        files[n]=p.read_text();before[str(p.relative_to(ROOT))]=digest(p)
    for p in [Path(__file__).resolve(),*[binding.record(n)for n in names]]:before[str(p.relative_to(ROOT))]=digest(p)
    return files,before,ids
