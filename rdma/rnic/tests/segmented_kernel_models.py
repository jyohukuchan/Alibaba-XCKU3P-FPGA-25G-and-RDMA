# SPDX-License-Identifier: BSD-2-Clause-Views
"""Only Linux/MMIO/pin/DMA/completion boundary models, not kernel bodies."""
import zero_kernel_models as old

once=old.once;MODEL=old.MODEL


def sq_model():
    return once(old.sq_model(),'as02_zero_wqe_decode(&a,','as02_segmented_wqe_decode(&a,')


def verbs_model():
    t=once(old.verbs_model(),'static bool zero_feature;',
        'static bool zero_feature,segmented_feature;\nstatic unsigned int segmented_bad_tuple;')
    t=once(t,'case AS02_CQC_FEATURES:if(atomic_feature)return 15;',
        'case AS02_CQC_FEATURES:if(segmented_feature || segmented_bad_tuple==2)return segmented_bad_tuple==1 ? 15:31;\n'
        '        if(atomic_feature){return 15;}')
    t=once(t,'if(atomic_access_feature){*out=zero_feature ? AS02_CTL_ZERO_NATIVE_FEATURES:AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;break;}',
        'if(atomic_access_feature){*out=segmented_feature ? AS02_CTL_SEGMENTED_NATIVE_FEATURES:\n'
        '            zero_feature ? AS02_CTL_ZERO_NATIVE_FEATURES:AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;break;}')
    return once(t,'if(atomic_bad_geometry){','if(atomic_bad_geometry || segmented_bad_tuple){')
