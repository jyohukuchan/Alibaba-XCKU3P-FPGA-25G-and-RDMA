#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual candidate CQ semantic predicate: wide flags3 ONLY for profile8.

Compile real derived headers with UBSan, enumerate every profile/flag/length/
capacity combination, retain original profile0..7 behavior byte-exactly.
This is NOT kernel callback/ownership/native identity/live API qualification.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/kernel'))
import derive_segmented_write_kernel as candidate

C=r'''
#include <stdio.h>
#include <string.h>
#include "atomic_profile.h"
#include "cq_io.h"
int main(void){
 unsigned profiles[]={0,1,2,3,4,5,6,7,8,9,0xffffffffU};
 unsigned bytes[]={0,1,4095,4096,4097,8193,1048575,1048576,1048577,0xffffffffU};
 unsigned caps[]={0,1,4096,8194,1048576};
 struct as02_cq_decoded d;unsigned count=0;
 for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);p++)
 for(unsigned flags=0;flags<256;flags++)
 for(unsigned n=0;n<sizeof(bytes)/sizeof(*bytes);n++)
 for(unsigned c=0;c<sizeof(caps)/sizeof(*caps);c++){
  memset(&d,0,sizeof(d));d.profile=profiles[p];d.work.opcode=AS02_WQE_RECV;
  d.work.length=caps[c];d.notification_flags=flags;d.notification=flags ? 0x89abcdefU:0;
  d.received_bytes=bytes[n];printf("%u %u %u %u %d\n",profiles[p],flags,bytes[n],caps[c],as02_cq_notification_valid(&d));count++;
 }
 return count==140800 ? 0:1;
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier records')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-cq-semantics-',dir=ROOT/'rdma/rnic/build'))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_limit_seconds=30,runtime_limit_seconds=10,
        kernel_callbacks_executed=False,matched_native_identity_proved=False,hardware_verified=False,new_installed_capability=False)
    try:
        generated=candidate.derive();old=candidate.base.derive();k=run/'kernel';k.mkdir()
        for q in candidate.KERNEL.iterdir():
            if q.is_file()and q.suffix=='.h':shutil.copy2(q,k/q.name)
        for q,t in generated.items():
            if q.suffix=='.h':(k/q.name).write_text(t)
        (run/'test.c').write_text(C)
        own=[Path(__file__).resolve(),*[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(candidate.KERNEL)]]
        before={str(q.relative_to(ROOT)):digest(q)for q in [*own,*[q for q in candidate.KERNEL.iterdir()if q.is_file()and q.suffix=='.h']]}
        result['source_sha256']=before
        summary=[]
        for name,headers in [('old',old),('new',generated)]:
            for q,t in headers.items():
                if q.suffix=='.h':(k/q.name).write_text(t)
            command=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(k),str(run/'test.c'),'-o',str(run/name)]
            start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=30)
            (run/(name+'-compile.log')).write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError(name+' actual-header compile failed')
            c=subprocess.run([str(run/name)],capture_output=True,text=True,timeout=10)
            (run/(name+'-output.txt')).write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError(name+' actual-header matrix runtime failed')
            summary.append(dict(name=name,seconds=time.monotonic()-start,rows=[tuple(map(int,s.split()))for s in c.stdout.splitlines()]))
        old_rows,new_rows=summary[0]['rows'],summary[1]['rows']
        if len(old_rows)!=140800 or len(new_rows)!=140800:raise ValueError('entire CQ matrix required')
        previous=0;new_wide=0
        for old_row,row in zip(old_rows,new_rows):
            profile,flags,length,capacity,accepted=row
            if row[:4]!=old_row[:4]:raise ValueError('same full semantic inputs required')
            if profile!=8:
                if row!=old_row:raise ValueError('older/unknown profile behavior changed')
                previous+=1;continue
            # Independent policy oracle only for the distinct new profile;
            # zero-length original semantics are checked against profile7.
            if flags not in [0,1,3]:expected=0
            elif length==0:expected=old_rows[((7*256+flags)*10)*5+list([0,1,4096,8194,1048576]).index(capacity)][4]
            else:expected=int(length<=1048576 and (flags==3 or length<=capacity))
            if accepted!=expected:raise ValueError('new profile semantic oracle mismatch:'+str(row))
            if flags==3 and 4096<length<=1048576 and accepted:new_wide+=1
        if new_wide!=20:raise ValueError('all new wide notification lengths/capacities required')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,matrix_cases=140800,old_and_unknown_rows_identical=previous,
            new_wide_WRITE_rows=new_wide,old_profile7_WRITE_max_bytes=4096,new_profile8_WRITE_max_bytes=1048576)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.rglob('*')if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,matrix_cases=140800,old_profile7_unchanged=True)),flush=True)


if __name__=='__main__':main()
