// SPDX-License-Identifier: BSD-2-Clause-Views
// Execute actual derived HLS C++ functions, not a replacement protocol model.
// C simulation has no four-state/reset/RTL scheduling/native-DMA proof.
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <streambuf>
#include "ib_transport_protocol/ib_transport_protocol.cpp"

static unsigned checks = 0, headers = 0, table_responses = 0, retries = 0;
static void require(bool ok, const char *message) {
    ++checks;
    if (!ok) throw std::runtime_error(message);
}
struct Quiet : std::streambuf { int overflow(int c) override { return c; } };

static void check_header(event ev, uint32_t expected) {
    hls::stream<ackEvent> ack;
    hls::stream<event> read, app, exh;
    hls::stream<ap_uint<16>> conn, msn_req, lengths;
    hls::stream<ibhMeta> bth;
    hls::stream<txMsnRsp> msn_rsp;
    hls::stream<txPacketInfo> info;
    hls::stream<ap_uint<24>> timer;
    hls::stream<net_axis<512>> words;
    app.write(ev);
    meta_merger<79>(ack, read, app, conn, bth, exh);
    require(conn.read() == ev.qpn, "meta-merger QP");
    require(!bth.empty(), "meta-merger BTH");
    bth.read();
    msn_rsp.write(txMsnRsp(0x123456, 0xa55a96c3));
    for (unsigned n = 0; n != 6; ++n)
        generate_exh<512,79>(exh, msn_rsp, msn_req, lengths, info, timer, words);
    require(msn_req.read() == ev.qpn, "MSN query QP");
    require(!words.empty(), "actual RETH output");
    net_axis<512> word = words.read();
    require(word.last == 1 && words.empty(), "one complete RETH");
    for (unsigned n = 0; n != 4; ++n)
        require(word.data(8*(8+n)+7, 8*(8+n)) == ((expected >> (24-8*n)) & 255),
                "actual network-order full-width RETH key");
    for (unsigned n = 0; n != 8; ++n)
        require(word.data(8*n+7, 8*n) == ((ev.addr.to_uint64() >> (56-8*n)) & 255),
                "actual network-order full-width RETH address");
    require(!lengths.empty() && !info.empty() && !timer.empty(), "RETH sideband outputs");
    lengths.read(); info.read(); timer.read();
    if (ev.op_code == RC_RDMA_READ_REQUEST)
        require(word.keep == 0xffff, "READ RETH exact byte validity");
    ++headers;
}

static retransEntry issue(ibOpCode opcode, uint32_t key, bool valid, bool host,
                          uint32_t psn, unsigned length = 65) {
    hls::stream<txMeta> sq;
    hls::stream<retransEvent> retry;
    hls::stream<retransAddrLen> addrlen;
    hls::stream<memCmdInternal> mem;
    hls::stream<event> output;
    hls::stream<retransMeta> meta;
    hls::stream<retransEntry> insert;
    ap_uint<32> count = 0;
    ap_uint<192> params = 0;
    params(63,0) = UINT64_C(0xf123456789abc040);
    params(127,64) = UINT64_C(0xe23456789abcd080);
    params(159,128) = length;
    params(191,160) = key;
    sq.write(txMeta(opcode, 1, host, 1, 7, params, valid));
    local_req_handler<77>(sq, retry, addrlen, mem, output, count);
    require(sq.empty() && retry.empty() && !output.empty(), "local request consumed once");
    event ev = output.read();
    require(ev.rkey == key && ev.rkey_valid == valid, "per-WR local event context");
    require(ev.addr == UINT64_C(0xe23456789abcd080) && ev.length == length,
            "unmodified virtual address/length");
    if (opcode == RC_RDMA_READ_REQUEST) require(mem.empty(), "READ has no source read");
    else require(mem.read().host == host && mem.empty(), "initial source-host selection");
    check_header(ev, valid ? key : 0xa55a96c3);
    meta.write(retransMeta(1, psn, opcode));
    merge_retrans_request(meta, addrlen, insert);
    require(meta.empty() && addrlen.empty(), "actual retransmission metadata merge");
    retransEntry entry = insert.read();
    require(entry.rkey == key && entry.rkey_valid == valid && entry.host == host,
            "merged key/validity/host context");
    return entry;
}

static void check_table_entry(retransMetaEntry e, unsigned i, bool appended) {
    uint32_t key = i == 0 ? 0 : (UINT32_C(0x80000000) ^ (i * UINT32_C(2654435761)));
    require(e.rkey == key && e.rkey_valid == (i & 1) && e.host == ((i >> 1) & 1),
            "all metadata key/validity/host fields");
    require(e.psn == i && e.opCode == RC_RDMA_READ_REQUEST && e.length == i+1,
            "metadata PSN/opcode/length preserved");
    require(e.localAddr == UINT64_C(0xf123456789000000)+i &&
            e.remoteAddr == UINT64_C(0xe23456789a000000)+i, "metadata full addresses");
    require(e.lst == (i & 1) && e.offs == (i & 15) && e.valid,
            "metadata completion/offset/valid preserved");
    require(e.next == (appended ? (i+1)%META_TABLE_SIZE : 0) && e.isTail == !appended,
            "append changes only link/tail");
}

static void table_test() {
    hls::stream<retransMetaReq> req;
    hls::stream<retransMetaEntry> rsp;
    req.write(retransMetaReq(META_TABLE_SIZE-1));
    for (unsigned n = 0; n != META_TABLE_SIZE; ++n) {
        retrans_meta_table<88>(req, rsp);
        require(rsp.empty() && !req.empty(), "no admission during full initialization");
    }
    retrans_meta_table<88>(req, rsp);
    for (unsigned n = 0; n != META_TABLE_SIZE+1; ++n) {
        if (n != 0) { req.write(retransMetaReq(n-1)); retrans_meta_table<88>(req, rsp); }
        retransMetaEntry e = rsp.read();
        require(e.rkey == 0 && e.rkey_valid == 0 && e.host == PKG_INT &&
                e.psn == 0 && e.next == 0 && e.opCode == static_cast<ibOpCode>(0) &&
                e.localAddr == 0 && e.remoteAddr == 0 && e.length == 0 &&
                e.lst == 0 && e.offs == 0 && !e.valid && !e.isTail,
                "all thirteen initialized metadata fields");
        ++table_responses;
    }
    for (unsigned i = 0; i != META_TABLE_SIZE; ++i) {
        uint32_t key = i == 0 ? 0 : (UINT32_C(0x80000000) ^ (i * UINT32_C(2654435761)));
        retransEntry e(1, i, RC_RDMA_READ_REQUEST, UINT64_C(0xf123456789000000)+i,
                       UINT64_C(0xe23456789a000000)+i, i+1, i&1, i&15,
                       key, i&1, (i>>1)&1);
        req.write(retransMetaReq(i, retransMetaEntry(e)));
        retrans_meta_table<88>(req, rsp);
    }
    for (unsigned i = 0; i != META_TABLE_SIZE; ++i) {
        req.write(retransMetaReq(i)); retrans_meta_table<88>(req, rsp);
        check_table_entry(rsp.read(), i, false); ++table_responses;
        req.write(retransMetaReq(i, ap_uint<16>((i+1)%META_TABLE_SIZE)));
        retrans_meta_table<88>(req, rsp);
        req.write(retransMetaReq(i)); retrans_meta_table<88>(req, rsp);
        check_table_entry(rsp.read(), i, true); ++table_responses;
    }
    require(req.empty() && rsp.empty(), "metadata queues fully checked");
}

static void retry_test() {
    hls::stream<retransUpdate> update;
    hls::stream<retransRdInit> init;
    hls::stream<retransmission> nak, timer;
    hls::stream<retransEntry> insert;
    hls::stream<retransEvent> events;
    auto tick = [&](unsigned count) {
        for (unsigned n = 0; n != count; ++n)
            retransmitter<87>(update, init, nak, timer, insert, events);
    };
    tick(2100);
    retransEntry expected[3] = {
        issue(RC_RDMA_READ_REQUEST, 0, true, true, 0xfffffe, 2*PMTU+65),
        issue(RC_RDMA_WRITE_ONLY, 0x80000001, true, true, 5),
        issue(RC_RDMA_READ_REQUEST, 0xdeadbeef, false, false, 6)
    };
    for (const auto &entry : expected) { insert.write(entry); tick(32); }
    auto verify = [&](unsigned first) {
        for (unsigned i = first; i != 3; ++i) {
            require(!events.empty(), "actual retry event present");
            retransEvent e = events.read(); ++retries;
            require(e.rkey == expected[i].rkey && e.rkey_valid == expected[i].rkey_valid &&
                    e.host == expected[i].host && e.psn == expected[i].psn &&
                    e.localAddr == expected[i].localAddr && e.remoteAddr == expected[i].remoteAddr &&
                    e.length == expected[i].length, "retry retains exact original WR context");
            hls::stream<txMeta> sq;
            hls::stream<retransEvent> retry;
            hls::stream<retransAddrLen> addrlen;
            hls::stream<memCmdInternal> mem;
            hls::stream<event> output;
            ap_uint<32> counter = 0;
            retry.write(e);
            local_req_handler<78>(sq, retry, addrlen, mem, output, counter);
            event ev = output.read();
            require(ev.rkey == e.rkey && ev.rkey_valid == e.rkey_valid &&
                    ev.psn == e.psn && ev.validPsn, "retry local-event PSN and key");
            if (e.op_code == RC_RDMA_READ_REQUEST) require(mem.empty(), "retry READ no source read");
            else require(mem.read().host == e.host, "retry does not force internal source");
            require(addrlen.empty(), "retry does not insert a duplicate owner");
            check_header(ev, e.rkey_valid ? e.rkey.to_uint() : 0xa55a96c3);
        }
        require(events.empty(), "no extra retry events");
    };
    timer.write(retransmission(1)); tick(64); verify(0);
    nak.write(retransmission(1,5)); tick(64); verify(1);
    update.write(retransUpdate(1,0xfffffe,RC_RDMA_READ_RESP_FIRST)); tick(32);
    require(!init.empty() && init.read().laddr == expected[0].localAddr,
            "actual READ FIRST destination initialization");
    expected[0].localAddr += PMTU; expected[0].remoteAddr += PMTU;
    expected[0].length -= PMTU; expected[0].psn += 1;
    timer.write(retransmission(1)); tick(64); verify(0);
    update.write(retransUpdate(1,0xffffff,RC_RDMA_READ_RESP_MIDDLE)); tick(32);
    expected[0].localAddr += PMTU; expected[0].remoteAddr += PMTU;
    expected[0].length -= PMTU; expected[0].psn += 1;
    require(expected[0].psn == 0 && expected[0].length == 65, "READ partial retry PSN wrap");
    timer.write(retransmission(1)); tick(64); verify(0);
    update.write(retransUpdate(1,0,RC_RDMA_READ_RESP_LAST)); tick(32);
    timer.write(retransmission(1)); tick(64); verify(1);
    require(init.empty() && update.empty() && insert.empty(), "retry tests leave checked queues");
}

int main() {
    Quiet quiet;
    auto original = std::cout.rdbuf(&quiet);
    try {
        txMeta legacy;
        require(legacy.rkey_valid == 0, "legacy default constructor key policy");
        txMeta legacy_request(RC_RDMA_READ_REQUEST,1,1,1,0,ap_uint<192>(-1));
        require(legacy_request.rkey_valid == 0, "legacy request constructor key policy");
        ackEvent ack_input(ap_uint<24>(1));
        event ack(ack_input);
        require(ack.rkey == 0 && ack.rkey_valid == 0, "ACK carries no uninitialized key");
        for (uint32_t key : {UINT32_C(0),UINT32_C(0x80000000),UINT32_C(0xffffffff),UINT32_C(0x12345678)})
            for (bool host : {false,true})
                for (ibOpCode op : {RC_RDMA_READ_REQUEST,RC_RDMA_WRITE_ONLY,RC_RDMA_WRITE_FIRST})
                    issue(op,key,true,host,0xfffffe);
        issue(RC_RDMA_READ_REQUEST,0xfeed1234,false,true,1);
        table_test(); retry_test();
        std::cout.rdbuf(original);
        std::cout << std::dec << "{\"pass_test\":true,\"checks\":" << checks
                  << ",\"actual_RETH_headers\":" << headers
                  << ",\"metadata_responses\":" << table_responses
                  << ",\"metadata_entries\":" << META_TABLE_SIZE
                  << ",\"metadata_fields\":13,\"actual_retry_events\":" << retries
                  << ",\"READ_partial_PSN_wrap\":true}\n";
        return 0;
    } catch (const std::exception &e) {
        std::cout.rdbuf(original);
        std::cerr << "WRKEY failure: " << e.what() << '\n'; return 1;
    }
}
