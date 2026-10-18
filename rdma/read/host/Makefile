# SPDX-License-Identifier: BSD-2-Clause-Views
CC ?= cc
CFLAGS ?= -O2 -g
CPPFLAGS ?=
.PHONY: all check
all: ../build/rc_read_peer

../build/rc_read_peer: rc_read_peer.c
	mkdir -p ../build
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wall -Wextra -Werror -Wformat=2 -std=c11 $< -libverbs -lcrypto -o $@

check: all
	../build/rc_read_peer --self-test
