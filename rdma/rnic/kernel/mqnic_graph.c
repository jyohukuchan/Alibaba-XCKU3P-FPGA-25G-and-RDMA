/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/auxiliary_bus.h>
#include <linux/module.h>
#include <linux/pci.h>
#include <mqnic.h>
#include "mqnic_graph.h"

static bool enable_native_attach;
module_param(enable_native_attach, bool, 0400);
MODULE_PARM_DESC(enable_native_attach, "Allow explicit native graph attachment AFTER exact parent/header, physical/native/epoch and parent-lifetime qualification; NOT an automatic probe");

int as02_mqnic_native_open(struct auxiliary_device *adev, struct as02_native_lease *lease,
                          struct as02_native_graph **out)
{
    struct mqnic_adev *app;
    struct mqnic_dev *parent;
    struct mqnic_if *interface;
    struct as02_native_binding b={};
    int ret;
    if(!enable_native_attach)return -EACCES;
    if(!adev || !lease || !out || *out)return -EINVAL;
    app=container_of(adev,struct mqnic_adev,adev);parent=app->mdev;
    if(!parent || !parent->pdev || parent->dev!=&parent->pdev->dev)return -ENODEV;
    b.identity=(struct as02_native_parent){
        .vendor=parent->pdev->vendor,.device=parent->pdev->device,
        .subvendor=parent->pdev->subsystem_vendor,.subdevice=parent->pdev->subsystem_device,
        .app_id=parent->app_id,.mapped=!!parent->app_hw_addr,.bar_bytes=parent->app_hw_regs_size};
    ret=as02_native_parent_validate(&b.identity);if(ret)return ret;
    /* This reviewed native image uses interface0/data port0 only. Do not
     * attach a different NIC/netdev or infer a lower-bit register alias.
     */
    if(!parent->if_count || parent->if_count>MQNIC_MAX_IF)return -ENODEV;
    interface=parent->interface[0];
    if(!interface || interface->mdev!=parent || !interface->ndev_count ||
       interface->ndev_count>MQNIC_MAX_PORTS || !interface->ndev[0] ||
       interface->ndev[0]->dev.parent!=parent->dev)return -ENODEV;
    b.parent=parent->dev;b.data_netdev=interface->ndev[0];
    b.application_bar=parent->app_hw_addr;b.application_bytes=parent->app_hw_regs_size;
    return as02_native_graph_open(&b,lease,out);
}
EXPORT_SYMBOL_GPL(as02_mqnic_native_open);
