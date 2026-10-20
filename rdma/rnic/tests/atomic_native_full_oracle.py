# SPDX-License-Identifier: BSD-2-Clause-Views
"""Independent whole-wire/common-state oracle for mixed full-native Atomic."""
import json
import struct
import atomic_native_full_fixture as fixture


def verify(output):
    rows=[json.loads(line.split(' ',1)[1])for line in output.splitlines()if line.startswith('NATIVE_ATOMIC_RESULT ')]
    if len(rows)!=1:raise ValueError('missing/duplicate actual native Atomic summary')
    summary=rows[0]
    expected=dict(pass_test=True,Atomic_requests=3,normal_WRITEs=1,retired=3,core_receipts=3,
        actual_Atomic_SFD=3,actual_native_SFD=1,read_TLPs=5,write_TLPs=3,fences=3,
        no_posted_WQE_RQ_CQ=True,Atomic_MAC_receipt_model=False,physical_host_PHY_peer_PTP_input_models=True)
    if summary!=expected:raise ValueError('actual native memory/core/MAC proof incomplete')
    frames=fixture.link.frames(output)
    if [t for t,_ in frames]!=[1,2,0x4000,3]:raise ValueError('actual Atomic/native SFD order/identity')
    cases=[(0x12,0x987654,1,fixture.FIRST_OLD),(0x12,0x987654,1,fixture.FIRST_OLD),
        (0x11,0x987655,2,None),(0x12,0x987656,3,fixture.FIRST_OLD+1)]
    for (_,actual),(op,psn,msn,value)in zip(frames,cases):
        # Original shared HLS fixed IPv4/UDP/BTH/AETH serialization. Build
        # independently from expected semantics, not by repairing DUT bytes.
        body=bytes([op,0x40])+struct.pack('!HII',0xffff,196,psn)+bytes([0x1f if op==0x12 else 0x00])+msn.to_bytes(3,'big')
        if value is not None:body+=struct.pack('!Q',value)
        size=32+len(body)
        ip=bytearray(struct.pack('!BBHHHBBHII',0x45,2,size,0,0x4000,100,17,0,0xc6120b02,0xc6120b01))
        ip[10:12]=fixture.wire.internet_checksum(ip).to_bytes(2,'big')
        packet=bytes(ip)+struct.pack('!HHHH',4791,4791,size-20,0)+body+bytes(4)
        packet=packet[:-4]+fixture.wire.icrc_ipv4(packet)
        wanted=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if actual!=wanted:raise ValueError('independent full Ethernet/IPv4/UDP/BTH/AETH/Atomic/ICRC mismatch '+actual.hex()+' != '+wanted.hex())
    cores=[int(line.split()[1],16)for line in output.splitlines()if line.startswith('NATIVE_ATOMIC_CORE ')]
    retired=[tuple(int(s,16)for s in line.split()[1:])for line in output.splitlines()if line.startswith('NATIVE_ATOMIC_RETIRE ')]
    if len(cores)!=3 or len(retired)!=3:raise ValueError('missing/extra actual core/retirement receipt')
    for i,(core,(owner,retire))in enumerate(zip(cores,retired)):
        psn=[0x987654,0x987654,0x987656][i];epsn=[0x987655,0x987655,0x987657][i];msn=[1,1,3][i]
        wanted_owner=2|(0x9123456700000001<<24)|(psn<<88)|((i+1)<<112)
        wanted=wanted_owner|(0x14<<144)|(epsn<<152)|(msn<<176)|([0x1f,0x0f,0x1f][i]<<200)
        if core!=wanted or owner!=wanted_owner or retire!=wanted:raise ValueError('immutable owner/common EPSN/MSN/core/retirement mismatch')
    return dict(summary=summary,actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],
        actual_core_receipts=[f'{c:056x}'for c in cores],whole_wire_FCS_ICRC_and_same_table_state_oracles=True,
        actual_SQC_lease_denial=True,physical_host_root_PHY_peer_PTP_input_models=True)
