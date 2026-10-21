#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Build a checked extension of the exact27-case native runner, adding large WRs.

Freeze the derived runner; retain every prior oracle, unchanged1200s build/
30s case deadline, actual HLS and both global drains0. No hardware access.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_executor_native_full as parent
import segmented_wire_native_fixture as fixture

ROOT=fixture.ROOT;once=fixture.once


def runner_source():
    t=Path(parent.__file__).read_text();start=t.index('"""');end=t.index('"""',start+3)+3
    t=t[:start]+'''"""Actual coordinated large-wire graph:8193 WRITE/SEND plus all27 prior cases.

One actual generated HLS/MR/PTE/DMA/physical-nonce/source/MAC/CQ graph.
Physical host/root/peer/PHY/PTP endpoints modeled. All29 runtimes<=30s;
build<=1200s, original global drains0. Not Linux/hardware/timing signoff.
"""'''+t[end:]
    t=once(t,'import segmented_executor_native_sources as source','import segmented_wire_native_sources as source')
    t=once(t,'import segmented_executor_native_fixture as service','import segmented_wire_native_fixture as service')
    start=t.index("    if (evidence.get('zero_service_owner_bits')")
    end=t.index("    for n,h in evidence['source_sha256'].items():",start)
    t=t[:start]+'''    if not all(evidence.get(n)for n in ['large_native_admission','large_source_DMA_wired',
        'atomic_CQ_retirement_fanout','per_packet_lifetime_and_cache_advance_wired'])or any(
        evidence.get('module_counts',{}).get(n)!=1 for n in ['rocev2_segmented_executor_mux',
        'rocev2_segmented_source_executor','rocev2_segmented_child_executor','rocev2_memory_command_nonce',
        'rocev2_zero_service_owner','rocev2_zero_service_mac']):
        raise ValueError('matched complete coordinated large/source/CQ/HLS/nonce graph required')
'''+t[end:]
    t=t.replace("prefix='segmented-executor-native-full-'","prefix='segmented-wire-native-full-'")
    t=once(t,"prefix='as02-zero-native-obj-'","prefix='as02-segmented-wire-obj-'")
    t=once(t,"prefix='as02-zero-native-artifacts-'","prefix='as02-segmented-wire-artifacts-'")
    t=once(t,'actual_shared_physical_command_nonce=True,large_native_admission=False',
        'actual_shared_physical_command_nonce=True,large_native_admission=True')
    t=once(t,'large_native_wire_CQ=False,planned_cases=27',
        'large_native_wire_CQ=False,planned_cases=29,large_source_runtime_verified=False')
    t=once(t,'[*src,*fixture.link.SOURCES]', '[*src,*fixture.link.SOURCES,*service.BOARD_TX_SOURCES]')
    t=once(t,"'wqe_zero.c','wqe_zero.h']]]","'wqe_zero.c','wqe_zero.h','wqe_segmented.c','wqe_segmented.h']],service.CODEC_REPORT]")
    t=once(t,'service.CODEC_REPORT]', 'service.CODEC_REPORT,service.BOARD_FIFO_REPORT,service.PCIE_REQUEST_REPORT,*service.BOARD_FIFO_INPUTS]')
    t=once(t,"report['source_sha256']=before", "report['source_sha256']=before;report['actual_board_TX_FIFO_parameters']=service.board.parameters()")
    t=once(t,"        cases=[('WRITE',1,0,['+WRITE'],False,None),",
        "        cases=[('LARGE_WRITE',1,0,['+WRITE','+SEGMENTED'],False,None),\n"
        "            ('LARGE_SEND',3,0,['+SEND','+SEGMENTED'],False,None),\n"
        "            ('WRITE',1,0,['+WRITE'],False,None),")
    t=once(t,"if len(cases)!=27:raise ValueError('all25 prior cases plus ordinary WRITE/SEND required')",
        "if len(cases)!=29:raise ValueError('all27 prior cases plus actual8193 WRITE/SEND required')")
    t=once(t,'            words,records,request=fixture.old.variant(opcode,immediate,zero)if capacity is None else fixture.old.variant(2,0,False)',
        "            is_large=name.startswith('LARGE_')\n"
        '            if is_large:words,records,request,large_acks=service.large_variant(opcode)\n'
        '            else:words,records,request=fixture.old.variant(opcode,immediate,zero)if capacity is None else fixture.old.variant(2,0,False)')
    t=once(t,'            if capacity is not None and capacity>=0:\n                rx_words,rx_records,packets=',
        "            if is_large:inputs['large-acks.hex']=''.join(f'{w:037x}\\n'for w in large_acks)\n"
        '            if capacity is not None and capacity>=0:\n                rx_words,rx_records,packets=')
    t=once(t,'result.update(service.verify(output,opcode,run)if capacity==-1 else',
        'result.update(service.verify_large(output,records,request,opcode,run)if is_large else\n'
        '                service.verify(output,opcode,run)if capacity==-1 else')
    t=once(t,"            result['actual_source_and_atomic_CQ']=service.verify_executor(output,name,request,\n                result.get('full748_bit_CQ_owner'))",
        "            if not is_large:result['actual_source_and_atomic_CQ']=service.verify_executor(output,name,request,\n"
        "                result.get('full748_bit_CQ_owner'))")
    t=once(t,'ordinary_zero_service_runtime_verified=True,ordinary_source_runtime_verified=True)',
        'ordinary_zero_service_runtime_verified=True,ordinary_source_runtime_verified=True,\n'
        '            large_source_runtime_verified=True,large_native_wire_CQ=True)')
    ast.parse(t)
    return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-wire-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    # The original __main__ remains the generator, so its bytes are captured
    # by the runner's normal helper inventory as well as the frozen program.
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
