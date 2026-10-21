# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit Linux/MMIO/pin/DMA/CQ boundary models, not hardware authority."""
import segmented_read_kernel_models as base

once=base.once;MODEL=base.MODEL


def sq_model():
    t=base.sq_model()
    return once(t,'return sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_READ128 ?',
        'return sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_IMMEDIATE128 ?\n'
        '        as02_segmented_immediate_wqe_decode(a,bytes):\n'
        '        sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_READ128 ?')


def verbs_model():
    t=base.verbs_model()
    t=once(t,'static unsigned int segmented_read_bad_tuple;',
        'static unsigned int segmented_read_bad_tuple;\n'
        'static bool segmented_immediate_feature;static unsigned int segmented_immediate_bad_tuple;')
    t=once(t,'case AS02_CQC_FEATURES:if(segmented_read_feature',
        'case AS02_CQC_FEATURES:if(segmented_immediate_feature || segmented_immediate_bad_tuple==2){\n'
        '        return segmented_immediate_bad_tuple==1 ? 63:127;}\n        if(segmented_read_feature')
    t=once(t,'*out=segmented_read_feature ? AS02_CTL_SEGMENTED_READ_NATIVE_FEATURES:',
        '*out=segmented_immediate_feature ? AS02_CTL_SEGMENTED_IMMEDIATE_NATIVE_FEATURES:\n'
        '            segmented_read_feature ? AS02_CTL_SEGMENTED_READ_NATIVE_FEATURES:')
    return once(t,'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple){',
        'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple || segmented_immediate_bad_tuple){')
