#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compile/link immutable kernel-library/CSR-only auxiliary copies, NEVER load.

Actual running-kernel headers, W=1, matching GCC13 and pinned mqnic headers.
No ib_device/provider/callback execution, pinning, DMA, install or hot-unplug
proof. Private loaded-parent ABI remains unverified; auxiliary probe stays off.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
SOURCE=Path(__file__).resolve().parent
OWN=['Makefile','mr.c','mr.h','mr_contract.c','mr_contract.h','rnic_regs.h',
     'rnic_io.c','rnic_io.h','rnic_hw.c','rnic_hw.h','native_regs.h',
     'native_attach.c','native_attach.h','aux_control.c','wqe.c','wqe.h','verbs_wqe.c','sq.c','sq.h',
     'sq_io.c','sq_io.h','sq_hw.c','sq_hw.h','sq_regs.h',
     'cq_regs.h','cq_io.c','cq_io.h','cq_hw.c','cq_hw.h','cq.c','cq.h',
     'qp_hw.c','qp_hw.h','retry_io.c','retry_io.h','verbs.c','verbs.h','device.c','device.h',
     'native_graph.c','native_graph.h','mqnic_graph.c','mqnic_graph.h']
HEADERS=['mqnic.h','mqnic_hw.h']
PARENT_COMMIT='1ca0151b97af85aa5dd306d74b6bcec65904d2ce'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(mapping,base):
    for name,value in mapping.items():
        if digest(base/name)!=value:raise ValueError('source/frozen input changed: '+str(base/name))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',type=Path,default=ROOT/'external/corundum/modules/mqnic')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve previous evidence')
    parent=args.parent.resolve()
    revision=subprocess.check_output(['git','-C',str(parent),'rev-parse','HEAD'],text=True).strip()
    if revision!=PARENT_COMMIT:raise ValueError('unreviewed parent revision')
    release=os.uname().release
    compiler=Path(shutil.which('x86_64-linux-gnu-gcc-13')).resolve()
    originals=[*(SOURCE/n for n in OWN),*(parent/n for n in HEADERS),Path(__file__).resolve()]
    source_hashes={str(p.relative_to(ROOT)):digest(p) for p in originals}
    build_directory=ROOT/'rdma/rnic/build'
    build_directory.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='kernel-sq-frozen-',dir=build_directory))
    for name in OWN:shutil.copy2(SOURCE/name,run/name)
    (run/'parent').mkdir()
    for name in HEADERS:shutil.copy2(parent/name,run/'parent'/name)
    (run/'launch').mkdir()
    shutil.copy2(Path(__file__).resolve(),run/'launch/build_frozen.py')
    frozen={str(p.relative_to(run)):digest(p) for p in run.rglob('*') if p.is_file()}
    (run/'inputs.sha256').write_text(''.join(f'{h}  {n}\n' for n,h in sorted(frozen.items())))
    checked(source_hashes,ROOT);checked(frozen,run)
    command=['make','-C',str(run),'CC='+str(compiler),'AS02_BUILD_AUX=1',
             'MQNIC_SRC='+str(run/'parent'),'module']
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(dict(started_at=started,directory=str(run),frozen_inputs=len(frozen),
        source_frozen_before_compile=True,modules_will_not_be_loaded=True)),flush=True)
    with (run/'build.log').open('x')as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    checked(source_hashes,ROOT);checked(frozen,run)
    files=[run/n for n in frozen]+[run/'inputs.sha256',run/'build.log']
    modules={name:run/(name+'.ko') for name in ['as02_mr_support','as02_rnic_ctrl']}
    metadata={};symbols=[]
    if result.returncode==0:
        for name,p in modules.items():
            metadata[name]={field:subprocess.check_output(['modinfo','-F',field,str(p)],text=True).strip()
                            for field in ['vermagic','alias','parm','description']}
            if not metadata[name]['vermagic'].startswith(release+' '):raise ValueError('wrong module kernel')
            files.append(p)
        if metadata['as02_rnic_ctrl']['alias']!='auxiliary:mqnic.app_41534e31':
            raise ValueError('wrong auxiliary alias')
        output=subprocess.check_output(['nm','-g','--defined-only',str(modules['as02_mr_support'])],text=True)
        names={line.split()[-1] for line in output.splitlines() if line.split()}
        symbols=['as02_wqe_validate','as02_wqe_encode','as02_wqe_decode','as02_wqe_from_ib_send_wr',
                 'as02_wqe_validate_profile','as02_wqe_encode_profile','as02_wqe_decode_profile','as02_wqe_from_ib_send_wr_profile',
                 'as02_mr_pool_get_client','as02_mr_pool_put_client','as02_user_mr_get_work','as02_user_mr_put_work',
                 'as02_sq_pool_init','as02_sq_pool_destroy','as02_sq_create','as02_sq_close',
                 'as02_sq_cancel_receive','as02_sq_flush_receive','as02_sq_prepare_receive_cancel','as02_sq_post','as02_sq_complete',
                 'as02_sqc_io_init','as02_sqc_io_execute','as02_sqc_io_reconcile','as02_sqc_io_detach',
                 'as02_sq_hw_init','as02_sq_bind_transport_profile','as02_sq_hw_detach','as02_sq_hw_reconcile','as02_sqc_sq_hw_ops',
                 'as02_sq_complete_event','as02_sq_pool_get_completion_client','as02_sq_pool_put_completion_client',
                 'as02_cq_decode','as02_cq_decode_profile','as02_cq_io_init','as02_cq_io_poll','as02_cq_io_detach',
                 'as02_cq_hw_init','as02_cq_hw_poll','as02_cq_hw_detach','as02_cq_hw_get_client','as02_cq_hw_put_client',
                 'as02_cq_hw_arm','as02_cq_hw_disarm',
                 'as02_cq_create','as02_cq_destroy','as02_cq_poll','as02_cq_req_notify',
                 'as02_cq_attach_hardware','as02_cq_router_init','as02_cq_router_bind','as02_cq_router_unbind',
                 'as02_cq_router_abandon','as02_cq_publish',
                 'as02_qp_hw_init','as02_qp_hw_open','as02_qp_hw_close','as02_qp_hw_set_tx',
                 'as02_qp_hw_enable_retry','as02_qp_hw_set_retry','as02_retry_io_init','as02_retry_io_configure',
                 'as02_verbs_ops','as02_verbs_bind','as02_verbs_unbind','as02_verbs_reap',
                 'as02_device_alloc','as02_device_publish','as02_device_unpublish','as02_device_free','as02_device_ops',
                 'as02_native_lease_init','as02_native_graph_open','as02_native_graph_close','as02_native_graph_reconcile_control',
                 'as02_mqnic_native_open']
        if not set(symbols)<=names:raise ValueError('actual kernel WQE API missing')
    loaded=[line.split()[0]for line in Path('/proc/modules').read_text().splitlines()
            if line.startswith('as02_')]
    report=dict(scope=__doc__,started_at=started,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        terminal_exit_status=result.returncode,pass_test=result.returncode==0,
        source_sha256=source_hashes,source_and_frozen_inputs_unchanged=True,
        source_frozen_before_compile=True,own_inputs=len(OWN),pinned_parent_headers=2,
        launcher_inputs=1,frozen_files=len(frozen),parent_commit=revision,
        directory=str(run.relative_to(ROOT)),kernel=release,W=1,compiler=str(compiler),
        compiler_sha256=digest(compiler),command=command,modules=metadata,
        actual_kernel_WQE_symbols_linked=symbols,
        artifact_sha256={str(p.relative_to(ROOT)):digest(p) for p in files},
        probe_default_enabled=False,parent_header_runtime_compatibility_verified=False,
        installed=False,module_load_performed=False,as02_modules_loaded_observed=loaded,
        ib_device_registered=False,kernel_WR_callback_executed=False,user_pages_pinned=False,
        MMIO_executed=False,DMA_enabled=False,hardware_verified=False,
        kernel_CQ_callbacks_implemented_and_linked=result.returncode==0,
        PD_MR_QP_post_send_callbacks_implemented_and_linked=result.returncode==0,
        standard_verbs_or_provider_implemented=False,hot_unplug_lifetime_verified=False)
    report['standard_device_publication_entrypoints_implemented_and_linked']=result.returncode==0
    report['RDMA_bus_attachment_wired']=False
    report['explicit_pinned_parent_to_native_graph_adapter_linked']=result.returncode==0
    report['native_attach_default_enabled']=False
    with args.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','artifact_sha256']},indent=2))
    if result.returncode:raise SystemExit(1)


if __name__=='__main__':main()
