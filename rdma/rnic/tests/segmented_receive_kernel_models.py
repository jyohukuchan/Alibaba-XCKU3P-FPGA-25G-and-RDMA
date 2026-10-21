# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit Linux/MMIO/pin/DMA/completion models, not FPGA proof producers."""
import segmented_immediate_kernel_models as parent

once=parent.once;MODEL=parent.MODEL
# Retain the existing runner's old helper interface and all prior cases.
base=parent.base


def sq_model():
    t=parent.sq_model()
    t=once(t,'return sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_IMMEDIATE128 ?',
        'return sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_RECEIVE128 ?\n'
        '        as02_segmented_receive_wqe_decode(a,bytes):\n'
        '        sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_IMMEDIATE128 ?')
    expression='model.features==13 || model.features==15'
    if t.count(expression)!=2:raise ValueError('both model geometry and observation selections required')
    return t.replace(expression,expression+' || model.features==31')


def verbs_model():
    t=parent.verbs_model()
    t=once(t,'static bool segmented_immediate_feature;static unsigned int segmented_immediate_bad_tuple;',
        'static bool segmented_immediate_feature;static unsigned int segmented_immediate_bad_tuple;\n'
        'static bool segmented_receive_feature;static unsigned int segmented_receive_bad_tuple;')
    t=once(t,'case AS02_CQC_FEATURES:if(segmented_immediate_feature',
        'case AS02_CQC_FEATURES:if(segmented_receive_feature || segmented_receive_bad_tuple){\n'
        '        return segmented_receive_bad_tuple==2 ? 127:255;}\n'
        '        if(segmented_immediate_feature')
    t=once(t,'*out=segmented_immediate_feature ? AS02_CTL_SEGMENTED_IMMEDIATE_NATIVE_FEATURES:',
        '*out=segmented_receive_feature ? AS02_CTL_SEGMENTED_RECEIVE_NATIVE_FEATURES:\n'
        '            segmented_immediate_feature ? AS02_CTL_SEGMENTED_IMMEDIATE_NATIVE_FEATURES:')
    t=once(t,'if(atomic_feature)receive_model.features=15;',
        'if(atomic_feature)receive_model.features=15;\n'
        '        if((segmented_receive_feature || segmented_receive_bad_tuple==3) && segmented_receive_bad_tuple!=1)receive_model.features=31;')
    return once(t,'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple || segmented_immediate_bad_tuple){',
        'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple || segmented_immediate_bad_tuple || segmented_receive_bad_tuple){')
