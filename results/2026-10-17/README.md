# Recorded evidence

These are selected/derived records of the **2026-10-17 ECO experiment**,
not outputs of a new build or test of this publication.

- `tcp-summary.json`: aggregates and test parameters extracted from four
  original iperf3 client JSON records. Cookie/endpoint/host details and
  per-interval data are intentionally not copied.
- `ping-summary.txt`: transmitted/received/loss and RTT lines from eight
  ordinary/full-MTU ping logs and two 100-ping logs. Documentation/test-network
  endpoints are not host management addresses.
- `temperature-samples.txt`: the 112 recorded per-second temperature readings.
- `timing-summary-excerpt.rpt`: the beginning of the final timing summary,
  including the tool's cached-methodology warning and complete design summary.
- `route-status.rpt`: final route counts.
- `drc-summary-excerpt.rpt`: final DRC summary (26 warnings, no Error/Critical).
- `cdc-summary-excerpt.rpt`: final selected CDC summary, including inherited
  Critical/Warning classifications; not a claim of zero CDC findings.
- `bus-skew-slacks-excerpt.rpt`: header and all 38 final bus-skew slack lines.

Local paths/hostnames in report excerpts are redacted, and trailing formatting
spaces may be normalized. Tool copyright notices are retained. Reports are
not a redistribution of vendor IP, bitstreams or implementation checkpoints.
See [results and limitations](../../docs/RESULTS.md).
