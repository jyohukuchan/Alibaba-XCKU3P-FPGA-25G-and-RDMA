# Native protected READ/WRITE: 2026-10-18 UTC

The FPGA now initiates IPv4 RoCEv2 RC READ against native CX455A registered
memory, stores returned data in protected FPGA-local BRAM, and exposes it
through the version2 application BAR2. No software RXE endpoint or TCP payload
copy substitutes for the FPGA READ. Existing acknowledged WRITE also passes
on this same combined image.

## Verified finite cases

| Operation | Bytes per operation | Count | READ window | Payload bytes compared | Extra sentinel bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| READ | 1 | 1 | 1 | 1 | 127 |
| READ | 65 | 3 | 1 | 195 | 253 |
| READ | 4097 | 3 | 1 | 12291 | 253 |
| READ | 8193 | 3 | 2 | 24579 | 253 |
| READ | 65536 | 4 | 2 | 262144 | 0 |
| READ | 4096 | 64 | 2 | 262144 | 0 |
| READ | 1 | 4096 | 2 | 4096 | 258048 |
| READ after configuration error/CLEAR | 65 | 1 | 1 | 65 | 127 |
| WRITE | 65 | 3 | — | 195 | — |
| WRITE | 4096 | 3 | — | 12288 | — |

All byte mismatches are zero. All cases except the first start at PSN
`0xfffffe`; multi-operation/segmented cases exercise24-bit wrap. PMTU is4096:
4097/8193-byte responses use2/3packets per operation;65536bytes x4 uses64.
The two exact-full-buffer cases have no extra sentinel bytes because all
256KiB are payload; other cases independently cover tail/padding protection.

Each READ peer obtains a fresh32-byte kernel nonce, derives a non-repeating
SHAKE256 source, registers a REMOTE_READ-only MR on mlx5_0/CX455A and checks
the entire source stayed unchanged. The FPGA RAM is complement-prefilled;
the host compares every returned payload byte and every allocated sentinel
through actual32-bit PCIe BAR reads, not just completion counters/digests.
TCP transports endpoint/nonce metadata and controls, never source payload.
The8READ cases verify565515payload bytes and259061sentinel bytes; the2WRITE
cases verify12483receiver bytes. No sustained benchmark was run.

The error probe advertises a one-byte-short source range while retaining
the actual full source MR/QP. Hardware reports quiet ERR_CONFIG=1 with no
READ issued/captured; app-local CLEAR retains ownership, then a valid READ
passes without a global/NIC reset. Final run generation is11 (10valid runs
plus1rejected configuration), terminal WRITE DONE/core-reset/TX-quiescent.
Owned peers/controllers/thermal readers are stopped and control port18516
is free. [Native records](../results/2026-10-18/rocev2-rw-native-001.json)
link each case's client/peer/preflight/thermal evidence and raw hashes.

## Exact physical and programming identity

Tested combined bitstream SHA256:

```text
226c48c7756f311d511798c42435a438f20228eb313b909553638b12c3a58e0a
```

Build `as02mc04-25g-rw-g9gbomFJ` uses Vivado2025.2,
`xcku3p-ffvb676-1-e`, the READ-capable138-file HLS aggregate
`7bcfddc9cb856060ccc3fbe4c8599538a03bf16105176b44f737c22fb0be55ff`
and a766-line/600-unique-input manifest. The original full native25 gate,
constraints and implementation strategy are retained, without underclocking.

- Final setup WNS+0.052ns, hold WHS+0.010ns; no failing setup/hold/pulse endpoints.
- All206064routable nets fully routed, zero routing errors.
- All38bus skews met; minimum slack+1.743ns. All12check-timing categories zero.
- All four GT TX/RX clocks are2.560ns. DRC has0Error/0Critical,35ordinary warning checks.
- Final utilization:87761/162720LUTs,139029/325440registers,
  226/360BRAM tiles,39/48URAM,3/1368DSPs.

Separate read-only routed CDC/PHY inspections verify6VIO two-stage pairs,
4LFC chains/8destination registers,2GT asynchronous-control mode pins,
22static PHY bits,4reset stages and24scoped max-delay paths (minimum
slack+7.219ns). The18Critical CDC rows exactly match accepted WRITE003,
including clock pairs and endpoints. This is a conditional operating review,
not an unconditional CDC safety claim or a blanket waiver: keep PHY/DRP/
polarity/PRBS/PLL/rate/clocks stable during communication; no reprogramming,
PCIe hotplug/reset or Hardware Manager concurrently. Only the validated
read-only SYSMON JTAG sensor is permitted during tests.

The [static record](../results/2026-10-18/rocev2-rw-board-build-001.json)
is separate from [SRAM bringup](../results/2026-10-18/rocev2-rw-sram-bringup-001.json)
and native proof. Only the audited FPGA endpoint82:00.0 and its exclusive
80:03.0bridge were removed/rescanned on this host. Flash was not touched.
Management address/routes/MAC/MTU/flags are unchanged; unrelated devices and
CX455A mode were not reset or reconfigured. Do not copy these BDFs to another PC.
Accepted WRITE003 (`ce515167...`) remains an unmodified rollback artifact.
Endpoint and exclusive-bridge PCIe reports are identical immediately after
programming and after native tests. The root port retains historical sticky
Fatal/Surprise-Down/lane status with root error reporting disabled; no zero-
error/full-platform-health claim is inferred from Linux AER totals.

All10native cases ran under the validated85°Cstart/90°Cstop thermal guard:
20one-second samples,53.59..56.07°C, no over-temperature. Post-test current
samples were56.60..56.86°C. Read-only BIOS token query confirms Medium
remains active. These short samples do not qualify continuous-load cooling.

## Use on the existing audited host

See [the BAR API](ROCEV2_RW_API.md), [host tools](../rdma/read/host/README.md)
and [separate READ/WRITE build](../rdma/read/README.md). With the reviewed
image already loaded, dedicated link/namespaces restored and no other JTAG
client, one finite all-byte checked READ can be run from the repository root:

```sh
make -C rdma/read/host
AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES \
AS02_PHYSICAL_REVIEW_COMPLETE=YES \
AS02_TEMPERATURE_GUARD=/home/user/fpga-25gbe/diagnostics/run_with_temperature_guard.sh \
PYTHONDONTWRITEBYTECODE=1 \
  python3 rdma/read/host/native_rw_test.py --operation read \
    --message-bytes 4097 --count 3 --read-window 1 --psn 0xfffffe
```

The opt-ins attest prior physical/programming review; they do not prove an
arbitrary image safe. The tool also audits actual native provider/GID/BAR
ownership, pins the thermal reader and stops only its owned children.
Use `--probe-config-error` for the finite error/CLEAR/valid-READ sequence.
Use `--operation write` for the retained bounded-pattern WRITE path.

Capacity is256KiB, size1..65536bytes, count1..4096, with
`ceil(size/64)*64*count <=262144`. Compiled resource windows are1..32 and
must fit the actual peer's negotiated resources; native windows1and2 were
verified. This is a custom bounded experimental initiator, not a generic
FPGA libibverbs driver, inbound SEND/WRITE target, READ responder, arbitrary
host-memory DMA, IPv6/InfiniBand implementation or production qualification.
SRAM configuration is volatile. Historical WRITE003 throughput/retry claims
are not claims about this new image. Changes remain local; no commit/push
was performed as part of this READ implementation.
