#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""NEW per-WR transport delivery profile: exact HLS copies + explicit SQ adapter.

Only a NEW copy of the original integrity bridge's SQ interface is derived.
No generated HLS logic/headers/data are changed. Legacy named ports/hierarchy
stay intact; native mode takes a separate full32-bit key, including key0.
Preparation is NOT functional/physical/board/native/verbs qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT/'rdma/rtl/rocev2_integrity_transport.v'
ADAPTER = ROOT/'rdma/rnic/rtl/rocev2_wrkey_sq_adapter.v'
TARGETS = {'hls/ib_transport_protocol/ib_transport_protocol.hpp',
           'hls/ib_transport_protocol/ib_transport_protocol.cpp',
           'hls/ib_transport_protocol/retransmitter/retransmitter.hpp'}


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(ok, message):
    if not ok: raise ValueError(message)


def verify_hashes(values, base):
    for name, value in values.items():
        require(digest(base/name) == value, 'input hash mismatch: '+str(base/name))


def aggregate(directory):
    value = hashlib.sha256()
    files = sorted([*directory.glob('*.v'), *directory.glob('*.dat')])
    for p in files: value.update(p.name.encode()+b'\0'+p.read_bytes())
    return value.hexdigest(), files


def derive_bridge(text):
    """Exact interface-only transformation, never heuristic RTL repair."""
    changes = [
        ('module rocev2_integrity_transport (',
         'module rocev2_integrity_transport #(parameter LEGACY_QP_KEY = 1) ('),
        ('    input wire [239:0] s_axis_sq_tdata,',
         '    input wire [239:0] s_axis_sq_tdata,\n    input wire [31:0] s_axis_sq_rkey,'),
        ('rocev2_top transport (', '''wire [247:0] keyed_sq_data;
wire keyed_sq_valid, keyed_sq_ready;
rocev2_wrkey_sq_adapter #(.LEGACY_QP_KEY(LEGACY_QP_KEY)) sq_key_adapter (
    .s_axis_sq_tdata(s_axis_sq_tdata), .s_axis_rkey(s_axis_sq_rkey),
    .s_axis_sq_tvalid(s_axis_sq_tvalid), .s_axis_sq_tready(s_axis_sq_tready),
    .m_axis_sq_tdata(keyed_sq_data), .m_axis_sq_tvalid(keyed_sq_valid),
    .m_axis_sq_tready(keyed_sq_ready)
);

rocev2_top transport ('''),
        ('.s_axis_sq_meta_TDATA(s_axis_sq_tdata), .s_axis_sq_meta_TVALID(s_axis_sq_tvalid), .s_axis_sq_meta_TREADY(s_axis_sq_tready),',
         '.s_axis_sq_meta_TDATA(keyed_sq_data), .s_axis_sq_meta_TVALID(keyed_sq_valid), .s_axis_sq_meta_TREADY(keyed_sq_ready),'),
    ]
    for old, new in changes:
        require(text.count(old) == 1, 'unreviewed original SQ bridge interface: '+old)
        text = text.replace(old, new, 1)
    return text


def validate(records):
    source, hls, table, ctor = records
    require(source.get('source_freeze_prepared') and source.get('upstream_commit') ==
            '75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c', 'wrong source candidate')
    original, patched = source['source_sha256'], source['patched_source_sha256']
    require(set(original) == set(patched) and
            {n for n in original if original[n] != patched[n]} == TARGETS,
            'unreviewed per-WR source change set')
    require(source['metadata_entries'] == 2000 and source['metadata_fields'] == 13,
            'reduced metadata capacity/context')
    require(hls.get('pass_test') and hls.get('terminal_exit_status') == 0 and
            hls.get('SQ_AXIS_width_248_verified') and
            hls.get('source_and_frozen_inputs_unchanged') and
            hls['hls_build'] == source['hls_build'], 'unverified HLS candidate')
    require(table.get('pass_test') and table.get('four_state_simulation') is True and
            table.get('inputs_unchanged') and table.get('metadata_fields') == 13 and
            table.get('metadata_entries') == 2000 and table.get('sequential_initialization_required') and
            table.get('original_testbench_assertions_and_deadlines_preserved') and
            [table.get(k) for k in ['checks','zero_checks','data_checks','append_checks','reset_checks']] ==
            [8024,4023,2000,2001,16], 'incomplete four-state metadata reset evidence')
    require(ctor.get('characterization_pass') and ctor.get('release_reset_gate_pass') and
            ctor.get('total_observations') == 88 and ctor.get('invalid_observations') == 0 and
            len(ctor.get('observations', [])) == 88 and
            all(o.get('valid') for o in ctor['observations']), 'incomplete constructor evidence')
    require(table['generated_hls_sha256'] == ctor['generated_hls_sha256'] ==
            hls['generated_hls_sha256'], 'mixed generated candidates')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-record','hls-record','table-record','constructor-record','output']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(not output.exists(), 'never overwrite an existing delivery profile')
    paths = [args.source_record.resolve(), args.hls_record.resolve(),
             args.table_record.resolve(), args.constructor_record.resolve()]
    records = [json.loads(p.read_text()) for p in paths]
    validate(records)
    source, hls, table, ctor = records
    project = Path(source['hls_build'])
    raw = project/'solution1/syn/verilog'
    raw_hash, files = aggregate(raw)
    require(raw_hash == hls['generated_hls_sha256'] and len(files) == hls['generated_files'] == 138,
            'generated HLS changed/missing files')
    require(re.search(r'input\s+\[247:0\]\s+s_axis_sq_meta_TDATA;',
                      (raw/'rocev2_top.v').read_text()), 'unreviewed actual SQ port')
    input_files = [*paths, Path(__file__).resolve(), BRIDGE, ADAPTER]
    inputs = {str(p.relative_to(ROOT)):digest(p) for p in input_files}
    def current():
        verify_hashes(inputs, ROOT)
        verify_hashes(source['source_sha256'], Path(source['source_directory']))
        verify_hashes(source['profile_sha256'], ROOT)
        verify_hashes(source['frozen_sha256'], project.parent/'inputs')
        verify_hashes(hls['source_sha256'], ROOT)
        verify_hashes(table['source_sha256'], ROOT)
        verify_hashes(ctor['source_sha256'], ROOT)
        verify_hashes(table['selected_RTL_sha256'], raw)
        require(digest(raw/'rocev2_top_ipv4_generate_ipv4_512_s.v') == ctor['selected_module_sha256'],
                'constructor RTL changed')
        require(aggregate(raw)[0] == raw_hash, 'raw HLS changed')
    current()
    derived = derive_bridge(BRIDGE.read_text())
    destination = output/'solution1/syn/verilog'
    destination.mkdir(parents=True)
    copied = {}
    for p in files:
        shutil.copy2(p, destination/p.name)
        copied[p.name] = digest(p)
        require(digest(destination/p.name) == copied[p.name], 'source changed during copy')
    (destination/'rocev2_integrity_transport_wrkey.v').write_text(derived)
    shutil.copy2(ADAPTER, destination/ADAPTER.name)
    current()
    verify_hashes(copied, destination)
    delivery_hash, delivered = aggregate(destination)
    record = dict(scope=__doc__, profile='per-wr-key-context-v1', source_sha256=inputs,
        original_generated_HLS_sha256=raw_hash, original_generated_files=len(files),
        copied_raw_sha256=copied, generated_sha256={p.name:digest(p) for p in delivered},
        delivery_sha256=delivery_hash, delivery_files=len(delivered),
        output_directory=str(output), source_frozen_before_compile=True,
        original_sources_and_generated_RTL_unchanged=True,
        legacy_default_mode=1, explicit_key_mode=0, SQ_interface_transformation_only=True,
        source_profile=str(paths[0]), hls_record=str(paths[1]),
        reset_record=str(paths[2]), constructor_record=str(paths[3]),
        pass_test=False, prepared=True, hardware_verified=False, full_wire_verified=False,
        board_built=False, physical_signoff=False, release_authorized=False)
    with (output/'wrkey-delivery.json').open('x') as out:
        out.write(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if not k.endswith('sha256')}, indent=2))


if __name__ == '__main__':
    main()
