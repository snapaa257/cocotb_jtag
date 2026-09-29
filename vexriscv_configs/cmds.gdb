set pagination off
set confirm off
set architecture riscv:rv32
set remotetimeout 200
target extended-remote localhost:3333
printf ">>> GDB connected\n"
printf "PC   = 0x%x\n", $pc
printf "--- write x1 via GDB, read back ---\n"
set $x1 = 0xdeadbeef
printf "x1   = 0x%x\n", $x1
printf "--- read memory at reset vector ---\n"
x/4xw 0x80000000
monitor resume
monitor shutdown
quit
