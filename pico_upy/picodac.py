# https://docs.micropython.org/en/latest/library/machine.I2C.html
# https://ww1.microchip.com/downloads/en/DeviceDoc/22272C.pdf
# https://www.programming-electronics-diy.xyz/2021/10/dac-library-for-mcp4706-mcp4716-mcp4726.html

from machine import I2C, Pin, freq
from rp2 import asm_pio, PIO, StateMachine

TRIGGER_IN = Pin(10, Pin.IN, pull=Pin.PULL_DOWN)
TRIGGER_OUT = Pin(11, Pin.OUT)
DEBUG_OUT = Pin(12, Pin.OUT)
LED = Pin(25, Pin.OUT)
I2C1SCL = Pin(15)
I2C1SDA = Pin(14)

DAC_BITS = 10
DAC_MAX = 2**DAC_BITS - 1
DAC_MIN = 0

def triggered_message(x):
    print('Triggered!')
    LED.on()

# autopull must be False when using mov with osr
# TRIGGER_OUT is used for trigger output, DEBUG_OUT to observe what's going on
@asm_pio(sideset_init=(PIO.OUT_LOW, PIO.OUT_LOW,),
         autopull=False,)
def pio_simple_trigger():
    # Delay value
    nop().side(0b00)
    pull(block).side(0b00)
    mov(y, osr)

    # # Pin high value
    pull(block)
    mov(x, osr)

    # Wait for 0->1 on the TRIGGER_IN (cannot use constants, so have to hardcode it)
    wait(1, gpio, 10).side(0b10)

    label("waitloop")
    jmp(y_dec, "waitloop")

    label("highloop")
    jmp(x_dec, "highloop").side(0b11)
    
    # Message that we triggered
    irq(0)

def dac_value(fraction):
    return fraction * DAC_MAX

def set_vout_volatile(i2c, fraction):
    val = dac_value(fraction)
    val = int(val)
    power_bits = 0x00
    v1 = (val >> (10-4)) & 0x0f | power_bits << 4
    v2 = (val << 2) & 0xff
    i2c.writeto(addr, bytearray([v1, v2]))

sm = StateMachine(2, pio_simple_trigger, sideset_base=TRIGGER_OUT)
# sm.irq(triggered_message, hard=True)
PIO(0).irq(triggered_message)

i2c = I2C(id=1, scl=I2C1SCL, sda=I2C1SDA)
i2c.scan()
addr = i2c.scan()[0]
assert addr == 0x60, f'address should be 0x60, but is 0x{addr:02x}'

set_vout_volatile(i2c, .3) # should read ~1V

# could do some math here with freq() to provide time instead of cycles
print(f'wait={100*1/freq()}')
print(f'high={10000*1/freq()}')
LED.off()
sm.active(0)
sm.restart()
sm.put(100)
sm.put(10000)
sm.active(1)
