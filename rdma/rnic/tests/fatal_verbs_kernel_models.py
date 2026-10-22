# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit Linux/QP-certificate/MMIO models for actual fatal verbs C bodies."""
import segmented_write_kernel_models as parent
from pathlib import Path
once=parent.once;MODEL=parent.MODEL;base=parent.base
ROOT=Path(__file__).resolve().parents[3]


def sq_model():return parent.sq_model()


def verbs_model():
    t=parent.verbs_model()
    t=once(t,'u32 readl(const volatile void *p)','u32 fatal_legacy_readl(const volatile void *p)')
    return once(t,'void writel(u32 value,volatile void *p)','void fatal_legacy_writel(u32 value,volatile void *p)')


def verbs_header():
    t=(ROOT/'rdma/rnic/tests/kernel_verbs_model.h').read_text()
    old='struct ib_qp { struct ib_device *device;struct ib_pd *pd;struct ib_cq *send_cq,*recv_cq;u32 qp_num; };'
    new='''struct ib_event;
struct ib_qp { struct ib_device *device;struct ib_pd *pd;struct ib_cq *send_cq,*recv_cq;u32 qp_num;
    void (*event_handler)(struct ib_event *,void *);void *qp_context; };
enum ib_event_type { IB_EVENT_QP_FATAL=1,IB_EVENT_QP_REQ_ERR=2,IB_EVENT_QP_ACCESS_ERR=3 };
struct ib_event { struct ib_device *device;union {struct ib_qp *qp;}element;enum ib_event_type event; };'''
    return once(t,old,new)
