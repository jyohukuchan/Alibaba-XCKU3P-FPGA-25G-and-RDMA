// SPDX-License-Identifier: BSD-2-Clause-Views
// C-model milestone only. Not an RTL/cosimulation/hardware acceptance test.
#include "rocev2_config.hpp"
#include "rocev2/rocev2.hpp"
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using axis_word = ap_axiu<DATA_WIDTH, 0, 0, 0>;
void rocev2_top(hls::stream<axis_word>&, hls::stream<axis_word>&,
               hls::stream<txMeta>&, hls::stream<ackMeta>&,
               hls::stream<memCmd>&, hls::stream<memCmd>&,
               hls::stream<axis_word>&, hls::stream<axis_word>&,
               hls::stream<qpContext>&, hls::stream<ifConnReq>&, ap_uint<128>,
#ifdef DBG_IBV
               hls::stream<psnPkg>&,
#endif
               ap_uint<32>&, ap_uint<32>&, ap_uint<32>&, ap_uint<32>&, ap_uint<32>&);

static void require(bool condition, const char *message)
{
    if (!condition) { std::cerr << "FAIL: " << message << std::endl; std::exit(1); }
}

static std::vector<unsigned char> unhex(const std::string& text)
{
    std::vector<unsigned char> bytes;
    for (size_t i = 0; i < text.size(); i += 2)
        bytes.push_back(static_cast<unsigned char>(std::stoul(text.substr(i, 2), nullptr, 16)));
    return bytes;
}

static void drain(hls::stream<axis_word>& stream, std::vector<unsigned char>& bytes, unsigned& frames)
{
    while (!stream.empty()) {
        axis_word word = stream.read();
        for (unsigned i = 0; i < DATA_WIDTH / 8; ++i)
            if (word.keep[i]) bytes.push_back(word.data(i*8+7, i*8).to_uint());
        if (word.last) ++frames;
    }
}

int main()
{
    require(DATA_WIDTH == 512, "this probe expects 512-bit words");
    qpContext key_probe(READY_SEND, 2, 0x123456, 0x123456, 0xfedcba98, 0);
    require(key_probe.r_key == 0xfedcba98, "QP constructor truncated 32-bit rkey");
    hls::stream<axis_word> rx, tx, mem_write_data, mem_read_data;
    hls::stream<txMeta> sq;
    hls::stream<ackMeta> completions;
    hls::stream<memCmd> mem_write_cmd, mem_read_cmd;
    hls::stream<qpContext> contexts;
    hls::stream<ifConnReq> connections;
#ifdef DBG_IBV
    hls::stream<psnPkg> debug;
#endif
    ap_uint<32> crc_drops=0, psn_drops=0, retransmits=0, rx_count=0, tx_count=0;
    // FNS stores IPv4 addresses in byte-lane order, not host/network uint32.
    const ap_uint<32> local_ip = 0x020b12c6, peer_ip = 0x010b12c6;
    ap_uint<128> local_ips=0, peer_ips=0;
    for (unsigned i=0; i<4; ++i) {
        local_ips(i*32+31,i*32)=local_ip;
        peer_ips(i*32+31,i*32)=peer_ip;
    }
    contexts.write(qpContext(READY_SEND, 2, 0x123456, 0x123456, 0x214, 0));
    connections.write(ifConnReq(2, 196, peer_ips, 4791));
    // Independent golden-model WRITE_ONLY, derived from a real CX455A frame
    // with destination QPN changed to the configured table slot 2 and a new
    // valid ICRC. Input begins at IPv4, not the Ethernet header.
    auto packet = unhex(
        "4502007c0f704000401188d7c6120b01c6120b02cd0412b7006800000a40ffff00000002"
        "801234560000615eb7c6b00000000214000000405ad95cd356d548cf42c144fb7efd70f76"
        "ae96ce366e5189f1291148b0e8d00873ab93cb336b528af22a1245bde5dd057ca49cc43"
        "c645f87ff271f46bee6de0677cce1ebe");
    std::vector<unsigned char> received, acknowledgement;
    unsigned memory_frames=0, network_frames=0, commands=0;
    for (unsigned cycle=0; cycle<2000; ++cycle) {
        if (cycle==64) {
            for (unsigned offset=0; offset<packet.size(); offset+=DATA_WIDTH/8) {
                axis_word word;
                word.data=0; word.keep=0; word.strb=0;
                for (unsigned byte=0; byte<DATA_WIDTH/8 && offset+byte<packet.size(); ++byte) {
                    word.data(byte*8+7,byte*8)=packet[offset+byte];
                    word.keep[byte]=1; word.strb[byte]=1;
                }
                word.last=offset+DATA_WIDTH/8>=packet.size();
                rx.write(word);
            }
        }
        rocev2_top(rx, tx, sq, completions, mem_write_cmd, mem_read_cmd,
                   mem_write_data, mem_read_data, contexts, connections, local_ips,
#ifdef DBG_IBV
                   debug,
#endif
                   crc_drops, psn_drops, retransmits, rx_count, tx_count);
        while (!mem_write_cmd.empty()) {
            memCmd command=mem_write_cmd.read();
            ++commands;
            require(command.addr==0x615eb7c6b000ULL && command.len==64, "wrong memory command address/length");
        }
        drain(mem_write_data, received, memory_frames);
        drain(tx, acknowledgement, network_frames);
#ifdef DBG_IBV
        while (!debug.empty()) debug.read();
#endif
    }
    require(commands==1 && memory_frames==1 && received.size()==64, "missing/extra RDMA write data");
    for (unsigned i=0; i<received.size(); ++i)
        require(received[i]==static_cast<unsigned char>((i*131)^(i>>8)^0x5a), "payload mismatch");
    require(mem_read_cmd.empty() && completions.empty(), "unexpected read/completion event");
    require(network_frames==1 && acknowledgement.size()==44, "missing/incorrect pre-ICRC ACK frame");
    require(acknowledgement[28]==0x11, "wrong ACK opcode");
    require(acknowledgement[33]==0 && acknowledgement[34]==0 && acknowledgement[35]==196, "wrong ACK QPN");
    require(acknowledgement[37]==0x12 && acknowledgement[38]==0x34 && acknowledgement[39]==0x56, "wrong ACK PSN");
    require((acknowledgement[40]&0xe0)==0, "non-success AETH");
    std::cout << std::dec << "Counters: crc_drop=" << crc_drops << " psn_drop=" << psn_drops
              << " retrans=" << retransmits << " rx=" << rx_count << " tx=" << tx_count << std::endl;
    // Upstream counters increment per transport-stream WORD, not per packet:
    // BTH + RETH + 64 payload bytes span two 512-bit RX words; ACK is one.
    require(psn_drops==0 && retransmits==0 && rx_count==2 && tx_count==1, "unexpected protocol word counters");
    std::cout << "PASS C-model WRITE_ONLY: 64 data bytes, memory command, ACK QPN/PSN/AETH; ACK bytes="
              << acknowledgement.size() << ". External ICRC/protection/RTL timing still unverified." << std::endl;
    return 0;
}
