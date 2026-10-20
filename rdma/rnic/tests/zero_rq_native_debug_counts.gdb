set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +RQ +RQ_OP=3 +RQ_BUFFER
python
print('ZERO_RQ_NATIVE_COUNTS_ACTUAL_FATAL')
guard='tb__DOT__dut__DOT__native__DOT__network__DOT__datapath__DOT__responder__DOT__endpoint__DOT__shared_hls__DOT__guard__DOT__'
names=['rq_dma_seen','rq_local_queries','rq_remote_queries','router_descriptor_count','read_tlps','write_tlps',
       'fences','commands','statuses','local_committed_count','local_execution_guard','actual_native_SFD_count','fault']
import pathlib,re
header=pathlib.Path('/dev/shm/as02-zero-native-obj-4551z13t/Vtb___024root.h').read_text()
fields=sorted(set(re.findall(r'\b(tb__DOT__\w+)\s*;',header)))
for name in fields:
    if name.split('__DOT__')[-1] not in names+['expected_psn','descriptor_count']:continue
    if not (name.startswith('tb__DOT__dut__DOT__native__DOT__router__DOT__') or
            name.count('__DOT__')==1 or name==guard+'expected_psn'):continue
    print('%s = %s' % (name,gdb.parse_and_eval('as02_debug_root->'+name)))
end
quit
