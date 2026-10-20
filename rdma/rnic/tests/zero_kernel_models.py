# SPDX-License-Identifier: BSD-2-Clause-Views
"""Only Linux/MMIO/coherent-DMA/pin/completion models for zero-aware C."""
import atomic_access_kernel_models as old

once=old.once;MODEL=old.MODEL


def sq_model():
    return once(old.sq_model(),'as02_atomic_wqe_decode(&a,','as02_zero_wqe_decode(&a,')


def verbs_model():
    t=once(old.verbs_model(),'static bool atomic_access_feature,atomic_remote_mr;',
        'static bool zero_feature;\nstatic bool atomic_access_feature,atomic_remote_mr;')
    t=once(t,'if(atomic_access_feature){*out=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;break;}',
        'if(atomic_access_feature){*out=zero_feature ? AS02_CTL_ZERO_NATIVE_FEATURES:AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;break;}')
    t=once(t,'w->local_address-VA);', 'w->length ? w->local_address-VA:0);')
    t=once(t,'w->opcode==AS02_WQE_RECV ? 65:0;', 'w->opcode==AS02_WQE_RECV && !zero_feature ? 65:0;')
    return once(t,'CHECK(!verbs->destroy_cq(&cq.ibcq,NULL));CHECK(!verbs->dereg_mr(m,NULL));',
        'CHECK(!verbs->destroy_cq(&cq.ibcq,NULL));if(m){CHECK(!verbs->dereg_mr(m,NULL));}else{CHECK(!vdev.mr_count);}')
