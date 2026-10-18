# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual combined-app RTL simulation helpers. No FPGA or network access."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]


def modules(hls_build):
    rtl=hls_build.resolve() / 'solution1/syn/verilog'
    if not (rtl / 'rocev2_top.v').is_file():raise ValueError('missing generated HLS')
    names=('rocev2_write_engine.v','rocev2_pattern_source.v','rocev2_ethernet_tx.v',
        'rocev2_ipv4_icrc.v','rocev2_tx_padding.v','rocev2_integrity_transport.v','rocev2_tx_guard.v')
    sources=sorted(rtl.glob('*.v'))+[ROOT / 'rdma/rtl' / n for n in names]
    sources += [ROOT / 'rdma/read/rtl' / n for n in ('rocev2_read_engine.v','rocev2_read_buffer.v',
        'rocev2_rw_control.v','rocev2_rw_ethernet_rx.v','rocev2_rw_endpoint.v')]
    sources.append(ROOT / 'rdma/read/fpga/mqnic_app_block.v')
    axis=ROOT / 'external/corundum/fpga/lib/axis/rtl'
    eth=ROOT / 'external/corundum/fpga/lib/eth/rtl'
    sources += [axis / n for n in ('axis_fifo.v','axis_register.v','axis_adapter.v','axis_arb_mux.v','arbiter.v','priority_encoder.v')]
    sources += [eth / n for n in ('eth_axis_rx.v','eth_axis_tx.v','lfsr.v')]
    return sources,sorted(rtl.glob('*.dat'))


def hashes(paths):
    return {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths}


def simulate(tb,fixtures,hls_build,wall_timeout=300):
    sources,data=modules(hls_build)
    before=hashes(sources+data)
    with tempfile.TemporaryDirectory(prefix='as02-rw-app-') as directory:
        path=Path(directory)
        (path / 'tb.v').write_text(tb)
        for name,values in fixtures.items():
            (path / name).write_text(''.join(f'{v:x}\n' for v in values))
        for item in data:shutil.copy2(item,path / item.name)
        compiled=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path / 'test.vvp'),
                                 str(path / 'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=90)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        sim=subprocess.run(['vvp',str(path / 'test.vvp')],cwd=path,capture_output=True,text=True,timeout=wall_timeout)
        if sim.returncode or 'ERROR:' in sim.stdout or 'ERROR:' in sim.stderr:
            raise RuntimeError(sim.stdout+sim.stderr)
    if before!=hashes(sources+data):raise ValueError('compile inputs changed while simulation was live')
    generated=hashlib.sha256()
    rtl=hls_build.resolve() / 'solution1/syn/verilog'
    for file in sorted([*rtl.glob('*.v'),*rtl.glob('*.dat')]):
        generated.update(file.name.encode()+b'\0'+file.read_bytes())
    identity={str(f.relative_to(ROOT)):before[str(f)] for f in sources if f.is_relative_to(ROOT)}
    return sim.stdout,dict(generated_hls_sha256=generated.hexdigest(),source_sha256=identity,
                           generated_files=len(list(rtl.glob('*.v')))+len(data))


def ethernet_frames(output):
    frames,frame=[],bytearray()
    for line in output.splitlines():
        if line.startswith('OUT '):
            _,data,keep,last=line.split()
            beat=int(data,16).to_bytes(16,'little')
            frame.extend(beat[i] for i in range(16) if int(keep,16)&(1<<i))
            if last=='1':frames.append(bytes(frame));frame.clear()
    if frame:raise ValueError('truncated Ethernet output')
    return frames
