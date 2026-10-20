#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze actual RNIC FULL-board inputs for analysis, NEVER image release.

Current finite smoke/provenance checks do not replace the older complete
initiator warm/PMTU/timer regressions or resulting full-board/CDC/native gates.
The paired Tcl stops at a routed checkpoint, never writes a bitstream or
programs hardware. Every consumed source/constraint/IP/profile is copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'rdma/read/fpga'))
import check_build as old_gate
sys.path.insert(0,str(ROOT/'rdma/read/hls'))
import check_sources


def require(value,message):
    if not value:raise ValueError(message)


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def make_files(path,name):
    values=[]
    for line in path.read_text().splitlines():
        match=re.match(r'^([A-Z_]+)\s*(\+?=)\s*(.+)$',line)
        if match and match[1]==name:
            if match[2]=='=':values=[]
            values+=match[3].split()
    require(values,'missing Makefile list '+name)
    return values


def check_hashes(mapping,base,inputs):
    for name,expected in mapping.items():
        p=(base/name).resolve();require(digest(p)==expected,'stale input '+str(p));inputs.add(p)


def metadata_reset_proof(r):
    require(r.get('pass_test') and r.get('terminal_exit_status')==0 and
            r.get('sequential_initialization_required') is True and r.get('inputs_unchanged') and
            r.get('checks')==8024 and r.get('zero_checks')==4023 and
            r.get('data_checks')==2000 and r.get('append_checks')==2001 and
            r.get('reset_checks')==16,'incomplete metadata initialization/reset evidence')


def four_state_proof(r):
    require(r.get('four_state_simulation') is True and
            r.get('original_testbench_assertions_preserved') is True,
            'metadata transport requires actual four-state evidence, not compiled two-state substitution')


def verify(hls,profile,fns,evidence,hls_policy='state'):
    require(hls_policy in ['state','metadata-sequential'],'unknown reviewed HLS policy')
    metadata=hls_policy=='metadata-sequential'
    require(Path(old_gate.__file__).resolve()==ROOT/'rdma/read/fpga/check_build.py','wrong original physical-gate module')
    inputs={Path(__file__).resolve(),Path(__file__).with_name('build_board.tcl'),
            Path(old_gate.__file__).resolve(),Path(check_sources.__file__).resolve()}
    check_hashes(old_gate.PHYSICAL_INPUTS,ROOT,inputs)
    p=profile/'native-profile.json';prepared=json.loads(p.read_text());inputs.add(p)
    require(prepared['pass_test'] and not prepared['board_built'],'invalid prepared source scope')
    require(prepared['output_directory']==str(profile),'wrong prepared source directory')
    for field in ['source_sha256','profile_sha256']:check_hashes(prepared[field],ROOT,inputs)
    check_hashes(prepared['generated_sha256'],profile,inputs)
    required=prepared['required_profile']
    require(required['APP_ID']=='0x41534e31' and required['APP_DMA_ENABLE']==1 and
            required['DMA_TAG_WIDTH']==19 and required['app_DMA_TAG_WIDTH']==16 and
            required['TX_SEQ_NUM_ENABLE']==1,'unsafe native DMA identity/tag/sequence profile')
    p=evidence/('rocev2-rnic-meta-reset-hls-001.json' if metadata else 'rocev2-rnic-state-hls-001.json')
    record=json.loads(p.read_text());inputs.add(p)
    expected_policy='state,synchronous,active-low;metadata-sequential-clear' if metadata else 'state,synchronous,active-low'
    require(record['pass_test'] and record['inputs_unchanged'] and not record['hardware_verified'] and
            record['reset_policy']==expected_policy and record['hls_build']==str(hls),'wrong HLS source candidate')
    require(check_sources.verify(fns)==record['source_sha256'],'changed FNS source')
    check_hashes(record['source_sha256'],fns,inputs);check_hashes(record['profile_sha256'],ROOT,inputs)
    if metadata:
        patched=record['patched_source_sha256'];original=record['source_sha256']
        require(record['sequential_clear_entries']==2000 and set(patched)==set(original) and
                [n for n in original if original[n]!=patched[n]]==
                ['hls/ib_transport_protocol/retransmitter/retransmitter.hpp'],
                'unreviewed metadata source patch set/capacity')
        check_hashes(patched,hls.parent/'inputs/fns',inputs)
    generated=sorted([*(hls/'solution1/syn/verilog').glob('*.v'),*(hls/'solution1/syn/verilog').glob('*.dat')])
    g=hashlib.sha256()
    for p in generated:g.update(p.name.encode()+b'\0'+p.read_bytes())
    identity=g.hexdigest();require(len(generated)==138 and identity==record['generated_hls_sha256'],'mixed generated HLS')
    inputs.update(generated)
    constructor='meta-reset-ipv4-001' if metadata else 'ipv4-reset-state-001'
    parent='meta-reset-parent-compile-001' if metadata else 'state-parent-compile-001'
    control='meta-reset-native-4state-002' if metadata else 'state-native-control-001'
    legacy={op:('meta-reset-'+op+'-4state-'+('002' if op=='read' else '001') if metadata else 'state-legacy-'+op+'-001') for op in ['read','write']}
    errors={kind:('meta-reset-'+kind+'-error-4state-001' if metadata else 'state-'+kind+'-error-001') for kind in ['read','fence']}
    names=[constructor,parent,control,*legacy.values(),*errors.values()]
    if metadata:names+=['meta-reset-table-001']
    records={}
    for name in names:
        p=evidence/('rocev2-rnic-'+name+'.json');r=json.loads(p.read_text());inputs.add(p);records[name]=r
        require(not r['hardware_verified'],'wrong evidence scope '+name)
        require(r.get('pass_test',r.get('characterization_pass',False)),'failed smoke '+name)
        if name!=parent:require(r['generated_hls_sha256']==identity,'mixed smoke HLS '+name)
        check_hashes(r.get('source_sha256',{}),ROOT,inputs)
    if metadata:
        metadata_reset_proof(records['meta-reset-table-001'])
        for name in [control,*legacy.values(),*errors.values()]:four_state_proof(records[name])
    r=records[constructor];require(r['release_reset_gate_pass'] and r['total_observations']==88 and r['invalid_observations']==0,'constructor reset regression')
    r=records[parent];params=r['parameter_values']
    require(r['profile_manifest_sha256']==digest(profile/'native-profile.json'),'different elaborated profile manifest')
    require(r['actual_patched_parent_core_app_elaborated'] and params['TX_TAG_WIDTH']==16 and
            params['DMA_TAG_WIDTH']==19 and params['AXIS_DATA_WIDTH']==64 and params['AXIS_SYNC_DATA_WIDTH']==128,'parent/app width elaboration missing')
    for name in ['mqnic_core.v','mqnic_core_pcie.v','mqnic_app_block.v']:
        require(r['source_sha256'].get(str((profile/name).relative_to(ROOT)))==digest(profile/name),'different elaborated parent/app source')
    r=records[control]
    require(r['actual_parent_proof_RTL'] and not r['parent_proof_uses_host_model_counters'] and
            not r['raw_Ethernet_config_driven'] and not r['raw_MR_PTE_QP_driven'] and
            r['all_host_sidebands_checked'] and
            len(r['host_replies'])==21 and r['write_bytes_checked']==130 and r['read_bytes_checked']==195 and
            r['summary']['ethernet_epoch']==2,'incomplete protected/control smoke')
    for op in ['read','write']:
        r=records[legacy[op]];require(r['operation']==op and r['message_bytes']==65 and
            r['wire_headers_checksums_verified'] and r['all_responder_descriptors_and_TLPs_forbidden'],'legacy smoke missing')
        if op=='read':require(r['capture_payload_bytes_verified']==65 and r['capture_sentinel_bytes_verified']==127,'capture guards missing')
    for kind in ['read','fence']:
        r=records[errors[kind]];require(r['actual_parent_proof_RTL'] and
            not r['parent_proof_uses_host_model_counters'] and r['summary']['guard_fault']==34 and
            r['summary']['completed']==0 and not r['summary']['page_release_proof'],'UR refusal missing')
    return inputs,identity


def collect(hls,profile):
    corundum=ROOT/'external/corundum';port=ROOT/'external/as02mc04-port'
    for directory,commit in [(corundum,'1ca0151b97af85aa5dd306d74b6bcec65904d2ce'),(port,'b00e73a136170604e40341b13b9b1fb9df9304fb')]:
        require(subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()==commit,'wrong pinned dependency')
    board=corundum/'fpga/mqnic/Nexus_K3P_S/fpga_25g';makefile=port/'Makefile'
    sources=[]
    for rel in make_files(makefile,'SYN_FILES'):
        p=(ROOT/'fpga/fpga_as02mc04_25g_cdc.v') if rel=='rtl/fpga_as02mc04.v' else (board/rel).resolve()
        if p.name in ['mqnic_core.v','mqnic_core_pcie.v']:p=profile/p.name
        sources.append(p)
    sources+=sorted((ROOT/'rdma/rtl').glob('*.v'))+sorted((ROOT/'rdma/read/rtl').glob('*.v'))
    sources+=sorted((ROOT/'rdma/rnic/rtl').glob('*.v'))+sorted((hls/'solution1/syn/verilog').glob('*.v'))
    sources+=[profile/'mqnic_app_block.v',corundum/'fpga/lib/eth/rtl/eth_axis_rx.v',corundum/'fpga/lib/eth/rtl/eth_axis_tx.v']
    sources=list(dict.fromkeys(p.resolve() for p in sources))
    constraints=[(ROOT/'fpga/as02mc04.xdc') if rel=='as02mc04.xdc' else (board/rel).resolve() for rel in make_files(makefile,'XDC_FILES')]
    constraints+=[ROOT/'fpga/vio_status_cdc.xdc',ROOT/'fpga/mac_flow_control_cdc.xdc']
    ip=[(port/rel).resolve() if rel=='ip/vio_status.tcl' else (board/rel).resolve() for rel in make_files(makefile,'IP_TCL_FILES')]
    data=sorted((hls/'solution1/syn/verilog').glob('*.dat'))
    for p in [*sources,*constraints,*ip,*data]:require(p.is_file(),'missing selected file '+str(p))
    for name in ['mqnic_core.v','mqnic_core_pcie.v','mqnic_app_block.v']:
        require([p for p in sources if p.name==name]==[profile/name],'old/duplicate native parent/app selected '+name)
    return sources,constraints,ip,data,makefile


def tcl(v):
    return '"'+str(v).replace('\\','\\\\').replace('"','\\"').replace('$','\\$').replace('[','\\[').replace(']','\\]')+'"'


def prepare(output,hls,profile,fns,evidence,hls_policy='state'):
    require(not output.exists(),'refuse to overwrite any board analysis directory')
    inputs,identity=verify(hls,profile,fns,evidence,hls_policy)
    sources,constraints,ip,data,makefile=collect(hls,profile)
    config=profile/'config_25g.tcl'
    inputs.update([*sources,*constraints,*ip,*data,makefile,config])
    before={str(p):digest(p) for p in inputs}
    output.mkdir(parents=True);frozen=output/'inputs';frozen.mkdir()
    mapping={}
    for p in sorted(inputs):
        rel=p.relative_to(ROOT) if p.is_relative_to(ROOT) else Path('external-source')/hashlib.sha256(str(p.parent).encode()).hexdigest()[:16]/p.name
        dest=frozen/'originals'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        require(digest(dest)==before[str(p)],'changed while copying '+str(p));mapping[p]=dest
    require(before=={str(p):digest(p) for p in inputs},'original inputs changed during preparation')
    lines=[]
    for name,paths in [('sources',sources),('constraints',constraints),('ip_scripts',ip),('memory_init',data)]:
        lines.append('set '+name+' [list '+' '.join(tcl(mapping[p]) for p in paths)+']')
    lines+=['set config_script '+tcl(mapping[config]),'set corundum '+tcl(ROOT/'external/corundum')]
    (frozen/'build_inputs.tcl').write_text('\n'.join(lines)+'\n')
    snapshots={str(p.relative_to(frozen)):digest(p) for p in frozen.rglob('*') if p.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(f'{h}  {n}\n' for n,h in sorted(snapshots.items())))
    report=dict(scope=__doc__,pass_test=True,analysis_inputs_prepared=True,release_authorized=False,
        full_legacy_regressions_rerun=False,full_board_physical_gate_passed=False,conditional_CDC_reviewed=False,
        hardware_verified=False,hls_policy=hls_policy,generated_hls_sha256=identity,profile_directory=str(profile),
        output_directory=str(output),selected_sources=[str(p) for p in sources],constraints=[str(p) for p in constraints],
        original_input_sha256=before,frozen_sha256=snapshots,
        driver=str(mapping[Path(__file__).with_name('build_board.tcl')]),
        missing_before_image=['Fresh full warm/PMTU/timer/initiator regression coverage for selected HLS.',
            'Original full-board clocks/setup/hold/pulse/skew/routing/DRC gates and conditional CDC review.',
            'Actual parent/app functional/native memory ownership and runtime-driver safety checks.'])
    with (output/'analysis-inputs.json').open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['output','hls-build','profile','fns-source']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--hls-policy',choices=['state','metadata-sequential'],default='state')
    parser.add_argument('--evidence',type=Path,default=ROOT/'results/2026-10-18')
    args=parser.parse_args()
    r=prepare(args.output.resolve(),args.hls_build.resolve(),args.profile.resolve(),args.fns_source.resolve(),args.evidence.resolve(),args.hls_policy)
    print(json.dumps({k:v for k,v in r.items() if not k.endswith('sha256')},indent=2))


if __name__=='__main__':main()
