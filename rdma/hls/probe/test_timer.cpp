// SPDX-License-Identifier: BSD-2-Clause-Views
// Exercise the actual patched HLS timer at the target clock, not a substitute.
#include <cstdlib>
#include <iostream>
#include "ib_transport_protocol/transport_timer.hpp"

static void require(bool condition, const char* message) {
    if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}

template<int INSTANCE>
struct Timer {
    hls::stream<rxTimerUpdate> clear;
    hls::stream<ap_uint<24> > set;
    hls::stream<retransmission> retrans;
    void step() { transport_timer<INSTANCE>(clear, set, retrans); }
    void idle(unsigned clocks) {
        for (unsigned i = 0; i < clocks; ++i) {
            step(); require(retrans.empty(), "unexpected retransmission");
        }
    }
    unsigned wait(unsigned qpn) {
        for (unsigned elapsed = 1; elapsed <= 250064; ++elapsed) {
            step();
            if (!retrans.empty()) {
                retransmission event = retrans.read();
                require(event.qpn == qpn && event.psn == 0, "wrong retry event");
                require(elapsed >= 250000, "timer expired before one millisecond");
                return elapsed;
            }
        }
        require(false, "timer did not expire within one scan margin"); return 0;
    }
};

int main() {
    require(MAX_QPS == 8 && AS02_TIMER_CLOCK_PS == 4000, "wrong target configuration");
    require(TIME_10us == 313 && TIME_50us == 1563 && TIME_100us == 3125 &&
            TIME_250us == 7813 && TIME_500us == 15625 && TIME_1ms == 31250 &&
            TIME_5ms == 156250 && TIME_12ms == 375000 && TIME_64ms == 2000000,
            "incorrect clock/scan conversion or rounding");
    Timer<71> timer;
    unsigned min_clocks = 250064, max_clocks = 0;
    for (unsigned qp = 0; qp < 8; ++qp) {
        timer.set.write(qp); timer.step();
        const unsigned elapsed = timer.wait(qp);
        if (elapsed < min_clocks) min_clocks = elapsed;
        if (elapsed > max_clocks) max_clocks = elapsed;
        timer.clear.write(rxTimerUpdate(qp, true)); timer.step();
    }
    // Restart-on-ACK must postpone expiry by a full real interval, not just
    // reset the retry counter or use the shortened upstream C-only constants.
    timer.set.write(7); timer.step(); timer.idle(100000);
    timer.clear.write(rxTimerUpdate(7, false)); timer.step(); timer.wait(7);
    timer.clear.write(rxTimerUpdate(7, true)); timer.step();
    timer.set.write(6); timer.step(); timer.idle(10000);
    timer.clear.write(rxTimerUpdate(6, true)); timer.step(); timer.idle(250080);

    // Simultaneous clear/set gives clear priority without losing the set.
    timer.clear.write(rxTimerUpdate(5, true)); timer.set.write(5); timer.step();
    require(!timer.set.empty(), "clear did not take priority");
    timer.step(); require(timer.set.empty(), "deferred set lost"); timer.wait(5);

    // The upstream +5 hazard skip indexed beyond an eight-entry table when
    // the scan position was 5 and QP 7 was updated. Sanitizers check the
    // actual array accesses, not merely that a modulo expression exists.
    Timer<72> boundary;
    boundary.idle(5); boundary.set.write(7); boundary.step(); boundary.idle(16);
    boundary.clear.write(rxTimerUpdate(7, true)); boundary.step(); boundary.idle(250080);
    std::cout << "RESULT {\"pass_test\":true,\"clock_ps\":4000,\"max_qps\":8,"
              << "\"first_retry_qps_checked\":8,\"retry_events_checked\":10,"
              << "\"first_retry_min_clocks\":" << min_clocks << ","
              << "\"first_retry_max_clocks\":" << max_clocks << ","
              << "\"ack_restart_checked\":true,\"ack_stop_checked\":true,"
              << "\"table_boundary_checked\":true,\"clear_set_priority_checked\":true}\n";
}
