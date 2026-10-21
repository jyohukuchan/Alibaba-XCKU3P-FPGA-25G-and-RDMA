#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""WIP source graph syntax/bindings only, explicitly NOT full elaboration.

New actual HLS is still a separate synthesis job. Icarus -i ignores missing
HLS/vendor leaves here, so a success cannot qualify generated HLS ports,
native operation or hardware/timing. It catches native wiring/syntax errors
before the mandatory later real generated-HLS elaboration/runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_receive as candidate
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    out=candidate.derive();run=Path(tempfile.mkdtemp(prefix='receive-message-graph-syntax-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-message-syntax-',dir='/dev/shm'))
    raw=[*candidate.RTL.glob('*.v'),ROOT/'rdma/rtl/rocev2_integrity_transport.v']
    inputs=[*raw,*list((ROOT/'rdma/rnic/fpga').glob('derive_*.py')),Path(__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    files=[]
    for pth in raw:
        if pth in out:
            p=run/pth.name;p.write_text(out[pth]);files.append(p)
        else:files.append(pth)
    # Strict source-level routing checks are not substituted for the later
    # actual synthesized776-bit port/runtime proof.
    root=out[candidate.RTL/'rocev2_native_rnic_endpoint.v']
    assert root.count('rocev2_receive_message_queue #(')==1
    assert root.count('.s_message_data(rq_message_data)')==1
    assert root.count('.m_recv_message_data(rq_message_data)')==1
    assert root.count('.s_retire_context(rq_packet_retire_context)')==1
    assert 'rq_retire_ready && recv_ack_retire_ready && recv_hls_retire_ready :'not in root
    bridge=out[ROOT/'rdma/rtl/rocev2_integrity_transport.v']
    assert bridge.count('rocev2_native_segmented_receive_top transport (')==1
    assert bridge.count('.m_axis_recv_message_TREADY(m_recv_message_ready)')==1
    parameters={n:1 for n in ['QP_TX_ENABLE','RETRY_ENABLE','SEND_ENABLE','RECV_ENABLE','RNR_ENABLE',
        'RECV_RETIRE_ENABLE','RECV_CQ_ENABLE','REQUEST_CQ_ENABLE','SEPARATE_RQ_ENABLE','RECV_CANCEL_ENABLE','DUPLEX_ENABLE']}
    command=['iverilog','-g2012','-i','-s','rocev2_native_rnic_endpoint',
        *['-Procev2_native_rnic_endpoint.'+n+'='+str(v)for n,v in parameters.items()],
        '-o',str(ram/'syntax'),*map(str,files)]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        command=command,limit_seconds=30,syntax_only=True,unknown_leaves_ignored=True,actual_generated_HLS=False,
        full_native_elaboration=False,native_runtime=False,hardware_verified=False,full_board_timing=False,
        explicit_profile_parameters=parameters,
        source_profile=dict(RNC=65535,CQC=255,SQC=13,RQC=31,receive_source_limit=1048576,old_default_unchanged=True))
    try:
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=30)
        (run/'syntax.log').write_text(c.stdout+c.stderr);result.update(exit=c.returncode,seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('new native source wiring/syntax failed:'+str(run/'syntax.log'))
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during compile')
        result.update(pass_test=True,source_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,syntax_only=True,actual_generated_HLS=False,seconds=result['seconds'])))


if __name__=='__main__':main()
