#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actual patched PCIe parent/core/app/native endpoint hierarchy.

Not functional simulation, physical timing, hardware, pinning or RDMA proof.
No parent/core/datapath stubs. Icarus only, no device programming.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--mac-tag-width',type=int,choices=[16,6],default=16,
                        help='board top explicitly overrides the core default6 with16')
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve previous evidence')
    profile=args.profile.resolve();manifest=json.loads((profile/'native-profile.json').read_text())
    for name,value in manifest['generated_sha256'].items():
        if digest(profile/name)!=value:raise ValueError('changed prepared source: '+name)
    rtl=args.hls_build.resolve()/'solution1/syn/verilog'
    sources=[profile/name for name in ['mqnic_core_pcie.v','mqnic_core.v','mqnic_app_block.v']]
    # Pinned board Makefile selects this round-robin implementation; its
    # module name deliberately differs from its filename, so -y is not enough.
    sources.append(ROOT/'external/corundum/fpga/common/rtl/mqnic_tx_scheduler_block_rr.v')
    sources+=sorted((ROOT/'rdma/rnic/rtl').glob('*.v'))
    sources+=sorted((ROOT/'rdma/read/rtl').glob('*.v'))
    sources+=sorted((ROOT/'rdma/rtl').glob('*.v'))
    sources+=sorted(rtl.glob('*.v'))
    library=[ROOT/'external/corundum/fpga/common/rtl']
    library+=[ROOT/'external/corundum/fpga/lib'/name/'rtl' for name in ['pcie','axi','axis','eth']]
    dependencies=sorted({p for directory in library for p in directory.glob('*.v')})
    before={str(p):digest(p) for p in [*sources,*dependencies,Path(__file__).resolve()]}
    params=dict(IF_COUNT=2,PORTS_PER_IF=1,APP_ID="32'h41534e31",APP_ENABLE=1,
        APP_CTRL_ENABLE=1,APP_DMA_ENABLE=1,APP_AXIS_DIRECT_ENABLE=0,APP_AXIS_SYNC_ENABLE=1,
        APP_AXIS_IF_ENABLE=0,APP_STAT_ENABLE=0,DMA_TAG_WIDTH=19,TX_SEQ_NUM_ENABLE=1,
        RAM_ADDR_WIDTH=15,TX_TAG_WIDTH=args.mac_tag_width,AXIS_DATA_WIDTH=64,AXIS_SYNC_DATA_WIDTH=128,
        AXIL_APP_CTRL_ADDR_WIDTH=24)
    command=['iverilog','-g2012','-s','mqnic_core_pcie']
    for k,v in params.items():command+=['-P',f'mqnic_core_pcie.{k}={v}']
    for directory in library:command+=['-y',str(directory)]
    with tempfile.TemporaryDirectory(prefix='as02-native-parent-compile-') as directory:
        result=subprocess.run([*command,'-o',str(Path(directory)/'parent.vvp'),*map(str,sources)],
                              capture_output=True,text=True,timeout=90)
    if before!={str(p):digest(p) for p in [*sources,*dependencies,Path(__file__).resolve()]}:
        raise ValueError('elaboration inputs changed')
    report=dict(scope=__doc__,pass_test=result.returncode==0,terminal_exit_status=result.returncode,
        hardware_verified=False,functional_simulation=False,physical_timing_pass=False,
        actual_patched_parent_core_app_elaborated=result.returncode==0,parameter_values=params,
        compiler_stdout=result.stdout,compiler_stderr=result.stderr,
        source_sha256={str(Path(k).relative_to(ROOT)):v for k,v in before.items()},
        profile_manifest_sha256=digest(profile/'native-profile.json'))
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2),flush=True)
    if result.returncode:raise SystemExit(1)


if __name__=='__main__':main()
