from machine import Pin, I2C, Timer, freq
from rp2 import asm_pio, PIO, StateMachine
import _thread

import time
import struct
import sys

TRIGGER_OUT = 7

@asm_pio(sideset_init=(PIO.OUT_LOW,),
         autopull=False,
         fifo_join=PIO.JOIN_NONE)
def pio_high_counter():
    # Delay value
    pull(block).side(0)
    mov(y, osr)

    # High value
    pull(block)
    mov(x, osr)

    label("waitloop")
    jmp(y_dec, "waitloop")

    label("highloop")
    jmp(x_dec, "highloop").side(1)
    
    nop().side(0)

sm = StateMachine(1, pio_high_counter, 
                  sideset_base=Pin(TRIGGER_OUT, Pin.OUT))