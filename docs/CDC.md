# CDC repair and remaining findings

The original board VIO read six PHY status bits directly in `pcie_user_clk`.
Those signals originate in independent PHY receive clock domains. The repair
adds **six independent two-flop chains (12 registers)** on the PCIe clock:

```text
PHY status bit → metastability stage → synchronized stage → VIO probe
```

The bits are independent status indicators, not an atomic multi-bit payload.
Both stages carry `ASYNC_REG`; only the asynchronous first-stage D pins are
false-pathed. Functional Ethernet logic, second-stage paths and VIO logic
remain timed. The ECO checks that every original non-debug driver/load is
preserved and uses Vivado's supported probe-remapping interface.

The recorded report classifies all six repaired crossings as CDC-3 Info,
depth two. Tcl assertions check stage connectivity and the 4 ns PCIe clock.
The clean RTL expresses the same structure before synthesis, but its fresh
implementation/hardware validation remains a separate open task.

## Remaining Critical CDC structures: 18

These findings were reviewed for the finite experiment, not waived as
universally safe:

1. **One rb_drp payload crossing (CDC-1).** Source write/data/address remain
   stable while a request flag crosses two flops; the destination captures
   after the synchronized flag, and acknowledgement returns through another
   two-flop handshake. Max-delay/bus-skew constraints remain enabled.
2. **Six polarity/inhibit crossings (CDC-1) and four PRBS-selection crossings
   (CDC-4).** These are inherited GT control paths, not packet FIFO data.
   They were left at static defaults during the experiment. Dynamic changes
   need a separate synchronization/protocol review; the test does not qualify
   arbitrary runtime GT reconfiguration.
3. **One reset structure (CDC-10).** An OR of reset sources asynchronously
   asserts a four-stage reset synchronizer, with synchronous release.
4. **Six GTYE4_CHANNEL TXELECIDLE / TXPD hard-pin structures (CDC-13).** These
   are dedicated transceiver controls, not ordinary fabric flip-flops. The
   upstream behavior and constraints were retained.

Review a fresh CDC report for each candidate design. A passing setup/hold
summary does not replace CDC analysis, and an inherited finding is not safe
merely because it existed upstream.

## Timing convergence

The first native implementation failed setup timing, with the direct VIO
crossings among its largest violations. Inserting the synchronizers was a
functional CDC correction, not a timing waiver. The first routed ECO still
failed WNS −0.099 ns; Explore improved this to −0.017 ns. Targeted data-net
rerouting and subsequent AggressiveExplore eventually met the original
native clocks and speed grade. Vivado performed those placement/routing
optimizations; this project does not claim a new physical-design algorithm.
