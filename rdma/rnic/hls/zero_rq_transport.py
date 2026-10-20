#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""RQ-owned zero SEND/Immediate in the SAME complete zero-requester core.

Real RX/BTH/EXH/empty EOF, ACK/MSN and common PSN receipts are mandatory;
no zero command/data write, invented RQ or absent-payload completion. Posted
zero buffers have canonical no-local-memory fields. A nonzero posted buffer
may receive zero bytes while retaining its owner. Incoming normal zero
WRITE/READ (which MUST NOT consume a fake RQ) are separate pending work.
SOURCE candidate only: no native/RQ/CQ/Linux/hardware/timing qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zero_request_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
once=base.once;change=base.change;NAME='rocev2_native_zero_rq_top'


def derive():
    out=base.derive()
    out[HPP]=change(out[HPP],'inline bool as02_recv_owner_valid(',lambda t:once(once(t,
        'n(307,276)!=0 && n(307,276)<=4096',
        'n(307,276)<=4096 && (n(307,276)!=0 || n(275,116)==0)'),
        'o.length!=0 && o.length<=4096', 'o.length<=4096'))
    out[HPP]=change(out[HPP],'struct pkgShift\n{',lambda t:once(t,
        'bool zero_read=false;', 'bool zero_receive=false;\n    bool zero_read=false;'))
    def receive(t):
        t=once(t,'            memoryWriteCmd.write(as02_duplex_command(c,false));',
            '            if(o.length!=0)memoryWriteCmd.write(as02_duplex_command(c,false));')
        t=once(t,'            memoryWriteCmd.write(as02_duplex_command(memCmd(0,wire_length,PKG_F,PKG_INT,meta.dest_qp),meta.request_owned));',
            '            if(o.length!=0)memoryWriteCmd.write(as02_duplex_command(memCmd(0,wire_length,PKG_F,PKG_INT,meta.dest_qp),meta.request_owned));')
        anchor='pkgShift s(SHIFT_NONE,meta.dest_qp);s.receive_owned=true;s.receive=p;'
        if t.count(anchor)!=2:raise ValueError('both actual RQ receive producers required')
        return t.replace(anchor,anchor+'s.zero_receive=o.length==0;')
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',receive)
    def merge(t):
        t=once(t,'ZERO_READ, QUARANTINE};','ZERO_READ, QUARANTINE, ZERO_RECEIVE};')
        t=once(t,'if(shift.zero_read)state=ZERO_READ;',
            'if(shift.zero_receive)state=ZERO_RECEIVE;\n            else if(shift.zero_read)state=ZERO_READ;')
        return once(t,'    case ZERO_READ:',r'''
    case ZERO_RECEIVE:
        if(!rx_NoSift2mergerFifo.empty()) {
            // This is the EOF word produced by the real received header
            // stripping, NEVER an empty-FIFO/quiet-interface certificate.
            auto w=rx_NoSift2mergerFifo.read();
            if(!shift.receive_owned || shift.request_owned || shift.receive.owner.length!=0 ||
               !as02_recv_owner_valid(shift.receive.owner,shift.receive.flags==3) ||
               w.keep!=0 || !w.last) {
                fault=true;regRequestPayloadFault=1;state=QUARANTINE;
            } else state=RECV_DONE;
        }
        break;
    case ZERO_READ:''')
    out[CPP]=change(out[CPP],'void merge_rx_pkgs(',merge)
    out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    original=base.base.parent.qp.BASE
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    before={str(p.relative_to(original)):digest(p)for p in original.rglob('*')if p.is_file()}
    files=derive();shutil.copytree(original/'fns',a.output/'fns');shutil.copytree(original/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if before!={n:digest(original/n)for n in before}:raise ValueError('original changed')
    info=dict(scope=__doc__,source_base=str(original),source_sha256=before,
        generator_sha256=digest(__file__),parent_generator_sha256=digest(base.__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        HLS_top=NAME,original_unchanged=True,request_context_bits=748,SQ_bits=408,request_done_bits=816,
        receive_context_bits=620,receive_owner_bits=680,receive_done_bits=752,
        zero_length_requester=True,zero_RQ_SEND_and_Immediate=True,normal_zero_responder_WRITE_READ=False,
        shared_PSN_MSN=True,native_integration=False,hardware_verified=False,source_only=True,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,original_unchanged=True)))


if __name__=='__main__':main()
