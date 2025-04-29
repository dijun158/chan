# coding: utf-8

from czsc.objects import Zhongshu, Zoushi
from typing import List
from czsc.analyze import BI
from czsc.enum import Direction, ZsEnd
import copy


def get_zhongshu_bi_num(bis: List[BI], limit):
    if len(bis) < 3:
        return None, ZsEnd.FewBi

    idx = 3
    for idx in range(3, len(bis)):
        sub_bis = bis[1:idx + 1]

        low = min(bi.low for bi in sub_bis)
        high = max(bi.high for bi in sub_bis)
        min_high = min(bi.high for bi in sub_bis)
        max_low = max(bi.low for bi in sub_bis)

        # 如果不是最后一笔，就要判断中枢破坏原因：1）三买；2）扩展；3）反向二卖
        # 跌破limit，limit是第一笔的起点，或者上一个中枢的高点形成扩展
        if low <= limit:
            return idx - 1, ZsEnd.DownLimit

        # 没有重叠部分，就会形成三买确认中枢结束，或者反向二卖确认中枢结束
        if min_high < max_low:
            if sub_bis[-1].low > max(bi.high for bi in bis[1:idx - 1]):
                return idx - 2, ZsEnd.Thirdbuy
            elif sub_bis[-1].high < min(bi.low for bi in bis[1:idx - 1]):
                return idx - 1, ZsEnd.FSecondBuy
            else:
                return idx - 1, ZsEnd.Spread

    return idx, ZsEnd.LastBi


def transfer_bi_list(bi_list: List[BI], parse_direction):
    transed_bi_list = []

    if parse_direction == Direction.Forward:
        if bi_list[0].direction == Direction.Up:
            transed_bi_list = copy.deepcopy(bi_list)
        else:
            for bi in bi_list:
                bic = copy.deepcopy(bi)
                bic.low = -bi.high
                bic.high = -bi.low
                transed_bi_list.append(bic)
    elif parse_direction == Direction.Backward:
        if bi_list[-1].direction == Direction.Down:
            transed_bi_list = list(reversed(bi_list))
        else:
            for bi in bi_list:
                bic = copy.deepcopy(bi)
                bic.low = -bi.high
                bic.high = -bi.low
                transed_bi_list.append(bic)
            transed_bi_list = list(reversed(transed_bi_list))

    return transed_bi_list


def get_bi_power(macd, begin_idx, end_idx, is_plus):
    power = 0

    for i in range(begin_idx, end_idx + 1):
        if is_plus and macd[i] > 0:
            power += macd[i]
        elif not is_plus and macd[i] < 0:
            power += macd[i]

    return abs(power)


def form_zhongshu(bis: List[BI], enter_bi_idx, num, macd, date_to_bar_idx):
    zhongshu = Zhongshu()
    zhongshu.bis = bis[enter_bi_idx + 1:enter_bi_idx + num + 1]
    zhongshu.bi_num = num
    zhongshu.gg = max(bi.high for bi in zhongshu.bis)
    zhongshu.dd = min(bi.low for bi in zhongshu.bis)
    zhongshu.zg = min(bi.high for bi in zhongshu.bis)
    zhongshu.zd = max(bi.low for bi in zhongshu.bis)

    enter_bi = bis[enter_bi_idx]
    zhongshu.enter_power = get_bi_power(macd, date_to_bar_idx[enter_bi.fx_a.dt], date_to_bar_idx[enter_bi.fx_b.dt],
                                        enter_bi.direction == Direction.Up)

    if len(bis) > enter_bi_idx + num + 1:
        leave_bi = bis[enter_bi_idx + num + 1]
        if (enter_bi.direction == Direction.Up and leave_bi.direction == Direction.Up and leave_bi.high > max(
                bi.high for bi in bis[enter_bi_idx + 1:enter_bi_idx + num + 1])) or \
                (enter_bi.direction == Direction.Down and leave_bi.direction == Direction.Down and leave_bi.low < min(
                    bi.low for bi in bis[enter_bi_idx + 1:enter_bi_idx + num + 1])):
            zhongshu.leave_power = get_bi_power(macd, date_to_bar_idx[leave_bi.fx_a.dt],
                                                date_to_bar_idx[leave_bi.fx_b.dt],
                                                enter_bi.direction == Direction.Up)

    return zhongshu


def get_zoushi(bi_list: List[BI], parse_direction, handle_last_zhongshu, macd, date_to_bar_idx, freq):
    if len(bi_list) < 3:
        return None

    zhongshu_bi_num_list, zs_end = get_zhongshu_bi_num_list(bi_list, parse_direction, handle_last_zhongshu)
    bi_num = sum(zhongshu_bi_num_list) + len(zhongshu_bi_num_list)
    if handle_last_zhongshu:
        bi_num += 1
    if zs_end == ZsEnd.Thirdbuy and bi_list[0].direction == Direction.Up:
        bi_num += 2

    zoushi = Zoushi(freq=freq, zhongshu_end=zs_end)
    if parse_direction == Direction.Forward:
        zoushi.bis = bi_list[:bi_num]
    else:
        zoushi.bis = bi_list[-bi_num:]

    enter_bi_idx = 0
    zhongshus = []
    for num in zhongshu_bi_num_list:
        zhongshu = form_zhongshu(zoushi.bis, enter_bi_idx, num, macd, date_to_bar_idx)
        zhongshus.append(zhongshu)
        enter_bi_idx += num + 1

    zoushi.zhongshus = zhongshus

    return zoushi


def get_zhongshu_bi_num_list(bi_list: List[BI], parse_direction, handle_last_zhongshu):
    transed_bi_list = transfer_bi_list(bi_list, parse_direction)

    zhongshu_bi_num_list = []
    limit = transed_bi_list[0].low
    idx = 0
    while len(transed_bi_list) > 0:
        zhongshu_bi_num, zs_end = get_zhongshu_bi_num(transed_bi_list[idx:], limit)
        if zhongshu_bi_num:
            zhongshu_bi_num_list.append(zhongshu_bi_num)

        if zs_end == ZsEnd.Thirdbuy:
            limit = max(bi.high for bi in transed_bi_list[idx + 1:idx + zhongshu_bi_num + 1])
            if idx + zhongshu_bi_num + 3 == len(transed_bi_list):
                break
            idx += zhongshu_bi_num + 1
        else:
            break

    if handle_last_zhongshu:
        last_zhongshu_bi_num = zhongshu_bi_num_list[-1]
        zhongshu_bi_num_list.pop()
        if len(transed_bi_list) >= 3:
            # 需要找到最高的笔，然后去掉其他的
            highest_bi_idx = 0
            for i in range(2, last_zhongshu_bi_num + 1, 2):
                if transed_bi_list[idx + i].high > transed_bi_list[highest_bi_idx].high:
                    highest_bi_idx = i

            if highest_bi_idx != 0:
                zhongshu_bi_num_list.append(highest_bi_idx - 1)
        else:
            # 这种要去掉
            pass

    if parse_direction == Direction.Forward:
        return zhongshu_bi_num_list, zs_end

    return list(reversed(zhongshu_bi_num_list)), zs_end

