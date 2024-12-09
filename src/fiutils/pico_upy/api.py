
from serial import Serial

def upython_reset(dev: Serial):
    dev.write(b'\r\n\r\n')
    dev.write(b'\x03\x03\x03') # CTRL-C + CTRL-D
    dev.write(b'\x03\x03\x04') # CTRL-C + CTRL-D
    ret = dev.read_until(b'information.\r\n>>> ')
    dev.write(b'run(0)\r\n') # CTRL-C + CTRL-D
    ret = dev.read_until(b'run(0)\r\n')
    # print(f'upython reset: {ret=}')
    return ret

def upython_arm_with_pattern(dev: Serial, pattern):
    if dev.in_waiting == 0:
        # There should be some data waiting, if not reset()
        print('reset')
        upython_reset(dev)
    
    ret = dev.read_until(b'val?> ')
    # print(ret)
    cmd = f'0x{pattern:08x}\r\n'.encode()
    dev.write(cmd)
    ret += dev.read_until(cmd)
    # print(ret)
    return ret