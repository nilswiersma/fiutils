import pandas as pd
import holoviews as hv

import operator

from itertools import combinations
from typing import Iterable, Union
from functools import reduce

def sample_by(ldf: pd.DataFrame, by: str, n: int=100) -> pd.DataFrame:
    return ldf.groupby(by).apply(lambda x: x.sample(min(n, len(x)))).reset_index(drop=True)

def summary_by(ldf: pd.DataFrame, by: str) -> pd.DataFrame:
    summary = pd.DataFrame(ldf[by].value_counts())
    summary.loc['Total'] = len(ldf[by])
    summary['percent'] = summary.values / len(ldf[by]) * 100
    summary['percent'] = summary['percent'].apply(lambda x: f'{x:.2f}')
    return summary

def multi_scatter(df: pd.DataFrame, dims: Iterable[str], by: str='verdict', nsample: int=None, ncols: int=2, *args, **kwargs) -> hv.NdLayout:
    if nsample:
        df_sample = sample_by(df, by, n=nsample)
    plts = []
    combs = list(combinations(dims, 2))
    for idx, (x, y) in enumerate(combs):
        plts.append(df_sample.hvplot.scatter(x=x, y=y, by=by, *args, **kwargs))
    layout = reduce(operator.add, plts)
    if len(combs) > 1:
        return layout.cols(ncols)
    return layout

# def hist2d(df, x, y, bins=10) -> pd.DataFrame:
#     # Use pd.cut and pd.pivot_table to hist2d the data (instead of np.histogram2d)
#     df2 = pd.DataFrame(columns=[x, y])
#     # Need to convert the labels to string, or we get exceptions further down the pipeline
#     try:
#         if len(bins) == 2:
#             xbins, ybins = bins
#         else:
#             raise ValueError(f'Do not like {bins=}')
#     except TypeError:
#         xbins = bins
#         ybins = bins
#     df2[x] = pd.cut(df[x], bins=xbins).apply(str)
#     df2[y] = pd.cut(df[y], bins=ybins).apply(str)
#     # Use the index to be able to count over something
#     dfp = df2.reset_index().pivot_table(index=y, columns=x, aggfunc='count').droplevel(0, 'columns')
#     return dfp

# def multi_heat2d(df: pd.DataFrame, dims: Iterable[str], bins: int=None, ncols: int=2, *args, **kwargs) -> hv.NdLayout:
#     plts = []
#     combs = list(combinations(dims, 2))
#     for idx, (x, y) in enumerate(combs):
#         plts.append(hist2d(df, x, y, bins).hvplot.heatmap(*args, **kwargs).opts(xrotation=45, xlabel=x, ylabel=y))
#     layout = reduce(operator.add, plts).opts(shared_axes=False)
#     if len(combs) > 1:
#         return layout.cols(ncols)
#     return layout

def multi_heat2d(df: pd.DataFrame, dims: Iterable[str], filter: Union[None, pd.Series]=None, bins: Union[Iterable[int], int]=10, ncols: int=2, *args, **kwargs) -> Union[hv.NdLayout, hv.HeatMap]:
    # Perform any filtering after cutting for consistent bins
    df_binned = pd.DataFrame(columns=dims)
    
    try:
        if len(bins) == len(dims):
            # Have a bin per dim
            it = zip(dims, bins)
        else:
            raise ValueError(f'Do not like {bins=}')
    except TypeError:
        it = zip(dims, [bins]*len(dims))

    for dim, bin in it:
        # Need to convert the labels to string, or we get exceptions further down the pipeline
        df_binned[dim] = pd.cut(df[dim], bins=bin).apply(str)

    plts = []
    combs = list(combinations(dims, 2))
    for idx, (x, y) in enumerate(combs):
        df_plot = df_binned
        if not isinstance(filter, type(None)):
            df_plot = df_binned[filter]
        plts.append(
            df_plot.reset_index().groupby([y, x])['index'].count().unstack().hvplot.heatmap(*args, **kwargs).opts(xrotation=45, xlabel=x, ylabel=y))
    layout = reduce(operator.add, plts).opts(shared_axes=False)
    if len(combs) > 1:
        return layout.cols(ncols)
    return layout
