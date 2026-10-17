#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Adapted publication helper; not the unmodified script used for recorded results.
# Changes MTUs and generates bounded traffic only after explicit opt-in.
[[ "${AS02_ALLOW_TRAFFIC_TEST:-}" == YES ]] || {
    printf 'Read docs/TESTING.md; set AS02_ALLOW_TRAFFIC_TEST=YES only with active thermal monitoring.\n' >&2
    exit 2
}
for required in AS02_CX_NS AS02_FPGA_NS AS02_CX_IF AS02_FPGA_IF AS02_CX_ADDR AS02_FPGA_ADDR AS02_CX_BDF AS02_FPGA_BDF AS02_MQNIC_DUMP AS02_MQNIC_DEV AS02_MQNIC_PORT AS02_TX_CLOCK_CHANNEL AS02_RX_CLOCK_CHANNEL; do
    [[ -n "${!required:-}" ]] || { printf 'Missing explicit test setting: %s\n' "$required" >&2; exit 2; }
done
for required in ip ethtool jq awk rg grep ss iperf3 timeout sudo; do
    command -v "$required" >/dev/null || { printf 'Missing tool: %s\n' "$required" >&2; exit 2; }
done
[[ "$AS02_CX_NS" != "$AS02_FPGA_NS" && "$AS02_CX_BDF" != "$AS02_FPGA_BDF" ]]
for bdf in "$AS02_CX_BDF" "$AS02_FPGA_BDF"; do
    [[ "$bdf" =~ ^[[:xdigit:]]{4}:[[:xdigit:]]{2}:[[:xdigit:]]{2}\.[0-7]$ ]] || exit 2
done
for index in "$AS02_MQNIC_PORT" "$AS02_TX_CLOCK_CHANNEL" "$AS02_RX_CLOCK_CHANNEL"; do
    [[ "$index" =~ ^[0-9]{1,2}$ ]] || exit 2
done
[[ "$AS02_TX_CLOCK_CHANNEL" != "$AS02_RX_CLOCK_CHANNEL" ]]
[[ "$AS02_MQNIC_DUMP" == /* && -x "$AS02_MQNIC_DUMP" && -c "$AS02_MQNIC_DEV" ]]
# Fail before changing MTUs if either interface belongs to the wrong device.
for role in CX FPGA; do
    ns_name=AS02_${role}_NS
    if_name=AS02_${role}_IF
    bdf_name=AS02_${role}_BDF
    info=$(sudo -n ip netns exec "${!ns_name}" ethtool -i "${!if_name}")
    actual_bdf=$(awk -F ': ' '$1 == "bus-info" {print $2}' <<< "$info")
    actual_driver=$(awk -F ': ' '$1 == "driver" {print $2}' <<< "$info")
    [[ "$actual_bdf" == "${!bdf_name}" ]] || { printf 'Wrong PCIe device for %s\n' "$role" >&2; exit 2; }
    if [[ "$role" == FPGA ]]; then [[ "$actual_driver" == mqnic ]]; else [[ "$actual_driver" == mlx5_core ]]; fi
done

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$project_dir/logs"
run_dir=$(mktemp -d "$project_dir/logs/benchmark-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")
server_pid=
initial_cx_mtu=
initial_fpga_mtu=
cleanup_server() {
    if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
        kill -TERM "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
}
cleanup() {
    cleanup_server
    if [[ "$initial_cx_mtu" =~ ^[0-9]+$ ]]; then
        sudo -n ip -n "$AS02_CX_NS" link set dev "$AS02_CX_IF" mtu "$initial_cx_mtu" || true
    fi
    if [[ "$initial_fpga_mtu" =~ ^[0-9]+$ ]]; then
        sudo -n ip -n "$AS02_FPGA_NS" link set dev "$AS02_FPGA_IF" mtu "$initial_fpga_mtu" || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
initial_cx_mtu=$(sudo -n ip -n "$AS02_CX_NS" -j link show dev "$AS02_CX_IF" | jq -er '.[0].mtu')
initial_fpga_mtu=$(sudo -n ip -n "$AS02_FPGA_NS" -j link show dev "$AS02_FPGA_IF" | jq -er '.[0].mtu')

wait_for_links() {
    for attempt in {1..100}; do
        if sudo -n ip -n "$AS02_CX_NS" -j link show dev "$AS02_CX_IF" | \
                jq -e '.[0].operstate == "UP"' > /dev/null && \
           sudo -n ip -n "$AS02_FPGA_NS" -j link show dev "$AS02_FPGA_IF" | \
                jq -e '.[0].operstate == "UP"' > /dev/null; then
            return 0
        fi
        sleep 0.1
    done
    printf 'Timed out waiting for both physical links to return after MTU change\n' >&2
    return 1
}

sudo -n ip netns exec "$AS02_CX_NS" ethtool "$AS02_CX_IF" > "$run_dir/cx4-link.txt"
grep -q 'Speed: 25000Mb/s' "$run_dir/cx4-link.txt"
grep -q 'Link detected: yes' "$run_dir/cx4-link.txt"
sudo -n ip netns exec "$AS02_CX_NS" ethtool --show-fec "$AS02_CX_IF" > "$run_dir/cx4-fec.txt"
sudo -n "$AS02_MQNIC_DUMP" -d "$AS02_MQNIC_DEV" -i "$AS02_MQNIC_PORT" > "$run_dir/fpga-info.txt"
# Select clock counters for the connected physical port; verify mapping first.
# Do not accept a fixed ethtool speed field as proof of a native 25G PHY.
awk -v tx="$AS02_TX_CLOCK_CHANNEL" -v rx="$AS02_RX_CLOCK_CHANNEL" '
    ($1 == "CH" tx ":" || $1 == "CH" rx ":") && $2 == "clock" && $3 == "freq:" {
        frequency = $4 + 0
        if (frequency < 390.0 || frequency > 391.0) bad = 1
        count++
    }
    END {exit (count != 2 || bad)}
' "$run_dir/fpga-info.txt"
sudo -n ip netns exec "$AS02_CX_NS" ethtool -S "$AS02_CX_IF" > "$run_dir/cx4-counters-before.txt"
sudo -n ip -n "$AS02_CX_NS" -j -s link show dev "$AS02_CX_IF" > "$run_dir/cx4-before.json"
sudo -n ip -n "$AS02_FPGA_NS" -j -s link show dev "$AS02_FPGA_IF" > "$run_dir/fpga-before.json"

run_test() {
    local label=$1
    shift
    sudo -n ip netns exec "$AS02_FPGA_NS" timeout 45s \
        iperf3 --server --one-off --bind "$AS02_FPGA_ADDR" --port 5201 --json \
        > "$run_dir/$label-server.json" 2> "$run_dir/$label-server.stderr" &
    server_pid=$!
    local ready=false
    for attempt in {1..50}; do
        if sudo -n ip netns exec "$AS02_FPGA_NS" ss -ltn 'sport = :5201' | \
                grep -q LISTEN; then
            ready=true
            break
        fi
        sleep 0.1
    done
    [[ "$ready" == true ]] || { printf 'iperf3 server did not start\n' >&2; exit 1; }
    sudo -n ip netns exec "$AS02_CX_NS" timeout 40s \
        iperf3 --client "$AS02_FPGA_ADDR" --bind "$AS02_CX_ADDR" --port 5201 \
        --time 20 --omit 3 --parallel 4 --json --get-server-output "$@" \
        > "$run_dir/$label.json"
    wait "$server_pid"
    server_pid=
    jq -e 'has("error") | not' "$run_dir/$label.json" > /dev/null
    jq -r --arg label "$label" \
        '[$label, (.end.sum_received.bits_per_second / 1000000000),
        .end.sum_sent.retransmits] | @tsv' "$run_dir/$label.json"
}

printf 'Results directory: %s\nTest\tReceiver Gbit/s\tTCP retransmissions\n' "$run_dir"
for mtu in 1500 9000; do
    sudo -n ip -n "$AS02_CX_NS" link set dev "$AS02_CX_IF" mtu "$mtu"
    sudo -n ip -n "$AS02_FPGA_NS" link set dev "$AS02_FPGA_IF" mtu "$mtu"
    # mqnic restarts its port on MTU changes; its carrier poll runs every second.
    wait_for_links
    sudo -n ip netns exec "$AS02_CX_NS" ping -c 10 -i 0.2 -W 1 "$AS02_FPGA_ADDR" \
        > "$run_dir/ping-mtu$mtu.txt"
    sudo -n ip netns exec "$AS02_FPGA_NS" ping -c 10 -i 0.2 -W 1 "$AS02_CX_ADDR" \
        > "$run_dir/ping-reverse-mtu$mtu.txt"
    grep -q ' 0% packet loss' "$run_dir/ping-mtu$mtu.txt"
    grep -q ' 0% packet loss' "$run_dir/ping-reverse-mtu$mtu.txt"
    sudo -n ip netns exec "$AS02_CX_NS" ping -c 3 -M do -s "$((mtu - 28))" \
        -W 1 "$AS02_FPGA_ADDR" > "$run_dir/ping-full-mtu$mtu.txt"
    sudo -n ip netns exec "$AS02_FPGA_NS" ping -c 3 -M do -s "$((mtu - 28))" \
        -W 1 "$AS02_CX_ADDR" > "$run_dir/ping-reverse-full-mtu$mtu.txt"
    rg -q ' 0% packet loss' "$run_dir/ping-full-mtu$mtu.txt"
    rg -q ' 0% packet loss' "$run_dir/ping-reverse-full-mtu$mtu.txt"
    run_test "mtu$mtu-cx4-to-fpga"
    run_test "mtu$mtu-fpga-to-cx4" --reverse
done

sudo -n ip netns exec "$AS02_CX_NS" ethtool -S "$AS02_CX_IF" > "$run_dir/cx4-counters-after.txt"
sudo -n ip -n "$AS02_CX_NS" -j -s link show dev "$AS02_CX_IF" > "$run_dir/cx4-after.json"
sudo -n ip -n "$AS02_FPGA_NS" -j -s link show dev "$AS02_FPGA_IF" > "$run_dir/fpga-after.json"
sudo -n "$AS02_MQNIC_DUMP" -d "$AS02_MQNIC_DEV" -i "$AS02_MQNIC_PORT" > "$run_dir/fpga-info-after.txt"
# Both directions traverse this same physical link. Reject any increment of
# the CX4's hardware CRC/symbol/transmit-error counters, or an unexpected reset.
awk '
    $1 ~ /^(rx_crc_errors_phy|rx_symbol_err_phy|rx_pcs_symbol_err_phy|tx_errors_phy):$/ {
        if (FNR == NR) before[$1] = $2
        else {
            if (!($1 in before) || $2 != before[$1]) bad = 1
            count++
        }
    }
    END {exit (count != 4 || bad)}
' "$run_dir/cx4-counters-before.txt" "$run_dir/cx4-counters-after.txt"
printf 'Completed: %s\n' "$run_dir"
