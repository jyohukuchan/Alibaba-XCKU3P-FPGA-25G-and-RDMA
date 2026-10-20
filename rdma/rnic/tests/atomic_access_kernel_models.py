# SPDX-License-Identifier: BSD-2-Clause-Views
"""Only boundary models for actual matched QP-access kernel C callbacks."""
import atomic128_kernel_models as old

once=old.once;sq_model=old.sq_model
MODEL=old.MODEL+'\n#define IB_ACCESS_REMOTE_ATOMIC 8\n'


def verbs_model():
    t=once(old.verbs_model(),'static bool immediate_feature,atomic_feature,',
        'static bool atomic_access_feature,atomic_remote_mr;\n'
        'static unsigned int requested_qp_access=6,qp_access_count;\n'
        'static u32 qp_access_commands[32];\nstatic bool immediate_feature,atomic_feature,')
    t=once(t,'    case AS02_CTL_FEATURES:\n        profile_reads++;',
        '    case AS02_CTL_FEATURES:\n        profile_reads++;\n'
        '        if(atomic_access_feature){*out=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;break;}')
    t=once(t,'if(op==AS02_CMD_QP){CHECK(!ctl_run);',
        'if(op==AS02_CMD_QP){CHECK(!ctl_run);\n'
        '        CHECK(qp_access_count<32);qp_access_commands[qp_access_count++]=ctl_stage[AS02_W_ACCESS];\n'
        '        CHECK(atomic_access_feature && ctl_stage[AS02_W_PD] ?\n'
        '          (ctl_stage[AS02_W_ACCESS]==6 || ctl_stage[AS02_W_ACCESS]==14):!ctl_stage[AS02_W_ACCESS]);')
    t=once(t,'if(op==AS02_CMD_QP_TX){CHECK(',
        'if(op==AS02_CMD_QP_TX){CHECK(!ctl_stage[AS02_W_ACCESS]);CHECK(')
    t=once(t,'VA,atomic_readonly_mr ? 4:7,NULL,NULL);',
        'VA,atomic_remote_mr ? 15:atomic_readonly_mr ? 4:7,NULL,NULL);')
    return once(t,'.qp_access_flags=6};','.qp_access_flags=requested_qp_access};')
