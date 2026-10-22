# SPDX-License-Identifier: BSD-2-Clause-Views
"""Derive optional fatal-event object/lifetime hooks on exact private profile8.

Default authored driver, existing frozen68 inputs and all old tests remain
untouched. Source integration and real-header compilation alone do not prove
live Linux reference safety, native-FEC attachment or completed recovery.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import audit_segmented_receive as binding
from audit_segmented_write_native_software import kernel_build_bindings
from segmented_write_payload_native_fixture import once

ROOT=binding.ROOT;digest=binding.digest
PARENT='write-psn-control-kernel-build-001'
EXTRA=['fatal_io.c','fatal_io.h','fatal_regs.h','fatal_verbs.c','fatal_verbs.h']


def derive(verbs,header,makefile):
    header=once(header,'#include "qp_hw.h"','#include "qp_hw.h"\n#include "fatal_verbs.h"')
    header=once(header,'    int error_progress_status;',
        '    struct as02_fatal_decoded fatal_event;\n'
        '    bool fatal_event_recorded, fatal_event_callback_pending, fatal_event_callback_active, fatal_event_notified;\n'
        '    int error_progress_status;')
    header=once(header,'    struct as02_verbs_qp *qp;','    struct as02_fatal_verbs *fatal;\n    struct as02_verbs_qp *qp;')
    verbs=once(verbs,'{ return READ_ONCE(d->initialized) && !READ_ONCE(d->stopping); }',
        '{ return READ_ONCE(d->initialized) && !READ_ONCE(d->stopping) &&\n'
        '    (!d->fatal || !READ_ONCE(d->fatal->detached)); }')
    verbs=once(verbs,'    if(q->sq_closed && !q->hw_owned){q->error_pending=false;return 0;}',
        '    if(q->fatal_event_callback_pending || q->fatal_event_callback_active)return -EAGAIN;\n'
        '    if(q->sq_closed && !q->hw_owned){q->error_pending=false;return 0;}')
    anchor='    if (!q->initialized || d->qp != q) { ret = -ESTALE; goto out; }\n    if (q->hw_owned) {'
    verbs=once(verbs,anchor,
        '    if (!q->initialized || d->qp != q) { ret = -ESTALE; goto out; }\n'
        '    if(q->fatal_event_callback_pending || q->fatal_event_callback_active){ret=-EBUSY;goto out;}\n'
        '    if (q->hw_owned) {')
    verbs=once(verbs,'    if (d->published || d->publishing || d->context_count ||',
        '    if (d->fatal || d->published || d->publishing || d->context_count ||')
    makefile=once(makefile,'retry_io.o verbs.o device.o','retry_io.o fatal_io.o fatal_verbs.o verbs.o device.o')
    return verbs,header,makefile


def inputs():
    r,rid=kernel_build_bindings(PARENT)
    if not r['pass_test']or not r['source_and_frozen_inputs_unchanged']or len(r['frozen_input_sha256'])!=68 or \
       (r['matched_RNC_features'],r['matched_CQC_features'],r['matched_SQC_features'],r['matched_RQC_features'],r['private_segmented_profile'])!=(131071,511,13,63,8):
        raise ValueError('exact actually built complete68-input private profile8 parent required')
    base=ROOT/r['directory'];files={n:(base/n).read_text()for n in r['frozen_input_sha256']}
    before={str((base/n).relative_to(ROOT)):digest(base/n)for n in files}
    files['verbs.c'],files['verbs.h'],files['Makefile']=derive(files['verbs.c'],files['verbs.h'],files['Makefile'])
    for n in EXTRA:
        p=ROOT/'rdma/rnic/kernel'/n
        if n in files:raise ValueError('new fatal component must not overwrite an existing parent input')
        files[n]=p.read_text();before[str(p.relative_to(ROOT))]=digest(p)
    before[str(Path(__file__).resolve().relative_to(ROOT))]=digest(__file__)
    before[str(binding.record(PARENT).relative_to(ROOT))]=digest(binding.record(PARENT))
    return files,before,rid
