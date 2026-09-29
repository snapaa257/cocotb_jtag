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

# Defisive setter,  assigns val to name in DUT
def _set(dut, name, val):
    if hasattr(dut, name):
        getattr(dut, name).value = val

# Feeding Core with NOP to run forever in background
async def ibus_nop_loop(dut):
    _set(dut, "iBus_cmd_ready", 1) # always ready to accept
    _set(dut, "iBus_rsp_payload_error", 0) # never errors
    dut.iBus_rsp_payload_inst.value = NOP
    dut.iBus_rsp_valid.value = 0
    while True:
        await RisingEdge(dut.clk)
        core_req_instr = dut.iBus_cmd_valid.value
        dut.iBus_rsp_valid.value = 1 if (core_req_instr.is_resolvable and int(core_req_instr) == 1) else 0 # guads against X/Z
        dut.iBus_rsp_payload_inst.value = NOP

# Tying off bus/signals not used as to not interfere
def tie_off(dut):
    _set(dut, "dBus_cmd_read", 1)
    for off_dBus in ("dBus_rsp_valid", "dBus_rsp_ready", "dBus_rsp_error", "dBus_rsp_data"):
        _set(dut, off_dBus, 0)
    for off_irq in ("imerInterrupt", "externalInterrupt", "softwareInterrupt"):
        _set(dut, off_irq, 0)

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
