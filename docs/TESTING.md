# Optional finite traffic test

`scripts/benchmark_25g.sh` is an **adapted publication helper**, not an unchanged
copy of the script used for the recorded results. Its syntax and refusal paths
are checked; its new parameterization has **not** been run against hardware.
It does not program the FPGA, create namespaces, load drivers, reset PCIe,
change FEC/speed or configure your peer for you.

## Before starting

- Complete the safety checks in [HARDWARE.md](HARDWARE.md).
- Prepare two dedicated network namespaces with the intended physical FPGA
  and ConnectX interfaces already inside them. Do not use a management path.
- Configure the test addresses, routes, 25G speed, FEC off and AN off yourself.
- Build mqnic utilities separately. Verify which `/dev/mqnic*` device and
  clock-counter channels correspond to the connected FPGA port.
- Review `scripts/test_config.example.sh` and set each variable explicitly.
  It contains placeholders, not device addresses from the original host.
- Ensure sufficient cooling and **active independent temperature monitoring**.
  This traffic helper has no thermal cutoff. The historical guard was a
  separate temporary supervisor and is not included as an automatic guarantee.
- Install iproute2, ethtool, iperf3, jq, awk, grep, ripgrep and coreutils.
  USB/root access may require `sudo -n` authorization.

For an already reviewed, isolated setup:

```bash
source scripts/test_config.example.sh  # first adapt its placeholders
AS02_ALLOW_TRAFFIC_TEST=YES bash scripts/benchmark_25g.sh
```

The helper verifies namespace/interface driver and PCIe BDF associations,
checks peer speed/link and FPGA native clock counters, then generates bounded
traffic. It **changes both test interfaces' MTUs to 1500 and 9000** and attempts
to restore their original MTUs on exit. A crash, forced kill or loss of sudo
access can prevent restoration; inspect the interfaces afterwards.

It runs ordinary and DF full-MTU pings in each direction, then iperf3 with four
TCP streams, 20 measured seconds and three omitted seconds, first one way and
then the other. It rejects changes in the four selected peer PHY error counters
and saves logs under ignored `logs/`. Passing this finite test does not prove
zero loss, simultaneous full-duplex line rate or RDMA support.

Raw logs can contain interface addresses, serials or host information. Review
and redact them before publication; do not commit a working directory wholesale.
