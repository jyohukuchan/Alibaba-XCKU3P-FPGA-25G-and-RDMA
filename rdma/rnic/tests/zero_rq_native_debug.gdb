set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +RQ +RQ_OP=3
python
print('ZERO_RQ_NATIVE_ACTUAL_FATAL')
for name in ['tb__DOT__rxgood','tb__DOT__rxbad','tb__DOT__request_drop_count',
             'tb__DOT__dut__DOT__rq_posted_count','tb__DOT__dut__DOT__rq_taken_count',
             'tb__DOT__dut__DOT__rq_core_proof_count']:
    print('%s = %s' % (name, gdb.parse_and_eval('as02_debug_root->' + name)))
end
quit
