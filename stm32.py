import struct
from functools import reduce
import operator
from serial import Serial

class STBL():
    START = b'\x7f'
    ACK = b'y'
    NACK = b'\x1f'
    VERSION = b'\x01\xfe'
    RDP1 = b'\x82\x7d'
    RDP0 = b'\x92\x6d'
    RDMEM = b'\x11\xee'
    WRMEM = b'\x31\xce'
    WRPROT = b'\x63\x9c'
    WRUNPROT = b'\x73\x8c'

def chk(data):
    return struct.pack('>B', reduce(operator.xor, data))

def pack_addr_chk(val):
    addr_b = struct.pack('>I', val)
    return addr_b + chk(addr_b)

def pack_data_chk(data):
    l = struct.pack('>B', len(data)-1)
    return l + data + chk(l + data)

def read_data(bl_dev: Serial, addr: int, l: int=4):
    ret = b''
    bl_dev.write(STBL.RDMEM)
    resp = bl_dev.read(1)
    ret += resp

    if resp == b'y':
        cmd = pack_addr_chk(addr)
        bl_dev.write(cmd)
        resp = bl_dev.read(1)
        ret += resp

        if resp == b'y':
            cmd = bytearray([l, ~l&0xff])
            bl_dev.write(cmd)
            resp = bl_dev.read(l+2)
            ret += resp
    
    return ret

def write_data(bl_dev: Serial, addr: int, data: bytes):
    ret = b''
    cmd = STBL.WRMEM
    bl_dev.write(cmd)
    resp = bl_dev.read(1)
    ret += resp

    if resp == b'y':
        cmd = pack_addr_chk(addr)
        bl_dev.write(cmd)
        resp = bl_dev.read(1)
        ret += resp

        if resp == b'y':
            cmd = pack_data_chk(data)
            bl_dev.write(cmd)
            resp = bl_dev.read(1)
            ret += resp
    
    return ret

def fill_region(bl_dev: Serial, start, size, blksize):
    for addr in range(start, start+size, blksize):
        data = b''
        for x in range(addr, addr+blksize, 0x4):
            data += struct.pack('>I', ~x&0xffffffff)
        resp = write_data(bl_dev, addr, data)
        print('FILL', hex(addr), data, resp)
        if resp != b'yyy':
            raise Exception(f'{resp=}')

def dump_region(bl_dev: Serial, start, size, blksize):
    for addr in range(start, start+size, blksize):
        resp = read_data(bl_dev, addr, blksize)
        print('DUMP', hex(addr), resp)
        if resp[:3] != b'yyy':
            raise Exception(f'{resp=}')

def fill_flash(bl_dev: Serial):
    fill_region(bl_dev, 0x08000000, 0x8000, 0x80)

def fill_eeprom(bl_dev: Serial):
    fill_region(bl_dev, 0x08080000, 0x780, 0x10)

def dump_flash(bl_dev: Serial):
    dump_region(bl_dev, 0x08000000, 0x8000, 0x80)

def dump_eeprom(bl_dev: Serial):
    dump_region(bl_dev, 0x08080000, 0x780, 0x10)