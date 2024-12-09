"""\
Function to arm a ChipShouter with minimal overhead, unless there are some errors reported.
"""

import time

from chipshouter import ChipSHOUTER

def chipshout_setup_attempt(cs: ChipSHOUTER, timeout_s=3):
    state = None
    trigger_safe = cs.trigger_safe
    # print(f'{trigger_safe=}')
    if not trigger_safe:
        state = cs.state

        if cs.state == 'fault':
            cs.clr_armed
            timeout_t = time.time()
            while not cs.trigger_safe and time.time() - timeout_t < timeout_s:
                time.sleep(.1)
            state = cs.state
            # print(f'{state=} after clr_armed')

        if state == 'fault':
            cs.reset = 1
            time.sleep(.1)
            cs.absent_temp = 60
            cs.mute = 1
            state = cs.state
            # print(f'{state=} after reset=1')

        if state == 'fault':
            raise Exception('Could not recover from fault')
        elif state == 'disarmed':
            cs.clr_armed = 1
            timeout_t = time.time()
            while not cs.trigger_safe and time.time() - timeout_t < timeout_s:
                time.sleep(.1)
            # print(f'{cs.trigger_safe=}')
            state = cs.state
            # print(f'{state=} after armed=1')
        elif state == 'armed':
            # print(f'{state=} already armed all along')
            pass

    if not (trigger_safe or state == 'armed'):
        raise Exception(f'Could not arm ChipSHOUTER, {state=} {cs.state=}')