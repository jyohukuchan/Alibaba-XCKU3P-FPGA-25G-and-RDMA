#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""One finite native version2 READ/WRITE case under the validated thermal guard.

No programming, RXE, fan, route/interface or NIC-reset changes. Physical review
and inspected SRAM programming are operator attestations, never inferred from
the version register or these flags. Source/MR and BAR bytes are independently
cross-checked before declaring a native READ result.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import time

import fpga_rw_client as client
import native_rw_preflight as preflight_module
import native_test as legacy

ROOT=client.ROOT
ROLES=preflight_module.ROLES
CONTROL_PORT=18516
require=legacy.require
GUARD_SHA256='dbe7a70cbc684f791c07385e0b9acc700bef353b04172eb27089668cd68562e1'
SENSOR_SHA256='7e741c725582947f724bc689fb06d93127d3c224bd050d9623b77deed7c712ab'


def validate_request(operation,size,count,psn,peer_psn,window,probe_config_error=False):
    cls=client.ReadConfig if operation=='read' else client.common.Config
    require(operation in ('read','write'),'unknown operation')
    require(not probe_config_error or operation=='read','configuration error recovery is READ only')
    args=dict(size=size,count=count,local_psn=psn)
    if operation=='read':args['read_window']=window
    cls(ROLES['fpga']['ip'],ROLES['peer']['ip'],2,4,**args).validate()
    require(0<=peer_psn<=0xFFFFFF,'peer PSN must fit24bits')


def require_authorization(environment):
    guard=legacy.require_authorization(environment)
    require(hashlib.sha256(guard.read_bytes()).hexdigest()==GUARD_SHA256,'thermal guard differs from the validated supervisor')
    sensor=guard.parent / 'read_temperature.cfg'
    require(sensor.is_file() and hashlib.sha256(sensor.read_bytes()).hexdigest()==SENSOR_SHA256,
            'JTAG sensor reader differs from the validated read-only KU3P/serial profile')
    return guard


def preflight():
    checked=subprocess.run(['sudo','-n',sys.executable,str(ROOT / 'rdma/read/host/native_rw_preflight.py'),
        '--require-application'],capture_output=True,text=True,timeout=30)
    require(checked.returncode==0,'native RW preflight refused before QP creation: '+checked.stdout[-600:]+checked.stderr[-600:])
    report=json.loads(checked.stdout)
    require(report.get('success') is True and report['application']['supported'] is True and
            report['application']['quiescent'] is True and report['application']['version']==0x20000,
            'preflight did not prove a quiescent version2 application')
    return report


def commands(report,operation,size,count,psn,peer_psn,window,log_dir,probe_config_error=False):
    fpga,peer=report['endpoints']['fpga'],report['endpoints']['peer'];native=report['native_receiver']
    require(report['success'] is True and report['application']['quiescent'] is True and
        report['application']['version']==0x20000 and native['device']=='mlx5_0' and
        native['bdf']==ROLES['peer']['bdf'] and native['port']==1 and native['link_layer']=='Ethernet' and
        native['gid_type']=='RoCE v2','not the audited native version2 test path')
    validate_request(operation,size,count,psn,peer_psn,window,probe_config_error)
    require(report['application']['run_id']<=(0xFFFFFFFD if probe_config_error else 0xFFFFFFFE),
            'insufficient run generations for requested finite test')
    prefix=['sudo','-n','ip','netns','exec',ROLES['peer']['namespace'],
            'timeout','--signal=TERM','--kill-after=3s','25s']
    if operation=='read':
        server=prefix+['env','AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES','AS02_PHYSICAL_REVIEW_COMPLETE=YES',
            str(ROOT / 'rdma/read/build/rc_read_peer'),'mlx5_0',str(native['gid_index']),ROLES['peer']['ip'],
            str(size),str(count),str(CONTROL_PORT),str(peer_psn),str(window)]
    else:
        server=prefix+[str(ROOT / 'rdma/build/rc_write_peer'),'mlx5_0',str(native['gid_index']),'listen',
            ROLES['peer']['ip'],str(size),str(count),str(CONTROL_PORT),str(peer_psn)]
    controller=['sudo','-n','ip','netns','exec',ROLES['fpga']['namespace'],
        'timeout','--signal=TERM','--kill-after=3s','20s','env','AS02_ALLOW_FPGA_RDMA=YES',
        sys.executable,str(ROOT / 'rdma/read/host/fpga_rw_client.py'),'--operation',operation,
        '--bdf',ROLES['fpga']['bdf'],'--local-ip',ROLES['fpga']['ip'],'--peer-ip',ROLES['peer']['ip'],
        '--local-mac',fpga['mac'],'--peer-mac',peer['mac'],'--message-bytes',str(size),'--count',str(count),
        '--port',str(CONTROL_PORT),'--qpn','2','--psn',str(psn),'--read-window',str(window),
        '--report',str(log_dir / 'client.json')]
    if probe_config_error:controller.append('--probe-config-error')
    return server,controller


def verify_config_error_recovery(report,result,size,count):
    proof=result.get('configuration_error_probe',{})
    require(result.get('config_error_recovery_verified') is True and proof.get('success') is True and
        proof.get('advertised_remote_bytes')==size*count-1 and proof.get('required_remote_bytes')==size*count and
        proof.get('expected_error_code')==1 and proof.get('application_commands')==[1,2] and
        proof.get('global_reset_requested') is False and proof.get('clear_without_global_reset') is True and
        proof.get('peer_mr_lease_retained') is True and proof.get('no_read_sq_issued') is True and
        proof.get('no_roce_tx_or_completion') is True,'configuration error recovery evidence is missing')
    before=proof['before'];failed=proof['error_terminal'];cleared=proof['cleared_idle']
    baseline=report['application']['run_id']
    require(before['run_id']==baseline and common_idle(before) and before['operation_mode']==1 and
        failed['run_id']==baseline+1 and cleared['run_id']==baseline+1 and common_idle(cleared) and
        cleared['operation_mode']==1 and result['run_id']==baseline+2,
        'configuration error/CLEAR/valid READ generation sequence differs')
    require(client.common.safe_terminal(failed['status']) and client.common.state(failed['status'])==8 and
        failed['status']&client.common.FAILED and not failed['status']&client.common.DONE and
        failed['status']&0x80 and failed['operation_mode']==1 and failed['error_code']==1 and
        all(failed[key]==0 for key in ('issued','acknowledged','committed','capture_bytes','authorized',
            'response_chunks','padding_bytes','capture_error','read_commands','read_bytes')) and
        failed['capture_state']==6 and all(value==0 for value in failed['diagnostics'].values()),
        'configuration error issued data/SQ or was not a protected quiescent rejection')
    require(all(cleared['diagnostics'][key]==before['diagnostics'][key] for key in ('0xc0','0xc4')),
        'invalid source extent changed cumulative RoCE TX/completion counters')


def common_idle(snapshot):
    return bool(client.common.safe_terminal(snapshot['status']) and client.common.state(snapshot['status'])==0 and
        snapshot['status']&0x80 and not snapshot['status']&(client.common.DONE|client.common.FAILED))


def verify_results(report,result,events,operation,size,count,psn,peer_psn,window,probe_config_error=False):
    require(result.get('operation')==operation and result.get('application_version')==0x20000,
            'not a version2 operation result')
    if operation=='write':
        return dict(legacy.verify_results(report,result,events,size,count,psn,peer_psn),operation='write',
                    native_write_completed=True,native_read_completed=False)
    require(operation=='read' and result.get('success') is True and result.get('hardware_access') is True and
        result.get('host_bar_verified') is True and result.get('source_verified_unchanged') is True and
        result.get('tx_quiescence_verified') is True,'READ client did not verify source/BAR/quiescence')
    require(result.get('config_error_probe_requested') is probe_config_error and
        result.get('config_error_recovery_verified') is probe_config_error,'requested error/recovery scope differs')
    if probe_config_error:verify_config_error_recovery(report,result,size,count)
    total=size*count;stride=(size+63)&~63;extent=min(client.CAPACITY,stride*count+64)
    require(result['bdf']==ROLES['fpga']['bdf'] and result['message_bytes']==size and result['messages']==count and
        result['local_qpn']==2 and result['local_psn']==psn and result['peer_psn']==peer_psn and
        result['issued']==count and result['acknowledged']==count and result['committed']==count and
        result['capture_bytes']==total and result['total_bytes']==total and result['payload_bytes_compared']==total and
        result['bar_bytes_compared']==extent and result['sentinel_bytes_compared']==extent-total and
        result['mismatches']==0 and result['read_window']==window,'READ transfer identity/counts differ')
    require(result.get('source_payload_transferred_over_tcp') is False and result.get('control_only_tcp') is True and
        result.get('software_roce_in_this_client') is False and
        result.get('fpga_payload_destination')=='protected_local_capture_ram' and
        result.get('expected_payload_complement_prefilled') is True,'READ was replaced with a software/source-copy path')
    require(client.common.safe_terminal(result['status']) and client.common.state(result['status'])==7 and
        result['status']&client.common.DONE and not result['status']&client.common.FAILED and result['error_code']==0,
        'READ was not a successful quiescent hardware operation')
    require(result['status']&0x80 and result['operation_mode']==1 and
        result['run_id']==report['application']['run_id']+1+int(probe_config_error) and result['diagnostics']['0xcc']==0 and
        result['diagnostics']['0xac']==0 and result['diagnostics']['0xb0']==0,
        'READ generation/mode or transport guard differs from audited ownership')
    require(result['capture_error']==0 and result['authorized']==count and result['capture_state']==6 and
        result['capture_lease']==stride*count and result['padding_bytes']==((-size)&3)*count and
        result['response_chunks']==((size+4095)//4096)*count and result['read_commands']==0 and
        result['read_bytes']==0 and result['elapsed_cycles']>0,'capture/protected READ counters differ')
    native=report['native_receiver']
    require(report['success'] is True and report['application']['quiescent'] is True and
        native['device']=='mlx5_0' and native['bdf']==ROLES['peer']['bdf'] and native['port']==1 and
        native['gid_type']=='RoCE v2' and native['link_layer']=='Ethernet','source provider identity was not audited')
    listening=legacy.one_event(events,'listening');source=legacy.one_event(events,'read_source')
    remote=legacy.one_event(events,'read_remote');unchanged=legacy.one_event(events,'read_source_unchanged')
    require(listening['ip']==ROLES['peer']['ip'] and listening['port']==CONTROL_PORT,'wrong source control listener')
    require(source['device']=='mlx5_0' and source['bdf']==ROLES['peer']['bdf'] and
        source['gid_index']==native['gid_index'] and ipaddress.IPv6Address(source['gid'])==ipaddress.IPv6Address(native['gid']) and
        source['qpn']==result['peer_qpn'] and source['psn']==peer_psn and source['message_bytes']==size and
        source['messages']==count and source['path_mtu']==4096 and source['read_resources']>=window and
        source['rkey']==result['peer_rkey'] and source['address']==result['peer_address'] and
        source['remote_read_granted'] is True and source['remote_write_granted'] is False,
        'source is not this native REMOTE_READ-only MR/QP/PSN/GID')
    require(remote['qpn']==2 and remote['psn']==psn and remote['read_resources']==window,'wrong FPGA endpoint at source')
    require(source['nonce']==result['nonce'] and source['source_sha256']==result['expected_payload_sha256']==
        result['actual_payload_sha256'] and len(bytes.fromhex(source['nonce']))==32,'independent source/BAR nonce or digest differs')
    require(hashlib.sha256(client.source_data(bytes.fromhex(source['nonce']),size,count)).hexdigest()==source['source_sha256'],
            'source does not match independent nonce/extent derivation')
    require(unchanged.get('pass') is True and unchanged['bytes']==total and unchanged['mismatches']==0 and
        unchanged['client_quiescent_control'] is True and unchanged['client_aborted'] is False,
        'source MR lifetime/all-byte unchanged verification failed')
    return dict(operation='read',native_transfer_verified=True,native_read_completed=True,native_write_completed=False,
        source_memory_verified=True,host_bar_memory_verified=True,verified_bytes=total,message_bytes=size,messages=count,
        local_psn=psn,peer_psn=peer_psn,native_peer=native,nonce=source['nonce'],source_sha256=source['source_sha256'],
        payload_sha256=result['actual_payload_sha256'],capture_bytes=total,response_chunks=result['response_chunks'],
        padding_bytes=result['padding_bytes'],sentinel_bytes_verified=extent-total,
        seconds_from_hw_counter=result['seconds_from_hw_counter'],includes_initialization_and_drain=True,
        config_error_probe_requested=probe_config_error,config_error_recovery_verified=probe_config_error,
        configuration_error_probe=result.get('configuration_error_probe') if probe_config_error else None,
        global_reset_between_error_and_read=False,
        source_payload_transferred_over_tcp=False)


def source_identity(operation):
    files=['rdma/read/host/native_rw_test.py','rdma/read/host/native_rw_preflight.py',
        'rdma/read/host/fpga_rw_client.py','rdma/host/native_test.py','rdma/host/native_preflight.py',
        'rdma/host/fpga_write_client.py']
    files+=['rdma/read/host/rc_read_peer.c','rdma/read/build/rc_read_peer'] if operation=='read' else \
        ['rdma/host/rc_write_peer.c','rdma/build/rc_write_peer']
    return {name:hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}


def worker(args,log_dir):
    peer=controller=None
    result=dict(event='native_rw_worker',operation=args.operation,success=False,hardware_rdma_verified=False,
        thermal_guard_result_pending=True,message_bytes=args.message_bytes,messages=args.count,
        config_error_probe_requested=args.probe_config_error,
        software_rxe_created=False,fpga_programmed=False,network_configuration_modified=False,fan_settings_changed=False)
    try:
        report=preflight();legacy.dump(log_dir / 'preflight.json',report)
        result['tool_source_sha256']=source_identity(args.operation)
        owned=subprocess.run(['sudo','-n','ip','netns','exec',ROLES['peer']['namespace'],
            'ss','-H','-ltn','sport = :'+str(CONTROL_PORT)],capture_output=True,text=True,check=True,timeout=5).stdout
        require(not owned.strip(),'another process already owns the private control port; refusing takeover')
        peer_cmd,controller_cmd=commands(report,args.operation,args.message_bytes,args.count,args.psn,args.peer_psn,
            args.read_window,log_dir,args.probe_config_error)
        legacy.dump(log_dir / 'commands.json',dict(peer=peer_cmd,client=controller_cmd))
        with (log_dir / 'peer.jsonl').open('x') as out,(log_dir / 'client.log').open('x') as err:
            peer=subprocess.Popen(peer_cmd,stdout=out,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+5
            while not any(e.get('event')=='listening' for e in legacy.events(log_dir / 'peer.jsonl')):
                require(peer.poll() is None and time.monotonic()<deadline,'native source startup failed/timed out')
                time.sleep(0.02)
            controller=subprocess.Popen(controller_cmd,stdout=err,stderr=subprocess.STDOUT)
            require(controller.wait(timeout=25)==0,'FPGA controller failed; inspect client.log/client.json')
            require(peer.wait(timeout=5)==0,'native source/receiver failed; inspect peer.jsonl')
        result.update(verify_results(report,json.loads((log_dir / 'client.json').read_text()),
            legacy.events(log_dir / 'peer.jsonl'),args.operation,args.message_bytes,args.count,args.psn,args.peer_psn,
            args.read_window,args.probe_config_error),success=True)
        if args.probe_config_error:
            result.update(config_error_recovery_verified=True,global_reset_between_error_and_read=False)
    except BaseException as error:result.update(error=str(error) or type(error).__name__,success=False)
    finally:
        client_clean=legacy.stop_owned(controller);peer_clean=legacy.stop_owned(peer)
        result['owned_children_stopped_without_force']=client_clean and peer_clean
        if not result['owned_children_stopped_without_force']:result.update(success=False,error='forced child cleanup; quiescence unproven')
        legacy.dump(log_dir / 'worker.json',result)
    return 0 if result['success'] else 1


def final_result(guard_status,worker_result):
    require(guard_status==0 and worker_result.get('success') is True and
        worker_result.get('native_transfer_verified') is True and worker_result.get('owned_children_stopped_without_force') is True,
        'thermal supervisor/worker did not verify a clean finite operation')
    if worker_result['operation']=='read':
        require(worker_result.get('native_read_completed') is True and worker_result.get('source_memory_verified') is True and
            worker_result.get('host_bar_memory_verified') is True,'READ source/BAR evidence incomplete')
        if worker_result.get('config_error_probe_requested'):
            require(worker_result.get('config_error_recovery_verified') is True and
                worker_result.get('global_reset_between_error_and_read') is False,
                'requested READ error recovery was not verified without global reset')
    else:require(worker_result.get('receiver_memory_verified') is True,'WRITE receiver evidence incomplete')
    return dict(worker_result,event='native_fpga_rw_test',hardware_rdma_verified=True,
        thermal_guard_result_pending=False,thermal_guard_exit_status=0,
        physical_review_operator_attested=True,physical_gate_automatically_checked=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation',choices=('read','write'),required=True)
    parser.add_argument('--message-bytes',type=int,default=65)
    parser.add_argument('--count',type=int,default=1)
    parser.add_argument('--psn',type=lambda s:int(s,0))
    parser.add_argument('--peer-psn',type=lambda s:int(s,0),default=0x987654)
    parser.add_argument('--read-window',type=int,default=1)
    parser.add_argument('--probe-config-error',action='store_true',
        help='READ only: finite invalid-source-range rejection/CLEAR followed by the valid native READ')
    parser.add_argument('--under-temperature-guard',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--log-dir',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args();args.psn=args.psn if args.psn is not None else secrets.randbelow(1<<24)
    validate_request(args.operation,args.message_bytes,args.count,args.psn,args.peer_psn,args.read_window,args.probe_config_error)
    guard=require_authorization(os.environ)
    binary=ROOT / ('rdma/read/build/rc_read_peer' if args.operation=='read' else 'rdma/build/rc_write_peer')
    require(os.access(binary,os.X_OK),'build the selected native peer first')
    def interrupted(signum,_):raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    if args.under_temperature_guard:
        require(args.log_dir is not None and args.log_dir.is_dir() and
            args.log_dir.resolve().parent==(ROOT / 'rdma/logs').resolve(),'invalid owned worker directory')
        return worker(args,args.log_dir)
    require(args.log_dir is None,'supervisor creates its own exclusive worker directory')
    preflight()  # No guard/JTAG/QP start if app/link identity is wrong.
    log_dir=Path(tempfile.mkdtemp(prefix='native-rw-',dir=ROOT / 'rdma/logs'))
    result=dict(event='native_fpga_rw_test',operation=args.operation,success=False,hardware_rdma_verified=False,
        observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),log_directory=str(log_dir))
    supervisor=None
    try:
        result['temperature_guard_sha256']=hashlib.sha256(guard.read_bytes()).hexdigest()
        result['temperature_sensor_sha256']=hashlib.sha256((guard.parent / 'read_temperature.cfg').read_bytes()).hexdigest()
        command=['bash',str(guard),sys.executable,str(Path(__file__).resolve()),'--under-temperature-guard',
            '--log-dir',str(log_dir),'--operation',args.operation,'--message-bytes',str(args.message_bytes),
            '--count',str(args.count),'--psn',str(args.psn),'--peer-psn',str(args.peer_psn),'--read-window',str(args.read_window)]
        if args.probe_config_error:command.append('--probe-config-error')
        print('Finite native RW logs: '+str(log_dir),flush=True)
        with (log_dir / 'temperature-guard.log').open('x') as out:
            supervisor=subprocess.Popen(command,stdout=out,stderr=subprocess.STDOUT)
            guard_status=supervisor.wait(timeout=60)
        result['thermal_guard_exit_status']=guard_status
        result.update(final_result(guard_status,json.loads((log_dir / 'worker.json').read_text())))
    except BaseException as error:result.update(success=False,hardware_rdma_verified=False,error=str(error) or type(error).__name__)
    finally:
        if not legacy.stop_owned(supervisor):result.update(success=False,hardware_rdma_verified=False,error='forced thermal-supervisor cleanup')
        legacy.dump(log_dir / 'result.json',result)
    print(json.dumps(result,indent=2));return 0 if result['success'] else 1


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as error:
        print('refused/failed: '+str(error),file=sys.stderr);sys.exit(1)
