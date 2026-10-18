# Native version2 READ/WRITE tools

These tools have verified8finite native FPGA READ cases and2same-image WRITE
regressions on the reviewed SRAM-loaded version2 image, including full256KiB
BAR readback and error/CLEAR recovery. See [the results/use guide](../../../docs/ROCEV2_READ_RESULTS.md).
The preserved WRITE003 image is version1: new clients must still refuse it.
A passing board build, conditional CDC review and inspected SRAM programming
must precede native testing of any different image.

## Components

- `rc_read_peer.c`: native CX455A responder restricted to mlx5_0 /
 0000:03:00.0 on198.18.10.1. Registers one REMOTE_READ-only source MR and
  grants the requested bounded responder resources. It posts no SEND,
  WRITE or READ work requests; the RNIC handles FPGA READ requests.
- `fpga_rw_client.py`: original audited PCI identity/shared lock, strict
  version2/capture layout checks and32-bit UC BAR accesses. READ verifies
  completions AND RAM commit/authorization/chunk counters, then reads and
  compares every payload and sentinel byte. WRITE retains the original
  pattern-source protocol/receiver verification with exclusive mode0.
- `native_rw_preflight.py`: read-only audit of the existing dedicated
  namespaces, PCI BDFs, native provider, GID,25G/FEC and version2 ownership.
  It never creates a QP, sends packets, probes capture RAM, resets hardware,
  or changes network/fan state. BAR reads require appropriate OS privileges.
- `native_rw_test.py`: one finite guarded native operation, scoped child
  cleanup, source/BAR/provider cross-checks and exclusive evidence files.
  Only the successful outer thermal supervisor can claim a native result;
  worker records alone remain temperature-pending and not hardware-verified.

## Independent nonce data and control protocol

Every peer process obtains a fresh32-byte nonce with kernel `getrandom`.
Synthetic source bytes are:

```text
SHAKE256(nonce || uint32_be(message_bytes) || uint32_be(message_count), total_bytes)
```

The peer fills its registered source and retains an independent comparison
copy. The client derives its expected reference from the nonce, prefills
each RAM payload byte with its complement and leaves0xa5slot/guard sentinels.
TCP never transports source payload bytes; it exchanges a256-byte ASCII/NUL
endpoint record and one-byte readiness/completion controls. Data acquisition
is the actual FPGA RDMA READ; final validation is actual BAR RAM readback.

The READ endpoint record is:

```text
AS02RD2 qpn_hex psn_hex rkey_hex address_hex size_decimal count_decimal gid_hex32 nonce_hex64 resources_decimal\n
```

It is padded to256bytes with NULs. Fixed widths, zero padding, GID/IP,
size/count,64-bit range and read-resource limits are checked. The FPGA
endpoint exports rkey/address0; it is not a public READ responder MR.
The peer sends`R`after native QP setup. Client`R`arms the finite run;
client`D`means DONE/quiescence and all BAR bytes verified. A quiesced failed
client may send`A`, never substitute it for success. Peer`P`means its entire
source stayed unchanged; an abort still exits as a failed transfer.

## Offline use

Dependencies are the already installed libibverbs and OpenSSL libcrypto.
Compilation/self-tests do not access devices or require root:

```sh
make -C rdma/read check-native-host
```

The C/Python source generator is checked byte-for-byte. Models exercise
1/65/4097-byte operations and the complete256KiB capture extent, wrong
versions/owners, malformed endpoints, resource limits, incomplete counters,
unwritten/stale/tail/sentinel data, readiness failures and bounded abort.

## Live safety contract

Do not enable these flags until physical/CDC review and the inspected SRAM
programming step have actually completed. They are operator attestations,
not automatic proof of installed image identity or timing. The supervising
tool additionally pins the previously validated temperature guard and
read-only JTAG sensor profile, retaining85Cstart /90Cstop limits.

A finite test invocation on the already audited dedicated test host has this form:

```sh
AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES \
AS02_PHYSICAL_REVIEW_COMPLETE=YES \
AS02_TEMPERATURE_GUARD=/absolute/path/to/validated/run_with_temperature_guard.sh \
python3 rdma/read/host/native_rw_test.py --operation read \
  --message-bytes 4097 --count 3 --psn 0xfffffe
```

The default read window is1; larger windows must fit actual peer resources.
The helper refuses an existing control listener and stops only child handles
it created. No persistent communication, RXE setup, flash write, fan change,
interface/route alteration, global reset or FPGA programming is performed.
The result explicitly distinguishes operator-attested physical review from
automatically checked native data/provider/thermal evidence.

For a finite error/recovery case, append `--probe-config-error` to a READ
invocation. While retaining the same BAR lock and peer MR/QP lease, the
client advertises a source range one byte shorter than required. It demands
quiescent ERR_CONFIG=1, zero issued/authorized/captured operations and no
transport progress. It then issues app-local CLEAR (not a global/NIC reset),
checks that generation and cumulative RoCE TX/completion counters did not
change during CLEAR, restores the full range and performs the normal READ
with all BAR payload/sentinel bytes compared. Two fresh run generations are
required; a failed rejection cannot be counted as a passing READ.

The recovery path has separate host-tool negative-control tests and an
actual generated-HLS/combined-app RTL probe (`tests/probe_rw_recovery.py`).
Neither replaces physical/native verification. After physical review and
SRAM bringup, the finite native matrix should include1/65-byte tails,
4097/8193-byte segmented responses, multiple operations with PSN wrap,
65536bytes x4 (the full256KiB), a resource-window case, this error/CLEAR
recovery case, and the original all-byte native WRITE regression. No
persistent throughput run is needed or authorized by these tools.
