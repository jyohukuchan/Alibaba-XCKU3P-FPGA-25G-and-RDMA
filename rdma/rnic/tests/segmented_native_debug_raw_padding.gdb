set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +WRITE +SEGMENTED
python
import gdb
print('SEGMENTED_NATIVE_RAW_HLS_PADDING')
# The consumed width-adapter shifter has keep0 at the fatal, so it cannot
# prove the original packet. Inspect the genuine retained HLS BTH instead.
base='as02_debug_root->tb__DOT__dut__DOT__native__DOT__network__DOT__datapath__DOT__responder__DOT__endpoint__DOT__shared_hls__DOT__guard__DOT__transport__DOT__qptx_core__DOT__core__DOT__native_request_core__DOT__transport__DOT__generate_ibh_512_0_U0__DOT__'
value=sum(int(gdb.parse_and_eval(base+'header_header_4.m_storage[%d]'%i))<<(32*i) for i in range(3))
data=value.to_bytes(12,'little')
print('RAW_HLS_BTH '+data.hex())
print('HLS_opcode',data[0],'HLS_pad',(data[1]>>4)&3,'HLS_PSN',int.from_bytes(data[9:12],'big'))
end
quit
