# RDMA research roadmap

**No RDMA or InfiniBand capability is implemented or claimed today.** A
successful Ethernet NIC test is a foundation, not an RDMA demonstration.
This roadmap is a development proposal, not a committed delivery schedule.

1. Complete clean-RTL build validation, repeat hardware tests, investigate
   MTU1500/retransmission behavior, and add longer bidirectional load tests.
2. Define the intended RDMA scope and choose an implementation only after
   checking its FPGA/tool requirements, resource use, host integration and
   license. No third-party RDMA core is selected by this publication.
3. For a RoCEv2 path, integrate the required packet/state/memory machinery
   and host-facing control/software interface. Ethernet link-up alone is not
   sufficient. Identify supported operations and reliability/error behavior.
4. Demonstrate actual supported RDMA operations against a compatible peer,
   checking data integrity, completion/error semantics and interoperability.
   Report verbs/software requirements, limitations and results explicitly.
5. Treat native InfiniBand as a separate, substantially different project;
   it is not enabled by renaming a RoCEv2/Ethernet build or changing one flag.

Future milestones should carry reproducible tests and precise claims. Do
not advertise an RDMA-capable release until an RDMA engine and corresponding
software/interoperability tests actually exist.
