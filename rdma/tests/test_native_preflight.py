#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Pure observation fixtures: no sysfs, namespaces, QPs, MMIO or traffic."""
import copy
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "host"))
import native_preflight as preflight


def fixture():
    devices = {}
    for role, expected in preflight.ROLES.items():
        mac = "d6:b9:fb:83:a4:51" if role == "fpga" else "b8:83:03:67:c5:d0"
        devices[role] = dict(bdf=expected["bdf"], driver=expected["driver"], pci=copy.deepcopy(expected["pci"]),
                             addresses=[dict(ifname=expected["interface"], flags=["UP", "LOWER_UP"], operstate="UP",
                                             mtu=9000, address=mac, addr_info=[dict(family="inet", local=expected["ip"], prefixlen=30)])],
                             driver_info=f'driver: {expected["driver"]}\nbus-info: {expected["bdf"]}\n',
                             link="Link detected: yes\n" + ("Speed: 25000Mb/s\nDuplex: Full\n" if role == "peer" else ""))
    return dict(devices=devices, rdma=dict(device="mlx5_0", port=1, bdf="0000:03:00.0", state="4: ACTIVE",
                                          link_layer="Ethernet", gids=[dict(index=37, gid="::ffff:198.18.10.1",
                                                                             type="RoCE v2", netdev="enp3s0np0")]),
                peer_fec="Active FEC encoding: Off\n", application=dict(bar2_present=False, registers_read=False))


class PreflightTests(unittest.TestCase):
    def test_ethernet_mode_despite_infiniband_pci_class_and_dynamic_gid(self):
        observed = fixture()
        self.assertEqual(observed["devices"]["peer"]["pci"]["class"], 0x020700)
        result = preflight.audit(observed)
        self.assertTrue(result["success"])
        self.assertEqual(result["native_receiver"]["gid_index"], 37)
        self.assertEqual(result["endpoints"]["fpga"]["mac"], "d6:b9:fb:83:a4:51")
        self.assertIsNone(result["endpoints"]["fpga"]["reported_speed"])
        self.assertIsNone(result["application"]["supported"])
        self.assertFalse(result["native_receiver"]["active_mtu_checked"])

    def test_wrong_card_driver_netdev_or_subsystem_is_refused(self):
        for role, key, value in (("fpga", "bdf", "0000:07:00.0"), ("peer", "driver", "rdma_rxe")):
            with self.subTest(role=role, key=key):
                observed = fixture(); observed["devices"][role][key] = value
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed)
        for key in ("vendor", "device", "subsystem_vendor", "subsystem_device", "class"):
            with self.subTest(pci=key):
                observed = fixture(); observed["devices"]["fpga"]["pci"][key] ^= 1
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed)
        observed = fixture(); observed["devices"]["fpga"]["driver_info"] = "driver: mqnic\nbus-info: 0000:07:00.0\n"
        with self.assertRaises(preflight.PreflightError):
            preflight.audit(observed)

    def test_no_link_wrong_speed_duplex_or_fec(self):
        for field, value in (("link", "Speed: 10000Mb/s\nDuplex: Full\nLink detected: yes\n"),
                             ("link", "Speed: 25000Mb/s\nDuplex: Half\nLink detected: yes\n"),
                             ("link", "Speed: 25000Mb/s\nDuplex: Full\nLink detected: no\n")):
            with self.subTest(value=value):
                observed = fixture(); observed["devices"]["peer"][field] = value
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed)
        observed = fixture(); observed["peer_fec"] = "Active FEC encoding: RS\n"
        with self.assertRaises(preflight.PreflightError):
            preflight.audit(observed)

    def test_address_interface_mtu_and_mac_identity(self):
        mutations = (("ifname", "enp7s0"), ("flags", ["UP"]), ("operstate", "DOWN"),
                     ("mtu", 1500), ("address", "ff:ff:ff:ff:ff:ff"), ("address", "00:00:00:00:00:00"),
                     ("address", "bad"), ("addr_info", [dict(family="inet", local="192.168.0.148", prefixlen=24)]))
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                observed = fixture(); observed["devices"]["fpga"]["addresses"][0][key] = value
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed)
        observed = fixture(); observed["devices"]["fpga"]["addresses"].append({})
        with self.assertRaises(preflight.PreflightError):
            preflight.audit(observed)

    def test_native_rdma_provider_and_ethernet_layer_required(self):
        for key, value in (("device", "rxe_as02_ref"), ("port", 2), ("bdf", "0000:07:00.0"),
                           ("state", "2: INIT"), ("link_layer", "InfiniBand")):
            with self.subTest(key=key):
                observed = fixture(); observed["rdma"][key] = value
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed)

    def test_gid_must_match_ip_type_and_netdev_without_assumed_slot(self):
        for key, value in (("gid", "::ffff:198.18.11.1"), ("type", "IB/RoCE v1"),
                           ("netdev", "enp7s0"), ("index", 256)):
            with self.subTest(key=key):
                observed = fixture(); observed["rdma"]["gids"][0][key] = value
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed)
        observed = fixture(); observed["rdma"]["gids"] *= 2
        with self.assertRaises(preflight.PreflightError):
            preflight.audit(observed)

    def test_absent_unread_unknown_or_busy_application_cannot_start_test(self):
        app_fixtures = [dict(bar2_present=False, registers_read=False), dict(bar2_present=True, registers_read=False),
                        dict(bar2_present=True, registers_read=True, id=0, version=0),
                        dict(bar2_present=True, registers_read=True, id=0x524F4332, version=0x00010000, status=0x501)]
        for app in app_fixtures:
            with self.subTest(app=app):
                observed = fixture(); observed["application"] = app
                with self.assertRaises(preflight.PreflightError):
                    preflight.audit(observed, require_application=True)
        observed = fixture()
        observed["application"] = dict(bar2_present=True, registers_read=True, id=0x524F4332,
                                        version=0x00010000, status=0x38)
        self.assertTrue(preflight.audit(observed, require_application=True)["application"]["quiescent"])

    def test_read_only_bar_mapping_does_not_write_unknown_application(self):
        mapping = mock.MagicMock()
        with mock.patch.object(preflight.os, "open", return_value=5) as opened, \
                mock.patch.object(preflight.os, "fstat", return_value=mock.Mock(st_size=4096)), \
                mock.patch.object(preflight.os, "close") as closed, \
                mock.patch.object(preflight.mmap, "mmap") as mapped, \
                mock.patch.object(preflight.struct, "unpack_from", side_effect=[(0,), (0,)]) as unpacked:
            mapped.return_value.__enter__.return_value = mapping
            result = preflight.read_application(pathlib.Path("/test-only-device"))
            self.assertNotIn("status", result)
            self.assertEqual(unpacked.call_count, 2)
            self.assertEqual(mapped.call_args.kwargs["prot"], preflight.mmap.PROT_READ)
            self.assertFalse(opened.call_args.args[1] & preflight.os.O_RDWR)
            self.assertFalse(opened.call_args.args[1] & preflight.os.O_WRONLY)
            closed.assert_called_once_with(5)

    def test_bad_pci_identity_stops_collector_before_commands_or_bar_access(self):
        def resolve(path, **_):
            role = "fpga" if "82:00.0" in str(path) else "peer"
            return pathlib.Path("/mock-drivers") / preflight.ROLES[role]["driver"]

        def read(path, **_):
            role = "fpga" if "82:00.0" in str(path) else "peer"
            value = preflight.ROLES[role]["pci"][path.name]
            return hex(value ^ 1 if role == "fpga" and path.name == "vendor" else value)

        run = mock.Mock(side_effect=AssertionError("must not invoke namespace command"))
        with mock.patch.object(pathlib.Path, "resolve", autospec=True, side_effect=resolve), \
                mock.patch.object(pathlib.Path, "read_text", autospec=True, side_effect=read), \
                mock.patch.object(preflight, "read_application") as read_bar:
            with self.assertRaises(preflight.PreflightError):
                preflight.collect(sysfs=pathlib.Path("/mock-sysfs"), run=run, read_app=True)
            run.assert_not_called()
            read_bar.assert_not_called()

    def test_known_application_reads_status_and_closes_on_mapping_failure(self):
        with mock.patch.object(preflight.os, "open", return_value=5), \
                mock.patch.object(preflight.os, "fstat", return_value=mock.Mock(st_size=4096)), \
                mock.patch.object(preflight.os, "close") as closed, \
                mock.patch.object(preflight.mmap, "mmap"), \
                mock.patch.object(preflight.struct, "unpack_from", side_effect=[(0x524F4332,), (0x00010000,), (0x38,)]):
            self.assertEqual(preflight.read_application(pathlib.Path("/test-only-device"))["status"], 0x38)
            closed.assert_called_once_with(5)
        with mock.patch.object(preflight.os, "open", return_value=6), \
                mock.patch.object(preflight.os, "fstat", return_value=mock.Mock(st_size=4096)), \
                mock.patch.object(preflight.os, "close") as closed, \
                mock.patch.object(preflight.mmap, "mmap", side_effect=OSError("mapping refused")):
            with self.assertRaises(OSError):
                preflight.read_application(pathlib.Path("/test-only-device"))
            closed.assert_called_once_with(6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
