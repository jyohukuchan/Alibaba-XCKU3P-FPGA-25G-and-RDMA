/* SPDX-License-Identifier: BSD-2-Clause-Views
 * Finite native CX455A READ responder. No verbs data-send/WRITE/READ is posted:
 * the native RNIC serves FPGA READs from one explicitly registered source MR.
 * TCP carries a256-byte endpoint/nonce record and R/D/A/P/F control bytes only.
 */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <infiniband/verbs.h>
#include <inttypes.h>
#include <openssl/evp.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define CONTROL_BYTES 256
#define MAX_TOTAL 262144u
#define PEER_IP "198.18.10.1"
#define FPGA_IP "198.18.10.2"

struct endpoint {
    uint32_t qpn, psn, rkey, resources;
    uint64_t address;
    size_t size, count;
    union ibv_gid gid;
    uint8_t nonce[32];
};

static int transfer(int fd, void *buffer, size_t length, bool writing)
{
    uint8_t *p = buffer;
    while (length) {
        ssize_t n = writing ? send(fd, p, length, MSG_NOSIGNAL) : recv(fd, p, length, 0);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { fprintf(stderr, "control %s failed: %s\n", writing ? "send" : "recv", n ? strerror(errno) : "EOF"); return -1; }
        p += n; length -= (size_t)n;
    }
    return 0;
}

static void hex(char *output, const uint8_t *bytes, size_t count)
{
    for (size_t i = 0; i < count; ++i) snprintf(output + i * 2, 3, "%02x", bytes[i]);
}

static int unhex(const char *text, uint8_t *output, size_t count)
{
    if (strlen(text) != count * 2 || strspn(text, "0123456789abcdefABCDEF") != count * 2) return -1;
    for (size_t i = 0; i < count; ++i) {
        char part[3] = {text[i * 2], text[i * 2 + 1], 0};
        output[i] = (uint8_t)strtoul(part, NULL, 16);
    }
    return 0;
}

static int integer(const char *text, int base, size_t width, uint64_t maximum, uint64_t *output)
{
    const char *digits = base == 16 ? "0123456789abcdefABCDEF" : "0123456789";
    size_t n = strlen(text);
    if (!n || n > width || strspn(text, digits) != n) return -1;
    errno = 0; char *end = NULL;
    unsigned long long value = strtoull(text, &end, base);
    if (errno || !end || *end || value > maximum) return -1;
    *output = value; return 0;
}

static uint64_t number(const char *text, uint64_t maximum)
{
    if (!*text || *text == '+' || *text == '-') { fprintf(stderr, "invalid number\n"); exit(2); }
    errno = 0; char *end = NULL;
    unsigned long long value = strtoull(text, &end, 0);
    if (errno || !end || *end || value > maximum) { fprintf(stderr, "invalid number: %s\n", text); exit(2); }
    return value;
}

static int encode(char output[CONTROL_BYTES], const struct endpoint *e)
{
    char gid[33], nonce[65]; hex(gid, e->gid.raw, 16); hex(nonce, e->nonce, 32);
    memset(output, 0, CONTROL_BYTES);
    int n = snprintf(output, CONTROL_BYTES, "AS02RD2 %x %x %x %" PRIx64 " %zu %zu %s %s %u\n",
        e->qpn, e->psn, e->rkey, e->address, e->size, e->count, gid, nonce, e->resources);
    return n > 0 && n < CONTROL_BYTES ? 0 : -1;
}

static int decode(char input[CONTROL_BYTES], struct endpoint *e)
{
    char *nul = memchr(input, 0, CONTROL_BYTES);
    if (!nul || nul == input || nul[-1] != '\n') return -1;
    for (char *p = nul; p < input + CONTROL_BYTES; ++p) if (*p) return -1;
    nul[-1] = 0;
    if (*input == ' ' || !*input || input[strlen(input) - 1] == ' ' || strstr(input, "  ")) return -1;
    char *fields[11] = {0}, *save = NULL; size_t count = 0;
    for (char *p = strtok_r(input, " ", &save); p; p = strtok_r(NULL, " ", &save)) {
        if (count >= 10) return -1;
        fields[count++] = p;
    }
    if (count != 10 || strcmp(fields[0], "AS02RD2")) return -1;
    uint64_t values[7];
    if (integer(fields[1], 16, 6, 0xffffff, &values[0]) || integer(fields[2], 16, 6, 0xffffff, &values[1]) ||
        integer(fields[3], 16, 8, UINT32_MAX, &values[2]) || integer(fields[4], 16, 16, UINT64_MAX, &values[3]) ||
        integer(fields[5], 10, 5, 65536, &values[4]) || integer(fields[6], 10, 4, 4096, &values[5]) ||
        integer(fields[9], 10, 2, 32, &values[6]) || unhex(fields[7], e->gid.raw, 16) ||
        unhex(fields[8], e->nonce, 32)) return -1;
    e->qpn = (uint32_t)values[0]; e->psn = (uint32_t)values[1]; e->rkey = (uint32_t)values[2];
    e->address = values[3]; e->size = (size_t)values[4]; e->count = (size_t)values[5]; e->resources = (uint32_t)values[6];
    if (!e->size || !e->count || !e->resources || e->qpn < 2 || e->size * e->count > MAX_TOTAL) return -1;
    return 0;
}

static int derive(uint8_t *output, size_t total, const struct endpoint *e)
{
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    uint32_t context[2] = {htonl((uint32_t)e->size), htonl((uint32_t)e->count)};
    int ok = ctx && EVP_DigestInit_ex(ctx, EVP_shake256(), NULL) == 1 &&
        EVP_DigestUpdate(ctx, e->nonce, sizeof(e->nonce)) == 1 && EVP_DigestUpdate(ctx, context, sizeof(context)) == 1 &&
        EVP_DigestFinalXOF(ctx, output, total) == 1;
    EVP_MD_CTX_free(ctx); return ok ? 0 : -1;
}

static int sha256(char output[65], const uint8_t *bytes, size_t total)
{
    uint8_t digest[32]; unsigned length = 0;
    if (EVP_Digest(bytes, total, digest, &length, EVP_sha256(), NULL) != 1 || length != sizeof(digest)) return -1;
    hex(output, digest, sizeof(digest)); return 0;
}

static int self_test(void)
{
    struct endpoint e = {.qpn = 2, .psn = 0xfffffe, .size = 65, .count = 3, .resources = 1};
    for (size_t i = 0; i < sizeof(e.nonce); ++i) e.nonce[i] = (uint8_t)i;
    uint8_t payload[195], other[195]; char text[391], digest[65], nonce[65];
    if (derive(payload, sizeof(payload), &e) || derive(other, sizeof(other), &e) || memcmp(payload, other, sizeof(payload))) return 1;
    e.nonce[0] ^= 1;
    if (derive(other, sizeof(other), &e) || !memcmp(payload, other, sizeof(payload))) return 1;
    e.nonce[0] ^= 1;
    char packet[CONTROL_BYTES], copy[CONTROL_BYTES]; struct endpoint decoded = {0};
    if (encode(packet, &e)) return 1;
    memcpy(copy, packet, sizeof(copy)); if (decode(copy, &decoded) || decoded.size != 65 || decoded.count != 3 ||
        decoded.psn != e.psn || memcmp(decoded.nonce, e.nonce, sizeof(e.nonce))) return 1;
    for (int mode = 0; mode < 4; ++mode) {
        memcpy(copy, packet, sizeof(copy));
        if (mode == 0) copy[0] = 'X';
        if (mode == 1) copy[CONTROL_BYTES - 1] = 'X';
        if (mode == 2) memset(copy, 'a', sizeof(copy));
        if (mode == 3) copy[8] = '-';
        if (!decode(copy, &decoded)) return 1;
    }
    if (sha256(digest, payload, sizeof(payload))) return 1;
    hex(text, payload, sizeof(payload)); hex(nonce, e.nonce, sizeof(e.nonce));
    printf("{\"event\":\"offline_read_peer_test\",\"pass\":true,\"hardware_access\":false,"
        "\"message_bytes\":65,\"messages\":3,\"nonce\":\"%s\",\"payload_hex\":\"%s\",\"sha256\":\"%s\","
        "\"protocol_negative_controls\":4}\n", nonce, text, digest);
    return 0;
}

static int audited_device(void)
{
    char target[512];
    ssize_t n = readlink("/sys/class/infiniband/mlx5_0/device", target, sizeof(target) - 1);
    if (n <= 0 || (size_t)n >= sizeof(target) - 1) return -1;
    target[n] = 0; char *tail = strrchr(target, '/');
    return tail && !strcmp(tail + 1, "0000:03:00.0") ? 0 : -1;
}

static int listen_control(const char *ip, uint16_t port)
{
    int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    struct sockaddr_in local = {.sin_family = AF_INET, .sin_port = htons(port)}, remote = {0};
    if (fd < 0 || inet_pton(AF_INET, ip, &local.sin_addr) != 1) { if (fd >= 0) close(fd); return -1; }
    int yes = 1; setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) || listen(fd, 1)) { perror("bind/listen"); close(fd); return -1; }
    printf("{\"event\":\"listening\",\"ip\":\"%s\",\"port\":%u}\n", ip, port);
    struct pollfd ready = {.fd = fd, .events = POLLIN};
    if (poll(&ready, 1, 10000) != 1) { fprintf(stderr, "accept deadline\n"); close(fd); return -1; }
    socklen_t length = sizeof(remote); int accepted = accept(fd, (struct sockaddr *)&remote, &length); close(fd);
    struct in_addr wanted; inet_pton(AF_INET, FPGA_IP, &wanted);
    if (accepted < 0 || remote.sin_addr.s_addr != wanted.s_addr) {
        fprintf(stderr, "unexpected control peer\n"); if (accepted >= 0) close(accepted); return -1;
    }
    struct timeval deadline = {.tv_sec = 15};
    if (setsockopt(accepted, SOL_SOCKET, SO_RCVTIMEO, &deadline, sizeof(deadline)) ||
        setsockopt(accepted, SOL_SOCKET, SO_SNDTIMEO, &deadline, sizeof(deadline))) { close(accepted); return -1; }
    return accepted;
}

static int ready_qp(struct ibv_qp *qp, int gid_index, const struct endpoint *local, const struct endpoint *remote)
{
    struct ibv_qp_attr a = {.qp_state = IBV_QPS_RTR, .path_mtu = IBV_MTU_4096, .dest_qp_num = remote->qpn,
        .rq_psn = remote->psn, .max_dest_rd_atomic = (uint8_t)local->resources, .min_rnr_timer = 12};
    a.ah_attr.is_global = 1; a.ah_attr.port_num = 1; a.ah_attr.grh.dgid = remote->gid;
    a.ah_attr.grh.sgid_index = gid_index; a.ah_attr.grh.hop_limit = 64;
    if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_AV | IBV_QP_PATH_MTU | IBV_QP_DEST_QPN |
        IBV_QP_RQ_PSN | IBV_QP_MAX_DEST_RD_ATOMIC | IBV_QP_MIN_RNR_TIMER)) { perror("QP RTR"); return -1; }
    memset(&a, 0, sizeof(a)); a.qp_state = IBV_QPS_RTS; a.sq_psn = local->psn;
    a.timeout = 14; a.retry_cnt = 7; a.rnr_retry = 7; a.max_rd_atomic = 1;
    if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_SQ_PSN | IBV_QP_TIMEOUT | IBV_QP_RETRY_CNT |
        IBV_QP_RNR_RETRY | IBV_QP_MAX_QP_RD_ATOMIC)) { perror("QP RTS"); return -1; }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--self-test")) return self_test();
    if (argc < 8 || argc > 9) {
        fprintf(stderr, "Usage: %s mlx5_0 GID_INDEX " PEER_IP " BYTES COUNT PORT PSN [READ_RESOURCES=1]\n", argv[0]); return 2;
    }
    if (!getenv("AS02_ALLOW_NATIVE_FPGA_RDMA_TEST") || strcmp(getenv("AS02_ALLOW_NATIVE_FPGA_RDMA_TEST"), "YES") ||
        !getenv("AS02_PHYSICAL_REVIEW_COMPLETE") || strcmp(getenv("AS02_PHYSICAL_REVIEW_COMPLETE"), "YES")) {
        fprintf(stderr, "explicit finite-test/physical-review authorization required\n"); return 2;
    }
    if (strcmp(argv[1], "mlx5_0") || strcmp(argv[3], PEER_IP) || audited_device()) {
        fprintf(stderr, "requires audited native CX455A at0000:03:00.0 and dedicated IP\n"); return 2;
    }
    int gid_index = (int)number(argv[2], 255);
    struct endpoint local = {.size = number(argv[4], 65536), .count = number(argv[5], 4096),
        .psn = (uint32_t)number(argv[7], 0xffffff), .resources = argc == 9 ? (uint32_t)number(argv[8], 32) : 1};
    uint16_t port = (uint16_t)number(argv[6], 65535);
    size_t stride = (local.size + 63) & ~(size_t)63;
    if (!port || !local.size || !local.count || !local.resources || stride * local.count > MAX_TOTAL) {
        fprintf(stderr, "invalid capture size/count/port/read resources\n"); return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    int result = 1, fd = -1;
    struct ibv_device **devices = NULL; struct ibv_context *context = NULL;
    struct ibv_pd *pd = NULL; struct ibv_cq *cq = NULL; struct ibv_mr *mr = NULL; struct ibv_qp *qp = NULL;
    uint8_t *buffer = NULL, *expected = NULL;
    size_t random_bytes = 0;
    while (random_bytes < sizeof(local.nonce)) {
        ssize_t n = getrandom(local.nonce + random_bytes, sizeof(local.nonce) - random_bytes, GRND_NONBLOCK);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { perror("getrandom"); goto cleanup; }
        random_bytes += (size_t)n;
    }
    devices = ibv_get_device_list(NULL);
    if (!devices) { perror("device list"); goto cleanup; }
    for (size_t i = 0; devices[i]; ++i) if (!strcmp(ibv_get_device_name(devices[i]), argv[1])) {
        context = ibv_open_device(devices[i]); break;
    }
    if (!context) { fprintf(stderr, "cannot open native mlx5_0\n"); goto cleanup; }
    struct ibv_port_attr pa; struct ibv_gid_entry ge; struct ibv_device_attr da;
    if (ibv_query_port(context, 1, &pa) || pa.state != IBV_PORT_ACTIVE || pa.link_layer != IBV_LINK_LAYER_ETHERNET ||
        pa.active_mtu < IBV_MTU_4096 || ibv_query_gid_ex(context, 1, gid_index, &ge, 0) ||
        ge.gid_type != IBV_GID_TYPE_ROCE_V2 || ibv_query_device(context, &da) ||
        da.max_qp_rd_atom < (int)local.resources || da.max_qp_init_rd_atom < (int)local.resources) {
        fprintf(stderr, "requires active native Ethernet/RoCEv2 MTU4096 and negotiated READ resources\n"); goto cleanup;
    }
    uint8_t gid_prefix[12] = {0,0,0,0,0,0,0,0,0,0,255,255}; struct in_addr ip;
    inet_pton(AF_INET, PEER_IP, &ip);
    if (memcmp(ge.gid.raw, gid_prefix, 12) || memcmp(ge.gid.raw + 12, &ip, 4)) {
        fprintf(stderr, "wrong IPv4-mapped RoCEv2 GID\n"); goto cleanup;
    }
    local.gid = ge.gid; size_t total = local.size * local.count;
    pd = ibv_alloc_pd(context); cq = ibv_create_cq(context, 4, NULL, NULL, 0);
    if (!pd || !cq || posix_memalign((void **)&buffer, 4096, total) || !(expected = malloc(total)) || derive(buffer, total, &local)) {
        fprintf(stderr, "PD/CQ/source allocation/generation failed\n"); goto cleanup;
    }
    memcpy(expected, buffer, total);
    mr = ibv_reg_mr(pd, buffer, total, IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_READ);
    if (!mr) { perror("register REMOTE_READ MR"); goto cleanup; }
    struct ibv_qp_init_attr init = {.send_cq = cq, .recv_cq = cq, .qp_type = IBV_QPT_RC,
        .cap = {.max_send_wr = 1, .max_recv_wr = 1, .max_send_sge = 1, .max_recv_sge = 1}};
    qp = ibv_create_qp(pd, &init);
    if (!qp) { perror("create QP"); goto cleanup; }
    struct ibv_qp_attr qa = {.qp_state = IBV_QPS_INIT, .pkey_index = 0, .port_num = 1,
        .qp_access_flags = IBV_ACCESS_REMOTE_READ};
    if (ibv_modify_qp(qp, &qa, IBV_QP_STATE | IBV_QP_PKEY_INDEX | IBV_QP_PORT | IBV_QP_ACCESS_FLAGS)) {
        perror("QP INIT"); goto cleanup;
    }
    local.qpn = qp->qp_num; local.rkey = mr->rkey; local.address = (uintptr_t)buffer;
    char nonce[65], digest[65], gid[INET6_ADDRSTRLEN]; hex(nonce, local.nonce, 32);
    if (sha256(digest, buffer, total)) goto cleanup;
    inet_ntop(AF_INET6, local.gid.raw, gid, sizeof(gid));
    printf("{\"event\":\"read_source\",\"device\":\"mlx5_0\",\"bdf\":\"0000:03:00.0\",\"gid_index\":%d,"
        "\"gid\":\"%s\",\"qpn\":%u,\"psn\":%u,\"rkey\":\"0x%08x\",\"address\":\"0x%016" PRIx64 "\","
        "\"message_bytes\":%zu,\"messages\":%zu,\"path_mtu\":4096,\"read_resources\":%u,"
        "\"remote_read_granted\":true,\"remote_write_granted\":false,\"nonce\":\"%s\",\"source_sha256\":\"%s\"}\n",
        gid_index, gid, local.qpn, local.psn, local.rkey, local.address, local.size, local.count, local.resources, nonce, digest);
    fd = listen_control(argv[3], port); if (fd < 0) goto cleanup;
    char packet[CONTROL_BYTES], input[CONTROL_BYTES]; struct endpoint remote = {0};
    if (encode(packet, &local) || transfer(fd, packet, sizeof(packet), true) || transfer(fd, input, sizeof(input), false) || decode(input, &remote)) {
        fprintf(stderr, "bad endpoint record\n"); goto cleanup;
    }
    inet_pton(AF_INET, FPGA_IP, &ip);
    if (remote.qpn >= 8 || remote.size != local.size || remote.count != local.count || remote.rkey || remote.address ||
        remote.resources > local.resources || memcmp(remote.nonce, local.nonce, 32) ||
        memcmp(remote.gid.raw, gid_prefix, 12) || memcmp(remote.gid.raw + 12, &ip, 4)) {
        fprintf(stderr, "client endpoint/nonce/resources do not match the finite FPGA READ\n"); goto cleanup;
    }
    printf("{\"event\":\"read_remote\",\"qpn\":%u,\"psn\":%u,\"read_resources\":%u}\n", remote.qpn, remote.psn, remote.resources);
    if (ready_qp(qp, gid_index, &local, &remote)) goto cleanup;
    char ready = 'R', command = 0;
    if (transfer(fd, &ready, 1, true) || transfer(fd, &command, 1, false) || command != 'R' ||
        transfer(fd, &command, 1, false) || (command != 'D' && command != 'A')) goto cleanup;
    __sync_synchronize(); size_t mismatches = 0, first_bad = 0;
    for (size_t i = 0; i < total; ++i) if (buffer[i] != expected[i]) { if (!mismatches) first_bad = i; ++mismatches; }
    printf("{\"event\":\"read_source_unchanged\",\"bytes\":%zu,\"mismatches\":%zu,\"first_bad_offset\":%zu,"
        "\"client_quiescent_control\":true,\"client_aborted\":%s,\"pass\":%s}\n", total, mismatches, first_bad,
        command == 'A' ? "true" : "false", mismatches ? "false" : "true");
    ready = mismatches ? 'F' : 'P';
    if (transfer(fd, &ready, 1, true) || mismatches || command != 'D') goto cleanup;
    result = 0;
cleanup:
    if (fd >= 0) close(fd);
    if (qp) ibv_destroy_qp(qp);
    if (mr) ibv_dereg_mr(mr);
    free(buffer); free(expected);
    if (cq) ibv_destroy_cq(cq);
    if (pd) ibv_dealloc_pd(pd);
    if (context) ibv_close_device(context);
    if (devices) ibv_free_device_list(devices);
    return result;
}
