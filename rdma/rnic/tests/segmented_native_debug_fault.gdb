set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +WRITE +SEGMENTED
python
import gdb, os, pathlib, re
print('SEGMENTED_NATIVE_ACTUAL_OWNER_FATAL')
header=pathlib.Path(os.environ['AS02_NATIVE_DEBUG_OBJ'])/'Vtb___024root.h'
fields=sorted(set(re.findall(r'\b(tb__DOT__\w+)\s*;',header.read_text())))
counts=['fault','fault_code','cycle','big_source_commands','big_MR_queries','big_MR_responses',
        'big_expectations','big_advances','big_core_receipts','actual_SFD_count',
        'actual_native_SFD_count','local_committed_count','board_wire_eofs']
source=['active','source_issued','source_done','source_loaded','offer_valid','next_offset',
        'remaining','chunk','next_tag','command_count','memory_status_count','state',
        'owner_count','source_owner','source_active','legacy_active','source_select']
wire=['state','packet_index','whole_first_psn','packet_fault_pending','advance_pending',
      'memory_done','request_proved','request_done_seen','mac_done','receipt_seen','tail_left']
for name in fields:
    leaf=name.split('__DOT__')[-1]
    selected=(name.count('__DOT__')==1 and leaf in counts) or \
        ('fault' in leaf and 'Vcell' not in name and not leaf.startswith('__V')) or \
        ('dut__DOT__executor__DOT__' in name and leaf in source) or \
        ('dut__DOT__wire_lifetime__DOT__' in name and leaf in wire)
    if selected:
        try:
            value=int(gdb.parse_and_eval('as02_debug_root->'+name))
            if value or 'fault' not in leaf or name.count('__DOT__')<=2:
                print('%s = %d'%(name,value))
        except (gdb.error,TypeError):
            pass
end
quit
