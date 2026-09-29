SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/VexRiscv.v
COMPILE_ARGS += -g2012

TOPLEVEL = VexRiscv
MODULE   = test_jtag

include $(shell cocotb-config --makefiles)/Makefile.sim
