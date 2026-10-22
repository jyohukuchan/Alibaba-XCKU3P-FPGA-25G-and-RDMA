/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_FATAL_REGS_H
#define AS02_FATAL_REGS_H
/* Explicit optional aperture, NOT a completion-queue or standard verbs ABI.
 * No BAR probing/address assignment, capability advertisement or drain bit.
 */
#define AS02_FEC_ID 0x00U
#define AS02_FEC_ABI 0x04U
#define AS02_FEC_FEATURES 0x08U
#define AS02_FEC_STATUS 0x0cU
#define AS02_FEC_ACK 0x10U
#define AS02_FEC_LAST_ACK 0x14U
#define AS02_FEC_SEQUENCE 0x18U
#define AS02_FEC_FAULT_CODE 0x1cU
#define AS02_FEC_RECORD 0x40U
#define AS02_FEC_WORDS 32U
#define AS02_FEC_BYTES 0xc0U
#define AS02_FEC_ID_VALUE 0x46454331U
#define AS02_FEC_ABI_VALUE 0x00010000U
#define AS02_FEC_FEATURE_VALUE 0x0000000fU
#define AS02_FEC_VISIBLE 1U
#define AS02_FEC_FAULT 2U
#define AS02_FEC_EXHAUSTED 4U
#endif
