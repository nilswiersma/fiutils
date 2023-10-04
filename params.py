import json

from functools import reduce, partial
import operator

import numpy as np

class Parameter():
    def __init__(self, name, min=0, max=1, step=1, count=1, dtype='int', itype='uniform', *args, **kwargs) -> None:
        if itype == 'uniform':
            if dtype == 'int':
                self._f_gen = partial(np.random.randint, dtype=np.int32)
            elif dtype == 'float':
                self._f_gen = np.random.uniform
            else:
                raise NotImplementedError
        elif itype == 'range':
            if dtype == 'int':
                self._f_gen = partial(np.arange, dtype=np.int32)
            if dtype == 'float':
                self._f_gen = partial(np.arange, dtype=np.float32)
        elif itype == 'linspace':
            if dtype == 'int':
                self._f_gen = partial(np.linspace, dtype=np.int32)
            if dtype == 'float':
                self._f_gen = partial(np.linspace, dtype=np.float32)
        else:
            raise NotImplementedError

        self.name = name
        self.min = min
        self.max = max
        self.step = step
        self.count = count
        self.dtype = dtype
        self.itype = itype

        self.reset()
        
        self._generated = 0
    
    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._gen)
        except StopIteration:
            self.reset()
            raise StopIteration
    
    def __repr__(self):
        return f'<Parameter @ 0x{id(self)} {self.name} min={self.min} max={self.max} count={self.count} step={self.step} {self.dtype} {self.itype}>'
    
    def total(self):
        if self.itype == 'uniform':
            return self.count
        elif self.itype == 'range':
            if self.dtype == 'int':
                return self.max - self.min
            else:
                raise NotImplementedError
        elif self.itype == 'linspace':
            return self.count
        else:
            raise NotImplementedError
        
    def reset(self):
        if self.itype == 'uniform':
            self._gen = iter(self._f_gen(self.min, self.max, self.count))
        elif self.itype == 'range':
            self._gen = iter(self._f_gen(self.min, self.max, self.step))
        elif self.itype == 'linspace':
            self._gen = iter(self._f_gen(self.min, self.max, self.count))
        else:
            raise NotImplementedError

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k[0] != '_'}
    
    def to_json(self):
        return json.dumps(self.to_dict())


class Parameter2D():
    def __init__(self, name, a_x, a_y, b_x, b_y, stops_x, stops_y):
        self.name = name
        self.limits = ((a_x, a_y), (b_x, b_y))
        self.stops = (stops_x, stops_y)

        self.reset()

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._gen)
        except StopIteration:
            self.reset()
            raise StopIteration

    def total(self):
        return self.stops[0] * self.stops[1]

    def reset(self):
        # https://stackoverflow.com/questions/32208359/is-there-a-multi-dimensional-version-of-arange-linspace-in-numpy
        self._gen = iter(np.mgrid[self.limits[0][0]:self.limits[1][0]:complex(0, self.stops[0]), 
                         self.limits[0][1]:self.limits[1][1]:complex(0, self.stops[1])].reshape(2,-1).T)
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k[0] != '_'}
    
    def to_json(self):
        return json.dumps(self.to_dict())


# Custom product (instead of itertools.product) so generators with random values give new random values each iteration
def pproduct(iters):
    if not iters:
        yield {}
    else:
        for i in iter(iters[0]):
            try:
                key = iters[0].name
            except AttributeError:
                key = iters[0].__class__.__name__
            for rest in pproduct(iters[1:]):
                if key in rest.keys():
                    raise Exception(f"multiple definitions of {key=}")
                
                # unroll the thing if it is iterable so it will more easily go into a database
                try:
                    for idx, j in enumerate(i):
                        rest[f'{key}{idx}'] = j
                except TypeError:
                    rest[key] = i
                
                yield rest

def ptotal(iters):
    return reduce(operator.mul, map(lambda x: x.total(), iters))

def pdump(iters, fname):
    with open(fname, 'w') as f:
        json.dump([it.to_dict() for it in iters], fp=f, indent=4)

def pload(fname):
    with open(fname, 'r') as f:
        data = json.load(f)
        return [Parameter(**config) for config in data]