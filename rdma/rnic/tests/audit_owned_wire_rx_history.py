#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Identity/history audit of actual wire-RX candidates and recoverable archives.

This is NOT native host/WR/MR/DMA/CQ, physical timing, or full-goal completion.
Historical source aliases require exact frozen record/parent bytes, not waivers.
Reports are generated audit artifacts; original build/test reports are untouched.
"""
import argparse
import re
from pathlib import Path
import hashlib
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--parent-progress',type=Path,default=Path('results/2026-10-18/rocev2-rnic-progress-050.json'))
args=parser.parse_args()
repo=Path(__file__).resolve().parents[3]
if not args.report.is_absolute():args.report=repo/args.report
if not args.parent_progress.is_absolute():args.parent_progress=repo/args.parent_progress
if args.report.exists():parser.error('preserve existing audit evidence')
if not args.report.resolve().is_relative_to(repo/'results'):parser.error('audit report must be in this repository results/')
if not args.parent_progress.is_file():parser.error('parent progress must exist')
self_sha_started=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3];prefix='results/2026-10-18/rocev2-rnic-owned-wire-rx-'
pattern=re.compile(r'rocev2-rnic-owned-wire-rx-(?:hls|XSIM|derivation|keep|control-XSIM)-[0-9]+\.json$')
records=[str(f.relative_to(root))for f in sorted((root/'results/2026-10-18').glob('rocev2-rnic-owned-wire-rx-*.json'))if pattern.fullmatch(f.name)]
assert records
cache={};hashes={};errors=[];counts={};sources=[];out={}
def sha(p):
 p=p.resolve()
 if p not in cache:cache[p]=hashlib.sha256(p.read_bytes()).hexdigest()
 return cache[p]
def check(p,h,kind):
 p=Path(p);p=p if p.is_absolute()else root/p
 try:
  actual=sha(p);assert actual==h,(actual,h)
  hashes[str(p.relative_to(root))]=actual
  counts[kind]=counts.get(kind,0)+1
 except Exception as e:errors.append([str(p),kind,str(e)])
def source(r,n,f,h,kind):
 current=root/f
 if current.exists()and sha(current)==h:check(current,h,kind+' current');return
 run=root/r['retained_directory']
 dirs=[run/'inputs']
 if 'parent_record'in r:
  parent=json.loads((root/r['parent_record']).read_text());dirs.append(root/parent['retained_directory']/'inputs')
 mirrors=[p for d in dirs for p in [d/f,d/Path(f).name,d/'profile'/Path(f).name]]
 same=[p for p in mirrors if p.is_file()and sha(p)==h]
 if not same:errors.append([f,kind+' historical source','no exact frozen mirror in record or exact parent'])
 else:
  check(same[0],h,kind+' historical frozen');sources.append(dict(record=n,original=f,retained=str(same[0].relative_to(root)),sha256=h))
# Previous048 reports themselves must remain byte-exact, not rewritten claims.
old=json.loads((root/'results/2026-10-18/rocev2-rnic-progress-049.json').read_text())
parent=json.loads(args.parent_progress.read_text())
if 'current_record_frozen_rollback_audit'in parent['validation']:
 prior=parent['validation']['current_record_frozen_rollback_audit']['additional_wire_RX_verification']['artifact_sha256']
else:
 reference=parent['validation']['wire_history_audit']
 evidence=root/reference['record'];assert hashlib.sha256(evidence.read_bytes()).hexdigest()==reference['sha256']
 prior=json.loads(evidence.read_text())['artifact_sha256']

for n in records:
 r=json.loads((root/n).read_text());run=root/r['retained_directory'];out[n]=r
 if n in prior:check(n,prior[n],'unchanged048 report')
 hashes[n]=sha(root/n)
 for f,h in r.get('source_sha256',{}).items():source(r,n,f,h,'source')
 for field in ['generated_sha256','artifact_sha256','compiled_snapshot_sha256']:
  for f,h in r.get(field,{}).items():check(f,h,field)
 for f,h in r.get('frozen_source_sha256',{}).items():check(run/'inputs'/f,h,'frozen input')
 if 'tests'in r:
  for test in r['tests'].values():
   for f,h in test['source_sha256'].items():source(r,n,f,h,'unit')
 if r.get('pass_test'):
  assert r['terminal_exit_status']==0 if 'terminal_exit_status'in r else True
 for f in run.rglob('*'):
  if f.is_file():hashes[str(f.relative_to(root))]=sha(f)
# Exact archived terminal DBs, including543previous049 logical file paths.
import tarfile
archived_members=0;old_logical_members=0
old_wire=old['validation']['current_record_frozen_rollback_audit']['additional_wire_RX_verification']['artifact_sha256']
for archive_record in sorted((root/'results/2026-10-18').glob('rocev2-rnic-terminal-db-archive-*.json')):
 ar=json.loads(archive_record.read_text());am_path=ar['manifest'];am=json.loads((root/am_path).read_text())
 assert ar['expanded_duplicate_directories_removed']and ar['recoverable']
 for db,v in ar['targets'].items():
  check(v['archive'],v['archive_sha256'],'recoverable terminal DB archive')
  check(v['HLS_record'],v['HLS_record_sha256'],'archived DB exact terminal HLS record')
  assert not (root/db).exists(),db
  actual={}
  member_root=v.get('archive_member_root','db')
  with tarfile.open(root/v['archive'],'r:gz')as t:
   for member in t.getmembers():
    assert not member.issym()and not member.islnk()
    if member.isfile():
     assert member.name.startswith(member_root+'/')and '..'not in Path(member.name).parts
     actual[member.name[len(member_root)+1:]]=hashlib.sha256(t.extractfile(member).read()).hexdigest()
  assert actual==am[db]['sha256'],db
  if v.get('original049_checkpoint_exact_members_verified',0):
   prior_members={n[len(db)+1:]:h for n,h in old_wire.items()if n.startswith(db+'/')}
   assert prior_members==actual and len(actual)==543,db
   old_logical_members+=len(actual)
  archived_members+=len(actual)
 for f in [am_path,str(archive_record.relative_to(root))]:hashes[f]=sha(root/f)
assert archived_members>=2258 and old_logical_members==543
current_names=['rdma/rnic/hls/owned_wire_rx_profile.py','rdma/rnic/rtl/rocev2_owned_wire_rx.v',
 'rdma/rnic/tests/probe_owned_wire_rx.py','rdma/rnic/tests/probe_owned_wire_rx_xsim.py',
 'rdma/rnic/tests/owned_wire_rx_tb.v','rdma/rnic/tests/probe_owned_wire_rx_control_xsim.py',
 'rdma/rnic/tests/owned_wire_rx_control_tb.v','rdma/rnic/tests/test_owned_wire_rx_derivation.py',
 'rdma/rnic/tests/probe_owned_wire_rx_keep.py',
 'docs/ROCEV2_OWNED_WIRE_RX.md','docs/ROCEV2_RNIC_PROGRESS.md','docs/ROCEV2_SHARED_HLS.md','docs/ROCEV2_RX_OWNER_LOOKUP.md']
for f in current_names:hashes[f]=sha(root/f)
assert not errors,errors


self_file=Path(__file__).resolve()
assert sha(self_file)==self_sha_started,'audit source changed while running'
hashes[str(self_file.relative_to(root))]=sha(self_file)
small={n:{k:v for k,v in r.items()if k not in ['source_sha256','frozen_source_sha256','generated_sha256','artifact_sha256','compiled_snapshot_sha256','generated_modules','tests']}for n,r in out.items()}
result=dict(scope=__doc__,pass_test=True,terminal_exit_status=0,parent_progress=str(args.parent_progress.relative_to(root)),
 parent_progress_sha256=sha(args.parent_progress),records=small,verified_unique_files=len(cache),verification_counts=counts,errors=errors,
 retained_failed_records=[n for n,r in out.items()if not r.get('pass_test',False)],
 historical_source_aliases=sources,archived_temporary_DB_files_verified=archived_members,previous049_logical_DB_file_SHA_verified=old_logical_members,
 artifact_sha256=hashes,hardware_verified=False,native_or_physical_proof=False,goal_completion_proof=False)
with args.report.open('x')as report:report.write(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(record=str(args.report.relative_to(root)),sha256=hashlib.sha256(args.report.read_bytes()).hexdigest(),
 pass_test=True,records=len(records),physical_files=len(cache),archive_members=archived_members,
 previous049_logical_DB_members=old_logical_members,retained_failed_records=result['retained_failed_records'],errors=errors,goal_completion_proof=False)))
