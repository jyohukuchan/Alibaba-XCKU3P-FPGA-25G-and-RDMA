set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +RQ +RQ_OP=3
python
print('ZERO_RQ_NATIVE_PARSER_ACTUAL_FATAL')
guard='tb__DOT__dut__DOT__native__DOT__network__DOT__datapath__DOT__responder__DOT__endpoint__DOT__shared_hls__DOT__guard__DOT__'
for name in ['tb__DOT__rxgood','tb__DOT__rxbad','tb__DOT__request_drop_count',
             'tb__DOT__reject_error','tb__DOT__reject_valid',guard+'byte_count',guard+'frame_bad',guard+'state']:
    print('%s = %s' % (name, gdb.parse_and_eval('as02_debug_root->' + name)))
end
quit
