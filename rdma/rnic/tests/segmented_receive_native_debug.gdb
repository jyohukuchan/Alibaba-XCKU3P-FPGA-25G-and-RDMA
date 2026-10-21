set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +LARGE_RX +LARGE_RX_OP=3
python
import gdb,os,pathlib,re,json
print('SEGMENTED_RECEIVE_ORIGINAL_FATAL')
print('RX_FATAL_MESSAGE '+gdb.parse_and_eval('(char*)$rcx').string())
print('RX_FATAL_SOURCE_LINE '+str(int(gdb.parse_and_eval('$esi'))))
header=pathlib.Path(os.environ['AS02_NATIVE_DEBUG_OBJ'])/'Vtb___024root.h'
fields=sorted(set(re.findall(r'\b(tb__DOT__\w+)\s*;',header.read_text())))
top={'cycle','fault','fc','lrx_packet','lrx_commands','lrx_statuses','lrx_fenced_bytes',
     'lrx_post_queries','lrx_data_queries','lrx_placements','lrx_core','lrx_whole','lrx_packet_releases',
     'lrx_CQ_commits','lrx_CQ_retires','iv','ir','il','accepted','completed','rejected','rxgood','rxbad'}
guard={'state','byte_count','word_count','header','recv_completion_pending','recv_terminal_complete',
       'recv_group_active','recv_group_offset','recv_packet_offset','normal_checked_ready','parsed_qpn',
       'm_recv_query_qpn','s_recv_valid','s_recv_ready','lease','committed','expected_psn','word_index',
       'checked_valid','checked_ready','checked_last','opcode','fault','fault_code'}
queue={'held','armed','group_active','packet_done','packet_prepared','ticket_prepared','placed',
       'core_proved','mac_proved','message_proved','ticket_sent','committed','received_bytes',
       'packet_flags','packet_length','first_psn','next_psn','query_qpn','m_head_valid',
       'm_head_ready','post_qpn','fault','fault_code','posted_count','taken_count'}
bridge={'recv_held','recv_proved','recv_message_seen','recv_terminal','remote_operation_idle',
        'remote_receive_held','recv_owner_pending','role','fault','fault_code'}
router={'first','offset','enabled','classified_route','route_now','route_count','routes','rd_ptr','wr_ptr',
        'host_frame_count','roce_frame_count','drop_frame_count','overflow_count','stale_frame_count',
        'output_route_latched','output_stale','stored_route','fifo_ready','fifo_input_ready','input_transfer',
        'ipv4','udp','mac_match','bad','empty','full_wr','overflow_reg','wr_ptr_reg','wr_ptr_commit_reg','rd_ptr_reg',
        'drop_frame_reg','m_axis_tvalid_pipe_reg'}
refs={'enable','can_new','gate','context_ok','context_stable','granted','in_frame','references','fault','trusted_valid'}
for name in fields:
    leaf=name.split('__DOT__')[-1]
    selected=(name.count('__DOT__')==1 and leaf in top) or \
        ('__DOT__guard__DOT__'in name and leaf in guard) or \
        ('__DOT__receive_owners__DOT__owners__DOT__'in name and leaf in queue) or leaf in bridge or \
        (('__DOT__response_router__DOT__'in name or '__DOT__request_router__DOT__'in name) and leaf in router) or \
        ('__DOT__input_references__DOT__'in name and leaf in refs) or \
        (name.count('__DOT__')==2 and leaf.startswith(('native_rx','response_','request_','protected_','recv_','rq_')))
    if not selected:continue
    try:
        value=gdb.parse_and_eval('as02_debug_root->'+name)
        try:result=int(value)
        except (gdb.error,TypeError):
            array=value['m_storage'];lo,hi=array.type.range()
            result={'little_endian_words':[int(array[i])for i in range(lo,hi+1)]}
        print('RX_FATAL_FIELD '+json.dumps({'name':name,'value':result},sort_keys=True))
    except (gdb.error,TypeError,RuntimeError):pass
end
quit
