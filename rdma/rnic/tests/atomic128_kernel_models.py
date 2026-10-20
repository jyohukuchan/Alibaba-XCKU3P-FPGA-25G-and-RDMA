# SPDX-License-Identifier: BSD-2-Clause-Views
"""Only Linux/MMIO/DMA/peer boundary MODELS for checked actual kernel C.

Never substitute a SQ/MR/CQ/verbs body. Actual queue bytes are read AFTER
the real dma_wmb; new full CQ operands come from an explicitly modeled event.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];TESTS=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'rdma/rnic/kernel'))
from derive_atomic128 import once


def sq_model():
    t=(TESTS/'kernel_sq_hw_cases.c').read_text()
    t=once(t,'u32 observed_count;struct as02_wqe observed[256];',
        'u32 observed_count;struct as02_wqe observed[256];struct as02_atomic_wqe observed_atomic[256];')
    t=once(t,'case AS02_SQC_FEATURES:*value=model.features;break;',
        'case AS02_SQC_FEATURES:*value=model.features;break;\n'
        '    case AS02_SQC_DESCRIPTOR_BYTES:*value=(model.features==13 || model.features==15) ? 128:64;break;')
    a=t.index('                CHECK(mapping && mapping->bytes==')
    b=t.index('                CHECK(work.sequence==',a)
    t=t[:a]+r'''                if(model.features==13 || model.features==15){
                    struct as02_atomic_wqe a;
                    CHECK(mapping && mapping->bytes==(128U<<model.reply[10]));
                    CHECK(!as02_atomic_wqe_decode(&a,(u8 *)mapping->address+
                        ((model.producer-1)&((1U<<model.reply[10])-1))*128));
                    model.observed_atomic[model.observed_count]=a;work=a.base;
                }else{
                    CHECK(mapping && mapping->bytes==(64U<<model.reply[10]));
                    CHECK(!as02_wqe_decode_profile(&work,(u8 *)mapping->address+
                        ((model.producer-1)&((1U<<model.reply[10])-1))*64,
                        (model.features&AS02_SQC_IMMEDIATE_FEATURE) ? AS02_WQE_PROFILE_IMMEDIATE:0));
                }
'''+t[b:]
    return t


def verbs_model():
    t=(TESTS/'kernel_verbs_cases.c').read_text()
    t=once(t,'static bool immediate_feature;',
        'static bool immediate_feature,atomic_feature,atomic_readonly_mr,geometry_armed,atomic_drop_ack;\n'
        'static unsigned int atomic_bad_geometry,atomic_ack_writes;')
    t=once(t,'case AS02_CQC_FEATURES:return immediate_feature',
        'case AS02_CQC_FEATURES:if(atomic_feature)return 15;return immediate_feature')
    t=once(t,'case AS02_CQC_STATUS:return event_visible ? 3:0;',r'''
    case AS02_CQC_OWNER_BITS:return geometry_armed && atomic_bad_geometry==3 ? 620:748;
    case AS02_CQC_OPERAND_BASE:return geometry_armed && atomic_bad_geometry==4 ? 0x90:0xa0;
    case AS02_CQC_ATOMIC_OPERANDS:return event_visible ? event.compare:0;
    case AS02_CQC_ATOMIC_OPERANDS+4:return event_visible ? event.compare>>32:0;
    case AS02_CQC_ATOMIC_OPERANDS+8:return event_visible ? event.swap_add:0;
    case AS02_CQC_ATOMIC_OPERANDS+12:return event_visible ? event.swap_add>>32:0;
    case AS02_CQC_STATUS:return event_visible ? 3:0;''')
    t=once(t,'    event_visible=false;acknowledged=value;',
        '    atomic_ack_writes++;if(atomic_drop_ack)return;\n    event_visible=false;acknowledged=value;')
    t=once(t,'    if(immediate_feature && profile_mismatch!=2)model.features=AS02_SQC_IMMEDIATE_FEATURE_VALUE;',
        '    if(immediate_feature && profile_mismatch!=2)model.features=AS02_SQC_IMMEDIATE_FEATURE_VALUE;\n'
        '    if(atomic_feature)model.features=13;')
    t=once(t,'        CHECK(!as02_sq_hw_init_receive(',
        '        if(atomic_feature)receive_model.features=15;\n        CHECK(!as02_sq_hw_init_receive(')
    t=once(t,'    if(profile_mismatch){',r'''
    geometry_armed=true;
    if(atomic_bad_geometry){
        CHECK(as02_verbs_bind(&vdev,&mrs,&sq,&cqh,&qph,&vr,eth,sizeof(eth))==-EOPNOTSUPP);
        CHECK(!vdev.initialized && !sq.profile_bound && !sq.wqe_profile && !mrs.pd_zero_reserved);
        return;
    }
    if(profile_mismatch){''')
    t=once(t,'VA,7,NULL,NULL);','VA,atomic_readonly_mr ? 4:7,NULL,NULL);')
    t=once(t,'    event_visible=true; // Explicit model:',
        '    event.compare=model.observed_atomic[i].compare;event.swap_add=model.observed_atomic[i].swap_add;\n'
        '    event_visible=true; // Explicit model:')
    # Header-level geometry reads retain actual register locks and identity.
    t=once(t,'        receive_model=model;model=saved;return value;',
        '        receive_model=model;model=saved;\n'
        '        if(geometry_armed && atomic_bad_geometry==2 && address-(uintptr_t)receive_mmio==AS02_SQC_DESCRIPTOR_BYTES)value=64;\n'
        '        return value;')
    t=once(t,'if(address>=(uintptr_t)mmio && address<(uintptr_t)mmio+sizeof(mmio))return sq_readl(p);',
        'if(address>=(uintptr_t)mmio && address<(uintptr_t)mmio+sizeof(mmio)){\n'
        '        if(geometry_armed && atomic_bad_geometry==1 && address-(uintptr_t)mmio==AS02_SQC_DESCRIPTOR_BYTES)return 64;\n'
        '        return sq_readl(p);}')
    return t


MODEL=r'''
#ifndef AS02_ATOMIC128_BOUNDARY_MODEL_H
#define AS02_ATOMIC128_BOUNDARY_MODEL_H
#include "kernel_verbs_model.h"
#define IB_WR_ATOMIC_CMP_AND_SWP 5
#define IB_WR_ATOMIC_FETCH_AND_ADD 6
#define IB_WC_COMP_SWAP 3
#define IB_WC_FETCH_ADD 4
struct ib_atomic_wr {
 struct ib_send_wr wr;u64 remote_addr,compare_add,swap,compare_add_mask,swap_mask;u32 rkey;
};
static inline const struct ib_atomic_wr *atomic_wr(const struct ib_send_wr *w)
{ return container_of(w,const struct ib_atomic_wr,wr); }
#endif
'''

