#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actual native SQC->RX route binding and the service-only HLS bridge.

Two SEPARATE elaborations, NOT one integrated Atomic native datapath. The
native authority graph still uses the real Immediate HLS; the normal/Atomic
service-only bridge separately uses the real owned Atomic HLS. Neither is a
behavioral HLS model. No runtime/hardware/Linux/physical/timing qualification.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import check_immediate_native_elaboration as old
import derive_atomic_native_authority as authority
import derive_atomic_native_bridge as common
import test_atomic_mac_tx_rtl as mac

ROOT=old.ROOT
digest=old.delivery.digest


def compile_graph(directory,name,top,parameters,sources,wanted):
    command=['iverilog','-g2012','-s',top,'-o',str(directory/(name+'.vvp'))]
    command+=['-P'+top+'.'+k+'='+str(v)for k,v in parameters.items()]
    command+=list(map(str,dict.fromkeys(sources)))
    start=time.monotonic()
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (directory/(name+'.log')).write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError(name+' actual graph elaboration failed')
    for line in r.stderr.splitlines():
        if 'expects' in line and any(n in line for n in ['context','owner','atomic','sq_tdata','core_data','done','mac_data','notification']):
            raise ValueError(name+' typed port mismatch: '+line)
    netlist=(directory/(name+'.vvp')).read_text()
    counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',netlist))for n in wanted}
    if counts!=wanted:raise ValueError(name+' duplicate/missing actual core/authority '+str(counts))
    return dict(command=command,seconds=time.monotonic()-start,compiler_exit=0,module_counts=counts,runtime_test=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--native-hls-report',type=Path,required=True);p.add_argument('--owned-hls-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if shutil.disk_usage(ROOT).free<256*1024*1024:raise RuntimeError('unchanged elaboration256MiB guard')
    directory=Path(tempfile.mkdtemp(prefix='atomic-native-authority-elaboration-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,directory=str(directory.relative_to(ROOT)),
        runtime_test=False,hardware_verified=False,Atomic_native_datapath_integrated=False,
        standard_API_runtime=False,full_board_timing=False,tests={})
    try:
        src,data,before,_,generated=old.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),directory)
        for original,text in authority.derive().items():
            if original==authority.base.responder.ORIGINAL:
                name='rocev2_shared_protected_responder.v'
            else:name=original.name
            path=directory/name
            if not path.exists():
                if src.count(original)!=1:raise ValueError('one original SQC source required')
                src.remove(original);src.append(path)
            path.write_text(text)
            before[str(path.relative_to(ROOT))]=digest(path)
        src+=authority.EXTRA
        bridge=directory/'rocev2_atomic_native_integrity_transport.v';bridge.write_text(common.derive())
        hls=json.loads(a.owned_hls_report.read_text())
        if not hls.get('pass_test')or hls.get('HLS_top')!='rocev2_native_atomic_owned_top':
            raise ValueError('matched successful complete owned HLS required')
        raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
        for name,sha in hls['generated_sha256'].items():
            if digest(raw/name)!=sha:raise ValueError('owned raw changed')
        common_sources=[*sorted(raw.glob('*.v')),bridge,ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',
            ROOT/'rdma/rtl/rocev2_tx_padding.v',mac.AXIS/'axis_adapter.v',mac.AXIS/'axis_register.v',
            mac.AXIS/'axis_fifo.v',mac.ETH/'lfsr.v']
        helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
            (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
        before.update({str(f.relative_to(ROOT)):digest(f)for f in [*src,*common_sources,*data,
            *helpers,a.owned_hls_report.resolve()]})
        report['source_sha256']=before
        wanted={n:1 for n in ['rocev2_top','rocev2_native_immediate_top','rocev2_native_rnic_endpoint',
            'rocev2_mr_table','rocev2_mr_page_table','rocev2_atomic_qp_binding',
            'rocev2_shared_protected_responder','rocev2_shared_hls_transport']}
        wanted['rocev2_sq_control_regs']=2;wanted['rocev2_memory_origin_router']=2
        report['tests']['native_authority']=compile_graph(directory,'native','rocev2_native_rnic_endpoint',
            {f+'_ENABLE':1 for f in old.FEATURES},src,wanted)
        report['tests']['common_bridge']=compile_graph(directory,'common','rocev2_atomic_native_integrity_transport',
            dict(LEGACY_QP_KEY=0,REQUEST_CQ_ENABLE=1,RNR_ENABLE=1,RECV_RETIRE_ENABLE=1),
            common_sources,{'rocev2_atomic_native_integrity_transport':1,'rocev2_native_atomic_owned_top':1,
                'rocev2_native_atomic_owned_top_state_table_0_s':1})
        main=(directory/'rocev2_native_rnic_endpoint.v').read_text()
        if ".local_core_drained(1'b0)"not in main or ".hls_transport_drained(1'b0)"not in main:
            raise ValueError('global zero drains changed')
        for name,sha in before.items():
            if digest(ROOT/name)!=sha:raise ValueError('source changed during elaboration: '+name)
        report.update(pass_test=True,source_unchanged=True,default_graph_changed=False,both_global_drains_zero=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in directory.iterdir()if f.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,directory=str(directory),tests={n:v['seconds']for n,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()
