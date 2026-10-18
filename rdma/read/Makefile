.PHONY: check check-wire check-buffer check-engine check-rw check-native-host
check: check-wire check-buffer check-engine check-rw check-native-host

check-wire:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_read_wire.py -v

check-buffer:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_read_buffer_rtl.py -v

check-engine:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_read_engine_rtl.py -v

check-rw:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_rw_control_rtl.py -v
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_rw_ingress_rtl.py -v
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_rw_build_gate.py -v

check-native-host:
	$(MAKE) -C host check
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_rw_client.py -v
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_rw_preflight.py -v
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_native_rw_test.py -v
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_read_recovery.py -v
