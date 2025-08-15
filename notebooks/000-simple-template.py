import sys, os, logging
from fiutils.utils import get_run_id, setup_logger
lm = setup_logger('main')
__file__, timestamp = get_run_id('000-simple-template')
try:
    # If a timestampe is pass as argument, use that one instead
    timestamp = sys.argv[1]
    lm.info(f're-using {timestamp=}')
except IndexError:
    pass
with open('last_timestamp', 'w') as f: 
    f.write(timestamp)
lm.info(f'I identify as {__file__}, {timestamp}')

import time
import sqlite3

from pprint import pformat
from contextlib import closing
from types import SimpleNamespace

from fiutils.utils import setup_file_logger, setup_db, setup_params
from fiutils.db import db_append_row
from fiutils.params import Parameter, Parameter2D, pproduct, ptotal, pdump

setup_file_logger(__file__, timestamp)
lm.info(f'I identify as {__file__}, {timestamp}')

db_name, table_name, hist = setup_db(__file__, timestamp)
lm.info(f'{db_name=} {table_name=}')
lm.info(f'{pformat(hist)=}')

xy_stops = (10, 20)

progress = setup_params(__file__, timestamp, 
    Parameter('target_v', 2.4, itype='fixed'),
    Parameter('scan', max=500_000, itype='range'),
    Parameter2D('xy_scanner', 0, 100, 0, 200, *xy_stops),
    Parameter('scan_per_point', max=100, itype='range'),
    Parameter('glitch_delay_ns', 10, 10_000),
    Parameter('glitch_time_ns', 50, 1200),
    Parameter('glitch_v', 0.0, 1.5, dtype='float'),
)

prev_xy_scanner0 = None
prev_xy_scanner1 = None
do_move = False
do_reset = True

with closing(sqlite3.connect(db_name)) as db:
    for idx, settings in progress:
        try:
            t0 = time.time()*1000
            p = SimpleNamespace(**settings)

            p.idx = idx
            p.verdict = 'NORMAL00'
            p.stop = False
            p.do_move = do_move

            with progress.external_write_mode():
                lm.info(f'{idx=}')
            
            if do_reset:
                with progress.external_write_mode():
                    lm.warning('Reset!')
                
                time.sleep(.1)
                do_reset = False
            
            if do_move and (prev_xy_scanner0 != p.xy_scanner0 or prev_xy_scanner1 != p.xy_scanner1):
                with progress.external_write_mode():
                    lm.info(f'Moving to {p.xy_scanner0},{p.xy_scanner1}')
                prev_xy_scanner0 = p.xy_scanner0
                prev_xy_scanner1 = p.xy_scanner1
                
                time.sleep(.5)

            if (p.glitch_v * p.glitch_time_ns) > 1000:
                p.verdict = 'MUTE00'
            elif 400 < (p.glitch_v * p.glitch_time_ns) < 500:
                if 3000 < p.glitch_delay_ns < 5000:
                    p.verdict = 'GLITCH00'
                elif p.glitch_delay_ns > 9900:
                    p.verdict = 'ERROR00'
                    p.stop = True
                else:
                    pass
            else:
                pass
            
            if p.verdict not in ['NORMAL00', 'GLITCH00']:
                with progress.external_write_mode():
                    lm.error('Yikes, need a reset!')
                    do_reset = True

            p.iter_t = time.time_ns() - t0
            p.do_reset = do_reset

            try:
                hist[p.verdict] += 1
            except KeyError:
                hist[p.verdict] = 1
            
            with progress.external_write_mode():
                lm.info(pformat(p))
                lm.info(pformat(hist))
            
            db_append_row(db, table_name, p.__dict__)
        
        except KeyboardInterrupt:
            try:
                x = input('\n[c]ontinue/[q]uit?\n> ')
            except KeyboardInterrupt:
                break
            if x == 'c':
                continue
            elif x == 'q':
                break
            else:
                pass

lm.info('Thank you, bye!')
