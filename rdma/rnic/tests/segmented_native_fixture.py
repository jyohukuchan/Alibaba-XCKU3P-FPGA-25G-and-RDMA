# SPDX-License-Identifier: BSD-2-Clause-Views
"""Observe actual common nonce <-> actual paged backend; no signal injection.

All prior native cases run on the new segmented HLS. Large native admission,
source controller, wire/CQ lifetimes are not wired/qualified by these cases.
"""
import json
import zero_service_native_fixture as old

ROOT=old.ROOT;variant=old.variant;prelude=old.prelude;verify=old.verify
PAGE='dut.native.network.datapath.responder.endpoint'


def bench():
    text=old.bench()
    addition=r'''
integer nonce_admitted=0,nonce_issued=0,nonce_backend_completed=0,nonce_logical_completed=0,nonce_translated=0;
reg nonce_observer_active=0;
reg [144:0] expected_nonce_command=0;reg [15:0] expected_nonce_physical=0;
reg [7:0] expected_nonce_error=0;
always @(posedge clk)begin
 if(rst)begin
  nonce_admitted=0;nonce_issued=0;nonce_backend_completed=0;nonce_logical_completed=0;nonce_translated=0;
  nonce_observer_active=0;expected_nonce_command=0;expected_nonce_physical=0;expected_nonce_error=0;
 end else begin
  if(PAGE.memory_nonce.s_command_valid && PAGE.memory_nonce.s_command_ready)begin
   if(nonce_observer_active)$fatal(1,"common nonce admitted overlapping physical owner");
   expected_nonce_command={PAGE.memory_nonce.s_command_write,PAGE.memory_nonce.s_command_offset,
    PAGE.memory_nonce.s_command_length,PAGE.memory_nonce.s_command_key,PAGE.memory_nonce.s_command_tag};
   nonce_admitted=nonce_admitted+1;expected_nonce_physical=nonce_admitted[15:0];nonce_observer_active=1;
  end
  if(PAGE.memory.s_command_valid && PAGE.memory.s_command_ready)begin
   if(!nonce_observer_active ||
    {PAGE.memory.s_command_write,PAGE.memory.s_command_offset,PAGE.memory.s_command_length,PAGE.memory.s_command_key}!==expected_nonce_command[144:16] ||
    PAGE.memory.s_command_tag!==expected_nonce_physical)$fatal(1,"actual paged backend lost full command/physical nonce");
   nonce_issued=nonce_issued+1;
   if(expected_nonce_command[15:0]!=expected_nonce_physical)nonce_translated=nonce_translated+1;
  end
  if(PAGE.memory.m_status_valid && PAGE.memory.m_status_ready)begin
   if(!nonce_observer_active || PAGE.memory.m_status_tag!==expected_nonce_physical || nonce_backend_completed>=nonce_issued)
    $fatal(1,"foreign actual paged status reached nonce mapping");
   expected_nonce_error=PAGE.memory.m_status_error;nonce_backend_completed=nonce_backend_completed+1;
  end
  if(PAGE.memory_nonce.m_status_valid && PAGE.memory_nonce.m_status_ready)begin
   if(!nonce_observer_active || PAGE.memory_nonce.m_status_tag!==expected_nonce_command[15:0] ||
    PAGE.memory_nonce.m_status_error!==expected_nonce_error || nonce_logical_completed>=nonce_backend_completed)
    $fatal(1,"logical status without same genuine physical backend receipt");
   nonce_logical_completed=nonce_logical_completed+1;nonce_observer_active=0;
  end
 end
end
final begin
 $display("MEMORY_NONCE_NATIVE_RESULT {\"admitted\":%0d,\"issued\":%0d,\"backend_completed\":%0d,\"logical_completed\":%0d,\"translated\":%0d,\"active\":%0d,\"fault\":%0d}",
  nonce_admitted,nonce_issued,nonce_backend_completed,nonce_logical_completed,nonce_translated,nonce_observer_active,PAGE.memory_nonce.fault);
end
'''.replace('PAGE.',PAGE+'.')
    return old.once(text,'module tb;','module tb;\n'+addition)


def verify_nonce(output):
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('MEMORY_NONCE_NATIVE_RESULT ')]
    if len(rows)!=1:raise ValueError('missing actual common nonce/paged-backend observer')
    r=rows[0]
    if r['active'] or r['fault'] or len({r[n]for n in ['admitted','issued','backend_completed','logical_completed']})!=1 or r['translated']>r['issued']:
        raise ValueError('actual physical-command/logical-status lifetime incomplete:'+str(r))
    return r
