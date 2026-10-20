// SPDX-License-Identifier: BSD-2-Clause-Views
// Diagnostic ONLY: link the unchanged failed model objects with debug types.
// A debugger can inspect the actual root at the real Verilog fatal. Never
// suppress a fatal, mutate DUT state, or treat this diagnostic as a pass.
#include "verilated.h"
#include "Vtb.h"
#include "Vtb___024root.h"
#include <memory>

Vtb* as02_debug_top;
Vtb___024root* as02_debug_root;

int main(int argc, char** argv)
{
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    const std::unique_ptr<Vtb> topp{new Vtb{contextp.get()}};
    as02_debug_top=topp.get();
    as02_debug_root=topp->rootp;
    while (!contextp->gotFinish()) {
        topp->eval();
        if (!topp->eventsPending()) break;
        contextp->time(topp->nextTimeSlot());
    }
    topp->final();
    return 0;
}
