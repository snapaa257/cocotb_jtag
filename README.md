# JTAG interface with Cocotb
Github repository: https://github.com/snapaa257/cocotb_jtag.git

## Introduction
Cocotb-driven verification of the VexRiscv JTAG debug interface.
Motive of tests is to drive the TAP with cocotb + cocotbext-jtag, then moving up the  debug stack: DTM > DMI > OpenOCD > GDB.

Each test seeks to do the folowing: confirm the TAP responds, confirm the DMI bus is live,
confirm a real debugger (OpenOCD) can scan the chain, and finally confirm GDB can
halt and inspect the core end-to-end.

## Quick Note
The tests run against a VexRiscv core generated based on GenSmallAndProductive.scala config with EmbeddedRiscJtag plugin(real TAP).

## Installation
As time of this testing done, Ubuntu used!
1. **Prerequisities**: Icarus Verilog
   ```bash
    sudo apt install iverilog
   ```
Make sure **python3** is installed.

## Py Virtual Env
Create and activate a virtual environment, then install the test dependencies.

Create (first time only):
   ```bash
    python3 -m venv venv
   ```

Activate:
   ```bash
    source venv/bin/activate
   ```

Install packages:
   ```bash
    pip install cocotb cocotbext-jtag
   ```

> `cocotbext-jtag is what drives the JTAG TAP from cocotb. See reo for the
> driver API and usage details: 
> https://github.com/daxzio/cocotbext-jtag.git

## Usage examples
> All test_{name of test} run inside the virtual environment 
> Except xpack and OpenOCD

### 1. DTM / IDCODE - `test_jtag`
Clocks the TAP and reads the IDCODE back to confirm DTM responds and the JTAG chain is wired correctly.
   ```bash
    make MODULE=test_jtag
   ```

### 2. DMI - `test_dmi`
Moving up one layer: using DTM to issue DMI reads/writes to the Debug Module,
confirming the DMI bus beteen DTM and DM is live.
   ```bash
    make MODULE=test_dmi
   ```

### OpenOCD setup
The next two tests need a RISC-V-capable OpenOCD. Install it from the OpenOCDRiscv
repo below, then come back here and continue.
**Open a new terminal and peform this out of this repo**

> OpenOCD repository: https://github.com/SpinalHDL/openocd_riscv.git

### 3. OpenOCD - `test_openocd`
Run OpenOCD up against the running simulation so it can scan the chain, detect
the core, and halt it — confirming a real debugger can talk to the DUT.

Terminal 1:
   ```bash
    make MODULE=test_openocd
   ```

Terminal 2:
Move into the openocd_riscv repo cloned earlier
   ```bash
    ./src/openocd -f ../cocotb_jtag/vexriscv_configs/vexriscv_sim.cfg
   ```

### OR
To do more than halt/resume core on Terminal 2. That is read/write to register
   ```bash
    ./src/openocd -f ../cocotb_jtag/vexriscv_configs/vexriscv_mem.cfg
   ```


### GDB
At time of testing. xpack gdb used. 
Open a new terminal and peform this out of this repo 

   ```bash
    wget https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v12.2.0-1/xpack-riscv-none-elf-gcc-12.2.0-1-linux-x64.tar.gz
    tar xzf xpack-riscv-none-elf-gcc-12.2.0-1-linux-x64.tar.gz
   ```

### 4. GDB - `test_gdb`
Full stack: GDB connects to OpenOCD's gdbserver to halt the core and read/write
registers and memory, end-to-end debug bring-up.

Terminal 1:
   ```bash
    make MODULE=test_gdb
   ```

Terminal 2:
   ```bash
    ./src/openocd -f ../cocotb_jtag/vexriscv_configs/vexriscv_gdb.cfg
   ```

Terminal 3:
Wait until you see **listening for gdb connection** then run it
   ```bash
     xpack-riscv-none-elf-gcc-12.2.0-1/bin/riscv-none-elf-gdb -x cocotb_jtag/vexriscv_configs/cmd.gds
   ```

### OR
For Terminal 3, can manually do it
   ```bash
     xpack-riscv-none-elf-gcc-12.2.0-1/bin/riscv-none-elf-gdb -ex 'set remotetimeout 60' -ex 'target extended-remote localhost:3333'
   ```

## Exit Vitual Env
   ```bash
    deactivate
   ```
