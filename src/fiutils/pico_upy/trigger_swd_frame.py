"""
upython program to trigger on a value passing over SWD line.

Program onto rp2040 with upython with mpytool for example:
- pip install myptool
- mpytool -p /dev/ttyACM0 put utils/main.py

Notes:
- Use GPIO5 to monitor SWCLK (interacting only in wait instruction)
- USE GPIO0 to monitor SWDIO (configured as input pin)
- Use sideset for a debug line to observe what is going on (GPIO26)
- Use GPIO10 to generate an actual trigger signal via out
- LED on when it has generated trigger

find_value_in_frame() configures a value of up to 32 bits in one scratch register, 
and looks for this value in the observed bits by using the OSR to configure how 
many bits to look at at a time.

For example, run(0x08000000) will start looking for the value 0x08000000.

NOTE: The configured values work for read/write frames. FAult / WAit frames won't 
    work, and will fuck it up. Reset bits will fuck it up. Landing in the middle
    of a SWD frame will fuck it up.
"""

from machine import Pin, I2C, Timer
from rp2 import asm_pio, PIO, StateMachine
import _thread

import time
import struct
import sys

g_stop = True

SWDIO = 0
SWCLK = 5
TRIGGER_OUT = 10
LED = Pin(25, Pin.OUT, value=0)
DEBUG_OUT = 26 

NEEDLE = 0b11010001


def reverse_mask(x):
    x = ((x & 0x55555555) << 1) | ((x & 0xAAAAAAAA) >> 1)
    x = ((x & 0x33333333) << 2) | ((x & 0xCCCCCCCC) >> 2)
    x = ((x & 0x0F0F0F0F) << 4) | ((x & 0xF0F0F0F0) >> 4)
    x = ((x & 0x00FF00FF) << 8) | ((x & 0xFF00FF00) >> 8)
    x = ((x & 0x0000FFFF) << 16) | ((x & 0xFFFF0000) >> 16)
    return x

"""
NOTE: this is only correct for read/write frames, error/wait/fault frames will fuck it up,
    as well as reset bits. swd comms should be up before starting the state machine
"""
@asm_pio(set_init=(PIO.OUT_LOW,),
         sideset_init=(PIO.OUT_LOW,), 
         autopull=False,
         autopush=False,
         fifo_join=PIO.JOIN_NONE)
def pio_match_one_data():
    # Configure y once with the value we are looking for
    set(pins, 0)

    pull(block)
    mov(y, osr)

    label("start")
    pull(block)
    mov(x, osr)

    label("bitloop")
    wait(0, gpio, 5)
    nop().side(0b1)
    nop().delay(0b111)
    in_(pins, 1)
    wait(1, gpio, 5)
    jmp(x_dec, "bitloop")
    # push().side(0b0)
    mov(x, reverse(isr)).side(0b0)

    jmp(x_not_y, "start")
    set(pins, 1)
    irq(rel(0)).delay(0b111) # add some delay to make trigger show up in logic analyzer
    set(pins, 0)
    label("done")
    # Dump any remaining tx_fifo values
    pull(block)
    mov(x, osr)
    jmp("done")

pin_clk = Pin(SWCLK, Pin.IN)
sm = StateMachine(0, pio_match_one_data,
                  freq=int(10e6), # adjust based on swd clock, in my case clock is 4us (250KHz), so 10MHz gives 40 cycles per bit
                  in_base=Pin(SWDIO, Pin.IN), 
                  sideset_base=Pin(DEBUG_OUT), 
                  set_base=Pin(TRIGGER_OUT, Pin.OUT),
                  jmp_pin=Pin(SWDIO))

def irq_triggered(x):
    global g_stop
    g_stop = True
    LED.on()
    print(f'NEEDLE FOUND')

sm.irq(irq_triggered)

def find_value_in_frame(needle):
    global g_stop
    g_stop = False
    sm.restart()
    sm.active(1)
    sm.put(needle)

    while not g_stop:
        # This needs to happen fast, have a couple of cycles per bit to set up things
        # if more speed is needed, move it all to C (or a C library). Checking one global
        # seems okay in terms of time.

        # 13 bits of "header"
        """
        https://developer.arm.com/documentation/ddi0413/c/debug-access-port/sw-dp/overview-of-protocol-operation?lang=en

        - 13 bits of "header", things like start, operation, turnaround, ack, turnaround
        - 32 bits of write data
        - 1 bit of parity at the end
        """
        sm.put(13-1)
        sm.put(32-1)
        sm.put(1-1)
        
    ### Use these lines if you're pushing isr for debugging
    # x = sm.get()
    # print(f'{bin(x)=} {hex(x)=} {hex(reverse_mask(x))=}')
    # x = sm.get()
    # print(f'{bin(x)=} {hex(x)=} {hex(reverse_mask(x))=}')
    # x = sm.get()
    # print(f'{bin(x)=} {hex(x)=} {hex(reverse_mask(x))=}')

def run(needle):
    # return _thread.start_new_thread(find_value_in_frame, (needle,))
    while True:
        needle = input("val?> ")
        try:
            find_value_in_frame(int(needle))
        except KeyboardInterrupt:
            pass

print('READY')

# run(0x08000000)