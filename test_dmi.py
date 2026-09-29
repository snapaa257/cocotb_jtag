"""
 This test is to prove that the DM logic required to halt/resume Core is alive
 Now keeping in mind, DM is a CDC crossing, unlike DTM&DTMCS which are TCK domain
 
 NOTE: BFM (Bus Functional Model)
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotbext.jtag import JTAGBus, JTAGDriver, JTAGDevice

# params
ABITS = 7
IR_IDCODE, IR_DTMCS, IR_DMI = 0x01, 0x10, 0x11
DMCONTROL, DMSTATUS = 0x10, 0x11
OP_NOP, OP_READ, OP_WRITE = 0, 1, 2
DMI_SUCCESS, DMI_BUSY = 0, 3 # result code after trans, 
DTMCS_DMIRESET = 1 << 16 # bit to clr busy flag

# shifting raw bitstream into DMI DR
def  dmi_pack(addr, data, op):
     return  (addr << 34)  | ((data & 0xFFFFFFFF) << 2) | (op & 0x03)

# Describes the JTAG model in dut
class VexDevice(JTAGDevice):
    def __init__(self):
        super().__init__(name="vexriscv", idcode=0x10002FFF, ir_len=5)
        self.add_jtag_reg("IDCODE", 32, IR_IDCODE)
        self.add_jtag_reg("DTMCS", 32, IR_DTMCS)
        self.add_jtag_reg("DMI", ABITS + 32 + 2, IR_DMI)

# Wrapper around the BFM write call
async def scan(jtag, reg, val):
    await jtag.write(reg, val)
    return jtag.ret_val

# Clear busy flag when DMI is busy
async def dmireset(jtag):
    await scan(jtag, "DTMCS", DTMCS_DMIRESET)

# Read transaction with retry logic
async def dmi_read(jtag, addr, tries=8):
    await scan(jtag, "DMI", dmi_pack(addr, 0, OP_READ))
    raw = 0
    for _ in range(tries):
        raw = await scan(jtag, "DMI", dmi_pack(0, 0, OP_NOP))
        op = raw & 0x3
        if op == DMI_SUCCESS:
            return (raw >> 2) & 0xFFFFFFFF # mask of 2-bit op
        if op == DMI_BUSY:
            await dmireset(jtag)
            await scan(jtag, "DMI", dmi_pack(addr, 0, OP_READ))
    raise Exception(f"DMI read @0x{addr:x} stuck busy; last data=0x{(raw >> 2) & 0xFFFFFFFF:08x}")

async def  dmi_write(jtag, addr, data, tries=8):
    await scan(jtag, "DMI", dmi_pack(addr, data, OP_WRITE))
    raw = 0
    for _ in range(tries):
        raw = await scan(jtag, "DMI", dmi_pack(0, 0, OP_NOP))
        op = raw & 0x3
        if op == DMI_SUCCESS:
            return
        if op == DMI_BUSY:
            await dmireset(jtag)
            await scan(jtag, "DMI", dmi_pack(addr, data, OP_WRITE))
    raise Exception(f"DMI write @0x{addr:x} stuck busy")

@cocotb.test()
async def dmstatus_test(dut):
# Reset block and clock start
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.reset.value = 1
    dut.debugReset.value = 1
    await Timer(50, unit="ns")
    dut.reset.value = 0
    dut.debugReset.value = 0
    await Timer(50, unit="ns")

# JTAG Setup
    bus = JTAGBus(dut, prefix="jtag")
    jtag = JTAGDriver(bus)
    dev = VexDevice()
    dev.idle_delay = 16
    jtag.add_device(dev)
    await jtag.reset_fsm()

# IDCODE check
    idcode = await scan(jtag, "IDCODE", 0)
    assert idcode == 0x10002FFF, f"idcode 0x{idcode:08x}"
    dut._log.info(f"IDCODE = 0x{idcode:08x}")

# DMTCS check
    dtmcs = await scan(jtag, "DTMCS", 0)
    dut._log.info(f"DTMCS = 0x{dtmcs:08x} version={dtmcs & 0xF} abits={(dtmcs >> 4) & 0x3F}")
    assert (dtmcs >> 4) & 0x3F == ABITS, "DTMCS abits mismatch"
    await dmireset(jtag)

# DM 
    await dmi_write(jtag, DMCONTROL, 0x00000001) # dmactive = 1
    data = await dmi_read(jtag, DMSTATUS)

# unpacking individial dmstaus field
    version = data &  0x0F
    authenticated = (data >> 7) & 1
    anyhalted = (data >> 8) & 1
    allhalted = (data >> 9) & 1
    allrunning = (data >> 11) & 1
    dut._log.info(
        f"dmstatus = 0x{data:08x} version={version} authenticatd={authenticated}"
        f"anyhalted={anyhalted} allhalted={allhalted} allrunning={allrunning}"
    )
    assert version in (2, 3), f"dmstatus.version {version}"
    assert authenticated == 1, f"DM Not authenicated"
    dut._log.info("PASS: DM alive over DMI :)")
    dut._log.info("dmstatus read with op=success!")
