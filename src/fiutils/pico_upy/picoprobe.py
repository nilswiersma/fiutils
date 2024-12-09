# https://github.com/raspberrypi/picoprobe/blob/master/src/probe.pio

from rp2 import asm_pio, StateMachine, PIO
import machine
from machine import Pin, UART, freq

from _thread import start_new_thread

import utime
import random
import array
import struct

@micropython.viper
def reverse_mask(x: uint) -> uint:
    x = ((x & uint(0x55555555)) << 1)  | ((x & uint(0xAAAAAAAA)) >> 1)
    x = ((x & uint(0x33333333)) << 2)  | ((x & uint(0xCCCCCCCC)) >> 2)
    x = ((x & uint(0x0F0F0F0F)) << 4)  | ((x & uint(0xF0F0F0F0)) >> 4)
    x = ((x & uint(0x00FF00FF)) << 8)  | ((x & uint(0xFF00FF00)) >> 8)
    x = ((x & uint(0x0000FFFF)) << 16) | ((x & uint(0xFFFF0000)) >> 16)
    return x

def reverse_header(x):
    return reverse_mask(x) >> 24

def warning(*args, **kwargs):
    print('[WARNING]', *args, **kwargs)

def debug(*args, **kwargs):
    return
    print('[DEBUG]', *args, **kwargs)

def build_header(ap=True, read=True, addr=0):
    ret = 1
    ret |= (ap ^ read ^ ((addr>>1)&1) ^ (addr&1)) << 2
    ret |= addr << 3
    ret |= read << 5
    ret |= ap << 6
    ret |= 1 << 7 
    # ret |= addr << 3
    # ret |= (ap ^ read ^ ((addr>>1)&1) ^ (addr&1)) << 2
    debug(f'header=0b{ret:08b}')
    return ret

freq(270000000)

PROBE_SM = 1
TRIGGER_SM = 0

PROBE_PIN_OFFSET = 2
PROBE_PIN_SWCLK = Pin((PROBE_PIN_OFFSET + 0), Pin.OUT, pull=Pin.PULL_DOWN)
PROBE_PIN_SWDIO = Pin((PROBE_PIN_OFFSET + 1), Pin.OUT, pull=Pin.PULL_UP)

# Set lowest current value to the power pin, this reduces noise on the current measurement
def gpio_current(pin, config):
    ctrl = machine.mem32[0x4001c000 + 4 + 4*pin]
    ctrl &= ~(3 << 4)
    ctrl |= (config << 4)
    machine.mem32[0x4001c000 + 4 + 4*pin] = ctrl

gpio_current(5, 0b00)
POWER_PIN = Pin(5, Pin.OUT)
RESET_PIN = Pin(6, Pin.OUT, pull=Pin.PULL_DOWN)

EXT_TRIGGER_IN = Pin(7, Pin.IN)
EXT_TRIGGER_OUT = Pin(8, Pin.OUT, pull=Pin.PULL_DOWN)
EXT_TRIGGER_DEBUG = Pin(9, Pin.OUT, pull=Pin.PULL_DOWN)

PIO0_BASE = const(0x50200000)
PIO0_FSTAT = const(PIO0_BASE + 0x004)
PIO0_TXF1 = const(PIO0_BASE + 0x014)
PIO0_RXF1 = const(PIO0_BASE + 0x024)

# DP
DPIDR = 0b00 # 0x0[2:3]
CTRLSTAT = 0b10 # 0x4[2:3]
SELECT = 0b01 # 0x8[2:3]
RDBUFF = 0b11 # 0xC[2:3]

# AP
IDR = 0b11 # 0xFC[2:3]
CFG = 0b10 # 0xF4[2:3]
BASE = 0b01 # 0xF8[2:3]
CSW = 0b00 # 0x00[2:3]

TAR = 0b10 # 0x4[2:3]
DRW = 0b11 # 0xC[2:3]

BD0 = 0b00 # 0x10[2:3]
BD1 = 0b10 # 0x14[2:3]
BD2 = 0b01 # 0x18[2:3]
BD3 = 0b11 # 0x1C[2:3]

IDCODE = build_header(ap=False, read=True, addr=DPIDR)

DHCSR = 0xE000EDF0 # see DDI0419E_armv6m_arm.pdf

u = UART(0, 115200, tx=Pin(0), rx=Pin(1))

@asm_pio(autopush=False, autopull=False, in_shiftdir=PIO.SHIFT_RIGHT, out_shiftdir=PIO.SHIFT_RIGHT,
         sideset_init=(PIO.OUT_HIGH,),
         out_init=(PIO.OUT_HIGH,),)
def swd():
    label("write_cmd")
    label("turnaround_cmd")
    pull(block)
    label("write_bitloop")
    # clock to 0 one cycle earlier than bit makes the LA like it more, but doesn't matter for properly reading i think?
    # nop().side(0) 
    out(pins, 1).side(0)
    jmp(x_dec, "write_bitloop").side(1)[1]

    wrap_target()
    label("get_next_cmd")
    pull(block).side(0)
    out(x, 8)
    out(pindirs, 1)
    out(pc, 5)

    label("read_bitloop")
    nop()
    label("read_cmd")
    in_(pins, 1).side(1)[1]
    jmp(x_dec, "read_bitloop").side(0)
    push()
    wrap()

    # workaround for missing pio_sm_exec-like functionality
    jmp("write_cmd")
    jmp("get_next_cmd")
    jmp("turnaround_cmd")
    jmp("read_cmd")

sm = StateMachine(PROBE_SM, swd, freq=16_000_000,
                  sideset_base=PROBE_PIN_SWCLK, 
                  in_base=PROBE_PIN_SWDIO,
                  out_base=PROBE_PIN_SWDIO,
                  set_base=PROBE_PIN_SWDIO,)

@asm_pio(autopush=False, autopull=False,
         sideset_init=(PIO.OUT_LOW, PIO.OUT_LOW,),)
def trigger_wait():
    # Delay value
    pull(block).side(0)
    mov(y, osr)

    # High value
    pull(block)
    mov(x, osr)

    wait(1, pin, 0)

    label("waitloop")
    jmp(y_dec, "waitloop").side(0b10)

    label("highloop")
    jmp(x_dec, "highloop").side(0b11)
    
    nop().side(0)
sm_trigger = StateMachine(0, trigger_wait, 
                          sideset_base=EXT_TRIGGER_OUT,
                          in_base=EXT_TRIGGER_IN)

probe_offset = swd[1]
probe_offset_write_cmd = probe_offset + swd[0][-4]
probe_offset_get_next_cmd = probe_offset + swd[0][-3]
probe_offset_turnaround_cmd = probe_offset + swd[0][-2]
probe_offset_read_cmd = probe_offset + swd[0][-1]

CMD_WRITE = probe_offset_write_cmd
CMD_SKIP = probe_offset_get_next_cmd
CMD_TURNAROUND = probe_offset_turnaround_cmd
CMD_READ = probe_offset_read_cmd

@micropython.viper
def fmt_probe_command(bit_count: uint, out_en: uint, cmd: uint) -> uint:
    return uint( (bit_count - uint(1)) & uint(0xff) | out_en << uint(8) | cmd << uint(9) )

@micropython.viper
def parity(data: uint) -> uint:
    return ((data>>uint(0))  & uint(1)) ^ \
                ((data>>uint(1))  & uint(1)) ^ \
                ((data>>uint(2))  & uint(1)) ^ \
                ((data>>uint(3))  & uint(1)) ^ \
                ((data>>uint(4))  & uint(1)) ^ \
                ((data>>uint(5))  & uint(1)) ^ \
                ((data>>uint(6))  & uint(1)) ^ \
                ((data>>uint(7))  & uint(1)) ^ \
                ((data>>uint(8))  & uint(1)) ^ \
                ((data>>uint(9))  & uint(1)) ^ \
                ((data>>uint(10)) & uint(1)) ^ \
                ((data>>uint(11)) & uint(1)) ^ \
                ((data>>uint(12)) & uint(1)) ^ \
                ((data>>uint(13)) & uint(1)) ^ \
                ((data>>uint(14)) & uint(1)) ^ \
                ((data>>uint(15)) & uint(1)) ^ \
                ((data>>uint(16)) & uint(1)) ^ \
                ((data>>uint(17)) & uint(1)) ^ \
                ((data>>uint(18)) & uint(1)) ^ \
                ((data>>uint(19)) & uint(1)) ^ \
                ((data>>uint(20)) & uint(1)) ^ \
                ((data>>uint(21)) & uint(1)) ^ \
                ((data>>uint(22)) & uint(1)) ^ \
                ((data>>uint(23)) & uint(1)) ^ \
                ((data>>uint(24)) & uint(1)) ^ \
                ((data>>uint(25)) & uint(1)) ^ \
                ((data>>uint(26)) & uint(1)) ^ \
                ((data>>uint(27)) & uint(1)) ^ \
                ((data>>uint(28)) & uint(1)) ^ \
                ((data>>uint(29)) & uint(1)) ^ \
                ((data>>uint(30)) & uint(1)) ^ \
                ((data>>uint(31)) & uint(1))

def probe_read_mode():
    sm.put(fmt_probe_command(0, False, CMD_SKIP))

def probe_write_mode():
    sm.put(fmt_probe_command(0, False, CMD_SKIP))

def read(cmd):
    # cmd = reverse_header(cmd) # don't reverse output from LA, it's already reversed

    sm.put(fmt_probe_command(8, True, CMD_WRITE))
    sm.put(cmd)
    sm.put(fmt_probe_command(1, False, CMD_TURNAROUND))
    sm.put(0)
    sm.put(fmt_probe_command(3, False, CMD_READ)) # ACK
    ret0 = sm.get()
    sm.put(fmt_probe_command(32, False, CMD_READ)) # 32 bits of data
    ret1 = sm.get()
    sm.put(fmt_probe_command(1, False, CMD_READ)) # parity
    ret2 = sm.get()
    sm.put(fmt_probe_command(1, True, CMD_TURNAROUND)) # extra wait cycle which pulls swdio high again
    sm.put(0b1)

    # print(f'ret0=0b{ret0>>(32-3):03b}')
    # print(f'ret1=0b{ret1:032b} 0x{ret1:08x}') # 00001011110000010001010001110111
    # print(f'ret2=0b{ret2>>(32-1):01b}')

    ack = reverse_mask(ret0)
    rdata = ret1
    parity = ret2>>(32-1)

    check = 0
    for i in range(32):
        check ^= ((rdata >> i) & 1)

    if ack != 0b100:
        warning(f'ack not ok ack=0b{ack:03b}')

    if check != parity:
        warning(f'parity mismatch {check=} {parity=}')

    debug(f'ack=0b{ack:03b}')
    debug(f'rdata=0x{rdata:08x}')
    debug(f'{parity=}')

    return ack, rdata

def write(cmd, data):
    # cmd = reverse_header(cmd) # don't reverse output from LA, it's already reversed
    parity = 0
    for i in range(32):
        parity ^= ((data>>i)&1)
    sm.put(fmt_probe_command(8, True, CMD_WRITE))
    sm.put(cmd)
    sm.put(fmt_probe_command(1, False, CMD_TURNAROUND))
    sm.put(0)
    sm.put(fmt_probe_command(3, False, CMD_READ))
    ret0 = sm.get()
    sm.put(fmt_probe_command(1, True, CMD_TURNAROUND))
    sm.put(1)
    sm.put(fmt_probe_command(32, True, CMD_WRITE))
    sm.put(data)
    sm.put(fmt_probe_command(1, True, CMD_WRITE))
    sm.put(parity)
    sm.put(fmt_probe_command(1, True, CMD_TURNAROUND))
    sm.put(0)
    # print(f'ret0=0b{ret0>>(32-3):03b}')

    ack = reverse_mask(ret0)

    if ack != 0b100:
        warning(f'ack not ok ack=0b{ack:03b}')

    debug(f'ack=0b{ack:03b}')

    return ack

def idcode():
    ack, rdata = read(reverse_header(IDCODE))
    assert ack == 0b100, f'0b{ack:03b}'
    assert f'{rdata:032b}' == '00001011110000010001010001110111', f'0b{rdata:032b}'

@micropython.viper
def fast_write(cmd: uint, data: uint):
    fstat = ptr32(PIO0_FSTAT)
    rxf = ptr32(PIO0_RXF1)
    txf = ptr32(PIO0_TXF1)

    parity = ((data>>uint(0))  & uint(1)) ^ ((data>>uint(1))  & uint(1)) ^ ((data>>uint(2))  & uint(1)) ^ ((data>>uint(3))  & uint(1)) ^ ((data>>uint(4))  & uint(1)) ^ ((data>>uint(5))  & uint(1)) ^ ((data>>uint(6))  & uint(1)) ^ ((data>>uint(7))  & uint(1)) ^ ((data>>uint(8))  & uint(1)) ^ ((data>>uint(9))  & uint(1)) ^ ((data>>uint(10)) & uint(1)) ^ ((data>>uint(11)) & uint(1)) ^ ((data>>uint(12)) & uint(1)) ^ ((data>>uint(13)) & uint(1)) ^ ((data>>uint(14)) & uint(1)) ^ ((data>>uint(15)) & uint(1)) ^ ((data>>uint(16)) & uint(1)) ^ ((data>>uint(17)) & uint(1)) ^ ((data>>uint(18)) & uint(1)) ^ ((data>>uint(19)) & uint(1)) ^ ((data>>uint(20)) & uint(1)) ^ ((data>>uint(21)) & uint(1)) ^ ((data>>uint(22)) & uint(1)) ^ ((data>>uint(23)) & uint(1)) ^ ((data>>uint(24)) & uint(1)) ^ ((data>>uint(25)) & uint(1)) ^ ((data>>uint(26)) & uint(1)) ^ ((data>>uint(27)) & uint(1)) ^ ((data>>uint(28)) & uint(1)) ^ ((data>>uint(29)) & uint(1)) ^ ((data>>uint(30)) & uint(1)) ^ ((data>>uint(31)) & uint(1))

    txf[0] = uint(0x107) | uint(CMD_WRITE) << uint(9) 
    txf[0] = cmd
    txf[0] = uint(CMD_TURNAROUND) << uint(9) 
    txf[0] = 0
    txf[0] = uint(2) | uint(CMD_READ) << uint(9) 
    for _ in range(100):
        if not fstat[0] & uint(0x200):
            break
    _ = rxf[0]
    txf[0] = uint(CMD_TURNAROUND) << uint(9) 
    txf[0] = 1
    txf[0] = uint(0x11f) | uint(CMD_WRITE) << uint(9) 
    txf[0] = data
    txf[0] = uint(0x100) | uint(CMD_WRITE) << uint(9) 
    txf[0] = parity
    txf[0] = uint(0x100) | uint(CMD_TURNAROUND) << uint(9) 
    txf[0] = 0

def write_payload():
    fast_write(0x8B, 0x20000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20002000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000e1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20000609)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000040)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000080)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0xBB, 0x200000f1)
    utime.sleep_us(1)
    fast_write(0x8B, 0x200000c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4671b402)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00490849)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00495c09)
    utime.sleep_us(1)
    fast_write(0xBB, 0xbc02448e)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c04770)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60184b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c04770)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20001000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46854802)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfa91f000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0000e116)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20002000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0000e7fe)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b032280)
    utime.sleep_us(1)
    fast_write(0xBB, 0x421169d9)
    utime.sleep_us(1)
    fast_write(0xBB, 0x6298d0fc)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000100)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c04770)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40013800)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0004b510)
    utime.sleep_us(1)
    fast_write(0xBB, 0x34017820)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfff0f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2b007823)
    utime.sleep_us(1)
    fast_write(0xBB, 0xbd10d1f8)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b032220)
    utime.sleep_us(1)
    fast_write(0xBB, 0x421169d9)
    utime.sleep_us(1)
    fast_write(0xBB, 0x6a58d0fc)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4770b2c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40013800)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2101b573)
    utime.sleep_us(1)
    fast_write(0xBB, 0x24804a37)
    utime.sleep_us(1)
    fast_write(0xBB, 0x26f06ad3)
    utime.sleep_us(1)
    fast_write(0xBB, 0x62d3430b)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000140)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4d356ad3)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9301400b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x23a09b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x681805db)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40280324)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60184320)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43b06a58)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20400006)
    utime.sleep_us(1)
    fast_write(0xBB, 0x62584330)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4e2d6898)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43044028)
    utime.sleep_us(1)
    fast_write(0xBB, 0x6858609c)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40204c2b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x68d86058)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40052480)
    utime.sleep_us(1)
    fast_write(0xBB, 0x02c02080)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000180)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60d84328)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4d276818)
    utime.sleep_us(1)
    fast_write(0xBB, 0x402803a4)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60184320)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40066a58)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00c02080)
    utime.sleep_us(1)
    fast_write(0xBB, 0x62584330)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4e226898)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43204028)
    utime.sleep_us(1)
    fast_write(0xBB, 0x68586098)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60584030)
    utime.sleep_us(1)
    fast_write(0xBB, 0x402868d8)
    utime.sleep_us(1)
    fast_write(0xBB, 0x036d2580)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60dd4305)
    utime.sleep_us(1)
    fast_write(0xBB, 0x6b502580)
    utime.sleep_us(1)
    fast_write(0xBB, 0x432801ed)
    utime.sleep_us(1)
    fast_write(0x8B, 0x200001c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20036350)
    utime.sleep_us(1)
    fast_write(0xBB, 0x402b6b53)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9b009300)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43836cd3)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf3ef64d3)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf3818010)
    utime.sleep_us(1)
    fast_write(0xBB, 0x250c8810)
    utime.sleep_us(1)
    fast_write(0xBB, 0x681a4b13)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a432a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x8810f380)
    utime.sleep_us(1)
    fast_write(0xBB, 0x681a4811)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a4002)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4810685a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x605a4002)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60da228b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4311681a)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000200)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60192280)
    utime.sleep_us(1)
    fast_write(0xBB, 0x69d903d2)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd0fc4221)
    utime.sleep_us(1)
    fast_write(0xBB, 0x421169d9)
    utime.sleep_us(1)
    fast_write(0xBB, 0xbd73d0f9)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40021000)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfff3ffff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfffff0ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfffffdff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xffcfffff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfffffbff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40013800)
    utime.sleep_us(1)
    fast_write(0xBB, 0xefffe9ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xffffcfff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4a0a2001)
    utime.sleep_us(1)
    fast_write(0xBB, 0x6ad1b082)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000240)
    utime.sleep_us(1)
    fast_write(0xBB, 0x62d14301)
    utime.sleep_us(1)
    fast_write(0xBB, 0x6ad321a0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x400305c9)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9b019301)
    utime.sleep_us(1)
    fast_write(0xBB, 0x680b4a05)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2380401a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x431300db)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb002600b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c04770)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40021000)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfffff3ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x49224b21)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb510681a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a400a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x48202201)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43916801)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000280)
    utime.sleep_us(1)
    fast_write(0xBB, 0x68196001)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2108430a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x681a601a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a438a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x68192204)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd0fc4211)
    utime.sleep_us(1)
    fast_write(0xBB, 0x68da2103)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0011438a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x430a2201)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60da210c)
    utime.sleep_us(1)
    fast_write(0xBB, 0x400a68da)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd1fb2a04)
    utime.sleep_us(1)
    fast_write(0xBB, 0x68da21f0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60da438a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x491168da)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60da400a)
    utime.sleep_us(1)
    fast_write(0x8B, 0x200002c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x491068da)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60da400a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x490f681a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a400a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00922280)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00086819)
    utime.sleep_us(1)
    fast_write(0xBB, 0x42114010)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b0bd1fa)
    utime.sleep_us(1)
    fast_write(0xBB, 0x605a4a0b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60982205)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a480a)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfef2f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c0bd10)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40021000)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfeffffff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40022000)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000300)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfffff8ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xffffc7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfffffeff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe000e010)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0000063f)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00f42400)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe027b573)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b084a07)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x600146c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe0206013)
    utime.sleep_us(1)
    fast_write(0xBB, 0x1ff80000)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000340)
    utime.sleep_us(1)
    fast_write(0xBB, 0xff5500aa)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b084a07)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x600146c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe00c6013)
    utime.sleep_us(1)
    fast_write(0xBB, 0x1ff80000)
    utime.sleep_us(1)
    fast_write(0xBB, 0xffff0000)
    utime.sleep_us(1)
    fast_write(0xBB, 0xff7ef7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xff62f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfedcf7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ff488d)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2401fec5)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000380)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ff2502)
    utime.sleep_us(1)
    fast_write(0xBB, 0x466bfecb)
    utime.sleep_us(1)
    fast_write(0xBB, 0x78d870d8)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c01cde)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfeb0f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ff200a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x7833fead)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2b20b2d8)
    utime.sleep_us(1)
    fast_write(0xBB, 0x3841d03f)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2b04b2c3)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2804d8eb)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ffd8e9)
    utime.sleep_us(1)
    fast_write(0xBB, 0x5843fe87)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00a7036d)
    utime.sleep_us(1)
    fast_write(0xBB, 0x699a4b7e)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd1fc4222)
    utime.sleep_us(1)
    fast_write(0x8B, 0x200003c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x487e4a7d)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4a7e60da)
    utime.sleep_us(1)
    fast_write(0xBB, 0x60da497e)
    utime.sleep_us(1)
    fast_write(0xBB, 0x611a4a7e)
    utime.sleep_us(1)
    fast_write(0xBB, 0x611a4a7e)
    utime.sleep_us(1)
    fast_write(0xBB, 0x05122280)
    utime.sleep_us(1)
    fast_write(0xBB, 0x01762680)
    utime.sleep_us(1)
    fast_write(0xBB, 0x19926010)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd1f9428a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b4a7a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000400)
    utime.sleep_us(1)
    fast_write(0xBB, 0x497b600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x699a600a)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd1fc4222)
    utime.sleep_us(1)
    fast_write(0xBB, 0x422a699a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x619dd000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4222699a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x685ad1fc)
    utime.sleep_us(1)
    fast_write(0xBB, 0x605a4322)
    utime.sleep_us(1)
    fast_write(0xBB, 0x22a0e062)
    utime.sleep_us(1)
    fast_write(0xBB, 0x05d22680)
    utime.sleep_us(1)
    fast_write(0xBB, 0x03b66951)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4033040b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43184388)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe7a46190)
    utime.sleep_us(1)
    fast_write(0xBB, 0x222023a0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x629a05db)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000440)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4a5d4b6c)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4a5e601a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b6b601a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a4a6b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a4a6b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20a046c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x301805c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe75d2120)
    utime.sleep_us(1)
    fast_write(0xBB, 0x23a0e78f)
    utime.sleep_us(1)
    fast_write(0xBB, 0x05db2220)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b62629a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a4a52)
    utime.sleep_us(1)
    fast_write(0xBB, 0x601a4a53)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4a614b60)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4a61601a)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c0601a)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000480)
    utime.sleep_us(1)
    fast_write(0xBB, 0x05c020a0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x21203018)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe77ae75c)
    utime.sleep_us(1)
    fast_write(0xBB, 0x93012300)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe44f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x06009b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x90014318)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe3ef7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x04009b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x90014318)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe38f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x02009b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x90014318)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe32f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43189b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9b019001)
    utime.sleep_us(1)
    fast_write(0x8B, 0x200004c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9301681b)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0e009801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe14f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0c009801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ffb2c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9801fe0f)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c00a00)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe0af7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c09801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfe06f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x228021a0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x694805c9)
    utime.sleep_us(1)
    fast_write(0xBB, 0x04030392)
    utime.sleep_us(1)
    fast_write(0xBB, 0x22204013)
    utime.sleep_us(1)
    fast_write(0xBB, 0x43134382)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe740618b)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000500)
    utime.sleep_us(1)
    fast_write(0xBB, 0x05362680)
    utime.sleep_us(1)
    fast_write(0xBB, 0x93016833)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2b009b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2008d01e)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdf0f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ff2000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x1230fded)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ffb2c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2000fde9)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfde6f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0e009801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfde2f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0c009801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ffb2c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9801fddd)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c00a00)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000540)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdd8f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c09801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdd4f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x015b2380)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b1c18f6)
    utime.sleep_us(1)
    fast_write(0xBB, 0xd1d5429e)
    utime.sleep_us(1)
    fast_write(0xBB, 0x05362680)
    utime.sleep_us(1)
    fast_write(0xBB, 0x93016833)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2b009b01)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2008d01e)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdc4f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ff2000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x1230fdc1)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ffb2c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x2000fdbd)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdbaf7ff)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000580)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0e009801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdb6f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x0c009801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xf7ffb2c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x9801fdb1)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c00a00)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfdacf7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xb2c09801)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfda8f7ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4b173601)
    utime.sleep_us(1)
    fast_write(0xBB, 0x429e36ff)
    utime.sleep_us(1)
    fast_write(0xBB, 0xe6e8d1d6)
    utime.sleep_us(1)
    fast_write(0xBB, 0x20000614)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40022000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x89abcdef)
    utime.sleep_us(1)
    fast_write(0xBB, 0xdeadbeef)
    utime.sleep_us(1)
    fast_write(0x8B, 0x200005c0)
    utime.sleep_us(1)
    fast_write(0xBB, 0x02030405)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08010000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x8c9daebf)
    utime.sleep_us(1)
    fast_write(0xBB, 0x13141516)
    utime.sleep_us(1)
    fast_write(0xBB, 0xcafebabe)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080000)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080100)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080200)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080300)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080400)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080500)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080600)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08080700)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4002200c)
    utime.sleep_us(1)
    fast_write(0xBB, 0x40022014)
    utime.sleep_us(1)
    fast_write(0xBB, 0xfbead9c8)
    utime.sleep_us(1)
    fast_write(0x8B, 0x20000600)
    utime.sleep_us(1)
    fast_write(0xBB, 0x24252627)
    utime.sleep_us(1)
    fast_write(0xBB, 0x08000800)
    utime.sleep_us(1)
    fast_write(0xBB, 0x4770e7fe)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c0b5f8)
    utime.sleep_us(1)
    fast_write(0xBB, 0x46c0b5f8)
    utime.sleep_us(1)
    fast_write(0xBB, 0x56494c41)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00000a45)
    utime.sleep_us(1)
    fast_write(0xBB, 0x00200000)
    utime.sleep_us(1)

def setup():
    # DebugPort CTRL/STAT OK 0x50000000 CSYSPWRUPACK=0, CSYSPWRUPREQ=1, CDBGPWRUPACK=0, CDBGPWRUPREQ=1, CDBGRSTACK=0, CDBGRSTREQ=0, TRNCNT=0x000, MASKLANE=0x0, WDATAERR=0, READOK=0, STICKYERR=0, STICKYCMP=0, TRNMODE=Normal, STICKYORUN=0, ORUNDETECT=0
    fast_write(0xA9, 0x50000000)
    utime.sleep_us(1)
    # DebugPort SELECT OK 0x00000000 APSEL=0x00, APBANKSEL=0x0, PRESCALER=0x0
    fast_write(0xB1, 0x00000000)
    utime.sleep_us(1)
    # AccessPort CSW OK 0x23000012 DbgSwEnable=0, Prot=0x23, SPIDEN=0, Mode=0x0, TrInProg=0, DeviceEn=0, AddrInc=Increment single, Size=Word (32 bits)
    fast_write(0xA3, 0x23000012)
    utime.sleep_us(1)

def halt():
    # AccessPort TAR OK 0xE000EDF0 
    fast_write(0x8B, 0xE000EDF0)
    utime.sleep_us(1)
    # AccessPort DRW OK 0xA05F0003 
    fast_write(0xBB, 0xA05F0003)
    utime.sleep_us(1)
    # DebugPort RDBUFF OK 0x00000000 
    read(0xBD)

def resume():
    # print('RESUME')
    # AccessPort TAR OK 0xE000EDF0 
    fast_write(0x8B, 0xE000EDF0)
    utime.sleep_us(1)
    # AccessPort DRW OK 0xA05F0001 
    fast_write(0xBB, 0xA05F0001)
    utime.sleep_us(1)
    # DebugPort RDBUFF OK 0x00000000 
    read(0xBD)

def set_sp(sp):
    # print('WRITE SP <- 0x20002000')
    # AccessPort BD2 OK 0x20002000 
    fast_write(0x93, 0x20002000)
    utime.sleep_us(1)
    # AccessPort BD1 OK 0x0001000D 
    fast_write(0x8B, 0x0001000D)
    utime.sleep_us(1)

def set_pc(pc):
    # print('WRITE PC <- RESET VECTOR (0x200010CD)')
    # AccessPort BD2 OK 0x200010CD
    fast_write(0x93, pc)
    utime.sleep_us(1)
    # AccessPort BD1 OK 0x0001000F 
    fast_write(0x8B, 0x0001000F)
    utime.sleep_us(1)

def boot_payload_sram(powerdown_ms=100, resetdown_ms=5):
    POWER_PIN.off()
    RESET_PIN.off()
    utime.sleep_ms(powerdown_ms)
    POWER_PIN.on()
    utime.sleep_ms(resetdown_ms)
    RESET_PIN.on()

    # sm.put(10 & 0xff | 1 << 8 | PC_WRITE << 9)
    sm.restart()
    sm.exec(probe_offset_get_next_cmd)
    sm.active(1)

    # WData 0x0BC11477 reg IDCODE bits DESIGNER=0x477, PARTNO=0xBC11, Version=0x0

    # sm.put(fmt_probe_command(32, True, CMD_WRITE))
    # sm.put(0xffff_ffff_ffff_ffff)
    # sm.put(fmt_probe_command(50-32, True, CMD_WRITE))
    # sm.put(0xffff_ffff_ffff_ffff)
    # sm.put(fmt_probe_command(4, True, CMD_WRITE))
    # sm.put(0)

    machine.mem32[PIO0_TXF1] = fmt_probe_command(32, True, CMD_WRITE)
    machine.mem32[PIO0_TXF1] = 0xffff_ffff_ffff_ffff
    machine.mem32[PIO0_TXF1] = fmt_probe_command(50-32, True, CMD_WRITE)
    machine.mem32[PIO0_TXF1] = 0xffff_ffff_ffff_ffff
    machine.mem32[PIO0_TXF1] = fmt_probe_command(4, True, CMD_WRITE)
    machine.mem32[PIO0_TXF1] = 0

    # test first few frames that i see in LA from openocd
    # print('Request DebugPort Read IDCODE')
    idcode()

    setup()

    halt()

    # print('START WRITING CODE')

    write_payload()

    # print('FINISH WRITING CODE')

    # AccessPort TAR OK 0xE000EDF0 
    fast_write(0x8B, 0xE000EDF0)
    utime.sleep_us(1)
    # DebugPort SELECT OK 0x00000010 APSEL=0x00, APBANKSEL=0x1, PRESCALER=0x0
    fast_write(0xB1, 0x00000010)
    utime.sleep_us(1)
    # AccessPort BD2 OK 0x01000000 
    fast_write(0x93, 0x01000000)
    utime.sleep_us(1)
    # AccessPort BD1 OK 0x00010010 
    fast_write(0x8B, 0x00010010)
    utime.sleep_us(1)

    set_pc(0x200000E1)
    set_sp(0x20002000)

    # DebugPort SELECT OK 0x00000000 APSEL=0x00, APBANKSEL=0x0, PRESCALER=0x0
    fast_write(0xB1, 0x00000000)
    utime.sleep_us(1)

    resume()

    idcode()

    while not u.any(): 
        pass
    print(u.read(u.any()))
    # print(u.read(1024))
    # u.write(b' ')
    # utime.sleep_ms(100)
    # print(u.read(1024))
    # u.write(b'C\x1f\xf8\x00\x00')
    # utime.sleep_ms(100)
    # print(u.read(1024))

def urw(w, nread=1024, timeout_ms=2000):
    u.write(w)
    t0 = utime.ticks_ms()
    while not u.any() and (utime.ticks_ms() - t0) < timeout_ms:
        pass
    return u.read(nread)

def toggle_led():
    return urw(b' ')

def set_rdp0():
    return urw(b'A')

def set_rdp1():
    return urw(b'B')

def read_mem(addr):
    return urw(b'C' + struct.pack(b'>I', addr))

def fill_markers():
    return urw(b'D')

def read_markers():
    return urw(b'E', nread=10000, timeout_ms=5)

def read_rdp():
    return read_mem(0x1ff80000)

def rdp_cycle(delay_ns):
    boot_payload_sram()
    set_rdp1()
    print(read_rdp())
    boot_payload_sram()
    arm_trigger_go(delay_ns)
    print(read_rdp())

def pre():
    boot_payload_sram()
    val = read_rdp()
    print(val)
    if val[-3:] != b'U\x00\xaa':
        set_rdp0()
        boot_payload_sram()
    fill_markers()
    set_rdp1()
    boot_payload_sram()

def arm_trigger_go(delay_ns, high_ns=80):
    if not sm_trigger.active():
        sm_trigger.active(1)
    ns_per_cycle_ns = 1e-9*freq()
    sm_trigger.put(int(delay_ns * ns_per_cycle_ns))
    sm_trigger.put(int(high_ns * ns_per_cycle_ns))
    print(set_rdp0())

def post():
    boot_payload_sram()
    print(read_rdp())
    print('markers1')
    print(read_markers())
    print('markers2')
    print(read_markers())

# boot_payload_sram()