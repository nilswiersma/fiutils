#!/usr/bin/env python3

##
## Copyright (C) 2019 Marc Schink <dev@zapb.de>
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

import sys
import math
import argparse
import struct
import enum

from .openocd import OpenOcd

class Register(enum.IntEnum):
    R0 = 0
    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4
    R5 = 5
    R6 = 6
    R7 = 7
    R8 = 8
    R9 = 9
    R10 = 10
    R11 = 11
    R12 = 12
    SP = 13
    LR = 14
    PC = 15
    PSR = 16

WORD_SIZE = 4

# Initial stack pointer (SP) value.
INITIAL_SP = 0x20000200

# Vector Table Offset Register (VTOR).
VTOR_ADDR = 0xe000ed08
# Interrupt Control and State Register (ICSR).
ICSR_ADDR = 0xe000ed04
# System Handler Control and State Register (SHCSR).
SHCSR_ADDR = 0xe000ed24
# NVIC Interrupt Set-Enable Registers (ISER).
NVIC_ISER0_ADDR = 0xe000e100
# NVIC Interrupt Set-Pending Registers (ISPR).
NVIC_ISPR0_ADDR = 0xe000e200
# Debug Exception and Monitor Control Register (DEMCR).
DEMCR_ADDR = 0xe000edfc
# Memory region with eXecute Never (XN) property.
MEM_XN_ADDR = 0xe0000000

SVC_INST_ADDR = 0x20000000
NOP_INST_ADDR = 0x20000002
LDR_INST_ADDR = 0x20000004
UNDEF_INST_ADDR = 0x20000006

# Inaccessible exception numbers.
INACCESSIBLE_EXC_NUMBERS = [0, 1, 7, 8, 9, 10, 13]


SRAM_ADDR = 0x20000000
SRAM_SIZE_BYTES = 0x2000

def hardfault_to_infinite_thread_loop(openocd: OpenOcd):
    # bx lr at 0x20000000
    openocd.send('mww 0x20000000 0x4770')
    # b #0 at 0x20000004
    openocd.send('mww 0x20000004 0xe7fe')

    # Make sure LR is EXC_RETURN value 0xfffffff9
    lr = openocd.read_register('lr')
    if lr != 0xfffffff9:
        print(f'lr was 0x{lr:08x} instead of 0xfffffff9')
        openocd.write_register('lr', 0xfffffff9)

    # Set pc to bx lr
    openocd.write_register('pc', 0x20000000)
    openocd.step()

    # pc is now the return value from the exception stack
    pc = openocd.read_register('pc')
    print(f'pc=0x{pc:08x}')

    # Set pc to while(1){}
    openocd.write_register('pc', 0x20000004)
    openocd.step()

def dump_systemmemory(openocd: OpenOcd):
    pass
    for offset in range(0, 0x1000, 0x100):
        openocd.send(f'dump_image l0systemmem3-{offset:03x}.bin {0x1ff00000+offset} 0x100')

def fill_sram_memory(openocd: OpenOcd):
    openocd.send(f'write_memory 0x20000000 16 {{ {" ".join(["0x41414141"]*4096)} }}')

def fill_flash_memory(openocd: OpenOcd):
    if False:
        # FLASH_BASE 0x40022000
        # Unlock FLASH_PECR via FLASH_PEKEYR
        openocd.send('mww 0x4002200c 0x89ABCDEF')
        openocd.send('mww 0x4002200c 0x02030405')

        # Clear PRGLOCK via FLASH_PRGKEY, 
        openocd.send('mww 0x40022010 0x8c9daebf')
        openocd.send('mww 0x40022010 0x13141516')

    ret = openocd.send('mdw 0x40022004')
    print(ret)
    assert ret.strip() == '0x40022004: 00000004', f'{ret=}'

    if False:
        # Put some dummy code at the start of flash which configures and turns on LED
        with open('../../led_on/led_on.bin', 'rb') as f:
            led_payload = f.read()
            values = ' '.join(['0x'+led_payload[x:x+4][::-1].hex() for x in range(0, len(led_payload), 4)])
            print(f'Writing LED payload to 0x08000000: {values[:100]}...')
            openocd.send(f'write_memory 0x08000000 32 {{ {values} }}') # 8-bit writes don't work!

        # Fill rest of flash
        START = 0x200 # leave 0x200 for the led on instructions
        assert len(led_payload) < START
    else:
        START = 0

    BASE = 0x08000000
    SIZE = 0x8000
    values = ' '.join(f'0x{~(BASE + x)&0xffffffff:08x}' for x in range(START, SIZE, 4))
    print(f'Filling 0x{BASE:08x} with {values[:100]}...')
    openocd.send(f'write_memory 0x{BASE+START:08x} 32 {{ {values} }}')

    # Fill eeprom
    START = 0
    BASE = 0x08080000
    SIZE = 0x800
    values = ' '.join(f'0x{~(BASE + x)&0xffffffff:08x}' for x in range(START, SIZE, 4))
    print(f'Filling 0x{BASE:08x} with {values[:100]}...')
    openocd.send(f'write_memory 0x{BASE:08x} 32 {{ {values} }}')

    print('dumping back')

    openocd.send('dump_image test-flash.bin 0x08000000 0x8000')
    openocd.send('dump_image test-eeprom.bin 0x08080000 0x800')

def dump_settings(openocd: OpenOcd):
    print(openocd.send('mdw 0x1ff80000'))
    print(openocd.send('mdw 0x40022018'))
    print(openocd.send('mdw 0x4002201c'))
    print(openocd.send('mdw 0x40022004'))
    print(openocd.send('mdw 0x08000000'))

def set_rdp1(openocd: OpenOcd):
    # FLASH_BASE 0x40022000
    # Unlock FLASH_PECR via FLASH_PEKEYR
    openocd.send('mww 0x4002200c 0x89ABCDEF')
    openocd.send('mww 0x4002200c 0x02030405')

    # Unlock option bytes OPTLOCK via FLASH_OPTKEYR 
    openocd.send('mww 0x40022014 0xfbead9c8')
    openocd.send('mww 0x40022014 0x24252627')

    # PECR should be 0x2 (only PRG_LOCK set) instead of reset value 0x7
    ret = openocd.send('mdw 0x40022004')
    print(ret)
    assert ret == '0x40022004: 00000002 ', f'{repr(ret), repr("0x40022004: 00000002")}'

    # OPTR read only (last byte is RDP)
    print(openocd.send('mdw 0x4002201c'))

    # enable RDP1
    openocd.send('mww 0x1ff80000 0xffff0000')

    print('Power cycle to make it have effect')

def set_rdp0_and_mass_erase(openocd: OpenOcd):
    # FLASH_BASE 0x40022000
    # Unlock FLASH_PECR via FLASH_PEKEYR
    openocd.send('mww 0x4002200c 0x89ABCDEF')
    openocd.send('mww 0x4002200c 0x02030405')

    # Unlock option bytes OPTLOCK via FLASH_OPTKEYR 
    openocd.send('mww 0x40022014 0xfbead9c8')
    openocd.send('mww 0x40022014 0x24252627')

    # PECR should be 0x2 (only PRG_LOCK set) instead of reset value 0x7
    ret = openocd.send('mdw 0x40022004')
    print(ret)
    assert ret == '0x40022004: 00000002 '

    # OPTR read only (last byte is RDP)
    print(openocd.send('mdw 0x4002201c'))

    # enable RDP0
    openocd.send('mww 0x1ff80000 0xff5500aa')

    print('Power cycle to make it have effect')

import operator
from functools import reduce
def tx(x): s.write(bytearray(x)); return s.readall()
def chk(l): return reduce(operator.xor, bytearray(struct.pack('>I', l)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--host', default='localhost',
        help='OpenOCD Tcl interface host')
    parser.add_argument('--port', type=int, default=6666,
        help='OpenOCD Tcl interface port')
    args = parser.parse_args()

    oocd = OpenOcd(args.host, args.port)

    try:
        oocd.connect()
        dump_settings(oocd)
    except Exception as e:
        sys.exit('Failed to connect to OpenOCD')
