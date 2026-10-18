#!/usr/bin/env bash
# Finite, explicitly labelled host-software RXE reference, not FPGA RDMA.
set -euo pipefail
[[ ${AS02_ALLOW_REFERENCE_TEST:-} == YES ]] || {
    printf 'Refusing traffic: set AS02_ALLOW_REFERENCE_TEST=YES.\n' >&2; exit 2;
}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/../.." && pwd)
if [[ ${1:-} != --guarded ]]; then
    [[ -n ${AS02_TEMPERATURE_GUARD:-} && -f $AS02_TEMPERATURE_GUARD ]] || {
        printf 'Set AS02_TEMPERATURE_GUARD to the validated local temperature guard.\n' >&2; exit 2;
    }
    exec bash "$AS02_TEMPERATURE_GUARD" bash "$script_dir/reference_test.sh" --guarded
fi
[[ $# == 1 ]] || exit 2
peer="$project_dir/rdma/build/rc_write_peer"
[[ -x $peer ]] || { printf 'Run make -C rdma first.\n' >&2; exit 2; }
sudo -n true
fpga_ns=fpga10g-fpga
cx_ns=fpga10g-cx4
fpga_if=enp130s0np1
rxe_name=rxe_as02_ref
reference_if=as02rxe0
[[ $(basename "$(readlink -f /sys/bus/pci/devices/0000:82:00.0/driver)") == mqnic ]]
[[ $(basename "$(readlink -f /sys/bus/pci/devices/0000:03:00.0/driver)") == mlx5_core ]]
sudo -n ip netns exec "$fpga_ns" ip -4 address show dev "$fpga_if" | rg -q '198\.18\.10\.2/30'
sudo -n ip netns exec "$cx_ns" ip -4 address show dev enp3s0np0 | rg -q '198\.18\.10\.1/30'
if [[ -e /sys/class/infiniband/$rxe_name ]]; then
    printf 'Existing %s is not owned by this run; refusing to replace it.\n' "$rxe_name" >&2; exit 2;
fi
if ip link show dev "$reference_if" >/dev/null 2>&1 || \
    sudo -n ip netns exec "$fpga_ns" ip link show dev "$reference_if" >/dev/null 2>&1; then
    printf 'Existing %s is not owned by this run.\n' "$reference_if" >&2; exit 2
fi
if ip -4 route show exact 198.18.11.0/30 | rg -q . || \
    sudo -n ip netns exec "$cx_ns" ip -4 address show dev enp3s0np0 | rg -q '198\.18\.11\.'; then
    printf 'Reference subnet 198.18.11.0/30 is already configured; refusing.\n' >&2; exit 2
fi
mkdir -p "$project_dir/rdma/logs"
log_dir=$(mktemp -d "$project_dir/rdma/logs/reference-XXXXXXXX")
sudo -n ip netns exec "$cx_ns" ethtool enp3s0np0 > "$log_dir/link.txt"
rg -q 'Speed: 25000Mb/s' "$log_dir/link.txt"
rg -q 'Link detected: yes' "$log_dir/link.txt"
capture_pid=
server_pid=
rxe_created=false
reference_created=false
peer_address_added=false
rxe_module_owned=false
cleanup() {
    if [[ -n $server_pid ]]; then
        sudo -n kill -TERM "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    if [[ -n $capture_pid ]]; then
        sudo -n kill -INT "$capture_pid" 2>/dev/null || true
        wait "$capture_pid" 2>/dev/null || true
    fi
    if [[ $rxe_created == true ]]; then
        sudo -n rdma link delete "$rxe_name"
    fi
    if [[ $reference_created == true ]]; then
        if ip link show dev "$reference_if" >/dev/null 2>&1; then
            sudo -n ip link delete "$reference_if"
        else
            sudo -n ip netns exec "$fpga_ns" ip link delete "$reference_if"
        fi
    fi
    if [[ $peer_address_added == true ]]; then
        sudo -n ip netns exec "$cx_ns" ip address del 198.18.11.1/30 dev enp3s0np0
    fi
    if [[ $rxe_module_owned == true ]]; then
        sudo -n rmmod rdma_rxe || printf 'RXE module is now in use elsewhere; left loaded.\n' >&2
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf 'REFERENCE ONLY: software RXE <-> CX455A; logs %s\n' "$log_dir"
if [[ ! -d /sys/module/rdma_rxe ]]; then
    sudo -n modprobe rdma_rxe
    rxe_module_owned=true
fi
# Linux 6.17 RXE's UDP socket/route lookup uses init_net. Keep the existing
# physical netdev in its namespace and move ONLY a new macvlan into init_net.
sudo -n ip netns exec "$fpga_ns" ip link add "$reference_if" link "$fpga_if" type macvlan mode bridge
reference_created=true
sudo -n ip netns exec "$fpga_ns" ip link set "$reference_if" netns 1
sudo -n ip link set "$reference_if" up
sudo -n ip address add 198.18.11.2/30 dev "$reference_if"
sudo -n ip netns exec "$cx_ns" ip address add 198.18.11.1/30 dev enp3s0np0
peer_address_added=true
sudo -n rdma link add "$rxe_name" type rxe netdev "$reference_if"
rxe_created=true
# Do not assume GID slots; locate the actual IPv4-mapped RoCEv2 entry.
find_gid() {
    local device=$1 expected=$2 index value base
    base=/sys/class/infiniband/$device/ports/1
    for index in {0..15}; do
        [[ -f $base/gids/$index ]] || continue
        value=$(head -n 1 "$base/gids/$index")
        if [[ $value == "$expected" ]] && [[ $(head -n 1 "$base/gid_attrs/types/$index") == 'RoCE v2' ]]; then
            printf '%s\n' "$index"; return 0
        fi
    done
    return 1
}
rxe_gid=$(find_gid "$rxe_name" 0000:0000:0000:0000:0000:ffff:c612:0b02)
cx_gid=$(find_gid mlx5_0 0000:0000:0000:0000:0000:ffff:c612:0b01)
sudo -n timeout --signal=INT --kill-after=2s 90s \
    tcpdump --immediate-mode -i "$reference_if" -s 0 -B 4096 -U -w "$log_dir/reference.pcap" 'udp port 4791' \
    > "$log_dir/tcpdump.log" 2>&1 &
capture_pid=$!
for attempt in {1..100}; do
    rg -q 'listening on' "$log_dir/tcpdump.log" && break
    kill -0 "$capture_pid" || { printf 'Capture stopped unexpectedly.\n' >&2; exit 1; }
    sleep 0.05
done
rg -q 'listening on' "$log_dir/tcpdump.log"
for size in 1 63 64 65 4095 4096 4097 8192; do
    for direction in cx-to-rxe rxe-to-cx; do
        case_id="${direction}-${size}"
        if [[ $direction == rxe-to-cx ]]; then
            receiver_ns=$cx_ns; receiver_device=mlx5_0; receiver_gid=$cx_gid; receiver_ip=198.18.11.1
            sender_ns=; sender_device=$rxe_name; sender_gid=$rxe_gid
        else
            receiver_ns=; receiver_device=$rxe_name; receiver_gid=$rxe_gid; receiver_ip=198.18.11.2
            sender_ns=$cx_ns; sender_device=mlx5_0; sender_gid=$cx_gid
        fi
        receiver_prefix=(sudo -n)
        sender_prefix=(sudo -n)
        [[ -z $receiver_ns ]] || receiver_prefix+=(ip netns exec "$receiver_ns")
        [[ -z $sender_ns ]] || sender_prefix+=(ip netns exec "$sender_ns")
        "${receiver_prefix[@]}" timeout --kill-after=2s 18s "$peer" \
            "$receiver_device" "$receiver_gid" listen "$receiver_ip" "$size" 16 \
            > "$log_dir/$case_id-receiver.jsonl" 2>&1 &
        server_pid=$!
        for attempt in {1..100}; do
            rg -q '"event":"listening"' "$log_dir/$case_id-receiver.jsonl" && break
            kill -0 "$server_pid" || { printf 'Receiver stopped; see %s\n' "$log_dir" >&2; exit 1; }
            sleep 0.05
        done
        rg -q '"event":"listening"' "$log_dir/$case_id-receiver.jsonl"
        "${sender_prefix[@]}" timeout --kill-after=2s 16s "$peer" \
            "$sender_device" "$sender_gid" connect "$receiver_ip" "$size" 16 \
            > "$log_dir/$case_id-sender.jsonl" 2>&1
        wait "$server_pid"
        server_pid=
        printf 'PASS reference %s (16 writes, all bytes verified)\n' "$case_id"
    done
done
# Let final ACK processing finish; immediate mode avoids block-buffer loss.
sleep 1
sudo -n kill -INT "$capture_pid"
wait "$capture_pid" || [[ $? == 130 ]]
capture_pid=
sudo -n rdma link delete "$rxe_name"
rxe_created=false
python3 "$project_dir/rdma/host/summarize_reference.py" "$log_dir" > "$log_dir/summary.json"
printf 'Reference complete; temporary RXE removed. Logs: %s\n' "$log_dir"
