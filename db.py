from contextlib import closing
import sqlite3

import numpy as np

def db_setup(conn: sqlite3.Connection):
    conn.execute('pragma journal_mode=wal')
    sqlite3.register_adapter(np.int32, int)
    sqlite3.register_adapter(np.int64, int)
    sqlite3.register_adapter(np.float32, float)
    sqlite3.register_adapter(np.float64, float)

def db_append_row(conn: sqlite3.Connection, table: str, data: "list[dict]"):
    with closing(conn.cursor()) as cursor:
        if isinstance(data, dict):
            f_insert = cursor.execute
            keys = list(data.keys())
        elif isinstance(data, list):
            if not isinstance(data[0], dict):
                raise TypeError(f'data must be dict or iterable of dicts, not {type(data)=}')
            f_insert = cursor.executemany
            keys = list(data[0].keys())
        else:
            raise TypeError(f'data must be dict or list of dicts, not {type(data)=}')
            
        res = cursor.execute(f"SELECT * FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not res.fetchone():
            print(f'{table} does not exist yet, creating it')

            # if isinstance(data, dict):
            #     types = [TYPE_LOOKUP[type(x)] for x in data.values()]
            # elif isinstance(data, list):
            #     types = [TYPE_LOOKUP[type(x)] for x in data[0].values()]
            # else:
            #     raise TypeError
            # create_s = ', '.join(f'{k} {t}' for k,t in zip(keys, types))

            create_s = ', '.join(keys)

            cursor.execute(f"CREATE TABLE '{table}'({create_s})")
        else:
            pass
    
        f_insert(f"INSERT INTO '{table}' VALUES ({ ','.join(f':{col}' for col in keys) })", data)
        cursor.connection.commit()

def db_get_hist(conn: sqlite3.Connection, table: str) -> dict:
    # hist = pd.DataFrame(columns=['count()'])
    # hist.index.rename('verdict', inplace=True)
    hist = {}
    with closing(conn.cursor()) as cursor:
        res = cursor.execute(f"SELECT * FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not res.fetchone():
            print(f'{table} does not exist yet')
        else:
            res = cursor.execute(f"SELECT verdict,count() FROM '{table}' GROUP BY verdict")
            for k,v in res.fetchall():
                hist[k] = v
    return hist

