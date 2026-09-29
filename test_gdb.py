"""
 Test is to do much more than halt/resume core
 OpenOCD + GDB over remote-bitbang with real memory model
 on both iBus and dBus so registers can be read, single-step,
 and Memory access

"""

import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge
from cocotbext.jtag import JTAGBus
from cocotbext.jtag.ocd_client import OCDDriver

NOP = 0x00000013 # no-op, harmless instr. for cpu to run

# Defisive setter,  assigns val to name in DUT
def _set(dut, name, val):
    if hasattr(dut, name):
        getattr(dut, name).value = val

# Sparse fake RAM that both buses share
class Mem:
    def __init__(self): # empty backing store
        self.d = {}
    def word_ret(self, addr): # return stored word or NOP if nothing writen
        return self.d.get(addr & ~3, NOP)
    def masked_write(self, addr, data, mask): # byte-masked write
        adr = addr & ~3
        cur = self.d.get(adr, 0) # fetch existing word to modify. def 0
        for index in range(4):
            if (mask >> index) & 1: # 4 bits, 1 bit per byte lane
                # clear byte slot, extract mtching byte from incoming data, mv back to slot and merge in "|"
                cur = (cur & ~(0xFF << (index * 8))) | (((data >> (index * 8)) & 0xFF) << (index * 8))
        self.d[adr] = cur # store merged word

# instruction fetch of memory, returns word stored
async def ibus_server(dut, mem):
    _set(dut, "iBus_cmd_ready", 1)
    _set(dut, "iBus_rsp_payload_error", 0)
    dut.iBus_rsp_valid.value = 0
    dut.iBus_rsp_payload_inst.value = NOP
    while True:
        await RisingEdge(dut.clk)
        core_req_inst = dut.iBus_cmd_valid.value
        if core_req_inst.is_resolvable and int(core_req_inst) == 1:
            pc = int(dut.iBus_cmd_payload_pc.value)
            dut.iBus_rsp_payload_inst.value = mem.word_ret(pc)
            dut.iBus_rsp_valid.value = 1
        else:
            dut.iBus_rsp_valid.value = 0

# data memory, loads and stores
async def dbus_server(dut, mem):
    _set(dut, "dBus_cmd_ready", 1)
    _set(dut, "dBus_rsp_error", 0)
    _set(dut, "dBus_rsp_data", 0)
    _set(dut, "dBus_rsp_ready", 0)
    while True:
        await RisingEdge(dut.clk)
        core_req_inst = dut.dBus_cmd_valid.value
        if core_req_inst.is_resolvable and int(core_req_inst) == 1:
            addr = int(dut.dBus_cmd_payload_address.value)
            wr = int(dut.dBus_cmd_payload_wr.value)
            if wr:
                data = int(dut.dBus_cmd_payload_data.value)
                mask = int(dut.dBus_cmd_payload_mask.value)
                mem.masked_write(addr, data, mask)
            rdata = mem.word_ret(addr)
            await RisingEdge(dut.clk)
            dut.dBus_rsp_data.value = rdata
            dut.dBus_rsp_ready.value = 1
            await RisingEdge(dut.clk)
            dut.dBus_rsp_ready.value = 0
        else: 
            dut.dBus_rsp_ready.value = 0

def tie_off(dut):
    for off_irq in ("timerInterrupt", "externalInterrupt", "softwareInterrupt"):
        _set(dut, off_irq, 0)

# monitor jtag TAP drive
async def jtag_monitor(dut):
    while True:
        await RisingEdge(dut.jtag_tck)
        dut._log.info(f"TMS={dut.jtag_tms.value} TDI={dut.jtag_tdi.value} TDO={dut.jtag_tdo.value}")


@cocotb.test()
async def gdb_test(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    tie_off(dut)
    mem = Mem()

    # tiny program at reset vector, a few NOPs then jump-to-self
    base = 0x80000000
    for index in range(8):
        mem.d[base + 4 * index] = NOP
    mem.d[base + 32] = 0x0000006F # infinite loop, core stays put

    dut.reset.value = 1
    dut.debugReset.value = 1
    await Timer(50, unit="ns")
    dut.reset.value = 0
    dut.debugReset.value = 0
    cocotb.start_soon(ibus_server(dut, mem))
    cocotb.start_soon(dbus_server(dut, mem))
    #cocotb.start_soon(jtag_monitor(dut))
    await Timer(200, unit="ns")

    bus = JTAGBus(dut, prefix="jtag")
    dut._log.info("Waiting for OpenOCD on localhosy:9999..")
    driver = OCDDriver(bus, host="localhost", port=9999, period=1000, units="ns")
    #driver.log.setLevel(logging.DEBUG)
    await driver._start_parse()
    dut._log.info("session finished")
