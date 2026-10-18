CC ?= cc
CFLAGS ?= -O2 -g
CPPFLAGS ?=
WARNINGS = -Wall -Wextra -Werror -Wformat=2

.PHONY: all check check-host check-rtl clean
all: build/rc_write_peer

build/rc_write_peer: host/rc_write_peer.c
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(WARNINGS) -std=c11 $< -libverbs -o $@

check: check-host check-rtl

check-host: all
	build/rc_write_peer --self-test
	! build/rc_write_peer
	! build/rc_write_peer missing 1 connect 198.18.10.1 0
	python3 -m unittest discover -s tests -p test_wire.py -v
	python3 -m unittest discover -s tests -p test_fpga_write_client.py -v
	python3 -m unittest discover -s tests -p test_native_preflight.py -v
	python3 -m unittest discover -s tests -p test_native_test.py -v
	python3 -m unittest discover -s tests -p test_mac_rx_fault.py -v
	python3 -m unittest discover -s tests -p test_native_fault_test.py -v

check-rtl:
	python3 -m unittest discover -s tests -p test_icrc_rtl.py -v
	python3 -m unittest discover -s tests -p test_metadata_backpressure_rtl.py -v
	python3 -m unittest discover -s tests -p test_ethernet_rtl.py -v
	python3 -m unittest discover -s tests -p test_padding_rtl.py -v
	python3 -m unittest discover -s tests -p test_write_engine_rtl.py -v
	python3 -m unittest discover -s tests -p test_control_rtl.py -v
	python3 -m unittest discover -s tests -p test_tx_guard_rtl.py -v
	python3 -m unittest discover -s tests -p test_mac_drain_rtl.py -v

clean:
	$(RM) build/rc_write_peer
