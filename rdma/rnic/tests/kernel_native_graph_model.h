/* SPDX-License-Identifier: BSD-2-Clause-Views */
#ifndef AS02_NATIVE_GRAPH_TEST_MODEL_H
#define AS02_NATIVE_GRAPH_TEST_MODEL_H
#include "kernel_device_model.h"
#define MQNIC_MAX_IF 8U
#define MQNIC_MAX_PORTS 8U
struct auxiliary_device { struct device dev; };
struct pci_dev { struct device dev;u16 vendor,device,subsystem_vendor,subsystem_device; };
struct mqnic_dev;
struct mqnic_if { struct mqnic_dev *mdev;u32 ndev_count;struct net_device *ndev[MQNIC_MAX_PORTS]; };
struct mqnic_dev { struct device *dev;struct pci_dev *pdev;u64 app_hw_regs_size;u8 *app_hw_addr;
    u32 app_id,if_count;struct mqnic_if *interface[MQNIC_MAX_IF]; };
struct mqnic_adev { struct auxiliary_device adev;struct mqnic_dev *mdev; };
/* Explicit module-loader parameter model, not a physical readiness proof. */
#define module_param(name,type,perm) bool *model_parameter_##name=&name
#define MODULE_PARM_DESC(name,text)
extern bool *model_parameter_enable_native_attach;
void usleep_range(unsigned long,unsigned long);
#endif
