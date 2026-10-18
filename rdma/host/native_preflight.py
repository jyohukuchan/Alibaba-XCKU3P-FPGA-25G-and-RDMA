#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only audit of the dedicated FPGA/CX455A native-25G test path.

No QPs, packets, interface changes, resets or programming. BAR2 is not
mapped unless --read-application/--require-application is explicitly used.
This audit does not certify physical timing, temperature or RDMA operation.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import mmap
import os
import pathlib
import re
import struct
import subprocess
import sys

from fpga_write_client import safe_terminal


ROLES = {
    "fpga": dict(bdf="0000:82:00.0", driver="mqnic", namespace="fpga10g-fpga",
                 interface="enp130s0np1", ip="198.18.10.2", pci={
                     "vendor": 0x1234, "device": 0x1001, "subsystem_vendor": 0x1CE4,
                     "subsystem_device": 0x0009, "class": 0x020000}),
    "peer": dict(bdf="0000:03:00.0", driver="mlx5_core", namespace="fpga10g-cx4",
                 interface="enp3s0np0", ip="198.18.10.1", pci={
                     "vendor": 0x15B3, "device": 0x1013, "class": 0x020700}),
}


class PreflightError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PreflightError(message)


def fields(output):
    """LC_ALL=C ethtool field names; never infer wire mode from PCI class."""
    result = {}
    for line in output.splitlines():
        key, colon, value = line.strip().partition(":")
        if colon:
            result[key] = value.strip()
    return result


def audit_pci(devices):
    for role, expected in ROLES.items():
        device = devices[role]
        require(device["bdf"] == expected["bdf"], role + ": unexpected BDF")
        require(device["driver"] == expected["driver"], role + ": unexpected PCI driver")
        for name, value in expected["pci"].items():
            require(device["pci"][name] == value, role + ": unexpected PCI " + name)


def audit(snapshot, require_application=False):
    audit_pci(snapshot["devices"])
    endpoints = {}
    for role, expected in ROLES.items():
        observed = snapshot["devices"][role]
        require(len(observed["addresses"]) == 1, role + ": expected exactly one netdev")
        address = observed["addresses"][0]
        require(address["ifname"] == expected["interface"], role + ": unexpected netdev")
        require({"UP", "LOWER_UP"}.issubset(address["flags"]) and address["operstate"] == "UP",
                role + ": interface/link is not up")
        require(address["mtu"] == 9000, role + ": expected audited MTU 9000")
        require(any(item.get("family") == "inet" and item.get("local") == expected["ip"] and
                    item.get("prefixlen") == 30 for item in address["addr_info"]),
                role + ": expected dedicated test IPv4 /30")
        mac = address["address"].lower()
        require(re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", mac) is not None,
                role + ": malformed MAC")
        mac_value = int(mac.replace(":", ""), 16)
        require(mac_value != 0 and not mac_value & (1 << 40), role + ": non-unicast MAC")
        info, link = fields(observed["driver_info"]), fields(observed["link"])
        require(info.get("driver") == expected["driver"] and info.get("bus-info") == expected["bdf"],
                role + ": netdev driver/BDF does not match PCI identity")
        require(link.get("Link detected") == "yes", role + ": link not detected")
        if role == "peer":
            require(link.get("Speed") == "25000Mb/s" and link.get("Duplex") == "Full",
                    "peer: requires actual 25Gb full-duplex link")
        # mqnic's ethtool currently supplies link only, not a speed value.
        endpoints[role] = {key: expected[key] for key in ("bdf", "driver", "namespace", "interface", "ip")}
        endpoints[role].update(mac=mac, mtu=address["mtu"], link_detected=True,
                               reported_speed=link.get("Speed"), firmware=info.get("firmware-version"))

    rdma = snapshot["rdma"]
    require(rdma["device"] == "mlx5_0" and rdma["port"] == 1 and
            rdma["bdf"] == ROLES["peer"]["bdf"], "RDMA provider is not the audited native CX455A")
    require(rdma["state"] == "4: ACTIVE" and rdma["link_layer"] == "Ethernet",
            "native RDMA port must be active Ethernet")
    wanted_gid = ipaddress.IPv6Address("::ffff:" + ROLES["peer"]["ip"])
    matches = [entry for entry in rdma["gids"] if ipaddress.IPv6Address(entry["gid"]) == wanted_gid and
               entry["type"] == "RoCE v2" and entry["netdev"] == ROLES["peer"]["interface"] and
               0 <= entry["index"] <= 255]
    require(len(matches) == 1, "expected one actual IPv4-mapped RoCEv2 GID on the native netdev")
    require(fields(snapshot["peer_fec"]).get("Active FEC encoding") == "Off",
            "peer FEC differs from the audited no-FEC FPGA path")
    app = dict(snapshot["application"])
    app.update(supported=None, quiescent=None)
    if app["registers_read"]:
        app["supported"] = app.get("id") == 0x524F4332 and app.get("version") == 0x00010000
        app["quiescent"] = bool(app["supported"] and safe_terminal(app["status"]))
    if require_application:
        require(app["bar2_present"] and app["registers_read"] and app["supported"] and app["quiescent"],
                "supported ROC2 BAR2 and proven TX quiescence are required; no test was started")
    return dict(success=True, endpoints=endpoints,
                native_receiver=dict(device="mlx5_0", port=1, bdf=rdma["bdf"],
                                     link_layer="Ethernet", gid_index=matches[0]["index"],
                                     gid=matches[0]["gid"], gid_type="RoCE v2", active_fec="Off",
                                     active_mtu_checked=False), application=app)


def run_command(argv):
    result = subprocess.run(argv, check=True, text=True, capture_output=True, timeout=15,
                            env=dict(os.environ, LC_ALL="C"))
    return result.stdout


def read_application(device):
    require(sys.byteorder == "little" and os.uname().machine == "x86_64",
            "BAR2 reading is audited for this x86_64 host only")
    # Only known non-clearing registers are read; never create a write mapping.
    fd = os.open(device / "resource2", os.O_RDONLY | os.O_SYNC | os.O_CLOEXEC)
    try:
        require(os.fstat(fd).st_size >= 4096, "application BAR2 aperture is too small")
        with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ) as mapping:
            values = dict(id=struct.unpack_from("<I", mapping, 0)[0],
                          version=struct.unpack_from("<I", mapping, 4)[0])
            if values["id"] == 0x524F4332 and values["version"] == 0x00010000:
                values["status"] = struct.unpack_from("<I", mapping, 12)[0]
            return values
    finally:
        os.close(fd)


def collect(sysfs=pathlib.Path("/sys"), run=run_command, read_app=False):
    devices = {}
    for role, expected in ROLES.items():
        device = sysfs / "bus/pci/devices" / expected["bdf"]
        devices[role] = dict(bdf=expected["bdf"], driver=(device / "driver").resolve(strict=True).name,
                             pci={name: int((device / name).read_text(), 16) for name in expected["pci"]})
    # Refuse a swapped/unknown card before any namespace command or MMIO read.
    audit_pci(devices)
    for role, expected in ROLES.items():
        prefix = ["sudo", "-n", "ip", "netns", "exec", expected["namespace"]]
        devices[role].update(addresses=json.loads(run(prefix + ["ip", "-j", "address", "show", "dev", expected["interface"]])),
                             driver_info=run(prefix + ["ethtool", "-i", expected["interface"]]),
                             link=run(prefix + ["ethtool", expected["interface"]]))
    ibdev = sysfs / "class/infiniband/mlx5_0"
    port = ibdev / "ports/1"
    gids = []
    for item in sorted((port / "gids").iterdir(), key=lambda path: int(path.name)):
        gid = item.read_text().strip()
        if int(ipaddress.IPv6Address(gid)) == 0:
            continue
        gids.append(dict(index=int(item.name), gid=gid,
                         type=(port / "gid_attrs/types" / item.name).read_text().strip(),
                         netdev=(port / "gid_attrs/ndevs" / item.name).read_text().strip()))
    rdma = dict(device="mlx5_0", port=1, bdf=(ibdev / "device").resolve(strict=True).name,
                state=(port / "state").read_text().strip(),
                link_layer=(port / "link_layer").read_text().strip(), gids=gids)
    peer_fec = run(["sudo", "-n", "ip", "netns", "exec", ROLES["peer"]["namespace"],
                    "ethtool", "--show-fec", ROLES["peer"]["interface"]])
    device = sysfs / "bus/pci/devices" / ROLES["fpga"]["bdf"]
    app = dict(bar2_present=(device / "resource2").exists(), registers_read=False)
    if read_app and app["bar2_present"]:
        app.update(read_application(device), registers_read=True)
    return dict(devices=devices, rdma=rdma, peer_fec=peer_fec, application=app)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-application", action="store_true", help="also read ROC2 ID/version/status without writes")
    parser.add_argument("--require-application", action="store_true", help="read BAR2 and refuse absent/unknown/busy ROC2")
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    result = dict(event="native_preflight", success=False, traffic_generated=False,
                  hardware_configuration_modified=False, fpga_programmed=False, rdma_qp_created=False,
                  hardware_rdma_verified=False, timing_verified=False, temperature_checked=False,
                  observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
    try:
        snapshot = collect(read_app=args.read_application or args.require_application)
        result["observations"] = snapshot
        result.update(audit(snapshot, require_application=args.require_application))
    except (PreflightError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    rendered = json.dumps(result, indent=2) + "\n"
    print(rendered, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
