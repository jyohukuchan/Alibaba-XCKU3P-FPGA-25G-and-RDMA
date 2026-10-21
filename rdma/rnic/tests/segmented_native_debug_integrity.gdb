set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +WRITE +SEGMENTED
python
import gdb,os,pathlib,re
print('SEGMENTED_NATIVE_ACTUAL_INTEGRITY_FATAL')
header=pathlib.Path(os.environ['AS02_NATIVE_DEBUG_OBJ'])/'Vtb___024root.h'
prefix='tb__DOT__dut__DOT__native__DOT__network__DOT__datapath__DOT__responder__DOT__endpoint__DOT__shared_hls__DOT__guard__DOT__'
fields=re.findall(r'\b(tb__DOT__\w+)\s*;',header.read_text())
guard=['core_rx_bad','core_tx_bad','core_overflow','qp_apply_bad','core_write_valid','core_read_valid',
       'core_write_data_valid','lease','zero_receive','zero_service','write_operation','command_done','data_done',
       'fault','fault_code','state']
for name in sorted(set(fields)):
    if not name.startswith(prefix):continue
    local=name[len(prefix):]
    selected=local in guard or local.startswith('transport__DOT__qptx_core__DOT__core__DOT__tx_integrity__DOT__')
    if selected:
        try:
            value=gdb.parse_and_eval('as02_debug_root->'+name)
            try: encoded='0x%x'%int(value)
            except (gdb.error,TypeError):
                size=int(value.type.sizeof)
                if size>64:continue
                words=(size+3)//4
                number=sum(int(value['m_storage'][i])<<(32*i) for i in range(words))
                encoded='0x%x'%number
            print('%s = %s'%(local,encoded))
        except (gdb.error,TypeError):pass
end
quit
