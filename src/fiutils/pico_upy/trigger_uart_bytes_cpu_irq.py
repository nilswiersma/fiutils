"""
upython program to trigger on a UART string.

The actual matching is done in the CPU, and therefore way too slow in python.

TBD move it to C. Or maybe can chain multiple state machines together?
"""

from machine import Pin
from rp2 import asm_pio, PIO, StateMachine

HOST_TX = 0
TRIGGER_OUT = Pin(10, Pin.OUT, value=0)
LED = Pin(25, Pin.OUT, value=0)
CROWBAR_OUT = 15
DEBUG_OUT = 26 

@asm_pio(set_init=(PIO.OUT_LOW,),
         sideset_init=(PIO.OUT_LOW,), 
         autopull=False,
         autopush=True,
         push_thresh=32,
         fifo_join=PIO.JOIN_NONE)
def pio_collect_uart_byte():
    # Stall until start bit, then delay until start bit is finished
    wait(0, pin, 0).delay(7)

    # Stall a little bit more to end up in the middle of a bit cycle
    nop().delay(2)
    in_(pins, 1).delay(6)#.side(1)
    in_(pins, 1).delay(6)#.side(0)
    in_(pins, 1).delay(6)#.side(1)
    in_(pins, 1).delay(6)#.side(0)
    
    in_(pins, 1).delay(6)#.side(1)
    in_(pins, 1).delay(6)#.side(0)
    in_(pins, 1).delay(6)#.side(1)
    in_(pins, 1).delay(6)#.side(0)
    
    # Zero pad byte, alert cpu for pattern matching
    in_(null, 24)
    irq(0).side(0)
    # Parity bit remaining cycles
    nop().delay(6-2)#.side(0)

    # Stop bit is always 1, after that we can start waiting for 0 again
    wait(1, pin, 0)

# This works, but is way too slow in python
l = []
ref = [0x01, 0xfe]
def irq_check_trigger(x):
    global l
    x = sm.get()
    l.append(x)
    if l[-len(ref):] == ref:
        TRIGGER_OUT.on()
        l = []
        print('DONE')
        TRIGGER_OUT.off()
    l = l[-len(ref):]
    print(l)
    print(f'0x{x:02x} / 0b{x:08b}')
     
    
baudrate = 115200
bit_cycle = 1 / baudrate
# Target 4 sm cycles per uart bit cycle
sm_freq = int(1 / (bit_cycle / 7))
print(f'{sm_freq=} {1/sm_freq=}')
sm = StateMachine(0, pio_collect_uart_byte,
                  freq=sm_freq,
                  in_shiftdir=PIO.SHIFT_RIGHT,
                  in_base=Pin(HOST_TX, Pin.IN), 
                  sideset_base=Pin(DEBUG_OUT))
sm.irq(irq_check_trigger)

def run():
     sm.active(1)
     sm.restart()

print('READY')
run()
