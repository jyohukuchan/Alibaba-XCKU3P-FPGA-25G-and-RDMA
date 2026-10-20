# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched full-native Immediate requester stimuli, not injected core/CQ proofs.

Reuse actual coherent SQ, MR/PTE/PCIe, replay, MAC and CQ checks. Append
immutable immediate separately and verify the exact real20-word CQ context.
Host/root/MAC pins and peer are explicit models; actual HLS remains required.
"""
import re
import native_duplex_request_fixture as old
import probe_native_retry as base
import check_immediate_native_elaboration as elaboration

matched=elaboration.matched
once=matched.once

def audit_profile(tb):
    tb=once(tb,'if(sq_value!==511)', 'if(sq_value!==1023)')
    tb=once(tb,'if(sq_value!==1)$fatal(1,"native SQ must advertise control-only");',
        'if(sq_value!==5)$fatal(1,"matched Immediate descriptor SQ profile");')
    task=r'''
task audit_immediate_profile;
 integer fp;
 begin
  fp=$fopen("profile.hex","w");if(!fp)$fatal(1,"actual native capability capture");
  read_reg(AS02_CTL_FEATURES,sq_value);if(sq_value!==1023)$fatal(1,"actual full Immediate RNC");$fdisplay(fp,"%08h",sq_value);
  read_reg(24'h402008,sq_value);if(sq_value!==5)$fatal(1,"actual Immediate SQC");$fdisplay(fp,"%08h",sq_value);
  read_reg(24'h405008,sq_value);if(sq_value!==7)$fatal(1,"actual Immediate RQC");$fdisplay(fp,"%08h",sq_value);
  read_reg(24'h403008,sq_value);if(sq_value!==7)$fatal(1,"actual Immediate CQC");$fdisplay(fp,"%08h",sq_value);
  $fclose(fp);
 end
endtask
'''
    tb=once(tb,'reg [144:0] stimulus',task+'\nreg [144:0] stimulus')
    # Only the ORIGINAL profile check, not this task's new readback check.
    pattern=r'(if\(sq_value!==1023\)\$fatal\(1,"(?:actual complete duplex requester capability missing|actual receive CQ capability)"\);)'
    tb,n=re.subn(pattern,r'\1audit_immediate_profile();',tb)
    if n!=1:raise ValueError('unique actual native profile check required')
    return tb

def case():
    tb,words,records,request=old.case(base.case)
    tb=matched.request_fields(matched.widths(tb))
    tb=once(tb,'integer runtime_native_opcode=2,request_event_file,request_word;',
        'integer runtime_native_opcode=2,request_event_file,request_word;\nreg [31:0] runtime_immediate=0;')
    tb=once(tb,' if($test$plusargs("SEND"))runtime_native_opcode=3;',
        ' if($test$plusargs("SEND"))runtime_native_opcode=3;\n'
        ' if($test$plusargs("SEND_IMM"))runtime_native_opcode=5;\n'
        ' if($test$plusargs("WRITE_IMM"))runtime_native_opcode=6;\n'
        ' if($value$plusargs("IMM=%h",runtime_immediate))begin end')
    # SEND_IMM has no remote VA/rkey. WRITE_IMM has the original full RETH.
    tb=tb.replace('runtime_native_opcode==3 ?',
        '(runtime_native_opcode==3 || runtime_native_opcode==5) ?')
    tb=once(tb,"(runtime_native_opcode==2 ? 8'h0c : runtime_native_opcode==1 ? 8'h0a : 8'h04)",
        "(runtime_native_opcode==2 ? 8'h0c : runtime_native_opcode==1 ? 8'h0a : runtime_native_opcode==5 ? 8'h05 : runtime_native_opcode==6 ? 8'h0b : 8'h04)")
    tb=once(tb,"expected_request_owner[19:0]!==3 || held_request_proof[619:0]!==expected_request_owner ||",
        "expected_request_owner[619:588]!==runtime_immediate ||\n"
        " expected_request_owner[19:0]!==3 || held_request_proof[619:0]!==expected_request_owner ||")
    tb=once(tb,'request_word<19;','request_word<20;')
    tb=once(tb,'$fdisplay(request_event_file,"%08h",sq_value);$fclose(request_event_file);',r'''$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h40303c,sq_value);if(sq_value)$fatal(1,"TX CQ fabricated receive flags");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h403090,sq_value);if(sq_value)$fatal(1,"TX CQ fabricated receive notification");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h403008,sq_value);if(sq_value!==7)$fatal(1,"matched Immediate completion format");$fdisplay(request_event_file,"%08h",sq_value);
$fclose(request_event_file);''')
    # Frontend metadata is meaningful at its handoff, not after it has
    # legitimately cleared authorization. The full retained owner/proof and
    # all20 actual CQ words are still checked at retirement above.
    tb=once(tb,'reg [144:0] stimulus',r'''
always @(posedge clk)if(!rst)begin
 if(dut.m_work_handoff && dut.m_work_immediate!==runtime_immediate)
  $fatal(1,"actual authorized SQ handoff lost Immediate");
 if(dut.owner_take && dut.sq_m_executor_context[619:588]!==runtime_immediate)
  $fatal(1,"actual immutable owner handoff lost Immediate");
end
reg [144:0] stimulus''')
    # Real HLS QP apply receipt, not a behavioral-model stall hook.
    tb=once(tb,r'''qp_model_allow=0;write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(23)begin @(negedge clk);if(!control_busy || quiet || config_safe)$fatal(1,"QP TX returned before real apply");end
read_reg(AS02_CTL_STATUS,sq_value);if(sq_value&AS02_ST_REPLY)$fatal(1,"fabricated state apply reply");
qp_model_allow=1;collect_native(9,403,0,0,0);''',
        'write_reg(AS02_CTL_DOORBELL,1,15,0,1);collect_native(9,403,0,0,0);')
    # All V sources are supplied from the COMPLETE matched substitution set.
    # Keep real register/header includes, never include duplicate old parents.
    tb=re.sub(r'^\s*`include "[^\"]+\.v"\s*$', '',tb,flags=re.M)
    if 'force 'in tb:raise ValueError('no internal signal force')
    return audit_profile(tb)


def variant(opcode,immediate):
    legacy_opcode=3 if opcode==5 else 1 if opcode==6 else opcode
    words,records,request=old.variant(base.case,legacy_opcode)
    if opcode not in (5,6):
        if immediate:raise ValueError('ordinary WQE notification must be0')
        return words,records,request
    result=[]
    for raw in records:
        r=bytearray(raw)
        # Fixed64-byte actual SQ descriptor: separate32-bit LE immediate.
        # Validate against actual C profile codec in the launcher, not only
        # this stimulus oracle. Existing key/VA and reserved bytes untouched.
        r[44:46]=opcode.to_bytes(2,'little')
        r[48:52]=immediate.to_bytes(4,'little')
        result.append(bytes(r))
    p=bytearray(request);p[28]=5 if opcode==5 else 11
    index=40 if opcode==5 else 56
    p[index:index]=immediate.to_bytes(4,'big')
    p=old.parent.qp.main.response.repair(p)
    return words,result,p


def verify(output,request,opcode):
    return old.verify(output,request,opcode)
