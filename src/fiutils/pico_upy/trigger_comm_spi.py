# mpytool -p /dev/ttyACM0 put fiutils/pico_upy/trigger_comm_spi.py main.py && mpytool -p /dev/ttyACM0 repl

from machine import Pin, SPI, freq
from rp2 import PIO, StateMachine, asm_pio

import time
import struct


SCK = Pin(2, Pin.OUT, pull=Pin.PULL_DOWN)
MOSI = Pin(3, Pin.OUT, pull=Pin.PULL_DOWN)
MISO = Pin(4, Pin.IN, pull=Pin.PULL_DOWN)
CS = Pin(5, Pin.OUT)
POWER = Pin(6, Pin.OUT, pull=Pin.PULL_DOWN)

TRIGGER_OUT = Pin(7)
TRIGGER2_OUT = Pin(8)

spi = SPI(0, sck=SCK, mosi=MOSI, miso=MISO)
spi.init(baudrate=20000) # 2MHz is normal max for rp2040

@asm_pio(set_init=(PIO.OUT_LOW,),)
def count_8_ticks():

    set(pins, 0)
    set(x, 6)

    # Need to hardcode SCK here
    wait(1, gpio, 2) # So that we can trigger on last rising edge

    label("tickloop")
    wait(0, gpio, 2)
    wait(1, gpio, 2)
    jmp(x_dec, "tickloop")
    
    # irq(1)
    set(pins, 1)
    set(x, 31)
    label("waitloop")
    wait(1, gpio, 2)
    jmp(x_dec, "waitloop")
    set(pins, 0)

    wrap_target()
    wrap()
sm = StateMachine(0, count_8_ticks, set_base=TRIGGER_OUT)

def chk(data):
    c = 0
    for b in data:
        c ^= b
    return struct.pack('>B', c)

def pack_addr_chk(val):
    addr_b = struct.pack('>I', val)
    return bytearray(addr_b + chk(addr_b))

def pack_data_chk(data):
    l = struct.pack('>B', len(data)-1)
    return bytearray(l + data + chk(l + data))

def pack_byte_chk(b):
    return bytearray([b, ~b&0xff])

def boot_frame(spi: SPI=spi):
    # Wait for sync byte
    in_ = bytearray([])
    out = bytearray([])
    for _ in range(1000):
        bo = 0x5a
        bi = spi.read(1, bo)
        out.append(bo)
        in_ += bi
        if bi == b'\xa5': 
            break
    
    # print(f'{len(in_)} bytes read until boot')
    # print('>', out.hex())
    # print('>', in_.hex())
    assert len(in_) != 1000

    bs = bytearray([0x0, 0x79, 0x0, 0x0])
    print('>', bs.hex())
    spi.write_readinto(bs, bs)
    print('<', bs.hex())

    assert bs == b'\xa5yy\xa5', f'{bs.hex()=}'

def get_id(spi: SPI=spi):
    # bs = bytearray([0x5a, 0x02, 0xfd, 0x00, 0x00, 0x79, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79, 0x0])
    bs = bytearray([0x5a]) + pack_byte_chk(0x02) + bytearray([0, 0, 0x79]) + \
        bytearray(4) + bytearray([0, 0, 0x79])
    print('>', bs.hex())
    spi.write_readinto(bs, bs)
    print('<', bs.hex())

def set_rdp0(spi: SPI=spi):
    # bs = bytearray([0x5a, 0x92, 0x6d, 0x00, 0x00, 0x79, 0x00, 0x00, 0x79])
    bs = bytearray([0x5a]) + pack_byte_chk(0x92)
    print('>', bs.hex())
    sm.active(1); sm.restart();
    spi.write_readinto(bs, bs)
    print('<', bs.hex())

    in_ = bytearray([])
    out = bytearray([])
    for _ in range(1000):
        bo = 0
        sm.active(1); sm.restart();
        bi = spi.read(1, bo)
        out.append(bo)
        in_ += bi
        if bi == b'y': 
            break
    bo = 0x79
    sm.active(1); sm.restart();
    bi = spi.read(1, bo)
    out.append(bo)
    in_ += bi
    print('>', out.hex())
    print('<', in_.hex())

    in_ = bytearray([])
    out = bytearray([])
    for _ in range(1000):
        bo = 0
        sm.active(1); sm.restart();
        bi = spi.read(1, bo)
        out.append(bo)
        in_ += bi
        if bi == b'y': 
            break
    bo = 0x79
    sm.active(1); sm.restart();
    bi = spi.read(1, bo)
    out.append(bo)
    in_ += bi
    print('>', out.hex())
    print('<', in_.hex())

def set_rdp1(spi: SPI=spi):
    # bs = bytearray([0x5a, 0x92, 0x6d, 0x00, 0x00, 0x79, 0x00, 0x00, 0x79])
    bs = bytearray([0x5a]) + pack_byte_chk(0x82)
    print('>', bs.hex())
    sm.active(1); sm.restart();
    spi.write_readinto(bs, bs)
    print('<', bs.hex())

    in_ = bytearray([])
    out = bytearray([])
    for _ in range(1000):
        bo = 0
        sm.active(1); sm.restart();
        bi = spi.read(1, bo)
        out.append(bo)
        in_ += bi
        if bi == b'y': 
            break
    bo = 0x79
    sm.active(1); sm.restart();
    bi = spi.read(1, bo)
    out.append(bo)
    in_ += bi
    print('>', out.hex())
    print('<', in_.hex())

    in_ = bytearray([])
    out = bytearray([])
    for _ in range(1000):
        bo = 0
        sm.active(1); sm.restart();
        bi = spi.read(1, bo)
        out.append(bo)
        in_ += bi
        if bi == b'y': 
            break
    bo = 0x79
    sm.active(1); sm.restart();
    bi = spi.read(1, bo)
    out.append(bo)
    in_ += bi
    print('>', out.hex())
    print('<', in_.hex())

def read_mem(spi: SPI=spi, addr=0x08000000, l=4):
    bs = bytearray([0x5a]) + pack_byte_chk(0x11) + bytearray([0, 0, 0x79])
    print('>', bs.hex())
    spi.write_readinto(bs, bs)
    print('<', bs.hex())

    if bs[1:] == b'Z\xa5\xa5\xa5yy'[1:]:
        # bs = bytearray([0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x79])
        bs = pack_addr_chk(addr) + bytearray([0, 0, 0x79])
        print('>', bs.hex())
        spi.write_readinto(bs, bs)
        print('<', bs.hex())

        if bs[1:] == b'Z\xa5\xa5\xa5\xa5\xa5yy'[1:]:
            # bs = bytearray([0x04, 0xfb, 0x00, 0x00, 0x79, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            bs = pack_byte_chk(l) + bytearray([0, 0, 0x79]) + bytearray(l + 2)
            print('>', bs.hex())
            spi.write_readinto(bs, bs)
            print('<', bs.hex())

def write_mem(spi: SPI=spi, addr=0x08000000, data=b'\xde\xad\xbe\xef'):
    bs = bytearray([0x5a]) + pack_byte_chk(0x31) + bytearray([0, 0, 0x79])
    print('>', bs.hex())
    spi.write_readinto(bs, bs)
    print('<', bs.hex())

    if bs[1:] == b'Z\xa5\xa5\xa5yy'[1:]:
        bs = pack_addr_chk(addr) + bytearray([0, 0, 0x79])
        print('>', bs.hex())
        spi.write_readinto(bs, bs)
        print('<', bs.hex())

        if bs[1:] == b'Z\xa5\xa5\xa5\xa5\xa5yy'[1:]:
            bs = pack_data_chk(data) # + bytearray([0, 0, 0x79])
            print('>', bs.hex())
            spi.write_readinto(bs, bs)
            print('<', bs.hex())

            miso = bytearray([])
            mosi = bytearray([])
            for _ in range(1000):
                bo = 0
                bi = spi.read(1, bo)
                mosi.append(bo)
                miso += bi
                if bi == b'y': 
                    break
            bo = 0x79
            bi = spi.read(1, bo)
            mosi.append(bo)
            miso += bi
            print('>', mosi.hex())
            print('<', miso.hex())
            return (mosi, miso)

def fill_region(bl_dev: SPI, start, size, blksize):
    for addr in range(start, start+size, blksize):
        data = b''
        for x in range(addr, addr+blksize, 0x4):
            # data += struct.pack('>I', 0xbd75d47b)
            data += struct.pack('>I', 0xdd22dd22)
        resp = write_mem(bl_dev, addr, data)
        print('FILL', hex(addr), data, resp)
        if resp[1][-1:] != b'y':
            raise Exception(f'{resp=}')

def dump_region(bl_dev: SPI, start, size, blksize):
    for addr in range(start, start+size, blksize):
        resp = read_mem(bl_dev, addr, blksize)
        print('DUMP', hex(addr), resp)
        # if resp[:3] != b'yyy':
        #     raise Exception(f'{resp=}')

def fill_flash(bl_dev: SPI=spi):
    fill_region(bl_dev, 0x08000000, 0x8000, 0x80)

def fill_eeprom(bl_dev: SPI=spi):
    fill_region(bl_dev, 0x08080000, 0x780, 0x10)

def dump_flash(bl_dev: SPI=spi):
    dump_region(bl_dev, 0x08000000, 0x8000, 0x80)

def dump_eeprom(bl_dev: SPI=spi):
    dump_region(bl_dev, 0x08080000, 0x780, 0x10)

def check_bytes():
    for x in range(21):
        if x == 0: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x5a; print(f'{0:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 1: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x11; print(f'{1:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 2: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0xee; print(f'{2:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 3: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{3:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 4: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x79; print(f'{4:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 5: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x08; print(f'{5:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 6: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{6:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 7: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{7:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 8: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{8:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 9: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x08; print(f'{9:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 10: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{10:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 11: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x79; print(f'{11:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 12: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x04; print(f'{12:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 13: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0xfb; print(f'{13:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 14: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{14:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 15: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x79; print(f'{15:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 16: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{16:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 17: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{17:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 18: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{18:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 19: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{19:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))
        if x == 20: sm.active(1); sm.restart(); print(f'armed {x:2d}')
        i = 0x00; print(f'{20:2d}, 0x{i:02x}', end=' ')
        print(spi.read(1, i))

        time.sleep_ms(50)
    
def flush(n=100):
    # Check if slave has anything else to send
    mosi = bytearray(n)
    miso = bytearray(n)
    spi.write_readinto(mosi, miso)
    return (b'' + mosi, b'' + miso)

def run1(spi: SPI=spi, trigger=True):
    mosi = b''
    miso = b''

    bs = bytearray([0x5a, 0x11])
    mosi += bs
    # print('>', bs.hex())
    spi.write_readinto(bs, bs)
    miso += bs
    # print('<', bs.hex())
    
    if trigger:
        sm.active(1); sm.restart();
    
    bs = 0xee
    mosi += bytearray([bs])
    # print('>', f'{bs:02x}')
    bs = spi.read(1, bs)
    miso += bs
    # print('<', bs.hex())
    
    bs = bytearray([0x00, 0x00, 0x79])
    mosi += bs
    # print('>', bs.hex())
    spi.write_readinto(bs, bs)
    miso += bs
    # print('<', bs.hex())

    return (mosi, miso)
    
def run2(spi: SPI=spi, trigger=True):
    mosi = b''
    miso = b''

    bs = bytearray([0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x79, 0x04, 0xfb, 0x00, 0x00])
    mosi += bs
    # print('>', bs.hex())
    spi.write_readinto(bs, bs)
    miso += bs
    # print('<', bs.hex())
    
    if trigger:
        sm.active(1); sm.restart();
    
    bs = 0x79
    mosi += bytearray([bs])
    # print('>', f'{bs:02x}')
    bs = spi.read(1, bs)
    miso += bs
    # print('<', bs.hex())

    bs = bytearray([0x00, 0x00, 0x00, 0x00, 0x00])
    mosi += bs
    # print('>', bs.hex())
    spi.write_readinto(bs, bs)
    miso += bs
    # print('<', bs.hex())
    
    return (mosi, miso)
    
def run(spi: SPI=spi):
    boot_frame(spi)
    run1()
    run2(trigger=False)

# # time.sleep(.1)
# boot_frame(spi)
# get_id(spi)
# get_id(spi)
# get_id(spi)
# get_id(spi)
# read_mem(spi, addr=0x08000000, l=4)
# read_mem(spi, addr=0x1ff00000, l=8)
# read_mem(spi, addr=0x08080000, l=4)
# read_mem(spi, addr=0x20000000, l=8)
# read_mem(spi, addr=0x08000060, l=4)
# write_mem(spi, addr=0x08000060, data=bytes.fromhex('deadbeef'))
# read_mem(spi, addr=0x08000060, l=4)

# while True: spi.read(1, 0x0); time.sleep_ms(500)

# write_mem(spi, addr=0x08000000, data=b'dead')
# read_mem(spi, addr=0x08000000, l=4)
# read_mem(spi, addr=0x08000000, l=4)
# get_id(spi)

# target_sequence()