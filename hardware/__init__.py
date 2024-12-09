from serial.tools import list_ports

from .chronology import Chronology
from .spider import Spider

def port_info():
    for port in list_ports.comports():
        print(f'{port.device=}, {port.description=}, {port.name=}, {port.manufacturer=}, {port.usb_info()=}')

def find_upython():
    for port in list_ports.comports():
        if port.manufacturer == 'MicroPython':
            return port.device
    return None

def find_spider():
    # NOTE: it exposes two com ports, assuming the first hit in the list is what we want always
    for port in list_ports.comports():
        if port.description == 'Spider - Spider' or 'Test Tool 1.x' in port.description:
            return port.device
    return None

def find_stlink_uart():
    for port in list_ports.comports():
        if port.description == 'STM32 STLink - ST-Link VCP Ctrl':
            return port.device
    return None

def find_3018():
    for port in list_ports.comports():
        if '1A86:7523' in port.usb_info():
            return port.device
    return None

def find_chipshouter():
    for port in list_ports.comports():
        if 'ChipSHOUTER' in port.description:
            return port.device
    return None    

def arm_spider_glitch(glitcher: Chronology, glitch_v, glitch_delay_s, glitch_time_s, do_glitch=True):
    glitcher.forget_events()
    # glitcher.set_gpio_now(0, 0)
    glitcher.wait_trigger(8, Spider.RISING_EDGE, 1)
    # glitcher.set_gpio(0, 1)
    if do_glitch:
        glitcher.glitch(
            Spider.GLITCH_OUT1,
            glitch_v,
            glitch_delay_s,
            glitch_time_s,
        )
    # glitcher.set_gpio(0, 0)
    glitcher.start()

def arm_spider_glitch2(glitcher: Chronology, 
                      glitch_v, glitch_delay_s, glitch_time_s, 
                      glitch_v2, glitch_delay_s2, glitch_time_s2, 
                      do_glitch=True):
    glitcher.forget_events()
    # glitcher.set_gpio_now(0, 0)
    glitcher.wait_trigger(8, Spider.RISING_EDGE, 1)
    # glitcher.set_gpio(0, 1)
    if do_glitch:
        glitcher.glitch(
            Spider.GLITCH_OUT1,
            glitch_v,
            glitch_delay_s,
            glitch_time_s,
        )
    glitcher.wait_trigger(8, Spider.RISING_EDGE, 1)
    if do_glitch:
        glitcher.glitch(
            Spider.GLITCH_OUT1,
            glitch_v2,
            glitch_delay_s2,
            glitch_time_s2,
        )
    # glitcher.set_gpio(0, 0)
    glitcher.start()