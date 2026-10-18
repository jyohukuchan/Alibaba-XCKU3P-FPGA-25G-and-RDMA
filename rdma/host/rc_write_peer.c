/* SPDX-License-Identifier: BSD-2-Clause-Views
 * Finite RC RDMA WRITE interoperability/data-integrity harness.
 * TCP is only the out-of-band control channel, never the data transfer.
 */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <infiniband/verbs.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define CONTROL_BYTES 256
#define WINDOW 32
#define MAX_TOTAL (64u * 1024u * 1024u)

struct endpoint {
    uint32_t qpn, psn, rkey;
    uint64_t address;
    size_t size, count;
    union ibv_gid gid;
};

static double monotonic(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) { perror("clock_gettime"); exit(1); }
    return t.tv_sec + t.tv_nsec / 1e9;
}

static int transfer(int fd, void *buffer, size_t length, bool writing)
{
    char *p = buffer;
    while (length) {
        ssize_t n = writing ? send(fd, p, length, MSG_NOSIGNAL) : recv(fd, p, length, 0);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { fprintf(stderr, "control %s failed: %s\n", writing ? "send" : "receive", n ? strerror(errno) : "EOF"); return -1; }
        p += n;
        length -= (size_t)n;
    }
    return 0;
}

static int control_socket(const char *ip, uint16_t port, bool server)
{
    int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0) { perror("socket"); return -1; }
    struct sockaddr_in address = {.sin_family = AF_INET, .sin_port = htons(port)};
    struct timeval deadline = {.tv_sec = 15};
    int yes = 1;
    if (inet_pton(AF_INET, ip, &address.sin_addr) != 1 || address.sin_addr.s_addr == INADDR_ANY) {
        fprintf(stderr, "an explicit IPv4 address is required\n"); close(fd); return -1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &deadline, sizeof(deadline)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &deadline, sizeof(deadline))) {
        perror("socket timeout"); close(fd); return -1;
    }
    if (server) {
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
        if (bind(fd, (struct sockaddr *)&address, sizeof(address)) || listen(fd, 1)) {
            perror("bind/listen"); close(fd); return -1;
        }
        printf("{\"event\":\"listening\",\"ip\":\"%s\",\"port\":%u}\n", ip, port);
        int accepted = accept(fd, NULL, NULL);
        close(fd);
        if (accepted < 0) { perror("accept"); return -1; }
        fd = accepted;
        if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &deadline, sizeof(deadline)) ||
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &deadline, sizeof(deadline))) {
            perror("accepted socket timeout"); close(fd); return -1;
        }
    } else if (connect(fd, (struct sockaddr *)&address, sizeof(address))) {
        perror("connect"); close(fd); return -1;
    }
    return fd;
}

static int exchange(int fd, const struct endpoint *local, struct endpoint *remote)
{
    char output[CONTROL_BYTES] = {0}, input[CONTROL_BYTES] = {0};
    char gid[33];
    for (int i = 0; i < 16; ++i) snprintf(gid + i * 2, 3, "%02x", local->gid.raw[i]);
    int n = snprintf(output, sizeof(output), "AS02RC1 %x %x %x %" PRIx64 " %zu %zu %s\n",
                     local->qpn, local->psn, local->rkey, local->address, local->size, local->count, gid);
    if (n < 0 || n >= CONTROL_BYTES || transfer(fd, output, sizeof(output), true) ||
        transfer(fd, input, sizeof(input), false)) return -1;
    input[sizeof(input) - 1] = 0;
    if (sscanf(input, "AS02RC1 %x %x %x %" SCNx64 " %zu %zu %32s", &remote->qpn,
               &remote->psn, &remote->rkey, &remote->address, &remote->size, &remote->count, gid) != 7 ||
        strlen(gid) != 32 || remote->qpn > 0xffffff || remote->psn > 0xffffff ||
        remote->size != local->size || remote->count != local->count) {
        fprintf(stderr, "invalid/mismatched control endpoint\n"); return -1;
    }
    for (int i = 0; i < 16; ++i) {
        unsigned byte;
        if (sscanf(gid + i * 2, "%2x", &byte) != 1) return -1;
        remote->gid.raw[i] = (uint8_t)byte;
    }
    return 0;
}

static void print_endpoint(const char *event, const char *device, int gid_index, const struct endpoint *e)
{
    char gid[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, e->gid.raw, gid, sizeof(gid));
    printf("{\"event\":\"%s\",\"device\":\"%s\",\"gid_index\":%d,\"gid\":\"%s\","
           "\"qpn\":%u,\"psn\":%u,\"rkey\":\"0x%08x\",\"address\":\"0x%016" PRIx64 "\","
           "\"message_bytes\":%zu,\"messages\":%zu,\"path_mtu\":4096}\n",
           event, device, gid_index, gid, e->qpn, e->psn, e->rkey, e->address, e->size, e->count);
}

static int ready(struct ibv_qp *qp, int gid_index, const struct endpoint *local, const struct endpoint *remote)
{
    struct ibv_qp_attr a = {.qp_state = IBV_QPS_RTR, .path_mtu = IBV_MTU_4096,
                          .dest_qp_num = remote->qpn, .rq_psn = remote->psn,
                          .max_dest_rd_atomic = 1, .min_rnr_timer = 12};
    a.ah_attr.is_global = 1;
    a.ah_attr.port_num = 1;
    a.ah_attr.grh.dgid = remote->gid;
    a.ah_attr.grh.sgid_index = gid_index;
    a.ah_attr.grh.hop_limit = 64;
    if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_AV | IBV_QP_PATH_MTU |
                      IBV_QP_DEST_QPN | IBV_QP_RQ_PSN | IBV_QP_MAX_DEST_RD_ATOMIC | IBV_QP_MIN_RNR_TIMER)) {
        perror("QP RTR"); return -1;
    }
    memset(&a, 0, sizeof(a));
    a.qp_state = IBV_QPS_RTS;
    a.sq_psn = local->psn;
    a.timeout = 14;
    a.retry_cnt = 7;
    a.rnr_retry = 7;
    a.max_rd_atomic = 1;
    if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_SQ_PSN | IBV_QP_TIMEOUT |
                      IBV_QP_RETRY_CNT | IBV_QP_RNR_RETRY | IBV_QP_MAX_QP_RD_ATOMIC)) {
        perror("QP RTS"); return -1;
    }
    return 0;
}

static uint8_t pattern(size_t index)
{
    return (uint8_t)((index * 131u) ^ (index >> 8) ^ 0x5au);
}

static uint8_t initial_value(size_t index, bool receiver)
{
    /* Every unwritten byte must differ from its expected value, including
     * single-byte WRITEs; a constant sentinel can accidentally equal data. */
    return receiver ? (uint8_t)~pattern(index) : pattern(index);
}

static int write_data(struct ibv_qp *qp, struct ibv_cq *cq, struct ibv_mr *mr,
                      uint8_t *buffer, const struct endpoint *remote)
{
    size_t sent = 0, completed = 0;
    double start = monotonic(), deadline = start + 12;
    while (completed < remote->count) {
        while (sent < remote->count && sent - completed < WINDOW) {
            struct ibv_sge sge = {.addr = (uintptr_t)buffer + sent * remote->size,
                                  .length = (uint32_t)remote->size, .lkey = mr->lkey};
            struct ibv_send_wr wr = {.wr_id = sent + 1, .sg_list = &sge, .num_sge = 1,
                                     .opcode = IBV_WR_RDMA_WRITE, .send_flags = IBV_SEND_SIGNALED};
            struct ibv_send_wr *bad = NULL;
            wr.wr.rdma.remote_addr = remote->address + sent * remote->size;
            wr.wr.rdma.rkey = remote->rkey;
            int rc = ibv_post_send(qp, &wr, &bad);
            if (rc) { fprintf(stderr, "post_send: %s\n", strerror(rc)); return -1; }
            ++sent;
        }
        struct ibv_wc wc[WINDOW];
        int n = ibv_poll_cq(cq, WINDOW, wc);
        if (n < 0) { fprintf(stderr, "poll_cq failed\n"); return -1; }
        for (int i = 0; i < n; ++i) {
            if (wc[i].status != IBV_WC_SUCCESS || wc[i].opcode != IBV_WC_RDMA_WRITE || wc[i].wr_id != completed + 1) {
                fprintf(stderr, "completion id=%" PRIu64 " status=%s opcode=%u vendor=%u\n",
                        wc[i].wr_id, ibv_wc_status_str(wc[i].status), wc[i].opcode, wc[i].vendor_err);
                return -1;
            }
            ++completed;
        }
        if (monotonic() > deadline) { fprintf(stderr, "RDMA completion deadline exceeded\n"); return -1; }
        if (!n) {
            const struct timespec pause = {.tv_nsec = 10000};
            nanosleep(&pause, NULL);
        }
    }
    double elapsed = monotonic() - start;
    printf("{\"event\":\"write_completions\",\"messages\":%zu,\"bytes\":%zu,\"seconds\":%.9f,"
           "\"gbit_per_second\":%.6f,\"benchmark_claim\":false}\n", completed,
           completed * remote->size, elapsed, completed * remote->size * 8.0 / elapsed / 1e9);
    return 0;
}

static void usage(const char *name)
{
    fprintf(stderr, "Usage: %s DEVICE GID_INDEX {listen|connect} IPv4 [BYTES=64] [COUNT=16] [PORT=18516] [PSN=1193046]\n"
                    "Finite WRITE test: receiver checks every transferred byte; explicit device/GID required.\n", name);
}

static uint64_t number(const char *s, uint64_t maximum)
{
    char *end;
    errno = 0;
    unsigned long long n = strtoull(s, &end, 0);
    if (errno || !*s || *end || n > maximum) { fprintf(stderr, "invalid number: %s\n", s); exit(2); }
    return n;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--self-test")) {
        for (size_t i = 0; i < 65536; ++i) {
            if (initial_value(i, true) == pattern(i) || initial_value(i, false) != pattern(i)) return 1;
        }
        printf("{\"event\":\"offline_pattern_test\",\"checked_offsets\":65536,\"pass\":true,\"hardware_access\":false}\n");
        return 0;
    }
    if (argc < 5 || argc > 9 || (strcmp(argv[3], "listen") && strcmp(argv[3], "connect"))) {
        usage(argv[0]); return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    const char *name = argv[1];
    int gid_index = (int)number(argv[2], 255);
    bool server = !strcmp(argv[3], "listen");
    struct endpoint local = {.size = argc > 5 ? number(argv[5], 1024 * 1024) : 64,
                             .count = argc > 6 ? number(argv[6], 65536) : 16,
                             .psn = argc > 8 ? (uint32_t)number(argv[8], 0xffffff) : 0x123456};
    uint16_t port = argc > 7 ? (uint16_t)number(argv[7], 65535) : 18516;
    if (!port || !local.size || !local.count || local.count > MAX_TOTAL / local.size) {
        fprintf(stderr, "invalid size/count/port (total cap 64 MiB)\n"); return 2;
    }
    int result = 1, fd = -1;
    struct ibv_device **devices = ibv_get_device_list(NULL);
    struct ibv_context *context = NULL;
    struct ibv_pd *pd = NULL;
    struct ibv_cq *cq = NULL;
    struct ibv_mr *mr = NULL;
    struct ibv_qp *qp = NULL;
    uint8_t *buffer = NULL;
    if (!devices) { perror("device list"); goto cleanup; }
    for (size_t i = 0; devices[i]; ++i) {
        if (!strcmp(ibv_get_device_name(devices[i]), name)) { context = ibv_open_device(devices[i]); break; }
    }
    if (!context) { fprintf(stderr, "cannot open device %s\n", name); goto cleanup; }
    struct ibv_port_attr port_attr;
    struct ibv_gid_entry gid_entry;
    if (ibv_query_port(context, 1, &port_attr) || port_attr.state != IBV_PORT_ACTIVE ||
        port_attr.link_layer != IBV_LINK_LAYER_ETHERNET || port_attr.active_mtu < IBV_MTU_4096 ||
        ibv_query_gid_ex(context, 1, gid_index, &gid_entry, 0) || gid_entry.gid_type != IBV_GID_TYPE_ROCE_V2) {
        fprintf(stderr, "requires active Ethernet/RoCEv2 GID and path MTU >=4096\n"); goto cleanup;
    }
    local.gid = gid_entry.gid;
    pd = ibv_alloc_pd(context);
    cq = ibv_create_cq(context, WINDOW * 2, NULL, NULL, 0);
    if (!pd || !cq || posix_memalign((void **)&buffer, 4096, local.size * local.count)) {
        fprintf(stderr, "PD/CQ/buffer allocation failed\n"); goto cleanup;
    }
    for (size_t i = 0; i < local.size * local.count; ++i) buffer[i] = initial_value(i, server);
    mr = ibv_reg_mr(pd, buffer, local.size * local.count, IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE);
    if (!mr) { perror("register MR"); goto cleanup; }
    struct ibv_qp_init_attr init = {.send_cq = cq, .recv_cq = cq, .qp_type = IBV_QPT_RC,
                                   .cap = {.max_send_wr = WINDOW, .max_recv_wr = 1, .max_send_sge = 1, .max_recv_sge = 1}};
    qp = ibv_create_qp(pd, &init);
    if (!qp) { perror("create QP"); goto cleanup; }
    struct ibv_qp_attr attr = {.qp_state = IBV_QPS_INIT, .pkey_index = 0, .port_num = 1,
                             .qp_access_flags = IBV_ACCESS_REMOTE_WRITE};
    if (ibv_modify_qp(qp, &attr, IBV_QP_STATE | IBV_QP_PKEY_INDEX | IBV_QP_PORT | IBV_QP_ACCESS_FLAGS)) {
        perror("QP INIT"); goto cleanup;
    }
    local.qpn = qp->qp_num;
    local.rkey = mr->rkey;
    local.address = (uintptr_t)buffer;
    print_endpoint("local_endpoint", name, gid_index, &local);
    fd = control_socket(argv[4], port, server);
    if (fd < 0) goto cleanup;
    struct endpoint remote = {0};
    if (exchange(fd, &local, &remote)) goto cleanup;
    print_endpoint("remote_endpoint", "peer", -1, &remote);
    if (ready(qp, gid_index, &local, &remote)) goto cleanup;
    char sync = 'R', other = 0;
    if (transfer(fd, &sync, 1, true) || transfer(fd, &other, 1, false) || other != sync) goto cleanup;
    if (server) {
        if (transfer(fd, &other, 1, false) || other != 'D') goto cleanup;
        __sync_synchronize();
        size_t mismatches = 0, first_bad = 0;
        for (size_t i = 0; i < local.size * local.count; ++i) {
            if (buffer[i] != pattern(i)) { if (!mismatches) first_bad = i; ++mismatches; }
        }
        printf("{\"event\":\"memory_verification\",\"bytes\":%zu,\"mismatches\":%zu,"
               "\"first_bad_offset\":%zu,\"pass\":%s}\n", local.size * local.count,
               mismatches, first_bad, mismatches ? "false" : "true");
        sync = mismatches ? 'F' : 'P';
        if (transfer(fd, &sync, 1, true) || mismatches) goto cleanup;
    } else {
        if (write_data(qp, cq, mr, buffer, &remote)) goto cleanup;
        sync = 'D';
        if (transfer(fd, &sync, 1, true) || transfer(fd, &other, 1, false) || other != 'P') goto cleanup;
        printf("{\"event\":\"receiver_verified\",\"pass\":true}\n");
    }
    result = 0;
cleanup:
    if (fd >= 0) close(fd);
    if (qp) ibv_destroy_qp(qp);
    if (mr) ibv_dereg_mr(mr);
    free(buffer);
    if (cq) ibv_destroy_cq(cq);
    if (pd) ibv_dealloc_pd(pd);
    if (context) ibv_close_device(context);
    if (devices) ibv_free_device_list(devices);
    return result;
}
