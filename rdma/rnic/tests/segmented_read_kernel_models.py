# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit Linux/MMIO/pin/DMA/CQ boundaries; actual kernel bodies unchanged."""
import segmented_kernel_models as old

once=old.once;MODEL=old.MODEL


def sq_model():
    t=old.sq_model()
    t=once(t,'static struct as02_sq_pool sq;',r'''
static struct as02_sq_pool sq;
static int read_profile_decode(struct as02_atomic_wqe *a,const u8 *bytes)
{
    return sq.wqe_profile==AS02_WQE_PROFILE_SEGMENTED_READ128 ?
        as02_segmented_read_wqe_decode(a,bytes):as02_segmented_wqe_decode(a,bytes);
}''')
    return once(t,'as02_segmented_wqe_decode(&a,','read_profile_decode(&a,')


def verbs_model():
    t=old.verbs_model()
    t=once(t,'static bool zero_feature,segmented_feature;',
        'static bool zero_feature,segmented_feature,segmented_read_feature;\nstatic unsigned int segmented_read_bad_tuple;')
    t=once(t,'case AS02_CQC_FEATURES:if(segmented_feature',
        'case AS02_CQC_FEATURES:if(segmented_read_feature || segmented_read_bad_tuple==2){\n'
        '        return segmented_read_bad_tuple==1 ? 31:63;}\n        if(segmented_feature')
    t=once(t,'*out=segmented_feature ? AS02_CTL_SEGMENTED_NATIVE_FEATURES:',
        '*out=segmented_read_feature ? AS02_CTL_SEGMENTED_READ_NATIVE_FEATURES:\n'
        '            segmented_feature ? AS02_CTL_SEGMENTED_NATIVE_FEATURES:')
    return once(t,'if(atomic_bad_geometry || segmented_bad_tuple){',
        'if(atomic_bad_geometry || segmented_bad_tuple || segmented_read_bad_tuple){')
