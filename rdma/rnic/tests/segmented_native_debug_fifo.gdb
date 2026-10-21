set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +WRITE +SEGMENTED
python
import gdb
print('SEGMENTED_NATIVE_ACTUAL_FIFO_FATAL')
fields = [
    'actual_tx_fifo__DOT__fifo_inst__DOT__overflow_reg',
    'actual_tx_fifo__DOT__fifo_inst__DOT__bad_frame_reg',
    'actual_tx_fifo__DOT__fifo_inst__DOT__drop_frame_reg',
    'actual_tx_fifo__DOT__fifo_inst__DOT__full_wr',
    'actual_tx_fifo__DOT__fifo_inst__DOT__wr_ptr_reg',
    'actual_tx_fifo__DOT__fifo_inst__DOT__wr_ptr_commit_reg',
    'actual_tx_fifo__DOT__fifo_inst__DOT__rd_ptr_reg',
    'actual_mac__DOT__error_underflow_reg',
    'actual_timestamp_fifo__DOT__overflow_reg',
    'big_source_commands', 'big_MR_queries', 'big_MR_responses',
    'big_expectations', 'big_advances', 'big_core_receipts',
    'actual_SFD_count', 'actual_native_SFD_count',
    'local_committed_count', 'dut__DOT__tx_frame_count', 'fault', 'cycle',
]
for field in fields:
    name = 'tb__DOT__' + field
    try:
        print('%s = %d' % (name, int(gdb.parse_and_eval('as02_debug_root->' + name))))
    except gdb.error as error:
        print('%s = UNAVAILABLE %s' % (name, error))
end
quit
