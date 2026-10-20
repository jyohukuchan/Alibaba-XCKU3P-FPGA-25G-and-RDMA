# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual complete normal+Atomic native source selection, no HLS model."""
from pathlib import Path
import sys
import atomic_native_owned_fixture as old
import derive_atomic_native as candidate

ROOT=old.ROOT;digest=old.digest


def sources(project,immediate_report,owned_report,run):
    src,data,before=old.sources(project,immediate_report,owned_report,run)
    for original,text in candidate.derive().items():
        name='rocev2_shared_protected_responder.v'if original==candidate.rx.stage.authority.base.responder.ORIGINAL else original.name
        p=run/name
        if p not in src:raise ValueError('missing actual full-native substitution '+name)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    src+=candidate.EXTRA+[ROOT/'external/corundum/fpga/lib/axis/rtl/axis_broadcast.v']
    src=list(dict.fromkeys(src))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers]})
    return src,data,before
