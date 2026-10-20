# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select one complete Atomic128 graph with SQC-bound QP access authority."""
from pathlib import Path
import sys
import atomic128_native_sources as old
import derive_atomic_access_native as candidate

ROOT=old.ROOT;digest=old.digest


def sources(project,immediate_report,owned_report,request_report,run):
    src,data,before=old.sources(project,immediate_report,owned_report,request_report,run)
    for original,text in candidate.derive().items():
        name='rocev2_shared_protected_responder.v'if original==candidate.authority.base.responder.ORIGINAL else original.name
        p=run/name
        if p not in src:
            if src.count(original)!=1:raise ValueError('one actual permission source required: '+name)
            src.remove(original);src.append(p)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers]})
    return src,data,before
