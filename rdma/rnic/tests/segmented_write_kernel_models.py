# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit profile8 Linux/MMIO/pin/DMA/completion models; never hardware proof."""
import segmented_receive_kernel_models as parent

once=parent.once;MODEL=parent.MODEL;base=parent.base


def sq_model():
    t=parent.sq_model()
    t=once(t,'return sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_RECEIVE128 ?',
        'return (sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_RECEIVE128 || sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_WRITE128) ?')
    expression='model.features==13 || model.features==15 || model.features==31'
    if t.count(expression)!=2:raise ValueError('both actual ring model geometry/observation selections required')
    return t.replace(expression,expression+' || model.features==63')


def verbs_model():
    t=parent.verbs_model()
    t=once(t,'static bool segmented_receive_feature;static unsigned int segmented_receive_bad_tuple;',
        'static bool segmented_receive_feature;static unsigned int segmented_receive_bad_tuple;\n'
        'static bool segmented_write_feature;static unsigned int segmented_write_bad_tuple;')
    t=once(t,'case AS02_CQC_FEATURES:if(segmented_receive_feature',
        'case AS02_CQC_FEATURES:if(segmented_write_feature || segmented_write_bad_tuple){\n'
        '        return segmented_write_bad_tuple==2 ? 255:511;}\n'
        '        if(segmented_receive_feature')
    t=once(t,'*out=segmented_receive_feature ? AS02_CTL_SEGMENTED_RECEIVE_NATIVE_FEATURES:',
        '*out=segmented_write_feature ? AS02_CTL_SEGMENTED_WRITE_NATIVE_FEATURES:\n'
        '            segmented_receive_feature ? AS02_CTL_SEGMENTED_RECEIVE_NATIVE_FEATURES:')
    t=once(t,'if((segmented_receive_feature || segmented_receive_bad_tuple==3) && segmented_receive_bad_tuple!=1)receive_model.features=31;',
        'if((segmented_receive_feature || segmented_receive_bad_tuple==3) && segmented_receive_bad_tuple!=1)receive_model.features=31;\n'
        '        if((segmented_write_feature || segmented_write_bad_tuple==3) && segmented_write_bad_tuple!=1)receive_model.features=63;')
    return once(t,
        'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple || segmented_immediate_bad_tuple || segmented_receive_bad_tuple){',
        'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple || segmented_immediate_bad_tuple || segmented_receive_bad_tuple || segmented_write_bad_tuple){')
