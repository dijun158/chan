# coding: utf-8

from czsc.analyze import BI
from czsc.enum import Direction
from czsc.utils import MACD
from datetime import datetime, timedelta
import numpy
from czsc.data.jq import get_kline_


def get_bi_view(bi: BI):
    no_touch = ""
    if bi.fx_a.high < bi.fx_b.low or bi.fx_a.low > bi.fx_b.high:
        no_touch = "!"
    fx_a_raw_bar_num = sum(len(ele.elements) for ele in bi.fx_a.elements)
    fx_b_raw_bar_num = sum(len(ele.elements) for ele in bi.fx_b.elements)

    left_raw_bars = bi.fx_a.elements[0].elements + bi.fx_a.elements[1].elements + \
                    bi.fx_a.elements[2].elements
    right_raw_bars = bi.fx_b.elements[0].elements + bi.fx_b.elements[1].elements + \
                     bi.fx_b.elements[2].elements

    if bi.direction == Direction.Up:
        low = min(bar.low for bar in left_raw_bars)
        high = max(bar.high for bar in right_raw_bars)

        left_raw_bar = left_raw_bars[0]
        for bar in left_raw_bars:
            if bar.low == low and bar.dt > left_raw_bar.dt:
                left_raw_bar = bar

        right_raw_bar = right_raw_bars[0]
        for bar in right_raw_bars:
            if bar.high == high and bar.dt > right_raw_bar.dt:
                right_raw_bar = bar
    else:
        high = max(bar.high for bar in left_raw_bars)
        low = min(bar.low for bar in right_raw_bars)

        left_raw_bar = left_raw_bars[0]
        for bar in left_raw_bars:
            if bar.high == high and bar.dt > left_raw_bar.dt:
                left_raw_bar = bar

        right_raw_bar = right_raw_bars[0]
        for bar in right_raw_bars:
            if bar.low == low and bar.dt > right_raw_bar.dt:
                right_raw_bar = bar

    return ("%s %s(%d) ~ %s(%d) %s" %
            (bi.symbol, left_raw_bar.dt.strftime('%Y-%m-%d'), fx_a_raw_bar_num,
             right_raw_bar.dt.strftime('%Y-%m-%d'), fx_b_raw_bar_num, no_touch))


def macd_helper(bars):
    diff, dea, macd = MACD(numpy.array([bar.close for bar in bars], dtype=numpy.double))
    date_to_bar_idx = {}
    for idx in range(0, len(bars)):
        date_to_bar_idx[bars[idx].dt] = idx

    return macd, date_to_bar_idx


def pre_check(symbol, num=30):
    thirty_days_before = datetime.now() - timedelta(days=30)

    if len(get_kline_(symbol, thirty_days_before.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'), "30m")) == 0:
        return None

    bars = get_kline_(symbol, "", datetime.now().strftime('%Y-%m-%d'), "d", num)
    if len(bars) < 10:
        return None

    return bars
