#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Prepare separate mechanically patched native sources, never a release.

Exact immutable input hashes are mandatory. The patch is applied only to new
copies in a newly created directory. Never writes the pinned parents, old
application, configuration, index, running FPGA, network or kernel state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
PATCH=Path(__file__).with_name('native-integration.patch')
INPUTS={
    'mqnic_core.v':('external/corundum/fpga/common/rtl/mqnic_core.v','655cbf64fdf6b49caf305488880cd85e53250d86d47ba91666fde037eb1d0275'),
    'mqnic_core_pcie.v':('external/corundum/fpga/common/rtl/mqnic_core_pcie.v','3380da8e7e584096416b7663ea25e77f349ce63db740b1ea997aa886ac1cd848'),
    'mqnic_app_block.v':('rdma/read/fpga/mqnic_app_block.v','93d62ddd343e712e89c47cba2615eb7debcca7636019a487c771ecb4d4d86b25'),
    'config_25g.tcl':('fpga/config_25g.tcl','6125aea101659836701591c892c68b734d1897136418e8b81074f833c9f50d83'),
}


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare(output):
    if output.exists():raise ValueError('refuse to overwrite any existing native directory')
    # Do not let a later edited patch escape the four newly copied targets.
    headers=[line for line in PATCH.read_text().splitlines() if line.startswith(('--- ','+++ '))]
    expected={prefix+name for name in INPUTS for prefix in ['--- a/','+++ b/']}
    if len(headers)!=len(expected) or set(headers)!=expected:
        raise ValueError('patch target set differs from the four native copies')
    for name,(source,expected) in INPUTS.items():
        if digest(ROOT/source)!=expected:raise ValueError('changed immutable source: '+source)
    before={str(p.relative_to(ROOT)):digest(p) for p in [PATCH,Path(__file__).resolve()]}
    output.mkdir(parents=True)
    for name,(source,expected) in INPUTS.items():shutil.copy2(ROOT/source,output/name)
    # GNU patch interprets these known four paths relative to the copy even
    # when it is inside another Git repository. Never select the Git index.
    for dry in [['--dry-run'],[]]:
        result=subprocess.run(['patch','--batch','--fuzz=0','-p1',*dry,'-i',str(PATCH)],
                              cwd=output,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    for name,(source,expected) in INPUTS.items():
        if digest(ROOT/source)!=expected:raise ValueError('original source changed during preparation')
    if before!={str(p.relative_to(ROOT)):digest(p) for p in [PATCH,Path(__file__).resolve()]}:
        raise ValueError('profile changed during preparation')
    hashes={name:digest(output/name) for name in INPUTS}
    report=dict(scope='Mechanically patched separate native candidate, not build/physical/runtime verification',
        pass_test=True,hardware_verified=False,board_built=False,programming_authorized=False,
        source_sha256={source:expected for source,expected in INPUTS.values()},profile_sha256=before,
        generated_sha256=hashes,output_directory=str(output.resolve()),
        required_profile=dict(APP_ID='0x41534e31',APP_ENABLE=1,APP_DMA_ENABLE=1,DMA_TAG_WIDTH=19,
                              app_DMA_TAG_WIDTH=16,TX_SEQ_NUM_ENABLE=1),
        needs_parent_guard_source='rdma/rnic/rtl/rocev2_pcie_parent_guard.v',
        limitations=['No full board compile/route/CDC/physical proof yet.',
                     'No global reset/epoch/hot-unplug memory-release certificate.',
                     'Parent fatal diagnosis/recovery must also reach the runtime driver.'])
    with (output/'native-profile.json').open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output.resolve()),indent=2))


if __name__=='__main__':main()
