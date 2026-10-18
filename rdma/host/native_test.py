#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""One finite native FPGA WRITE -> CX455A case under the external thermal guard.

Requires AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES, AS02_PHYSICAL_REVIEW_COMPLETE=YES
and AS02_TEMPERATURE_GUARD=/absolute/path/to/the/validated/guard.sh. The review
flag is an operator attestation, not an automatic physical-validation result.
No programming, RXE, interface changes, NIC resets or fan changes are made.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import os
import pathlib
import secrets
import signal
import subprocess
import sys
import tempfile
import time

from fpga_write_client import Config, mac_number
from native_preflight import ROLES

PROJECT = pathlib.Path(__file__).resolve().parents[2]
CONTROL_PORT = 18516


class TestError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise TestError(message)


def validate_request(size, count, psn, peer_psn):
    # Reuse the actual controller's limits; this does not access hardware.
    Config("198.18.10.2", "198.18.10.1", 2, 4, size, count, 2, psn).validate()
    require(0 <= peer_psn <= 0xFFFFFF, "peer PSN must fit 24 bits")


def require_authorization(environment):
    require(environment.get("AS02_ALLOW_NATIVE_FPGA_RDMA_TEST") == "YES",
            "set AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES for a finite native test")
    require(environment.get("AS02_PHYSICAL_REVIEW_COMPLETE") == "YES",
            "physical timing/DRC/CDC review and inspected SRAM programming must precede testing")
    guard = pathlib.Path(environment.get("AS02_TEMPERATURE_GUARD", ""))
    require(guard.is_absolute() and guard.is_file(), "set the absolute path of the validated temperature guard")
    return guard.resolve(strict=True)


def dump(path, result):
    with path.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")


def source_identity():
    files = ("rdma/host/native_test.py", "rdma/host/native_preflight.py",
             "rdma/host/fpga_write_client.py", "rdma/host/rc_write_peer.c", "rdma/build/rc_write_peer")
    return {name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files}


def preflight():
    result = subprocess.run(["sudo", "-n", sys.executable, str(PROJECT / "rdma/host/native_preflight.py"),
                             "--require-application"], text=True, capture_output=True, timeout=30)
    require(result.returncode == 0, "native preflight refused before QP creation: " + result.stdout[-500:] + result.stderr[-500:])
    report = json.loads(result.stdout)
    require(report["success"] is True and report["application"]["quiescent"] is True,
            "native preflight did not prove the expected quiescent application")
    return report


def commands(report, size, count, psn, peer_psn, log_dir):
    fpga, peer = report["endpoints"]["fpga"], report["endpoints"]["peer"]
    rdma = report["native_receiver"]
    require(report["success"] is True and report["application"]["quiescent"] is True and
            rdma["device"] == "mlx5_0" and rdma["bdf"] == ROLES["peer"]["bdf"] and
            rdma["port"] == 1 and rdma["link_layer"] == "Ethernet" and rdma["gid_type"] == "RoCE v2",
            "native receiver identity was not audited")
    # Audit-derived MACs/GID slot; role namespaces and BDF stay hard restricted.
    Config(ROLES["fpga"]["ip"], ROLES["peer"]["ip"], mac_number(fpga["mac"]),
           mac_number(peer["mac"]), size, count, 2, psn).validate()
    server = ["sudo", "-n", "ip", "netns", "exec", ROLES["peer"]["namespace"],
              "timeout", "--signal=TERM", "--kill-after=3s", "20s", str(PROJECT / "rdma/build/rc_write_peer"),
              "mlx5_0", str(rdma["gid_index"]), "listen", ROLES["peer"]["ip"],
              str(size), str(count), str(CONTROL_PORT), str(peer_psn)]
    client = ["sudo", "-n", "ip", "netns", "exec", ROLES["fpga"]["namespace"],
              "timeout", "--signal=TERM", "--kill-after=3s", "15s", "env", "AS02_ALLOW_FPGA_RDMA=YES",
              sys.executable, str(PROJECT / "rdma/host/fpga_write_client.py"), "--bdf", ROLES["fpga"]["bdf"],
              "--local-ip", ROLES["fpga"]["ip"], "--peer-ip", ROLES["peer"]["ip"],
              "--local-mac", fpga["mac"], "--peer-mac", peer["mac"], "--message-bytes", str(size),
              "--count", str(count), "--port", str(CONTROL_PORT), "--qpn", "2", "--psn", str(psn),
              "--report", str(log_dir / "client.json")]
    return server, client


def events(path):
    result = []
    for line in path.read_text().splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue  # Keep stderr in the raw log, never parse it as evidence.
        if isinstance(value, dict) and "event" in value:
            result.append(value)
    return result


def one_event(records, name):
    matches = [record for record in records if record.get("event") == name]
    require(len(matches) == 1, "missing/ambiguous receiver event: " + name)
    return matches[0]


def verify_results(report, client, receiver, size, count, psn, peer_psn):
    require(client.get("success") is True and client.get("receiver_verified") is True and
            client.get("tx_quiescence_verified") is True and client.get("hardware_access") is True,
            "controller did not verify receiver memory and FPGA TX quiescence")
    require(client["bdf"] == ROLES["fpga"]["bdf"] and client["message_bytes"] == size and
            client["messages"] == count and client["issued"] == count and client["acknowledged"] == count and
            client["total_bytes"] == size * count and client["elapsed_cycles"] > 0,
            "controller transfer identity/counts differ")
    require(client.get("software_roce_in_this_client") is False and client.get("control_only_tcp") is True and
            client.get("fpga_payload_source") == "bounded_local_pattern", "not the native FPGA pattern-source path")
    listening = one_event(receiver, "listening")
    require(listening["ip"] == ROLES["peer"]["ip"] and listening["port"] == CONTROL_PORT,
            "receiver listened on an unexpected control address/port")
    local, remote = one_event(receiver, "local_endpoint"), one_event(receiver, "remote_endpoint")
    memory = one_event(receiver, "memory_verification")
    rdma = report["native_receiver"]
    require(report["success"] is True and report["application"]["quiescent"] is True and
            rdma["device"] == "mlx5_0" and rdma["bdf"] == ROLES["peer"]["bdf"] and
            rdma["port"] == 1 and rdma["link_layer"] == "Ethernet" and rdma["gid_type"] == "RoCE v2",
            "native receiver identity was not audited")
    require(local["device"] == "mlx5_0" and local["gid_index"] == rdma["gid_index"] and
            ipaddress.IPv6Address(local["gid"]) == ipaddress.IPv6Address(rdma["gid"]) and
            local["qpn"] == client["peer_qpn"] and local["psn"] == peer_psn == client["peer_psn"] and
            local["path_mtu"] == 4096 and local["message_bytes"] == size and local["messages"] == count,
            "receiver is not the same native QP/GID/PSN/finite transfer")
    require(remote["qpn"] == client["local_qpn"] == 2 and remote["psn"] == psn == client["local_psn"] and
            remote["message_bytes"] == size and remote["messages"] == count and
            ipaddress.IPv6Address(remote["gid"]) == ipaddress.IPv6Address("::ffff:" + ROLES["fpga"]["ip"]),
            "receiver's remote endpoint does not describe this FPGA run")
    require(memory.get("pass") is True and memory["mismatches"] == 0 and memory["bytes"] == size * count,
            "receiver all-byte memory verification failed")
    return dict(native_transfer_verified=True, receiver_memory_verified=True,
                verified_bytes=size * count, message_bytes=size, messages=count,
                local_psn=psn, peer_psn=peer_psn, native_receiver=rdma,
                seconds_from_hw_counter=client["seconds_from_hw_counter"],
                payload_gbit_per_second_from_hw_counter=client["payload_gbit_per_second_from_hw_counter"],
                includes_initialization_and_drain=True)


def stop_owned(process):
    """Only a child Popen handle from this invocation; never scan/kill by name."""
    if process is None or process.poll() is not None:
        return True
    try:
        process.terminate()  # sudo forwards TERM; the controller attempts ABORT first.
        try:
            process.wait(timeout=5)
            return True
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            return False  # Forced cleanup never constitutes proven FPGA quiescence.
    except (OSError, subprocess.SubprocessError):
        return False


def worker(args, log_dir):
    receiver_process = client_process = None
    result = dict(event="native_test_worker", success=False, hardware_rdma_verified=False,
                  thermal_guard_result_pending=True, message_bytes=args.message_bytes, messages=args.count,
                  software_rxe_created=False, fpga_programmed=False,
                  network_configuration_modified=False, fan_settings_changed=False)
    try:
        report = preflight()  # Recheck inside the guard before opening any QP.
        dump(log_dir / "preflight.json", report)
        result["source_sha256"] = source_identity()
        listening = subprocess.run(["sudo", "-n", "ip", "netns", "exec", ROLES["peer"]["namespace"],
                                    "ss", "-H", "-ltn", "sport = :" + str(CONTROL_PORT)],
                                   text=True, capture_output=True, check=True, timeout=5).stdout
        require(not listening.strip(), "control port already owned by another process; refusing to replace it")
        server_command, client_command = commands(report, args.message_bytes, args.count, args.psn, args.peer_psn, log_dir)
        dump(log_dir / "commands.json", dict(receiver=server_command, client=client_command))
        with (log_dir / "receiver.jsonl").open("x") as receiver_log, (log_dir / "client.log").open("x") as client_log:
            receiver_process = subprocess.Popen(server_command, stdout=receiver_log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 5
            while not any(record.get("event") == "listening" for record in events(log_dir / "receiver.jsonl")):
                require(receiver_process.poll() is None, "native receiver exited before listening")
                require(time.monotonic() < deadline, "native receiver startup deadline exceeded")
                time.sleep(0.02)
            client_process = subprocess.Popen(client_command, stdout=client_log, stderr=subprocess.STDOUT)
            require(client_process.wait(timeout=20) == 0, "FPGA controller failed; inspect client.log/client.json")
            require(receiver_process.wait(timeout=5) == 0, "native receiver failed; inspect receiver.jsonl")
        result.update(verify_results(report, json.loads((log_dir / "client.json").read_text()),
                                     events(log_dir / "receiver.jsonl"), args.message_bytes, args.count,
                                     args.psn, args.peer_psn), success=True)
    except BaseException as error:
        result.update(error=str(error) or type(error).__name__, success=False)
    finally:
        # Normal error cleanup preserves MR/QP lifetime until client abort ends.
        # A thermal group stop may terminate both; QP teardown rejects late DMA.
        client_clean = stop_owned(client_process)
        receiver_clean = stop_owned(receiver_process)
        result["owned_children_stopped_without_force"] = client_clean and receiver_clean
        if not result["owned_children_stopped_without_force"]:
            result.update(success=False, error="forced child cleanup; FPGA quiescence is not established")
        dump(log_dir / "worker.json", result)
    return 0 if result["success"] else 1


def final_result(guard_status, worker_result):
    require(guard_status == 0, "temperature guard did not finish successfully")
    require(worker_result.get("success") is True and worker_result.get("native_transfer_verified") is True and
            worker_result.get("receiver_memory_verified") is True and
            worker_result.get("owned_children_stopped_without_force") is True,
            "native worker did not verify one clean finite transfer")
    return dict(worker_result, event="native_fpga_rdma_test", hardware_rdma_verified=True,
                thermal_guard_result_pending=False, thermal_guard_exit_status=0,
                physical_review_operator_attested=True, physical_gate_automatically_checked=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message-bytes", type=int, default=64)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--psn", type=lambda value: int(value, 0))
    parser.add_argument("--peer-psn", type=lambda value: int(value, 0), default=0x987654)
    parser.add_argument("--under-temperature-guard", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--log-dir", type=pathlib.Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.psn = args.psn if args.psn is not None else secrets.randbelow(1 << 24)
    validate_request(args.message_bytes, args.count, args.psn, args.peer_psn)
    guard = require_authorization(os.environ)
    require(os.access(PROJECT / "rdma/build/rc_write_peer", os.X_OK), "build the native peer with make -C rdma first")
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    if args.under_temperature_guard:
        require(args.log_dir is not None and args.log_dir.is_dir() and
                args.log_dir.resolve().parent == (PROJECT / "rdma/logs").resolve(), "invalid owned worker log directory")
        return worker(args, args.log_dir)
    require(args.log_dir is None, "log directory is created exclusively by the supervising invocation")
    # Read-only rejection happens before even starting the JTAG temperature reader.
    preflight()
    log_root = PROJECT / "rdma/logs"
    log_root.mkdir(exist_ok=True)
    log_dir = pathlib.Path(tempfile.mkdtemp(prefix="native-", dir=log_root))
    result = dict(event="native_fpga_rdma_test", success=False, hardware_rdma_verified=False,
                  observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), log_directory=str(log_dir))
    guard_process = None
    try:
        result["temperature_guard_sha256"] = hashlib.sha256(guard.read_bytes()).hexdigest()
        command = ["bash", str(guard), sys.executable, str(pathlib.Path(__file__).resolve()),
                   "--under-temperature-guard", "--log-dir", str(log_dir), "--message-bytes", str(args.message_bytes),
                   "--count", str(args.count), "--psn", str(args.psn), "--peer-psn", str(args.peer_psn)]
        print(f"Finite native test logs: {log_dir}", flush=True)
        with (log_dir / "temperature-guard.log").open("x") as guard_log:
            guard_process = subprocess.Popen(command, stdout=guard_log, stderr=subprocess.STDOUT)
            guard_status = guard_process.wait()  # Guard and worker both have finite internal deadlines.
        result["thermal_guard_exit_status"] = guard_status
        require(guard_status == 0, "temperature guard or worker failed; inspect temperature-guard.log")
        result.update(final_result(guard_status, json.loads((log_dir / "worker.json").read_text())))
    except BaseException as error:
        result.update(success=False, hardware_rdma_verified=False, error=str(error) or type(error).__name__)
    finally:
        if not stop_owned(guard_process):
            result.update(success=False, hardware_rdma_verified=False, error="temperature supervisor required forced cleanup")
        dump(log_dir / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"refused/failed: {error}", file=sys.stderr)
        sys.exit(1)
