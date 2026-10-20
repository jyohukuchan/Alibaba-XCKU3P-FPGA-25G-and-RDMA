/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Privileged new SQ mailbox ABI; NOT present in the old deployed image.
 * Mapped only by the source/offline rocev2_native_sq_endpoint at0x402000.
 * Not selected by the deployed mqnic parent/image, driver or provider.
 * This is control/fetch only, NOT local payload execution/CQ/verbs support.
 */
#ifndef AS02_SQ_REGS_H
#define AS02_SQ_REGS_H
#define AS02_SQC_ID_VALUE 0x53514331U
#define AS02_RQC_ID_VALUE 0x52514331U
#define AS02_SQC_ABI_VALUE 0x00010000U
#define AS02_SQC_BYTES 0x1000U
#define AS02_SQC_ID 0x000U
#define AS02_SQC_ABI 0x004U
#define AS02_SQC_FEATURES 0x008U
#define AS02_SQC_STATUS 0x00cU
#define AS02_SQC_DOORBELL 0x010U
#define AS02_SQC_REPLY_ACK 0x014U
#define AS02_SQC_CLEAR_ERROR 0x018U
#define AS02_SQC_LAST_SEQUENCE 0x01cU
#define AS02_SQC_STAGE 0x040U
#define AS02_SQC_REPLY 0x100U
#define AS02_SQC_REPLY_ERROR 0x13cU
#define AS02_SQC_REPLY_FLAGS 0x140U
#define AS02_SQC_REPLY_CONSUMER_LO 0x144U
#define AS02_SQC_REPLY_CONSUMER_HI 0x148U
#define AS02_SQC_WORDS 15U
#define AS02_SQC_AVAILABLE 0x01U
#define AS02_SQC_RESPONSE 0x02U
#define AS02_SQC_FATAL 0x04U
#define AS02_SQC_MMIO_ERROR 0x08U
#define AS02_SQC_ENDPOINT_FAULT 0x10U
#define AS02_SQC_EXHAUSTED 0x20U
#define AS02_SQC_ALLOC_FLAGS 0x07U
#define AS02_SQC_RETIRE_FLAGS 0x1fU
#define AS02_RQC_CANCEL_FEATURE 0x02U
#define AS02_SQC_IMMEDIATE_FEATURE 0x04U
#define AS02_SQC_IMMEDIATE_FEATURE_VALUE (1U|AS02_SQC_IMMEDIATE_FEATURE)
#define AS02_RQC_IMMEDIATE_FEATURE_VALUE (1U|AS02_RQC_CANCEL_FEATURE|AS02_SQC_IMMEDIATE_FEATURE)
#define AS02_RQC_CANCEL_FLAGS 0x3fU
/* Stage/reply words: sequence,command(1allocate/2publish/3retire),QPN,PD,
 * epoch64,cookie64,DMA64,log_depth,producer64,retire_request_nonce64.
 * All values complete little-endian32-bit MMIO words, low word first.
 * Fields are full-width checked BEFORE narrowing. Nonzero cookie/epoch;
 * rings2..256x64bytes, DMA64aligned64, exclusive end2^64legal.
 * Each DOORBELL writes exact staged sequence, full strobes. Sequence must
 * equal previous+1 and never wrap; snapshot immutable until exact reply ACK.
 * ACK is NOT CQ acknowledgement, DMA cancellation, MR unpin or reset proof.
 * Known semantic rejection has reply error/flags0; malformed/busy/partial/
 * duplicate bell/ACK accesses set sticky MMIO_ERROR, never mutate queues.
 * CLEAR_ERROR requires write1/full strobes and IDLE, never clears fatal.
 * Check ID/ABI/status, exact sequence/complete reply owner/layout/nonce,
 * error and required proof flags before acting. B completion alone is NOT
 * successful publication. Timeout/error after bell is potentially posted:
 * retain ring/MR/WR ownership until actual fresh source-bound recovery proof.
 * Producer increment is exactly1; fetch consumer/result NEVER retires a WR.
 * Allocation flags reflect actual empty/active/parent-safe acceptance.
 * Retire flags require actual invalidation AND captured parent/fetch/work/
 * wire/completion drain, exact final producer and fresh request nonce.
 * Actual fetcher's downstream guard MUST OR work|wire|completion guards;
 * otherwise post-capture guard changes could bypass its admission checks.
 * Those guards and parent proof are real hardware caller responsibilities.
 */
#endif
