/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Experimental rdma-core50/PABI34 provider for the actual native kernel
 * queues. Every operation uses standard uverbs commands. No user BAR mmap,
 * DMA-address exposure, synthetic completions or CPU payload-copy transport.
 * Build/test only; do not install before native/bus/lifetime qualification.
 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <infiniband/driver.h>

#define AS02_ABI 1U
#define AS02_FW (((uint64_t)0x10000<<32)|511U)
#define AS02_FW_IMMEDIATE (((uint64_t)0x10000<<32)|1023U)
struct as02_context { struct verbs_context base; };

static int query_device(struct ibv_context *c, const struct ibv_query_device_ex_input *in,
                        struct ibv_device_attr_ex *a, size_t bytes)
{
    struct ib_uverbs_ex_query_device_resp r={};size_t size=sizeof(r);
    int error=ibv_cmd_query_device_any(c,in,a,bytes,&r,&size);
    if(!error)snprintf(a->orig_attr.fw_ver,sizeof(a->orig_attr.fw_ver),"%08" PRIx32 ".%08" PRIx32,
        (uint32_t)(r.base.fw_ver>>32),(uint32_t)r.base.fw_ver);
    return error;
}
static int query_port(struct ibv_context *c,uint8_t port,struct ibv_port_attr *a)
{ struct ibv_query_port q={};return ibv_cmd_query_port(c,port,a,&q,sizeof(q)); }
static struct ibv_pd *alloc_pd(struct ibv_context *c)
{
    struct ibv_pd *p=calloc(1,sizeof(*p));struct ibv_alloc_pd q={};
    struct ib_uverbs_alloc_pd_resp r={};int error;
    if(!p)return NULL;
    error=ibv_cmd_alloc_pd(c,p,&q,sizeof(q),&r,sizeof(r));
    if(error){free(p);errno=error;return NULL;}return p;
}
static int dealloc_pd(struct ibv_pd *p)
{ int error=ibv_cmd_dealloc_pd(p);if(!error)free(p);return error; }
static struct ibv_mr *reg_mr(struct ibv_pd *p,void *address,size_t bytes,uint64_t iova,int access)
{
    struct verbs_mr *m=calloc(1,sizeof(*m));struct ibv_reg_mr q={};
    struct ib_uverbs_reg_mr_resp r={};int error;
    if(!m)return NULL;
    error=ibv_cmd_reg_mr(p,address,bytes,iova,access,m,&q,sizeof(q),&r,sizeof(r));
    if(error){free(m);errno=error;return NULL;}return &m->ibv_mr;
}
static int dereg_mr(struct verbs_mr *m)
{ int error=ibv_cmd_dereg_mr(m);if(!error)free(m);return error; }
static struct ibv_cq *create_cq(struct ibv_context *c,int entries,struct ibv_comp_channel *channel,int vector)
{
    struct ibv_cq *cq=calloc(1,sizeof(*cq));struct ibv_create_cq q={};
    struct ib_uverbs_create_cq_resp r={};int error;
    if(!cq)return NULL;
    error=ibv_cmd_create_cq(c,entries,channel,vector,cq,&q,sizeof(q),&r,sizeof(r));
    if(error){free(cq);errno=error;return NULL;}return cq;
}
static int destroy_cq(struct ibv_cq *cq)
{ int error=ibv_cmd_destroy_cq(cq);if(!error)free(cq);return error; }
static struct ibv_qp *create_qp(struct ibv_pd *p,struct ibv_qp_init_attr *a)
{
    struct ibv_qp *qp=calloc(1,sizeof(*qp));struct ibv_create_qp q={};
    struct ib_uverbs_create_qp_resp r={};int error;
    if(!qp)return NULL;
    error=ibv_cmd_create_qp(p,qp,a,&q,sizeof(q),&r,sizeof(r));
    if(error){free(qp);errno=error;return NULL;}return qp;
}
static int destroy_qp(struct ibv_qp *qp)
{ int error=ibv_cmd_destroy_qp(qp);if(!error)free(qp);return error; }
static int modify_qp(struct ibv_qp *qp,struct ibv_qp_attr *a,int mask)
{ struct ibv_modify_qp q={};return ibv_cmd_modify_qp(qp,a,mask,&q,sizeof(q)); }
static int query_qp(struct ibv_qp *qp,struct ibv_qp_attr *a,int mask,struct ibv_qp_init_attr *initial)
{ struct ibv_query_qp q={};return ibv_cmd_query_qp(qp,a,mask,initial,&q,sizeof(q)); }
static void free_context(struct ibv_context *c)
{
    struct as02_context *a=container_of(verbs_get_ctx(c),struct as02_context,base);
    verbs_uninit_context(&a->base);free(a);
}
static const struct verbs_context_ops as02_context_ops={
    .query_device_ex=query_device,.query_port=query_port,
    .alloc_pd=alloc_pd,.dealloc_pd=dealloc_pd,.reg_mr=reg_mr,.dereg_mr=dereg_mr,
    .create_cq=create_cq,.destroy_cq=destroy_cq,.poll_cq=ibv_cmd_poll_cq,
    .req_notify_cq=ibv_cmd_req_notify_cq,.create_qp=create_qp,.modify_qp=modify_qp,
    .query_qp=query_qp,.destroy_qp=destroy_qp,.post_send=ibv_cmd_post_send,
    .post_recv=ibv_cmd_post_recv,.free_context=free_context,
};
static struct verbs_context *alloc_context(struct ibv_device *device,int fd,void *private_data)
{
    struct as02_context *c;
    struct ibv_get_context q={};struct ib_uverbs_get_context_resp r={};
    struct ibv_device_attr_ex a={};struct ib_uverbs_ex_query_device_resp response={};
    size_t bytes=sizeof(response);int error;
    (void)private_data;
    c=verbs_init_and_alloc_context(device,fd,c,base,RDMA_DRIVER_UNKNOWN);
    if(!c)return NULL;
    error=ibv_cmd_get_context(&c->base,&q,sizeof(q),&r,sizeof(r));
    if(!error)error=ibv_cmd_query_device_any(&c->base.context,NULL,&a,sizeof(a),&response,&bytes);
    /* The name/PCI match alone is not authority to use native queues. The
     * actual kernel must expose the exact ABI/profile before any objects.
     */
    if(!error && (a.orig_attr.vendor_id!=0x1234 || a.orig_attr.vendor_part_id!=0x1001 ||
        (response.base.fw_ver!=AS02_FW && response.base.fw_ver!=AS02_FW_IMMEDIATE) ||
        a.orig_attr.max_sge!=1 || a.orig_attr.max_qp!=1))
        error=EPROTONOSUPPORT;
    if(error){verbs_uninit_context(&c->base);free(c);errno=error;return NULL;}
    verbs_set_ops(&c->base,&as02_context_ops);return &c->base;
}
static struct verbs_device *alloc_device(struct verbs_sysfs_dev *s)
{ (void)s;return calloc(1,sizeof(struct verbs_device)); }
static void uninit_device(struct verbs_device *d){free(d);}
static bool match_device(struct verbs_sysfs_dev *s)
{
    return s && s->match && s->match->kind==VERBS_MATCH_PCI &&
        s->match->vendor==0x1234 && s->match->device==0x1001 &&
        s->driver_id==RDMA_DRIVER_UNKNOWN && s->abi_ver==AS02_ABI &&
        !strncmp(s->ibdev_name,"as02_",5);
}
static const struct verbs_match_ent matches[]={VERBS_PCI_MATCH(0x1234,0x1001,NULL),{}};
static const struct verbs_device_ops as02_device_ops={
    .name="as02",.match_min_abi_version=AS02_ABI,.match_max_abi_version=AS02_ABI,
    .match_table=matches,.match_device=match_device,.alloc_device=alloc_device,
    .uninit_device=uninit_device,.alloc_context=alloc_context,
};
PROVIDER_DRIVER(as02,as02_device_ops);
