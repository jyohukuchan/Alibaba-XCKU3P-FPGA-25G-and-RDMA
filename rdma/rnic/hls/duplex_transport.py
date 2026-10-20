#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same native request/receive core with explicit memory-command provenance.

The two former AXI byte-padding bits become REMOTE=1/LOCAL=2, assigned by
the real command producer, not a current role/address heuristic. All94 actual
command bits and the one MR namespace remain unchanged. This is a new matched
top; never interpret padding from an older generated core as valid provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import request_retire_transport as parent

ROOT=parent.ROOT
CPP='hls/ib_transport_protocol/ib_transport_protocol.cpp'
HPP='hls/ib_transport_protocol/ib_transport_protocol.hpp'

def commands(text,output,local):
    pattern=re.escape(output)+r'\.write\(memCmd\(([^\n]+)\)\);'
    return re.subn(pattern,lambda m:output+'.write(as02_duplex_command(memCmd('+m[1]+'),'+local+'));',text)

def derive():
    out=parent.derive()
    out[HPP]=parent.once(out[HPP],'\tap_uint<4>  vfid; \n\tmemCmd() {}',
        '\tap_uint<4>  vfid; \n'
        '    ap_uint<2> origin=0; // [95:94]: REMOTE1 / LOCAL2; never DMA authority\n\tmemCmd() {}')
    out[HPP]=parent.once(out[HPP],'struct routedMemCmd\n{',
        'inline memCmd as02_duplex_command(memCmd c,bool local) {\n'
        '    c.origin=local ? ap_uint<2>(2):ap_uint<2>(1);return c;\n}\n\nstruct routedMemCmd\n{')
    def reads(t):
        split=t.index('\telse if (!localReadRequests.empty())')
        remote,n=commands(t[:split],'out','false')
        local,m=commands(t[split:],'out','true')
        if (n,m)!=(3,10):raise ValueError('unreviewed read-command producers '+str((n,m)))
        return remote+local
    out[CPP]=parent.change(out[CPP],'void mem_cmd_merger(',reads)
    def writes(t):
        t,n=commands(t,'memoryWriteCmd','meta.request_owned')
        if n!=11:raise ValueError('unreviewed write-command producers '+str(n))
        return t
    out[CPP]=parent.change(out[CPP],'void rx_exh_fsm(',writes)
    top='hls/rocev2/rocev2.cpp'
    if out[top].count('void rocev2_native_request_top(')!=2:
        raise ValueError('unreviewed complete top declarations')
    out[top]=out[top].replace('void rocev2_native_request_top(','void rocev2_native_duplex_top(')
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous generated source')
    base=parent.qp.BASE
    before={str(x.relative_to(base)):parent.qp.digest(x)for x in base.rglob('*')if x.is_file()}
    files=derive()
    shutil.copytree(base/'fns',a.output/'fns');shutil.copytree(base/'adapter',a.output/'adapter')
    for name,value in files.items():(a.output/'fns'/name).write_text(value)
    if before!={n:parent.qp.digest(base/n)for n in before}:raise ValueError('original changed')
    info=dict(scope=__doc__,source_base=str(base),source_sha256=before,
        generator_sha256=parent.qp.digest(__file__),parent_generator_sha256=parent.qp.digest(parent.__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        original_unchanged=True,external_replay=True,native_rnr=True,receive_retirement=True,
        request_retirement=True,duplex_memory_provenance=True,memory_command_bits=96,
        memory_origin_bits=[94,95],HLS_top='rocev2_native_duplex_top',
        source_only=True,whole_core_drain_proved=False,hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=info['HLS_top'],original_unchanged=True)))

if __name__=='__main__':main()
