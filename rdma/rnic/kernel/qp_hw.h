/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_QP_HW_H
#define AS02_QP_HW_H
#include "rnic_hw.h"
#include "sq.h"
#include "retry_io.h"

struct as02_qp_route {
    u32 qpn, pd, peer_qpn, local_ip, peer_ip, rx_psn, tx_psn;
};
/* The current protected responder has ONE connection context, not an
 * eight-entry QP table. Serialize it, and never advertise eight live QPs.
 * PD zero is reserved for a drained, inaccessible tombstone: no MR or SQ
 * created by verbs may use it. STOP alone does not revoke the old context.
 */
struct as02_qp_hw {
    struct as02_rnic_hw *control;
    struct as02_qp_route owner;
    struct as02_retry_io retry;
    void __iomem *retry_registers;
    u64 next_cookie;
    bool initialized, owned, uncertain;
};
int as02_qp_hw_init(struct as02_qp_hw *, struct as02_rnic_hw *);
int as02_qp_hw_open(struct as02_qp_hw *, const struct as02_qp_route *);
int as02_qp_hw_set_tx(struct as02_qp_hw *, u32 qpn, u16 pd, u32 tx_psn);
/* Privileged parent supplies the EXACT bounded new RRP1 aperture. Optional:
 * old firmware keeps rejecting mandatory RC retry attributes. No BAR probe,
 * registration or hardware programming is initiated by these library APIs.
 */
int as02_qp_hw_enable_retry(struct as02_qp_hw *, void __iomem *, size_t, u32);
int as02_qp_hw_set_retry(struct as02_qp_hw *, const struct as02_sq_handle *, u8, u8, u8);
/* On ANY error keep QP/PD/SQ/context references. No timeout/reset substitute
 * for the actual STOP + configuration + parent/core drain replies.
 */
int as02_qp_hw_close(struct as02_qp_hw *, u32 qpn, u16 pd);
#endif
