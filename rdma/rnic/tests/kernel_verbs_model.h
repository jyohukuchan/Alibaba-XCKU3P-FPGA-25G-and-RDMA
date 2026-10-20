/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Explicit Linux object/API model, never used by production code. */
#ifndef AS02_KERNEL_VERBS_MODEL_H
#define AS02_KERNEL_VERBS_MODEL_H
#define AS02_EXTENDED_IB_QP
#include "kernel_queue_model.h"
struct ib_cq;
struct ib_pd { struct ib_device *device; };
struct ib_qp { struct ib_device *device;struct ib_pd *pd;struct ib_cq *send_cq,*recv_cq;u32 qp_num; };
#include "kernel_cq_model.h"
#undef lockdep_assert_held
/* Both modeled spinlocks and mutexes wrap pthread_mutex_t. Check the exact
 * object is locked, including the new sleepable QP/RRP control MMIO path. */
#define lockdep_assert_held(s) do { assert(pthread_mutex_trylock(&(s)->native)==EBUSY); } while(0)
#define IB_ACCESS_LOCAL_WRITE 1
#define IB_ACCESS_REMOTE_WRITE 2
#define IB_ACCESS_REMOTE_READ 4
enum ib_qp_type { IB_QPT_RC=2 };
enum ib_sig_type { IB_SIGNAL_ALL_WR,IB_SIGNAL_REQ_WR };
enum ib_qp_state { IB_QPS_RESET,IB_QPS_INIT,IB_QPS_RTR,IB_QPS_RTS,IB_QPS_SQD,IB_QPS_SQE,IB_QPS_ERR };
enum ib_mtu { IB_MTU_4096=5 };
#define IB_QP_STATE 1
#define IB_QP_CUR_STATE (1<<1)
#define IB_QP_ACCESS_FLAGS (1<<3)
#define IB_QP_PKEY_INDEX (1<<4)
#define IB_QP_PORT (1<<5)
#define IB_QP_AV (1<<7)
#define IB_QP_PATH_MTU (1<<8)
#define IB_QP_TIMEOUT (1<<9)
#define IB_QP_RETRY_CNT (1<<10)
#define IB_QP_RNR_RETRY (1<<11)
#define IB_QP_RQ_PSN (1<<12)
#define IB_QP_MAX_QP_RD_ATOMIC (1<<13)
#define IB_QP_MIN_RNR_TIMER (1<<15)
#define IB_QP_SQ_PSN (1<<16)
#define IB_QP_MAX_DEST_RD_ATOMIC (1<<17)
#define IB_QP_CAP (1<<19)
#define IB_QP_DEST_QPN (1<<20)
#define RDMA_AH_ATTR_TYPE_ROCE 2
#define IB_AH_GRH 1
#define IB_GID_TYPE_ROCE_UDP_ENCAP 2
union ib_gid { u8 raw[16]; };
struct net_device;
struct ib_gid_attr { union ib_gid gid;struct ib_device *device;u32 port_num,gid_type,index;struct net_device *ndev; };
struct ib_global_route { union ib_gid dgid;const struct ib_gid_attr *sgid_attr;u32 flow_label;u8 traffic_class,hop_limit; };
struct rdma_ah_attr { u32 type,port_num,ah_flags,sl,static_rate;u8 dmac[6];struct ib_global_route grh; };
struct ib_qp_cap { u32 max_send_wr,max_recv_wr,max_send_sge,max_recv_sge,max_inline_data; };
struct ib_qp_init_attr {
    struct ib_cq *send_cq,*recv_cq;void *srq,*xrcd,*rwq_ind_tbl;
    struct ib_qp_cap cap;enum ib_sig_type sq_sig_type;enum ib_qp_type qp_type;
    u32 port_num,source_qpn,create_flags;
};
struct ib_qp_attr {
    enum ib_qp_state qp_state,cur_qp_state;enum ib_mtu path_mtu;struct ib_qp_cap cap;
    struct rdma_ah_attr ah_attr;u32 port_num,dest_qp_num,rq_psn,sq_psn;
    int qp_access_flags;u16 pkey_index;u8 max_dest_rd_atomic,max_rd_atomic,min_rnr_timer;
    u8 timeout,retry_cnt,rnr_retry;
};
struct ib_mr { struct ib_device *device;struct ib_pd *pd;u64 iova,length;u32 lkey,rkey; };
struct ib_dmah { int unused; };
struct ib_ucontext;
struct uverbs_attr_bundle { struct ib_udata driver_udata;struct ib_ucontext *context; };
static inline struct uverbs_attr_bundle *rdma_udata_to_uverbs_attr_bundle(struct ib_udata *u)
{return container_of(u,struct uverbs_attr_bundle,driver_udata);}
static inline u32 rdma_ah_get_port_num(const struct rdma_ah_attr *a) { return a->port_num; }
static inline u32 rdma_ah_get_ah_flags(const struct rdma_ah_attr *a) { return a->ah_flags; }
static inline u32 rdma_ah_get_sl(const struct rdma_ah_attr *a) { return a->sl; }
static inline u32 rdma_ah_get_static_rate(const struct rdma_ah_attr *a) { return a->static_rate; }
static inline u8 *rdma_ah_retrieve_dmac(struct rdma_ah_attr *a) { return a->dmac; }
static inline const struct ib_global_route *rdma_ah_read_grh(const struct rdma_ah_attr *a) { return &a->grh; }
struct ib_uverbs_file;
struct ib_ucontext { struct ib_device *device;struct ib_uverbs_file *ufile; };
struct ib_uverbs_file { struct ib_ucontext *context; };
static inline struct ib_ucontext *ib_uverbs_get_ucontext_file(struct ib_uverbs_file *f)
{return f->context;}
enum rdma_driver_id { RDMA_DRIVER_UNKNOWN };
enum rdma_link_layer { IB_LINK_LAYER_UNSPECIFIED,IB_LINK_LAYER_INFINIBAND,IB_LINK_LAYER_ETHERNET };
enum ib_atomic_cap { IB_ATOMIC_NONE };
struct ib_device_attr {
    u64 fw_ver,sys_image_guid,max_mr_size,page_size_cap,device_cap_flags,kernel_cap_flags;
    u32 vendor_id,vendor_part_id,hw_ver;
    int max_qp,max_qp_wr,max_send_sge,max_recv_sge,max_sge_rd,max_cq,max_cqe,max_mr,max_pd;
    int max_qp_rd_atom,max_res_rd_atom,max_qp_init_rd_atom;
    enum ib_atomic_cap atomic_cap;
    u16 max_pkeys;
};
struct ib_port_attr {
    int state,phys_state,max_mtu,active_mtu,gid_tbl_len;
    u32 phys_mtu,max_msg_sz;u16 pkey_tbl_len,active_speed;u8 active_width;
};
struct ib_port_immutable { int gid_tbl_len,pkey_tbl_len;u32 core_cap_flags,max_mad_size; };
struct ib_device_ops {
    void *owner;
    int (*alloc_pd)(struct ib_pd *,struct ib_udata *);
    int (*dealloc_pd)(struct ib_pd *,struct ib_udata *);
    struct ib_mr *(*reg_user_mr)(struct ib_pd *,u64,u64,u64,int,struct ib_dmah *,struct ib_udata *);
    int (*dereg_mr)(struct ib_mr *,struct ib_udata *);
    int (*create_cq)(struct ib_cq *,const struct ib_cq_init_attr *,struct uverbs_attr_bundle *);
    int (*destroy_cq)(struct ib_cq *,struct ib_udata *);
    int (*poll_cq)(struct ib_cq *,int,struct ib_wc *);
    int (*req_notify_cq)(struct ib_cq *,enum ib_cq_notify_flags);
    int (*create_qp)(struct ib_qp *,struct ib_qp_init_attr *,struct ib_udata *);
    int (*modify_qp)(struct ib_qp *,struct ib_qp_attr *,int,struct ib_udata *);
    int (*post_recv)(struct ib_qp *,const struct ib_recv_wr *,const struct ib_recv_wr **);
    int (*query_qp)(struct ib_qp *,struct ib_qp_attr *,int,struct ib_qp_init_attr *);
    int (*destroy_qp)(struct ib_qp *,struct ib_udata *);
    int (*post_send)(struct ib_qp *,const struct ib_send_wr *,const struct ib_send_wr **);
    size_t size_ib_pd,size_ib_qp,size_ib_cq;
    enum rdma_driver_id driver_id;
    u32 uverbs_abi_ver,uverbs_no_driver_id_binding;
    int (*query_device)(struct ib_device *,struct ib_device_attr *,struct ib_udata *);
    int (*query_port)(struct ib_device *,u32,struct ib_port_attr *);
    int (*get_port_immutable)(struct ib_device *,u32,struct ib_port_immutable *);
    enum rdma_link_layer (*get_link_layer)(struct ib_device *,u32);
    int (*query_pkey)(struct ib_device *,u32,u16,u16 *);
    int (*add_gid)(const struct ib_gid_attr *,void **);
    int (*del_gid)(const struct ib_gid_attr *,void **);
    int (*alloc_ucontext)(struct ib_ucontext *,struct ib_udata *);
    void (*dealloc_ucontext)(struct ib_ucontext *);
    void (*ufile_hw_cleanup)(struct ib_uverbs_file *);
    int (*enable_driver)(struct ib_device *);
    size_t size_ib_ucontext;
};
#define INIT_RDMA_OBJ_SIZE(ib,driver,member) .size_##ib=sizeof(struct driver)
void ib_set_device_ops(struct ib_device *,const struct ib_device_ops *);
#endif
