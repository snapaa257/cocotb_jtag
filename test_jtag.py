"""
 Proving the TAP via cocotb-jtag,  replica of the Verilog TB
 Device declared to match generated Core RTL, as in: idcode 0x10002fff, ir_len 5
 IDCODE instruction at IR opcode 0x01
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotbext.jtag import JTAGBus, JTAGDriver, JTAGDevice

class VexRiscv(JTAGDevice):
    def __init__(self):
        super().__init__(name="vexriscv", idcode=0x10002FFF, ir_len=5)
        self.add_jtag_reg("IDCODE", 32, 0x01)

@cocotb.test()
async def idcode_test(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.reset.value = 1
    dut.debugReset.value = 1
    await Timer(50, unit="ns")
    dut.reset.value = 0
    dut.debugReset.value = 0
    await Timer(50, unit="ns")

    bus = JTAGBus(dut, prefix="jtag") # map TAP
    jtag = JTAGDriver(bus)
    jtag.add_device(VexRiscv())

    await jtag.reset_fsm() # TM1=1 x5, TLR(Test-Logic-Reset)
    await jtag.read_idcode(retry=5) # covers CDC/async reset

    got = jtag.idcode
    dut._log.info(f"IDCODE read = 0x{got:08x}")
    assert got == 0x10002FFF, f"got 0x{got:08x}, expected 0x10002fff"
    dut._log.info("PASS: TAP alive via cocotb, IDCODE matches")
