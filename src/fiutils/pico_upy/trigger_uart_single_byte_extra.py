"""
upython program to trigger on a single UART byte.
"""

from machine import Pin, freq
from rp2 import asm_pio, PIO, StateMachine

HOST_TX = 0
TRIGGER_OUT = 10
LED = Pin(25, Pin.OUT, value=0)
CROWBAR_OUT1 = 2
CROWBAR_OUT2 = 3
DEBUG_OUT = 26 

@asm_pio(set_init=(PIO.OUT_LOW,),
         sideset_init=(PIO.OUT_LOW,), 
         autopull=False,
         autopush=False,
         fifo_join=PIO.JOIN_NONE)
def pio_match_uart_byte():
    # Get the reference byte once
    pull(block)
    mov(y, osr)

    wrap_target()
    # Stall until start bit, then delay until start bit is finished
    wait(0, pin, 0)
    nop().side(1).delay(6)

    # Stall a little bit more to end up in the middle of a bit cycle
    nop().side(1).delay(2)

    in_(pins, 1).delay(6)
    in_(pins, 1).delay(6)
    in_(pins, 1).delay(6)
    in_(pins, 1).delay(6)
    
    in_(pins, 1).delay(6)
    in_(pins, 1).delay(6)
    in_(pins, 1).delay(6)
    # Don't wait the entire cycle for the last bit for faster trigger
    in_(pins, 1)#.delay(6)
    
    # Zero pad byte, alert cpu for pattern matching
    in_(null, 24)
    mov(x, isr)
    jmp(x_not_y, "parity")
    irq(1) # Trigger faster in fast SM to get rid of jitter between uart bits and trigger
    irq(0)
    label("parity")
    # Wait the cycles we skipped before
    nop().delay(6)
    # Parity bit remaining cycles
    nop().delay(6-4)

    # Stop bit is always 1, after that we can start waiting for 0 again
    wait(1, pin, 0).side(0)

    
def irq_check_trigger(x):
    print('MATCH')
    
baudrate = 115200
bit_cycle = 1 / baudrate
# Target 4 sm cycles per uart bit cycle
sm_freq = int(1 / (bit_cycle / 7))
print(f'{sm_freq=} {1/sm_freq=}')
sm = StateMachine(0, pio_match_uart_byte,
                  freq=sm_freq,
                  in_shiftdir=PIO.SHIFT_RIGHT,
                  in_base=Pin(HOST_TX, Pin.IN),
                  sideset_base=Pin(DEBUG_OUT))
                  # sideset_base=Pin(TRIGGER_OUT))
sm.irq(irq_check_trigger, hard=True)

# # This works well if the parity bit is 0, to have an edge against the stop bit
# @asm_pio(sideset_init=(PIO.OUT_LOW,))
# def pio_irq_pinup():
#     wait(1, irq, 1)
#     wait(1, pin, 0)
#     nop().side(1)
#     nop().delay(7)
#     nop().side(0)
# sm1 = StateMachine(1, pio_irq_pinup,
#                   in_base=Pin(HOST_TX, Pin.IN),
#                   sideset_base=Pin(TRIGGER_OUT))
# sm1.active(1)

@asm_pio(sideset_init=(PIO.OUT_LOW,PIO.OUT_LOW,),
         autopull=False,
         fifo_join=PIO.JOIN_NONE)
def pio_high_counter():
    # Clear irq 1 if it was still high
    irq(1, clear)

    # Delay value
    pull(block).side(0)
    mov(y, osr)

    # High value
    pull(block)
    mov(x, osr)

    # Wait for irq from other statemachine
    wait(1, irq, 1)

    # Wait for 0->1 from UART parity -> stop bit
    wait(1, pin, 0)

    label("waitloop")
    jmp(y_dec, "waitloop").side(0b10)

    label("highloop")
    jmp(x_dec, "highloop").side(0b11)
    
    label("done2")
    jmp("done2").side(0b00)


sm2 = StateMachine(2, pio_high_counter, 
                   sideset_base=Pin(CROWBAR_OUT1, Pin.OUT))
# Runs once with config
def arm(byte, wait_time_s=1e-3, high_time_s=5e-3):
    sm.active(0)
    sm2.active(0)
    sm.restart()
    sm2.restart()

    sm.put(byte)
    sm2.put(int(wait_time_s/(1/freq())))
    sm2.put(int(high_time_s/(1/freq())))

    sm.active(1)
    sm2.active(1)

# Abuse crowbar for a power on reset
def reset():
    Pin(CROWBAR_OUT1, Pin.OUT).high()
    Pin(CROWBAR_OUT1, Pin.OUT).low()
    Pin(CROWBAR_OUT1, mode=Pin.ALT, alt=Pin.ALT_PIO0)
    
print('READY')
