set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +WRITE +SEGMENTED
python
import gdb
print('SEGMENTED_NATIVE_REJECTED_PACKET_BYTES')
base='as02_debug_root->tb__DOT__dut__DOT__native__DOT__network__DOT__datapath__DOT__responder__DOT__endpoint__DOT__shared_hls__DOT__guard__DOT__transport__DOT__qptx_core__DOT__core__DOT__tx_integrity__DOT__'
commit=int(gdb.parse_and_eval(base+'packet_fifo__DOT__wr_ptr_commit_reg'))
frame=bytearray()
for index in range(commit,commit+3):
    value=0
    for word in range(5):
        value|=int(gdb.parse_and_eval(base+'packet_fifo__DOT__mem.m_storage[%d].m_storage[%d]'%(index%1024,word)))<<(32*word)
    data=value&((1<<128)-1);keep=(value>>128)&65535
    print('FIFO_WORD %d %032x %04x last%d bad%d'%(index,data,keep,(value>>144)&1,(value>>145)&1))
    frame+=data.to_bytes(16,'little')[:keep.bit_count()]
print('REJECTED_STAGED_IP '+frame.hex())
print('IP_length',int.from_bytes(frame[2:4],'big'),'UDP_length',int.from_bytes(frame[24:26],'big'),
      'BTH_opcode',frame[28],'pad',(frame[29]>>4)&3,'captured_bytes',len(frame))
end
quit
