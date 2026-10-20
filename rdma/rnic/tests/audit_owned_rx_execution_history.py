#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Identity/provenance audit for progress052 owned actual RX execution.

Historical models/failed reports are not native/RTL/physical/goal proof.
The original051 parent/index remains immutable; new report output only.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[3]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    a.report=a.report.resolve()
    if a.report.exists():ap.error('preserve earlier audit evidence')
    if not a.report.is_relative_to(ROOT/'results'):ap.error('report must be in repository results/')
    cache={};artifacts={};aliases=[]
    def sha(n):
        q=Path(n);q=q if q.is_absolute()else ROOT/q
        if q not in cache:cache[q]=hashlib.sha256(q.read_bytes()).hexdigest()
        return cache[q]
    def read(n):return json.loads((ROOT/n).read_text())
    def check(n,h,index=True):
        assert sha(n)==h,n
        if index:artifacts[str(Path(n).relative_to(ROOT)if Path(n).is_absolute()else n)]=h
    parent_path='results/2026-10-18/rocev2-rnic-progress-051.json'
    parent_sha='188d405ff6e0b15e5a44817c14f9245fc727fd9f0ea5c72430f73013964e171e'
    check(parent_path,parent_sha,False);parent=read(parent_path)
    older_ref=parent['parent_progress'];check(older_ref['record'],older_ref['sha256'],False);older=read(older_ref['record'])
    wire_ref=parent['validation']['wire_history_audit'];check(wire_ref['record'],wire_ref['sha256'],False);wire=read(wire_ref['record'])
    old=older['validation']['current_record_frozen_rollback_audit'];extra=dict(old['additional_selected_artifact_verification']['artifact_sha256'])
    extra.update(parent['validation']['additional_selected_artifact_verification']['delta_from_parent']['sha256_overrides'])
    inherited={}
    for group in [old['artifact_sha256'],extra,wire['artifact_sha256']]:
        for n,h in group.items():
            if n in inherited:assert inherited[n]==h,n
            inherited[n]=h;check(n,h,False)
    assert len(inherited)==10540
    rollback=parent['validation']['rollback'];check(rollback['bitstream'],rollback['bitstream_sha256'],False)
    spec=importlib.util.spec_from_file_location('owned_rx_execution',ROOT/'rdma/rnic/hls/owned_rx_execution_profile.py')
    profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
    records={};pattern=re.compile(r'rocev2-rnic-owned-rx-execution-(?:C|derivation)-[0-9]+\.json$')
    for f in sorted((ROOT/'results/2026-10-18').glob('rocev2-rnic-owned-rx-execution-*.json')):
        if not pattern.fullmatch(f.name):continue
        name=str(f.relative_to(ROOT));r=read(name);run=ROOT/r['retained_directory'];check(name,sha(name))
        for n,h in r['source_sha256'].items():
            if sha(n)==h:check(n,h);continue
            mirrors=[run/'inputs'/n,run/'inputs/profile'/n]
            source_path=ROOT/n;fns=profile.source.BASE/'fns/hls'
            if source_path.is_relative_to(fns):mirrors.append(run/'inputs/fns/hls'/source_path.relative_to(fns))
            if source_path==profile.source.BASE/'adapter/rocev2_config.hpp':mirrors.append(run/'inputs/adapter/rocev2_config.hpp')
            exact=[q for q in mirrors if q.is_file()and sha(q)==h]
            assert exact,('no exact historical frozen source',name,n)
            check(exact[0],h);aliases.append(dict(record=name,source=n,frozen=str(exact[0].relative_to(ROOT)),sha256=h))
        for n,h in r['frozen_source_sha256'].items():check(run/'inputs'/n,h)
        for n,h in r['artifact_sha256'].items():check(n,h)
        for q in run.rglob('*'):
            if q.is_file():check(q,sha(q))
        eligible=r['pass_test']is True and r['terminal_exit_status']==0
        records[name]=dict(sha256=sha(name),raw_pass_test=r['pass_test'],terminal_exit_status=r['terminal_exit_status'],eligible_pass=eligible,retained_directory=r['retained_directory'],error_type=r.get('error_type'),error=r.get('error'))
    assert len(records)==15
    cpath='results/2026-10-18/rocev2-rnic-owned-rx-execution-C-008.json';upath='results/2026-10-18/rocev2-rnic-owned-rx-execution-derivation-007.json'
    c=read(cpath);u=read(upath);assert records[cpath]['eligible_pass']and records[upath]['eligible_pass']
    for r in [c,u]:
        for n,h in r['source_sha256'].items():assert sha(n)==h,('current source not current',n)
        assert not r['RTL_tested']and not r['hardware_verified']and not r['native_DMA_CQ']
    assert u['methods']==11 and c['simulation_exit_status']==0 and c['simulation_seconds']<30 and c['simulation_wall_bound_seconds']==30
    assert c['source_and_frozen_inputs_unchanged']and not c['HLS_constructed']and not c['ONE_shared_native_graph']and c['shared_local_core_drained']==0
    run=ROOT/c['retained_directory'];generated=run/'inputs/owned_rx_execution.hpp'
    assert generated.read_text()==profile.derive(profile.CPP.read_text())
    assert (run/'inputs/test_owned_rx_execution.cpp').read_bytes()==(ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp').read_bytes()
    command=json.loads((run/'compile-command.json').read_text());assert '-fsanitize=undefined'in command and '-fno-sanitize-recover=all'in command and '-DNDEBUG'not in command
    rows=[json.loads(s[len('OWNED_RX_EXECUTION '):])for s in (run/'run.stdout.log').read_text().splitlines()if s.startswith('OWNED_RX_EXECUTION ')]
    assert rows==[c['summary']];s=rows[0]
    assert s['positive_transactions']==12 and s['AETH_values']==256 and s['AETH_packets']==736 and s['nonpositive_control_packets']==672
    assert s['negative_cases']==18 and s['full_owner_bit_comparisons']==1612 and s['raw_padding_separate_from_DMA_length']
    ambiguous=[n for n,r in records.items()if r['raw_pass_test']and r['terminal_exit_status']!=0]
    assert ambiguous==['results/2026-10-18/rocev2-rnic-owned-rx-execution-C-006.json']
    assert not records[ambiguous[0]]['eligible_pass']and records[ambiguous[0]]['error_type']=='ValueError'
    retained_failures=[n for n,r in records.items()if not r['eligible_pass']];assert len(retained_failures)==6
    assert not (ROOT/'results/2026-10-18/rocev2-rnic-owned-rx-execution-invalid-preflight-052.json').exists()
    current_files=[Path(__file__).resolve(),ROOT/'docs/ROCEV2_OWNED_RX_EXECUTION.md',ROOT/'rdma/rnic/tests/test_owned_rx_execution_derivation.py',ROOT/'rdma/rnic/tests/probe_owned_rx_execution.py',ROOT/'rdma/rnic/hls/owned_rx_execution_profile.py',ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp']
    for q in current_files:check(q,sha(q))
    result=dict(scope=__doc__,pass_test=True,terminal_exit_status=0,parent_progress=parent_path,parent_progress_sha256=parent_sha,
        inherited_artifact_index_entries_verified_unchanged=len(inherited),parent_wire_history_audit=wire_ref,
        inherited_archive_members_authenticated_unchanged=6076,rollback_bit_sha256=rollback['bitstream_sha256'],
        current_C_record=cpath,current_C_record_sha256=sha(cpath),current_unit_record=upath,current_unit_record_sha256=sha(upath),
        current_C_summary=s,current_C_compile_seconds=c['compile_seconds'],current_C_simulation_seconds=c['simulation_seconds'],
        records=records,historical_frozen_source_aliases=aliases,retained_failed_or_unqualified_records=retained_failures,
        contradictory_historical_flags_not_promoted=ambiguous,current_source_files={str(q.relative_to(ROOT)):sha(q)for q in current_files},
        artifact_sha256=artifacts,verified_new_artifact_files=len(artifacts),root_free_bytes=shutil.disk_usage(ROOT).free,
        RTL_tested=False,ONE_shared_native_graph=False,hardware_verified=False,physical_signoff=False,native_DMA_CQ=False,goal_completion_proof=False,errors=[])
    with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(record=str(a.report.relative_to(ROOT)),sha256=sha(a.report),pass_test=True,records=len(records),new_artifact_files=len(artifacts),inherited_artifacts=len(inherited),current_C_summary=s,retained_failures=6,ambiguous_flags_not_promoted=1,errors=[],goal_completion_proof=False)))

if __name__=='__main__':main()
