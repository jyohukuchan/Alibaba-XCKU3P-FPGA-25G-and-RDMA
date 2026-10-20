set pagination off
set confirm off
set print thread-events off
set debuginfod enabled off
set breakpoint pending on
break vl_fatal
run +ZERO +SEND
python
import pathlib
import re
print('ZERO_NATIVE_DEBUG_ACTUAL_FATAL')
header = pathlib.Path('/dev/shm/as02-zero-native-obj-xg0inxki/Vtb___024root.h').read_text()
names = sorted(set(re.findall(r'\b(tb__DOT__dut__DOT__\w+)\s*;', header)))
# Normal C++ member lookup resolves Verilator's anonymous struct offsets.
for name in names:
    if not ('fault' in name.lower() or 'bad_owner' in name or 'bad_sq' in name or
            name.endswith(('core_rx_bad','core_tx_bad','core_overflow'))):
        continue
    try:
        number = int(gdb.parse_and_eval('as02_debug_root->' + name))
    except (gdb.error, TypeError, ValueError):
        continue
    if number:
        print('%s = 0x%x' % (name, number))
end
quit
