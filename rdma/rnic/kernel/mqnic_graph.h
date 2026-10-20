/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_MQNIC_GRAPH_H
#define AS02_MQNIC_GRAPH_H
#include "native_graph.h"
struct auxiliary_device;
/* Actual pinned-mqnic auxiliary-to-native adapter, not a registered probe.
 * Default-denied load-time enable_native_attach gate BEFORE private layout.
 * Even opt-in is not proof: caller must establish exact loaded parent/header,
 * physical native readiness, persistent epochs and stable BAR/netdev lifetime.
 * Caller must check graph_close SUCCESS before the parent unmaps its BAR.
 * Do NOT insert this in a void remove callback that cannot honor EBUSY.
 */
int as02_mqnic_native_open(struct auxiliary_device *, struct as02_native_lease *,
                          struct as02_native_graph **);
#endif
