# SPDX-License-Identifier: BSD-2-Clause-Views
"""Isolated actual-generated-HLS simulation, preserving baseline input hashes."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'rdma/read/tests'))
import rw_sim


def simulate(tb,fixtures,hls_build,wall_timeout=120):
    sources,data=rw_sim.modules(hls_build)
    sources += [ROOT/'rdma/rnic/rtl'/name for name in
                ('rocev2_mr_table.v','rocev2_protected_responder.v')]
    before=rw_sim.hashes(sources+data)
    with tempfile.TemporaryDirectory(prefix='as02-protected-responder-') as directory:
        path=Path(directory)
        (path/'tb.v').write_text(tb)
        for name,values in fixtures.items():
            (path/name).write_text(''.join(f'{value:x}\n' for value in values))
        for item in data:shutil.copy2(item,path/item.name)
        compile_result=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path/'test.vvp'),
                                       str(path/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=90)
        if compile_result.returncode:raise RuntimeError(compile_result.stdout+compile_result.stderr)
        result=subprocess.run(['vvp',str(path/'test.vvp')],cwd=path,capture_output=True,text=True,timeout=wall_timeout)
        if result.returncode or 'ERROR:' in result.stdout or 'ERROR:' in result.stderr:
            raise RuntimeError(result.stdout+result.stderr)
    if before!=rw_sim.hashes(sources+data):raise ValueError('source changed during simulation')
    rtl=hls_build.resolve()/'solution1/syn/verilog'
    generated=hashlib.sha256()
    for item in sorted([*rtl.glob('*.v'),*rtl.glob('*.dat')]):
        generated.update(item.name.encode()+b'\0'+item.read_bytes())
    return result.stdout,dict(generated_hls_sha256=generated.hexdigest(),
        generated_files=len(list(rtl.glob('*.v')))+len(data),
        source_sha256={str(item.relative_to(ROOT)):before[str(item)] for item in sources if item.is_relative_to(ROOT)})
