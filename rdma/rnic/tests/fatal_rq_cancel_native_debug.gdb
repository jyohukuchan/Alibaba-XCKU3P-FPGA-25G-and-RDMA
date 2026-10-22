set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
handle SIGABRT nostop print pass
break vl_fatal
run +LARGE_WRITE_RX +LARGE_RX_OP=5 +WRITE_FATAL_ACCESS +FATAL_RQ_CANCEL
python
import os,pathlib,re,json
print('FATAL_RQC_ACTUAL_ORIGINAL_ASSERTION')
header=pathlib.Path(os.environ['AS02_FATAL_RQC_DEBUG_OBJ'])/'Vtb___024root.h'
text=header.read_text();values={}
fields=re.findall(r'CData[^;]*?\b(tb__DOT__\w+)\s*;',text)
prefixes=['tb__DOT__dut__DOT__write_rnr_control__DOT__','tb__DOT__dut__DOT__zero_wire_lifetime__DOT__',
 'tb__DOT__dut__DOT__zero_reservation__DOT__','tb__DOT__dut__DOT__atomic_wire_lifetime__DOT__',
 'tb__DOT__dut__DOT__atomic_reservation__DOT__','tb__DOT__dut__DOT__fatal_rq_cancel_authority__DOT__']
for name in fields:
    if name in ['tb__DOT__fault','tb__DOT__fc','tb__DOT__dut__DOT__m_write_native_context_valid',
        'tb__DOT__dut__DOT__fatal_rq_cancel_authorized','tb__DOT__dut__DOT__write_abort_quarantined'] or \
        (name.startswith('tb__DOT__dut__DOT__') and name.count('__DOT__')==2 and ('guard'in name or 'fault'in name)) or \
        any(name.startswith(p)for p in prefixes):
        values[name]=int(gdb.parse_and_eval('as02_debug_root->'+name))
def wide(name,bits):
    return sum(int(gdb.parse_and_eval('as02_debug_root->'+name+'.m_storage[%d]'%i))<<(32*i)for i in range((bits+31)//32))
values['actual_live_context356']=format(wide('tb__DOT__dut__DOT__m_write_native_context',356),'089x')
values['actual_RQ_head620']=format(wide('tb__DOT__dut__DOT__rq_head_context',620),'0155x')
values['expected_RQ_head620']=format(wide('tb__DOT__lrx_owner',620),'0155x')
ctx='tb__DOT__dut__DOT__fatal_rq_cancel_authority__DOT__contexts.m_storage[2]'
values['retained_cert_context356']=format(wide(ctx,356),'089x')
values['retained_cert_frontier24']=int(gdb.parse_and_eval('as02_debug_root->tb__DOT__dut__DOT__fatal_rq_cancel_authority__DOT__frontiers.m_storage[2]'))
for leaf in ['owner_cookie','owner_epoch']:
    values['RQC_'+leaf]=int(gdb.parse_and_eval('as02_debug_root->tb__DOT__dut__DOT__native__DOT__independent_receive_frontend__DOT__receive_queue_control__DOT__'+leaf+'.m_storage[2]'))
print('FATAL_RQC_DEBUG_VALUES '+json.dumps(values,sort_keys=True))
end
continue
quit
