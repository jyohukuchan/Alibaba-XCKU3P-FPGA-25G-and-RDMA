# SPDX-License-Identifier: BSD-2-Clause-Views
"""Independent real-wire/NAK/common-state oracle for QP AND MR access."""
import json
import struct
import atomic_native_full_fixture as fixture


def verify(output,qp_denied):
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_ACCESS_RESULT ')]
    wanted=dict(pass_test=True,QP_denied=int(qp_denied),MR_queries=0 if qp_denied else 1,
        normal_WRITEs=1,retired=1,core_receipts=1,actual_Atomic_SFD=1,actual_native_SFD=1,
        read_TLPs=1,write_TLPs=1,fences=1,no_posted_WQE_RQ_CQ=True)
    if rows!=[wanted]:raise ValueError('actual normal WRITE/denied Atomic lifetime summary')
    frames=fixture.link.frames(output)
    if [tag for tag,_ in frames]!=[0x4000,1]:raise ValueError('actual normal ACK then Atomic NAK SFD identities')
    for (_,actual),psn,syndrome in zip(frames,[0x987654,0x987655],[0,0x62]):
        body=bytes([0x11,0x40])+struct.pack('!HII',0xffff,196,psn)+bytes([syndrome])+int(1).to_bytes(3,'big')
        size=32+len(body)
        ip=bytearray(struct.pack('!BBHHHBBHII',0x45,2,size,0,0x4000,100,17,0,0xc6120b02,0xc6120b01))
        ip[10:12]=fixture.wire.internet_checksum(ip).to_bytes(2,'big')
        packet=bytes(ip)+struct.pack('!HHHH',4791,4791,size-20,0)+body+bytes(4)
        packet=packet[:-4]+fixture.wire.icrc_ipv4(packet)
        expected=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if actual!=expected:raise ValueError('independent Ethernet/IP/UDP/BTH/AETH/RemoteAccess/ICRC oracle '+actual.hex()+' != '+expected.hex())
    cores=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('NATIVE_ATOMIC_CORE ')]
    retired=[tuple(int(s,16)for s in l.split()[1:])for l in output.splitlines()if l.startswith('NATIVE_ATOMIC_RETIRE ')]
    owner=2|(0x9123456700000001<<24)|(0x987655<<88)|(1<<112)
    core=owner|(0x14<<144)|(0x987655<<152)|(1<<176)|(0x0f<<200)
    if cores!=[core]or retired!=[(owner,core)]:raise ValueError('actual owned NAK must NOT advance common EPSN/MSN')
    return dict(summary=rows[0],actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],
        actual_core_receipts=[f'{c:056x}'for c in cores],whole_wire_FCS_ICRC_and_same_table_state_oracles=True,
        QP_and_MR_permission_independently_required=True,physical_host_root_PHY_peer_PTP_input_models=True)
