# SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views
ifneq ($(KERNELRELEASE),)
obj-m += as02_mr_support.o
as02_mr_support-y := mr.o mr_contract.o rnic_io.o rnic_hw.o wqe.o verbs_wqe.o sq.o sq_io.o sq_hw.o cq_io.o cq_hw.o cq.o qp_hw.o retry_io.o verbs.o device.o native_attach.o native_graph.o
ifeq ($(AS02_BUILD_AUX),1)
MQNIC_SRC ?= $(abspath $(src)/../../../external/corundum/modules/mqnic)
ccflags-y += -I$(MQNIC_SRC)
as02_mr_support-y += mqnic_graph.o
obj-m += as02_rnic_ctrl.o
as02_rnic_ctrl-y := aux_control.o native_attach.o rnic_io.o rnic_hw.o
endif
else
KDIR ?= /lib/modules/$(shell uname -r)/build
.PHONY: module
module:
	$(MAKE) -C $(KDIR) M=$(CURDIR) W=1 modules
endif
