set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +ZERO_SERVICE +SERVICE_OP=13
python
import os,pathlib,re
print('ZERO_SERVICE_NATIVE_ACTUAL_FATAL')
header=pathlib.Path(os.environ['AS02_SERVICE_DEBUG_OBJ'])/'Vtb___024root.h'
fields=sorted(set(re.findall(r'\b(tb__DOT__\w+)\s*;',header.read_text())))
names=['guard_byte','atomic_phase','expected_atomic_write','commands','statuses','read_tlps','write_tlps',
       'service_owner_count','service_hls_owner_count','service_core_count','service_retire_count','fault']
for name in fields:
    if name.count('__DOT__')==1 and name.split('__DOT__')[-1] in names:
        print('%s = %s'%(name,gdb.parse_and_eval('as02_debug_root->'+name)))
for index in [4100,4101,4108,4109,4116,4117]:
    print('actual_host[%d] = %d'%(index,int(gdb.parse_and_eval('as02_debug_root->tb__DOT__pcie_host.m_storage[%d]'%index))))
    print('actual_posted_valid[%d] = %d'%(index,int(gdb.parse_and_eval('as02_debug_root->tb__DOT__pcie_posted_valid.m_storage[%d]'%index))))
end
quit
