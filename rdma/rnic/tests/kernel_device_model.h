/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Explicit IB-core/netdev boundary MODEL; never in production module. */
#ifndef AS02_KERNEL_DEVICE_MODEL_H
#define AS02_KERNEL_DEVICE_MODEL_H
#include "kernel_verbs_model.h"
#define IB_PORT_ACTIVE 4
#define IB_PORT_DOWN 1
#define IB_PORT_PHYS_STATE_LINK_UP 5
#define IB_PORT_PHYS_STATE_DISABLED 3
#define IB_MTU_256 1
#define RDMA_CORE_CAP_PROT_ROCE_UDP_ENCAP 0x00800000
#define RDMA_CORE_CAP_ETH_AH 0x00002000
#define RDMA_NODE_IB_CA 1
#define NETREG_REGISTERED 1
#define IB_USER_VERBS_CMD_POST_SEND 28
#define IB_USER_VERBS_CMD_POST_RECV 29
#define IB_USER_VERBS_CMD_POLL_CQ 21
#define IB_USER_VERBS_CMD_REQ_NOTIFY_CQ 23
#define BIT_ULL(n) (1ULL<<(n))
#define cpu_to_be64(x) __builtin_bswap64((u64)(x))
struct net_device { struct device dev;u8 dev_addr[6];u32 mtu,reg_state;bool running,carrier; };
static inline bool ether_addr_equal(const u8 *a,const u8 *b){return !memcmp(a,b,6);}
static inline bool is_valid_ether_addr(const u8 *a){return !(a[0]&1) && (a[0]|a[1]|a[2]|a[3]|a[4]|a[5]);}
static inline bool netif_running(const struct net_device *n){return n->running;}
static inline bool netif_carrier_ok(const struct net_device *n){return n->carrier;}
static inline void dev_hold(struct net_device *n){get_device(&n->dev);}
static inline void dev_put(struct net_device *n){put_device(&n->dev);}
static inline int strscpy(char *d,const char *s,size_t n){snprintf(d,n,"%s",s);return strlen(d);}
struct ib_device *device_model_alloc(size_t);
#define ib_alloc_device(type,member) container_of(device_model_alloc(sizeof(struct type)),struct type,member)
void ib_dealloc_device(struct ib_device *);
int ib_device_set_netdev(struct ib_device *,struct net_device *,u32);
int ib_register_device(struct ib_device *,const char *,struct device *);
void ib_unregister_device(struct ib_device *);
int ib_get_eth_speed(struct ib_device *,u32,u16 *,u8 *);
#endif
