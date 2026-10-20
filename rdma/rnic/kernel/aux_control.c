/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* ASN1 native CSR-only auxiliary attachment. NO ib_device/verbs/MR exposure.
 * This compile-tested stage is NOT loaded or runtime-qualified. Its parent
 * private header MUST match the actual loaded mqnic before any future load.
 */
#include <linux/auxiliary_bus.h>
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/slab.h>
#include <mqnic.h>
#include "native_attach.h"
#include "rnic_hw.h"

#if !IS_ENABLED(CONFIG_PCI) || !IS_ENABLED(CONFIG_AUXILIARY_BUS)
#error "Native AS02 control attachment requires PCI and auxiliary bus"
#endif

struct as02_aux_control {
    struct as02_rnic_hw hw;
};

/* Default denial is BEFORE even dereferencing mqnic's PRIVATE layout. An
 * auxiliary alias alone is not a stable parent/header ABI compatibility
 * proof. Enabling this later requires the separate native load gates.
 */
static bool enable_probe;
module_param(enable_probe, bool, 0400);
MODULE_PARM_DESC(enable_probe, "Opt in to CSR-only probe AFTER exact parent/header and native firmware gates; no RDMA data plane");

static int as02_control_probe(struct auxiliary_device *adev,
                              const struct auxiliary_device_id *id)
{
    struct mqnic_adev *app;
    struct mqnic_dev *parent;
    struct as02_native_parent identity;
    struct as02_aux_control *control;
    int ret;

    if (!enable_probe)
        return -EACCES;
    app = container_of(adev, struct mqnic_adev, adev);
    parent = app->mdev;
    /* The parent owns PCI binding and BAR mappings. Do not claim/remap its
     * resources or touch any other NIC, legacy application or management IF.
     */
    if (!parent || !parent->pdev || parent->dev != &parent->pdev->dev)
        return -ENODEV;
    identity.vendor = parent->pdev->vendor;
    identity.device = parent->pdev->device;
    identity.subvendor = parent->pdev->subsystem_vendor;
    identity.subdevice = parent->pdev->subsystem_device;
    identity.app_id = parent->app_id;
    identity.mapped = !!parent->app_hw_addr;
    identity.bar_bytes = parent->app_hw_regs_size;
    ret = as02_native_parent_validate(&identity);
    if (ret)
        return ret;

    control = kzalloc(sizeof(*control), GFP_KERNEL);
    if (!control)
        return -ENOMEM;
    /* Exact identified control window; init READS only and requires the
     * fresh paused/empty/drained ABI. No seed, QP, doorbell, DMA or reset.
     */
    ret = as02_rnic_hw_init(&control->hw,
        parent->app_hw_addr+AS02_NATIVE_CONTROL_BASE,
        AS02_NATIVE_CONTROL_BYTES, 100000);
    if (ret) {
        kfree(control);
        return ret;
    }
    auxiliary_set_drvdata(adev, control);
    dev_info(&adev->dev, "ASN1 CSR-only control attached; no RDMA device, verbs, page mapping or DMA enabled\n");
    return 0;
}

static void as02_control_remove(struct auxiliary_device *adev)
{
    struct as02_aux_control *control = auxiliary_get_drvdata(adev);
    int ret;

    if (!control)
        return;
    auxiliary_set_drvdata(adev, NULL);
    /* Parent deletes this child before unmapping its BAR. No external
     * handles/APIs exist in this CSR-only stage, hence no concurrent users
     * or MR owners. Future data-plane code MUST add actual reference and
     * pool lifetime management, not assume this remains sufficient.
     */
    ret = as02_rnic_hw_detach(&control->hw);
    if (WARN_ON(ret)) {
        dev_err(&adev->dev, "control detach failed; context retained, no release proof inferred\n");
        return;
    }
    if (WARN_ON(control->hw.control.pending || control->hw.control.uncertain)) {
        dev_err(&adev->dev, "unexpected uncertain control owner retained; detach is NOT DMA-drain proof\n");
        return;
    }
    kfree(control);
}

static const struct auxiliary_device_id as02_control_ids[] = {
    { .name = AS02_NATIVE_AUX_NAME },
    { }
};
MODULE_DEVICE_TABLE(auxiliary, as02_control_ids);

static struct auxiliary_driver as02_control_driver = {
    .name = "as02_rnic_ctrl",
    .probe = as02_control_probe,
    .remove = as02_control_remove,
    .id_table = as02_control_ids,
};
module_auxiliary_driver(as02_control_driver);

MODULE_DESCRIPTION("AS02 ASN1 CSR-only native auxiliary control; NO standard RDMA device or verbs");
MODULE_LICENSE("Dual BSD/GPL");
MODULE_SOFTDEP("pre: mqnic");
