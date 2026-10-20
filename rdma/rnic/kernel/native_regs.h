/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* NEW native profile map, never write this ABI to the old deployed image. */
#ifndef AS02_NATIVE_REGS_H
#define AS02_NATIVE_REGS_H
#define AS02_NATIVE_RW_BASE 0x000000U
#define AS02_NATIVE_RW_BYTES 0x100000U
#define AS02_NATIVE_CONTROL_BASE 0x400000U
#define AS02_NATIVE_CONTROL_BYTES 0x1000U
#define AS02_NATIVE_ETH_BASE 0x401000U
#define AS02_NATIVE_ETH_BYTES 0x1000U
/* Only rocev2_native_sq_endpoint exposes this control-only SQC1 region.
 * The original native/deployed image still DECERRs here; probe ID/ABI first.
 * A mapped SQ CSR is NOT local payload execution, a CQ, or verbs support.
 */
#define AS02_NATIVE_SQ_BASE 0x402000U
#define AS02_NATIVE_SQ_BYTES 0x1000U
#define AS02_NATIVE_RETRY_BASE 0x404000U
#define AS02_NATIVE_RQ_BASE 0x405000U
#define AS02_NATIVE_RQ_BYTES 0x1000U
#define AS02_ETH_ID_VALUE 0x524e4531U
#define AS02_ETH_ABI_VALUE 0x00010000U
#define AS02_ETH_ID 0x00U
#define AS02_ETH_ABI 0x04U
#define AS02_ETH_STATUS 0x08U
#define AS02_ETH_EPOCH 0x0cU
#define AS02_ETH_COMMIT 0x10U
#define AS02_ETH_CLEAR_ERROR 0x14U
#define AS02_ETH_LAST_ERROR 0x18U
#define AS02_ETH_STAGE 0x20U
#define AS02_ETH_ACTIVE 0x40U
#define AS02_ETH_WORDS 6U
#define AS02_ETH_ST_ENABLED (1U << 0)
#define AS02_ETH_ST_SAFE (1U << 1)
#define AS02_ETH_ST_ERROR (1U << 2)
#define AS02_ETH_ST_COMMITTED (1U << 3)
#define AS02_ETH_ST_EXHAUSTED (1U << 4)
/* Stage/active order: local MAC low32/high16, peer MAC low32/high16,
 * numeric network-order local IPv4, enable(0/1). High/reserved bits must0.
 * Peer IP/QP/PD are authorized by the independent protected-QP mailbox.
 * COMMIT and CLEAR require full strobes and write1. COMMIT only at SAFE,
 * changes all fields atomically and increments a nonwrapping route epoch.
 * A rejected COMMIT leaves active fields unchanged. Sticky error may come
 * from another access: always check epoch and active readback as well.
 * CLEAR is not DMA cancellation, reset, MR revocation or page-release proof.
 */
#endif
