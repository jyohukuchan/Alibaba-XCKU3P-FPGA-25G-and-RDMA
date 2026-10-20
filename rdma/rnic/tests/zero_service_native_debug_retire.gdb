set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +ZERO_SERVICE +SERVICE_OP=13
python
import os,pathlib,re
print('ZERO_SERVICE_NATIVE_ACTUAL_RETIRE_FATAL')
header=pathlib.Path(os.environ['AS02_SERVICE_DEBUG_OBJ'])/'Vtb___024root.h'
fields=sorted(set(re.findall(r'\b(tb__DOT__\w+)\s*;',header.read_text())))
top=['service_seq','service_owner_count','service_hls_owner_count','service_core_count',
     'service_retire_count','fault','fc','cycle']
mac=['state','active','have_core','mac_started','mac_done','receipt_seen','tail_started',
     'tail_left','tag','next_tag','fault','fault_code','retired_count']
for name in fields:
    if ((name.count('__DOT__')==1 and name.split('__DOT__')[-1] in top) or
        ('__DOT__zero_wire_lifetime__DOT__' in name and name.split('__DOT__')[-1] in mac) or
        name in ['tb__DOT__dut__DOT__s_zero_retire_valid','tb__DOT__dut__DOT__m_zero_retire_ready']):
        print('%s = %s'%(name,gdb.parse_and_eval('as02_debug_root->'+name)))
def wide(name,bits):
    value=0
    for word in range((bits+31)//32):
        value|=int(gdb.parse_and_eval('as02_debug_root->'+name+'.m_storage[%d]'%word))<<(word*32)
    print('%s = %0*x'%(name,(bits+3)//4,value))
    return value
expected_owner=wide('tb__DOT__expected_service_owner',344)
expected_core=wide('tb__DOT__expected_service_core',400)
owner=wide('tb__DOT__dut__DOT__zero_wire_lifetime__DOT__owner',528)
core=wide('tb__DOT__dut__DOT__zero_wire_lifetime__DOT__core',400)
print('actual_owner_match = %s'%((owner&((1<<344)-1))==expected_owner))
print('actual_core_match = %s'%(core==expected_core))
end
quit
