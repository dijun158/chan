# coding: utf-8
"""
实时分析模块
用于处理实时K线数据的缠论分析
"""

# 导入必要的模块和类
import os  # 导入操作系统相关功能
from typing import List  # 导入类型提示功能
from .objects import Mark, Direction, BI, FX, RawBar, NewBar, InnerBI  # 导入自定义对象类
from .utils.echarts_plot import kline_pro  # 导入K线图绘制工具
from czsc.enum import BiReason  # 导入笔的原因枚举
from datetime import timedelta, datetime  # 导入日期时间处理模块
from copy import deepcopy  # 导入深拷贝功能

# 全局变量定义
inner_can_be_bi = {}  # 存储内部笔的缓存，用于优化性能
show_inner = False    # 控制是否显示内部笔的标记
check_one_min_after = None  # 记录需要在一分钟后检查的时间点
today = datetime.now()  # 记录当前系统时间
only_qiangbi = False   # 控制是否只显示强笔


def set_only_qiangbi():
    """
    设置只显示强笔的标志
    :return: None
    """
    global only_qiangbi  # 声明使用全局变量
    only_qiangbi = True  # 将全局变量设置为True


def find_fx(bars: List[NewBar], inner_idx, mark, weak_left=False, weak_right=False):
    """
    查找分型函数
    :param bars: K线数据列表
    :param inner_idx: 内部索引位置
    :param mark: 分型标记（顶分型或底分型）
    :param weak_left: 是否允许左侧弱分型
    :param weak_right: 是否允许右侧弱分型
    :return: 分型对象
    """
    # 初始化分型的左右边界和当前K线
    inner_left = inner_idx  # 设置左边界为当前索引
    inner_right = inner_idx  # 设置右边界为当前索引
    inner_bar = bars[inner_idx]  # 获取当前K线
    inner_low = inner_bar.low  # 记录当前K线的最低价
    inner_high = inner_bar.high  # 记录当前K线的最高价

    while True:  # 循环查找分型
        if mark == Mark.G:  # 如果是顶分型
            # 处理顶分型
            left = inner_left - 1  # 向左移动一个位置
            # 向左查找更低的低点
            while left >= 0 and bars[left].low >= inner_low:
                inner_low = bars[left].low  # 更新最低价
                inner_left -= 1  # 更新左边界
                left -= 1  # 继续向左移动

            right = inner_right + 1  # 向右移动一个位置
            # 向右查找更低的低点
            while right < len(bars) and bars[right].low >= inner_low:
                inner_low = bars[right].low  # 更新最低价
                inner_right += 1  # 更新右边界
                right += 1  # 继续向右移动

            # 检查左侧分型
            left_low = None  # 初始化左侧最低价
            if left >= 0:  # 如果还有左侧K线
                left_low = bars[left].low  # 记录左侧K线的最低价
                left -= 1  # 继续向左移动
                # 继续向左查找更低的低点
                while left >= 0 and bars[left].low >= left_low:
                    left_low = bars[left].low
                    left -= 1

            # 检查右侧分型
            right_low = None  # 初始化右侧最低价
            if right < len(bars):  # 如果还有右侧K线
                right_low = bars[right].low  # 记录右侧K线的最低价
                right += 1  # 继续向右移动
                # 继续向右查找更低的低点
                while right < len(bars) and bars[right].low >= right_low:
                    right_low = bars[right].low
                    right += 1

            # 检查分型是否有效
            if left_low and left_low >= inner_low:
                inner_low = left_low  # 更新最低价
                inner_left = left + 1  # 更新左边界
                left_low = None  # 重置左侧最低价
            if right_low and right_low >= inner_low:
                inner_low = right_low  # 更新最低价
                inner_right = right - 1  # 更新右边界
                right_low = None  # 重置右侧最低价

            # 检查是否满足分型条件
            if (left_low and inner_low > left_low and right_low and inner_low > right_low) or \
                    (weak_left and left == -1 and right_low and inner_low > right_low) or \
                    (weak_right and right == len(bars) and left_low and inner_low > left_low):
                elements = []  # 初始化元素列表

                # 处理左侧K线
                if left_low and inner_low > left_low:
                    left_bar = NewBar(symbol=inner_bar.symbol, freq=inner_bar.freq, dt=bars[left + 1].dt,
                                      high=max(bar.high for bar in bars[left + 1:inner_left]),
                                      low=max(bar.low for bar in bars[left + 1:inner_left]), elements=bars[left + 1:inner_left])
                    elements.append(left_bar)  # 添加左侧K线

                # 处理中间K线
                inner_bar = NewBar(symbol=inner_bar.symbol, freq=inner_bar.freq, dt=inner_bar.dt, high=inner_bar.high,
                                   low=max(bar.low for bar in bars[inner_left:inner_right + 1]), elements=bars[inner_left:inner_right + 1])
                elements.append(inner_bar)  # 添加中间K线

                # 处理右侧K线
                if right_low and inner_low > right_low:
                    right_bar = NewBar(symbol=inner_bar.symbol, freq=inner_bar.freq, dt=bars[right - 1].dt,
                                       high=max(bar.high for bar in bars[inner_right + 1:right]),
                                       low=max(bar.low for bar in bars[inner_right + 1:right]), elements=bars[inner_right + 1:right])
                    elements.append(right_bar)  # 添加右侧K线

                # 返回分型对象
                return FX(symbol=inner_bar.symbol, dt=inner_bar.dt, mark=mark, high=inner_high, low=min(bar.low for bar in elements),
                          fx=inner_high,
                          elements=elements)
            # 检查是否不满足分型条件
            elif (not weak_left and left_low is None and left == -1) or (not weak_right and right_low is None and right == len(bars)):
                return None  # 返回None表示不满足分型条件
        else:
            # 处理底分型
            left = inner_left - 1  # 向左移动一个位置
            # 向左查找更高的高点
            while left >= 0 and bars[left].high <= inner_high:
                inner_high = bars[left].high  # 更新最高价
                inner_left -= 1  # 更新左边界
                left -= 1  # 继续向左移动

            right = inner_right + 1  # 向右移动一个位置
            # 向右查找更高的高点
            while right < len(bars) and bars[right].high <= inner_high:
                inner_high = bars[right].high  # 更新最高价
                inner_right += 1  # 更新右边界
                right += 1  # 继续向右移动

            # 检查左侧分型
            left_high = None  # 初始化左侧最高价
            if left >= 0:  # 如果还有左侧K线
                left_high = bars[left].high  # 记录左侧K线的最高价
                left -= 1  # 继续向左移动
                # 继续向左查找更高的高点
                while left >= 0 and bars[left].high <= left_high:
                    left_high = bars[left].high
                    left -= 1

            # 检查右侧分型
            right_high = None  # 初始化右侧最高价
            if right < len(bars):  # 如果还有右侧K线
                right_high = bars[right].high  # 记录右侧K线的最高价
                right += 1  # 继续向右移动
                # 继续向右查找更高的高点
                while right < len(bars) and bars[right].high <= right_high:
                    right_high = bars[right].high
                    right += 1

            # 检查分型是否有效
            if left_high and left_high <= inner_high:
                inner_high = left_high  # 更新最高价
                inner_left = left + 1  # 更新左边界
                left_high = None  # 重置左侧最高价
            if right_high and right_high <= inner_high:
                inner_high = right_high  # 更新最高价
                inner_right = right - 1  # 更新右边界
                right_high = None  # 重置右侧最高价

            # 检查是否满足分型条件
            if (left_high and inner_high < left_high and right_high and inner_high < right_high) or \
                    (weak_left and left == -1 and right_high and inner_high < right_high) or \
                    (weak_right and right == len(bars) and left_high and inner_high < left_high):
                elements = []  # 初始化元素列表

                # 处理左侧K线
                if left_high and inner_high < left_high:
                    left_bar = NewBar(symbol=inner_bar.symbol, freq=inner_bar.freq, dt=bars[left + 1].dt,
                                      high=min(bar.high for bar in bars[left + 1:inner_left]),
                                      low=min(bar.low for bar in bars[left + 1:inner_left]), elements=bars[left + 1:inner_left])
                    elements.append(left_bar)  # 添加左侧K线

                # 处理中间K线
                inner_bar = NewBar(symbol=inner_bar.symbol, freq=inner_bar.freq, dt=inner_bar.dt, high=inner_bar.high,
                                   low=min(bar.low for bar in bars[inner_left:inner_right + 1]), elements=bars[inner_left:inner_right + 1])
                elements.append(inner_bar)  # 添加中间K线

                # 处理右侧K线
                if right_high and inner_high < right_high:
                    right_bar = NewBar(symbol=inner_bar.symbol, freq=inner_bar.freq, dt=bars[right - 1].dt,
                                       high=min(bar.high for bar in bars[inner_right + 1:right]),
                                       low=min(bar.low for bar in bars[inner_right + 1:right]), elements=bars[inner_right + 1:right])
                    elements.append(right_bar)  # 添加右侧K线

                # 返回分型对象
                return FX(symbol=inner_bar.symbol, dt=inner_bar.dt, mark=mark, high=max(bar.high for bar in elements), low=inner_low,
                          fx=inner_low, elements=elements)
            # 检查是否不满足分型条件
            elif (not weak_left and left_high is None and left == -1) or (not weak_right and right_high is None and right == len(bars)):
                return None  # 返回None表示不满足分型条件


def find_inner_bis1(bars: List[NewBar], direction):
    """
    查找内部笔的第一个版本
    :param bars: K线列表
    :param direction: 方向
    :return: 内部笔列表
    """
    inner_bis = []  # 初始化内部笔列表
    # 查找第一个笔
    for idx in range(1, len(bars)):
        # 判断是否满足笔的方向条件
        if (direction == Direction.Up and bars[idx].high > bars[0].high) or \
           (direction == Direction.Down and bars[idx].low < bars[0].low):
            # 确定笔的高低点
            high = bars[0].high if direction == Direction.Down else bars[idx].high
            low = bars[idx].low if direction == Direction.Down else bars[0].low
            # 创建内部笔对象
            inner_bis.append(InnerBI(left=0, right=idx, left_date=bars[0].dt, right_date=bars[idx].dt, direction=direction,
                                     high=high, low=low))
            break  # 找到第一个笔后退出循环

    # 如果没有找到第一个笔，直接返回空列表
    if len(inner_bis) == 0:
        return inner_bis

    # 继续查找后续的笔
    for idx in range(inner_bis[0].right, len(bars)):
        start = inner_bis[-1].right  # 获取上一笔的结束位置
        # 处理向下笔
        if inner_bis[-1].direction == Direction.Down:
            # 检查是否满足向上笔的条件
            if idx - start >= 3 and bars[idx].high >= max(bar.high for bar in bars[start:idx]) and bars[idx].low > bars[start].low:
                # 创建向上笔
                inner_bis.append(InnerBI(left=start, right=idx, high=bars[idx].high, low=bars[start].low, left_date=bars[start].dt,
                                         right_date=bars[idx].dt, direction=Direction.Up))
            # 处理笔的延伸
            elif bars[idx].low < inner_bis[-1].low:
                if bars[idx].high < inner_bis[-1].high:
                    # 更新笔的低点
                    inner_bis[-1].low = bars[idx].low
                    inner_bis[-1].right = idx
                    inner_bis[-1].right_date = bars[idx].dt
                else:
                    # 删除无效的笔
                    inner_bis.pop(-1)
        # 处理向上笔
        else:
            # 检查是否满足向下笔的条件
            if idx - start >= 3 and bars[idx].low <= min(bar.low for bar in bars[start:idx]) and bars[idx].high < bars[start].high:
                # 创建向下笔
                inner_bis.append(InnerBI(left=start, right=idx, high=bars[start].high, low=bars[idx].low, left_date=bars[start].dt,
                                         right_date=bars[idx].dt, direction=Direction.Down))
            # 处理笔的延伸
            elif bars[idx].high > inner_bis[-1].high:
                if bars[idx].low > inner_bis[-1].low:
                    # 更新笔的高点
                    inner_bis[-1].high = bars[idx].high
                    inner_bis[-1].right = idx
                    inner_bis[-1].right_date = bars[idx].dt
                else:
                    # 删除无效的笔
                    inner_bis.pop(-1)

    # 处理第一个笔
    if inner_bis[0].right - inner_bis[0].left < 3:
        inner_bis.pop(0)  # 如果第一个笔不满足最小K线数要求，则删除

    return inner_bis  # 返回内部笔列表


def find_inner_bis(bars: List[NewBar], direction, gap_num=3, pop_first=True):
    """
    查找内部笔
    :param bars: K线列表
    :param direction: 方向
    :param gap_num: 笔之间的最小间隔数
    :param pop_first: 是否移除第一个笔
    :return: 内部笔列表
    """
    inner_bis = []  # 初始化内部笔列表

    # 遍历所有K线
    for idx in range(1, len(bars)):
        # 确定下一个笔的方向
        if len(inner_bis) == 0:  # 如果是第一个笔
            next_direction = direction  # 使用指定的方向
        elif inner_bis[-1].direction == Direction.Up:  # 如果上一个笔是向上的
            next_direction = Direction.Down  # 下一个笔应该是向下的
        else:  # 如果上一个笔是向下的
            next_direction = Direction.Up  # 下一个笔应该是向上的

        # 确定笔的起始位置
        if len(inner_bis) == 0:  # 如果是第一个笔
            start = 0  # 从第一个K线开始
            # 查找合适的起始位置
            for j in range(0, idx):
                if (direction == Direction.Up and bars[j].low <= bars[start].low) or \
                        (direction == Direction.Down and bars[j].high >= bars[start].high):
                    start = j
        else:  # 如果不是第一个笔
            start = inner_bis[-1].right  # 从上一个笔的结束位置开始

        # 处理向上笔
        if next_direction == Direction.Up:
            # 检查是否满足向上笔的条件
            if (len(inner_bis) == 0 or idx - start >= gap_num) and \
                    bars[idx].high >= max(bar.high for bar in bars[start:idx]) and bars[idx].high > bars[start].high and \
                    bars[idx].low > bars[start].low:
                # 创建新的向上笔
                inner_bis.append(InnerBI(left=start, right=idx, high=bars[idx].high, low=bars[start].low, left_date=bars[start].dt,
                                         right_date=bars[idx].dt, direction=Direction.Up))
            # 处理笔的延伸
            elif len(inner_bis) > 0 and bars[idx].low <= inner_bis[-1].low:
                if bars[idx].high < inner_bis[-1].high:
                    # 更新笔的低点
                    inner_bis[-1].low = bars[idx].low
                    inner_bis[-1].right = idx
                    inner_bis[-1].right_date = bars[idx].dt
                else:
                    # 删除无效的笔
                    inner_bis.pop(-1)
        # 处理向下笔
        else:
            # 检查是否满足向下笔的条件
            if (len(inner_bis) == 0 or idx - start >= gap_num) and \
                    bars[idx].low <= min(bar.low for bar in bars[start:idx]) and bars[idx].low < bars[start].low and \
                    bars[idx].high < bars[start].high:
                # 创建新的向下笔
                inner_bis.append(InnerBI(left=start, right=idx, high=bars[start].high, low=bars[idx].low, left_date=bars[start].dt,
                                         right_date=bars[idx].dt, direction=Direction.Down))
            # 处理笔的延伸
            elif len(inner_bis) > 0 and bars[idx].high >= inner_bis[-1].high:
                if bars[idx].low > inner_bis[-1].low:
                    # 更新笔的高点
                    inner_bis[-1].high = bars[idx].high
                    inner_bis[-1].right = idx
                    inner_bis[-1].right_date = bars[idx].dt
                else:
                    # 删除无效的笔
                    inner_bis.pop(-1)

    # 处理第一个笔
    if pop_first and len(inner_bis) > 0 and inner_bis[0].right - inner_bis[0].left < gap_num:
        inner_bis.pop(0)  # 如果第一个笔不满足最小间隔要求，则删除

    return inner_bis  # 返回内部笔列表


def check_bibi(bars: List[NewBar], fx_a: FX):
    """
    检查笔的连续性
    :param bars: K线列表
    :param fx_a: 分型对象
    :return: 笔对象或None
    """
    if len(bars) < 3:  # 如果K线数量不足3根
        return None  # 无法形成笔

    # 查找分型B的位置
    idx = 0
    for i in range(1, len(bars)):
        if (fx_a.mark == Mark.G and bars[i].low <= bars[idx].low) or (fx_a.mark == Mark.D and bars[i].high >= bars[idx].high):
            idx = i

    # 确定分型B的标记和查找分型B
    mark = Mark.G if fx_a.mark == Mark.D else Mark.D
    fx_b = find_fx(bars, idx, mark)
    if fx_b is None:  # 如果找不到分型B
        return None  # 无法形成笔

    bar = bars[idx]  # 获取分型B所在的K线

    # 获取所有相关K线
    a = fx_a.get_all_bars()  # 获取分型A的所有K线
    b = [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]  # 获取分型A和B之间的K线
    bars_a = [x for x in fx_a.get_all_bars()] + [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]  # 合并所有K线

    # 确定笔的方向和高低点
    direction = Direction.Up if fx_a.mark == Mark.D else Direction.Down  # 确定笔的方向
    high = fx_b.high if direction == Direction.Up else fx_a.high  # 确定笔的高点
    low = fx_a.low if direction == Direction.Up else fx_b.low  # 确定笔的低点

    # 创建笔对象
    bi = BI(symbol=bar.symbol, fx_a=fx_a, fx_b=fx_b, direction=direction, high=high, low=low, bars=bars_a)

    # 检查是否有独立的K线和笔的连续性条件
    has_separate_k = len([x for x in bars if fx_a.get_right_dt() < x.dt < fx_b.get_left_dt()]) > 0
    if fx_a.high < fx_b.low or fx_a.low > fx_b.high and has_separate_k:
        return bi  # 返回有效的笔

    return None  # 返回无效的笔


def must_get_bibi(fx_a: FX, bars: List[NewBar]):
    """
    强制获取笔
    :param fx_a: 分型对象
    :param bars: K线列表
    :return: 笔对象
    """
    # 查找分型B的位置
    idx = 0
    for i in range(1, len(bars)):
        if (fx_a.mark == Mark.G and bars[i].low <= bars[idx].low) or (fx_a.mark == Mark.D and bars[i].high >= bars[idx].high):
            idx = i

    # 确定分型B的标记
    mark = Mark.G if fx_a.mark == Mark.D else Mark.D

    # 准备分型B的元素
    bar = bars[idx]  # 获取当前K线
    elements = bars[idx - 1:idx + 1]  # 获取相邻的K线
    if idx + 1 < len(bars):  # 如果还有后续K线
        elements.append(bars[idx + 1])  # 添加后续K线

    # 根据分型类型确定高低点和分型值
    if mark == Mark.G:  # 如果是顶分型
        high = bar.high  # 设置高点
        low = min(e.high for e in elements)  # 计算低点
        fx = high  # 设置分型值
    else:  # 如果是底分型
        high = max(e.high for e in elements)  # 计算高点
        low = bar.low  # 设置低点
        fx = low  # 设置分型值

    # 创建分型B对象
    fx_b = FX(symbol=bar.symbol, dt=bar.dt, mark=mark, high=high, low=low, fx=fx, elements=elements)

    # 获取所有相关K线并创建笔对象
    bars_a = [x for x in fx_a.get_all_bars()] + [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    direction = Direction.Up if fx_a.mark == Mark.D else Direction.Down
    high = fx_b.high if direction == Direction.Up else fx_a.high
    low = fx_a.low if direction == Direction.Up else fx_b.low
    bi = BI(symbol=bar.symbol, fx_a=fx_a, fx_b=fx_b, direction=direction, high=high, low=low, bars=bars_a)
    return bi  # 返回笔对象


class CZSC:
    def __init__(self, symbol, freq):
        """缠中说禅分析类的初始化

        :param symbol: 交易标的代码
        :param freq: K线周期
        """
        self.bars_raw = []      # 存储原始K线序列
        self.bars_ubi = []      # 存储未完成笔的无包含K线序列
        self.bi_list: List[BI] = []  # 存储已完成的笔列表
        self.symbol = symbol    # 交易标的代码
        self.freq = freq        # K线周期

        # 遍历并处理每一根K线
        i = 0
        while i < len(bars):
            bar = bars[i]
            self.update(bar)  # 更新分析结果
            if self.check_bi_after:  # 如果需要检查笔之后的情况
                i = self.reset_bar_idx(bars)  # 重置K线索引
                self.check_bi_after = None

            i += 1

    def __repr__(self):
        """返回对象的字符串表示"""
        return "<CZSC for {}>".format(self.symbol)

    def update(self, bar: RawBar, replace_last=True):
        """更新分析结果

        :param bar: 新的K线数据
        :param replace_last: 是否替换最后一根K线，实时行情时为True
        """
        if replace_last:
            # 替换最后一根K线
            self.bars_raw[-1] = bar
            new_bar = NewBar(symbol=bar.symbol, freq=bar.freq, dt=bar.dt, open=bar.open, close=bar.close, high=bar.high, low=bar.low,
                             vol=bar.vol, elements=[bar])
            self.bars_ubi.append(new_bar)
        else:
            # 添加新的K线
            self.bars_raw.append(bar)
            new_bar = NewBar(symbol=bar.symbol, freq=bar.freq, dt=bar.dt, open=bar.open, close=bar.close, high=bar.high, low=bar.low,
                             vol=bar.vol, elements=[bar])
            self.bars_ubi.append(new_bar)

        # 如果还没有形成笔
        if not self.bi_list:
            # 至少需要7根K线才能形成笔
            if len(self.bars_ubi) < 7:
                return None

            # 寻找最高点和最低点
            fx = None
            low_idx = 0  # 最低点索引
            high_idx = 0  # 最高点索引
            for i in range(1, len(self.bars_ubi)):
                if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                    low_idx = i

                if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                    high_idx = i

            # 根据最高点和最低点的位置关系确定第一笔的方向
            if high_idx < low_idx:
                # 先高后低，优先找顶分型
                fx = find_fx(self.bars_ubi, high_idx, Mark.G)

                if not fx:
                    # 如果顶分型不成立，尝试找底分型
                    fx = find_fx(self.bars_ubi, low_idx, Mark.D)
            else:
                # 先低后高，优先找底分型
                fx = find_fx(self.bars_ubi, low_idx, Mark.D)

                if not fx:
                    # 如果底分型不成立，尝试找顶分型
                    fx = find_fx(self.bars_ubi, high_idx, Mark.G)

            # 如果找到分型，尝试构建第一笔
            if fx:
                # 找到分型对应的K线位置
                for i in range(0, len(self.bars_ubi)):
                    if self.bars_ubi[i].dt == fx.dt:
                        break

                # 检查是否能构成笔
                bi = check_bibi(self.bars_ubi[i:], fx)
                if isinstance(bi, BI):
                    self.bi_list.append(bi)  # 添加到笔列表
                    # 更新未完成笔的K线序列，移除已经使用的K线
                    self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]

            return

        # 尝试基于最后一笔的结束分型延伸新的笔
        bi = check_bibi(self.bars_ubi, self.bi_list[-1].fx_b)
        if bi:
            # 如果能够形成新的笔，更新数据
            self.bars_ubi = [x for x in self.bars_ubi if x.dt >= bi.fx_b.get_right_dt()]
            self.bi_list.append(bi)
            return

        # 处理特殊情况：当前K线序列的最值超过最后一笔的极值
        min_low_ubi = min(bar.low for bar in self.bars_ubi)  # 当前序列最低价
        max_high_ubi = max(bar.high for bar in self.bars_ubi)  # 当前序列最高价
        last_bi = self.bi_list[-1]  # 最后一笔

        # 处理向上笔的情况
        if last_bi.direction == Direction.Up and max_high_ubi >= last_bi.high:
            if min_low_ubi <= last_bi.low and len(self.bi_list) > 2:
                # 满足笔破坏条件，强制生成一笔
                bi = must_get_bibi(last_bi.fx_b, self.bars_ubi)
                self.bi_list.append(bi)
                self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
                self.check_bi_after = True
            else:
                # 移除最后一笔，重新计算
                self.bi_list.pop(-1)
                if len(self.bi_list) == 0:
                    self.bars_ubi = last_bi.bars + [x for x in self.bars_ubi if x.dt > last_bi.bars[-1].dt]
                    return

                self.bars_ubi = [x for x in last_bi.bars if self.bi_list[-1].fx_b.get_right_dt() < x.dt < self.bars_ubi[0].dt] + \
                                self.bars_ubi

        # 处理向下笔的情况
        elif last_bi.direction == Direction.Down and min_low_ubi <= last_bi.low:
            if max_high_ubi >= last_bi.high and len(self.bi_list) > 2:
                # 满足笔破坏条件，强制生成一笔
                bi = must_get_bibi(last_bi.fx_b, self.bars_ubi)
                self.bi_list.append(bi)
                self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
                self.check_bi_after = True
            else:
                # 移除最后一笔，重新计算
                self.bi_list.pop(-1)
                if len(self.bi_list) == 0:
                    self.bars_ubi = last_bi.bars + [x for x in self.bars_ubi if x.dt > last_bi.bars[-1].dt]
                    return

                self.bars_ubi = [x for x in last_bi.bars if self.bi_list[-1].fx_b.get_right_dt() < x.dt < self.bars_ubi[0].dt] + \
                                self.bars_ubi

    def reset_bar_idx(self, bars):
        """重置K线索引

        :param bars: K线列表
        :return: 新的索引位置
        """
        # 移除最后一笔之后的K线
        last_raw_bar_dt = self.bi_list[-1].bars[-1].dt
        while self.bars_raw[-1].dt > last_raw_bar_dt:
            self.bars_raw.pop(-1)
            self.bars_ubi.pop(-1)

        # 找到对应的K线位置
        for i in range(0, len(bars)):
            if bars[i].dt == last_raw_bar_dt:
                return i

    def bi_num(self, need_fake=False):
        """获取笔的数量

        :param need_fake: 是否包含虚笔
        :return: 笔的数量
        """
        if need_fake:
            return len(self.bi_list)
        else:
            if len(self.bi_list) == 0:
                return 0
            if self.bi_list[-1].is_fake():
                return len(self.bi_list) - 1
            else:
                return len(self.bi_list)

    def update_fake_bi(self):
        """更新虚笔标记"""
        if len(self.bi_list) <= 0 or len(self.bars_ubi) == 0:
            return

        # 获取最后一笔的结束分型
        fx_a = self.bi_list[-1].fx_b
        # 判断是否需要添加虚笔
        if (fx_a.mark == Mark.G and min(bar.low for bar in self.bars_ubi) < fx_a.low) or \
                (fx_a.mark == Mark.D and max(bar.high for bar in self.bars_ubi) > fx_a.high):
            # 强制生成一笔
            bi = must_get_bibi(fx_a, self.bars_ubi)
            bi.fx_b.set_not_complete()  # 标记为未完成
            self.bi_list.append(bi)

            # 寻找内部的极值点
            inner_idx = 0
            for i in range(1, len(self.bars_ubi)):
                if bi.is_up():
                    # 向上笔，寻找更高点
                    if self.bars_ubi[i].high >= self.bars_ubi[inner_idx].high:
                        inner_idx = i
                    else:
                        # 找到顶分型
                        fx_b = find_fx(self.bars_ubi, inner_idx, Mark.G)
                        if fx_b and fx_b.low > fx_a.high:
                            bi.has_complete_bi = True
                            break
                else:
                    # 向下笔，寻找更低点
                    if self.bars_ubi[i].low <= self.bars_ubi[inner_idx].low:
                        inner_idx = i
                    else:
                        # 找到底分型
                        fx_b = find_fx(self.bars_ubi, inner_idx, Mark.D)
                        if fx_b and fx_b.high < fx_a.low:
                            bi.has_complete_bi = True
                            break

    def to_echarts_1(self, file_name, width: str = "1400px", height: str = '580px'):
        """生成echarts K线图

        :param file_name: 输出文件名
        :param width: 图表宽度
        :param height: 图表高度
        """
        # 转换K线数据格式
        kline = [x.__dict__ for x in self.bars_raw]
        # 构建笔的数据
        if len(self.bi_list) > 0:
            bi = [{'dt': x.fx_a.dt, "bi": x.fx_a.fx} for x in self.bi_list] + \
                 [{'dt': self.bi_list[-1].fx_b.dt, "bi": self.bi_list[-1].fx_b.fx}]
        else:
            bi = None
        # 生成图表
        chart = kline_pro(kline, bi=bi, width=width, height=height, title="{}-{}".format(self.symbol, self.freq))
        file_html = os.path.join("/home/czsc/static", file_name)
        chart.render(file_html)  # 保存图表
