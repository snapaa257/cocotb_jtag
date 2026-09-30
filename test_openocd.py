"""
 OpenOCD drives the sim over a live TCP socket (bitbaning)
 Pipleine OpenOCD->socket->OpenOCDCLient->TAP->DTM-DM ..
 OpenOCD paces TCK, NOPs feed ON iBus so core has something to execute.
 Halting/Resuming is possible as core is now running

"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge
from cocotbext.jtag import JTAGBus
from cocotbext.jtag.ocd_client import OCDDriver

NOP = 0x00000013 #  no-op, harmless instr. for cpu to run

# Feeding Core with NOP to run forever in background
async def ibus_nop_loop(dut):
    dut.iBusWishbone_ACK.value = 0
    dut.iBusWishbone_DAT_MISO.value = NOP
    dut.iBusWishbone_ERR.value = 0
    while True:
        await RisingEdge(dut.clk)
        cyc, stb = dut.iBusWishbone_CYC.value, dut.iBusWishbone_STB.value
        active = cyc.is_resolvable and stb.is_resolvable and int(cyc) and int(stb)
        dut.iBusWishbone_ACK.value = 1 if active else 0 #
        dut.iBusWishbone_DAT_MISO.value = NOP

# Tying off bus/signals not used as to not interfere
def tie_off(dut):
    dut.dBusWishbone_ACK.value = 0
    dut.dBusWishbone_DAT_MISO.value = 0
    dut.dBusWishbone_ERR.value = 0
    dut.timerInterrupt.value = 0
    dut.externalInterrupt.value = 0
    dut.softwareInterrupt.value = 0

# OCDDriver: Opens port and listens to OpenOCD single char bitbang commands
#   translates each into a drive on jtag
# ._start_parse: Serves OpenOCD commands one at a time, until OpenOCD sens 'Q' to stop
@cocotb.test()
async def openocd_test(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    tie_off(dut) # runs beore reset so no bus  left floating
    dut.reset.value = 1
    dut.debugReset.value = 1
    await Timer(50, unit="ns")
    dut.reset.value = 0
    dut.debugReset.value = 0
    cocotb.start_soon(ibus_nop_loop(dut)) # core sees nop right after reset
    await Timer(200, unit="ns")

    # OpenOCD Bridge
    bus = JTAGBus(dut, prefix="jtag")
    dut._log.info("Waiting for OpenOCD to connect on lh:9999")
    driver = OCDDriver(bus, host="localhost", port=9999, period=1000, units="ns")
    await driver._start_parse() 
    dut._log.info("OpenOCD session finished")
