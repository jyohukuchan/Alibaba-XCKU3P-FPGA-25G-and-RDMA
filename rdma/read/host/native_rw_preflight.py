#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only native25 path audit for the version2 RW application.

Reuse the frozen PCI/netdev/GID/FEC audit, not its version1 BAR interpretation.
No QPs, packets, RAM reads, configuration writes, resets, or programming.
"""
import argparse
import datetime
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import subprocess
import sys

import fpga_rw_client as client
import native_preflight as legacy

ROLES=legacy.ROLES
require=legacy.require


def read_application(device):
    require(sys.byteorder=='little' and os.uname().machine=='x86_64','BAR read is audited for this host only')
    fd=os.open(device / 'resource2',os.O_RDONLY|os.O_SYNC|os.O_CLOEXEC)
    try:
        aperture=os.fstat(fd).st_size
        require(aperture>=4096,'BAR2 lacks application registers')
        with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ) as mapping:
            def word(offset):return struct.unpack_from('<I',mapping,offset)[0]
            values=dict(id=word(0),version=word(4),aperture_bytes=aperture)
            # Never probe version2-specific offsets of an unknown application.
            if values['id']==0x524F4332 and values['version']==0x20000:
                values.update(status=word(12),mode=word(client.MODE),capacity=word(client.CAPACITY_REG),
                    ram_base=word(client.RAM_BASE_REG),run_id=word(client.RUN_ID),capture_state=word(client.CAPTURE_STATE))
            return values
    finally:os.close(fd)


def audit(snapshot,require_application=False):
    # Delegate ONLY the network/provider audit. The legacy BAR interpreter
    # assumes version1 status was read; our reader intentionally stops after
    # ID/version for ANY non-v2 image and must not accidentally invoke it.
    network_snapshot=dict(snapshot)
    network_snapshot['application']=dict(bar2_present=snapshot['application']['bar2_present'],registers_read=False)
    result=legacy.audit(network_snapshot,require_application=False)
    app=dict(snapshot['application']);app.update(supported=None,quiescent=None,generation_available=None)
    if app['registers_read']:
        app['supported']=app.get('id')==0x524F4332 and app.get('version')==0x20000 and \
            app.get('aperture_bytes',0)>=client.MMIO_BYTES and app.get('capacity')==client.CAPACITY and \
            app.get('ram_base')==client.RAM_BASE
        app['generation_available']=app.get('run_id',0xFFFFFFFF)<0xFFFFFFFF
        if app['supported']:
            status=app['status'];state=client.common.state(status)
            shape=state==0 and status&(client.common.DONE|client.common.FAILED)==0 or \
                state==7 and status&(client.common.DONE|client.common.FAILED)==client.common.DONE or \
                state==8 and status&(client.common.DONE|client.common.FAILED)==client.common.FAILED
            app['quiescent']=bool(client.common.safe_terminal(status) and shape and app.get('mode') in (0,1) and
                bool(status&0x80)==bool(app['mode']) and app.get('capture_state',0)&4)
        else:app['quiescent']=False
    if require_application:
        require(app['bar2_present'] and app['registers_read'] and app['supported'] and app['quiescent'] and
            app['generation_available'],'version2 RW BAR/quiescence/generation proof required; no QP/test started')
    result['application']=app
    return result


def collect(sysfs=Path('/sys'),run=legacy.run_command,read_app=False):
    observations=legacy.collect(sysfs=sysfs,run=run,read_app=False)
    app=observations['application']
    if read_app and app['bar2_present']:
        device=sysfs / 'bus/pci/devices' / ROLES['fpga']['bdf']
        app.update(read_application(device),registers_read=True)
    return observations


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-application',action='store_true')
    parser.add_argument('--require-application',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.report:require(not args.report.exists(),'preserve prior audit evidence')
    result=dict(event='native_rw_preflight',success=False,traffic_generated=False,rdma_qp_created=False,
        hardware_configuration_modified=False,fpga_programmed=False,hardware_rdma_verified=False,
        timing_verified=False,temperature_checked=False,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_sha256={str(p.relative_to(client.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (Path(__file__),Path(legacy.__file__),Path(client.__file__))})
    try:
        observations=collect(read_app=args.read_application or args.require_application)
        result['observations']=observations;result.update(audit(observations,args.require_application))
    except (legacy.PreflightError,OSError,ValueError,KeyError,subprocess.SubprocessError) as error:result['error']=str(error)
    print(json.dumps(result,indent=2))
    if args.report:
        with args.report.open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
    return 0 if result['success'] else 1


if __name__=='__main__':sys.exit(main())
