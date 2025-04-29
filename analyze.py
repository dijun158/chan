# coding: utf-8
"""
缠论分析系统主文件
包含缠论分析的核心算法和实现
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
    设置只显示强笔
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
            if left_low is not None and right_low is not None:
                if left_low < inner_low and right_low < inner_low:
                    return None  # 如果两侧都有更低的点，则不是有效的顶分型
                elif left_low < inner_low and not weak_left:
                    return None  # 如果左侧有更低的点且不允许弱分型，则无效
                elif right_low < inner_low and not weak_right:
                    return None  # 如果右侧有更低的点且不允许弱分型，则无效

            # 返回有效的顶分型对象
            return FX(symbol=inner_bar.symbol, dt=inner_bar.dt, mark=mark, high=inner_high, low=inner_low,
                     fx=inner_high, elements=bars[inner_left:inner_right + 1])
        else:  # 如果是底分型
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
            if left_high is not None and right_high is not None:
                if left_high > inner_high and right_high > inner_high:
                    return None  # 如果两侧都有更高的点，则不是有效的底分型
                elif left_high > inner_high and not weak_left:
                    return None  # 如果左侧有更高的点且不允许弱分型，则无效
                elif right_high > inner_high and not weak_right:
                    return None  # 如果右侧有更高的点且不允许弱分型，则无效

            # 返回有效的底分型对象
            return FX(symbol=inner_bar.symbol, dt=inner_bar.dt, mark=mark, high=inner_high, low=inner_low,
                     fx=inner_low, elements=bars[inner_left:inner_right + 1])


def find_inner_bis(bars: List[NewBar], direction, gap_num=3, pop_first=True):
    """
    查找内部笔的主函数
    :param bars: K线数据列表
    :param direction: 笔的方向（向上或向下）
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
    :param bars: K线数据列表
    :param fx_a: 分型对象
    :return: 是否满足笔的连续性条件
    """
    if len(bars) < 3:  # 如果K线数量不足3根
        return None  # 无法形成笔

    # 查找分型B的位置
    idx = 0
    for i in range(1, len(bars)):
        if (fx_a.mark == Mark.G and bars[i].low <= bars[idx].low) or (fx_a.mark == Mark.D and bars[i].high >= bars[idx].high):
            idx = i

    # 确定分型B的标记
    mark = Mark.G if fx_a.mark == Mark.D else Mark.D
    # 查找分型B
    fx_b = find_fx(bars, idx, mark)
    if fx_b is None:  # 如果找不到分型B
        return None  # 无法形成笔

    bar = bars[idx]  # 获取分型B所在的K线

    # 获取分型A的所有K线
    a = fx_a.get_all_bars()
    # 获取分型A和B之间的K线
    b = [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    # 合并所有K线
    bars_a = [x for x in fx_a.get_all_bars()] + [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    # 确定笔的方向
    direction = Direction.Up if fx_a.mark == Mark.D else Direction.Down
    # 确定笔的高低点
    high = fx_b.high if direction == Direction.Up else fx_a.high
    low = fx_a.low if direction == Direction.Up else fx_b.low
    # 创建笔对象
    bi = BI(symbol=bar.symbol, fx_a=fx_a, fx_b=fx_b, direction=direction, high=high, low=low, bars=bars_a)

    # 检查是否有独立的K线
    has_separate_k = len([x for x in bars if fx_a.get_right_dt() < x.dt < fx_b.get_left_dt()]) > 0
    # 检查是否满足笔的连续性条件
    if fx_a.high < fx_b.low or fx_a.low > fx_b.high and has_separate_k:
        return bi  # 返回有效的笔

    return None  # 返回无效的笔


def must_get_bibi(fx_a: FX, bars: List[NewBar]):
    """
    强制获取笔
    :param fx_a: 分型对象
    :param bars: K线数据列表
    :return: 笔对象
    """
    if len(bars) < 3:  # 如果K线数量不足3根
        return None  # 无法形成笔

    # 查找分型B的位置
    idx = 0
    for i in range(1, len(bars)):
        if (fx_a.mark == Mark.G and bars[i].low <= bars[idx].low) or (fx_a.mark == Mark.D and bars[i].high >= bars[idx].high):
            idx = i

    # 确定分型B的标记
    mark = Mark.G if fx_a.mark == Mark.D else Mark.D
    # 查找分型B
    fx_b = find_fx(bars, idx, mark)
    if fx_b is None:  # 如果找不到分型B
        return None  # 无法形成笔

    bar = bars[idx]  # 获取分型B所在的K线

    # 获取分型A的所有K线
    a = fx_a.get_all_bars()
    # 获取分型A和B之间的K线
    b = [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    # 合并所有K线
    bars_a = [x for x in fx_a.get_all_bars()] + [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    # 确定笔的方向
    direction = Direction.Up if fx_a.mark == Mark.D else Direction.Down
    # 确定笔的高低点
    high = fx_b.high if direction == Direction.Up else fx_a.high
    low = fx_a.low if direction == Direction.Up else fx_b.low
    # 创建笔对象
    bi = BI(symbol=bar.symbol, fx_a=fx_a, fx_b=fx_b, direction=direction, high=high, low=low, bars=bars_a)

    return bi  # 返回笔对象


class CZSC:
    """
    缠论分析系统主类
    用于实现缠论分析的核心功能
    """
    def __init__(self, bars: List[RawBar], freq: str, specified_start_left=None, specified_direction=None):
        """
        初始化缠论分析系统
        :param bars: K线数据列表
        :param freq: 时间周期
        :param specified_start_left: 指定的起始位置
        :param specified_direction: 指定的方向
        """
        self.bars_raw = []  # 原始K线序列
        self.bars_ubi = []  # 未完成笔的无包含K线序列
        self.bi_list: List[BI] = []  # 笔列表
        self.symbol = bars[0].symbol  # 交易品种代码
        self.freq = freq  # 时间周期
        self.specified_start_left = specified_start_left  # 指定的起始位置
        self.specified_direction = specified_direction  # 指定的方向
        self.check_bi_after = None  # 需要检查的时间点

        # 初始化处理所有K线
        i = 0
        while i < len(bars):
            bar = bars[i]  # 获取当前K线
            self.update(bar)  # 更新分析
            if self.check_bi_after:  # 如果需要检查
                i = self.reset_bar_idx(bars)  # 重置索引
                self.check_bi_after = None  # 清除检查标记
            i += 1  # 移动到下一个K线

    def __repr__(self):
        """
        返回对象的字符串表示
        :return: 字符串
        """
        return "<CZSC for {}>".format(self.symbol)  # 返回对象的字符串表示

    def update(self, bar: RawBar):
        """
        更新K线数据
        :param bar: 新的K线数据
        :return: None
        """
        # 添加新的K线到原始序列
        self.bars_raw.append(bar)
        # 创建新的无包含K线
        new_bar = NewBar(symbol=bar.symbol, freq=bar.freq, dt=bar.dt, open=bar.open, close=bar.close, high=bar.high, low=bar.low,
                         vol=bar.vol,
                         elements=[bar])
        # 添加到未完成笔序列
        self.bars_ubi.append(new_bar)

        # 处理第一个笔
        if not self.bi_list:
            if len(self.bars_ubi) < 6:  # 如果K线数量不足6根
                return None  # 无法形成笔

            fx = None  # 初始化分型
            # 处理指定的起始位置
            if self.specified_start_left and self.specified_start_left <= self.bars_ubi[-1].dt:
                if self.specified_direction == Direction.Up:  # 如果是向上笔
                    # 查找最低点和最高点
                    low_idx = 0
                    high_idx = 0
                    for i in range(1, len(self.bars_ubi)):
                        if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                            low_idx = i
                            high_idx = i

                        if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                            high_idx = i

                    if high_idx > low_idx:  # 如果最高点在最低点之后
                        fx = find_fx(self.bars_ubi, low_idx, Mark.D)  # 查找底分型
                else:  # 如果是向下笔
                    # 查找最高点和最低点
                    low_idx = 0
                    high_idx = 0
                    for i in range(1, len(self.bars_ubi)):
                        if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                            high_idx = i
                            low_idx = i

                        if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                            low_idx = i

                    if low_idx > high_idx:  # 如果最低点在最高点之后
                        fx = find_fx(self.bars_ubi, high_idx, Mark.G)  # 查找顶分型
            else:  # 如果没有指定起始位置
                # 查找最高点和最低点
                low_idx = 0
                high_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                        low_idx = i

                    if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                        high_idx = i

                # 确定分型类型
                if high_idx < low_idx:  # 如果最高点在最低点之前
                    fx = find_fx(self.bars_ubi, high_idx, Mark.G)  # 查找顶分型

                    if not fx:  # 如果找不到顶分型
                        fx = find_fx(self.bars_ubi, low_idx, Mark.D)  # 查找底分型
                else:  # 如果最低点在最高点之前
                    fx = find_fx(self.bars_ubi, low_idx, Mark.D)  # 查找底分型

                    if not fx:  # 如果找不到底分型
                        fx = find_fx(self.bars_ubi, high_idx, Mark.G)  # 查找顶分型

            # 处理找到的分型
            if fx:
                # 查找分型在K线序列中的位置
                for i in range(0, len(self.bars_ubi)):
                    if self.bars_ubi[i].dt == fx.dt:
                        break

                # 检查笔的连续性
                bi = check_bibi(self.bars_ubi[i:], fx)
                if isinstance(bi, BI):  # 如果是有效的笔
                    self.bi_list.append(bi)  # 添加到笔列表
                    # 更新未完成笔序列
                    self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]

            return

        # 处理后续的笔
        bi = check_bibi(self.bars_ubi, self.bi_list[-1].fx_b)
        if bi:  # 如果找到新的笔
            # 更新未完成笔序列
            self.bars_ubi = [x for x in self.bars_ubi if x.dt >= bi.fx_b.get_right_dt()]
            self.bi_list.append(bi)  # 添加到笔列表
            return

        # 获取当前未完成笔序列的最高点和最低点
        min_low_ubi = min(bar.low for bar in self.bars_ubi)
        max_high_ubi = max(bar.high for bar in self.bars_ubi)
        last_bi = self.bi_list[-1]  # 获取最后一个笔

        # 处理向上笔的延伸
        if last_bi.direction == Direction.Up and max_high_ubi >= last_bi.high:
            if min_low_ubi <= last_bi.low and len(self.bi_list) > 2:  # 如果满足条件
                bi = must_get_bibi(last_bi.fx_b, self.bars_ubi)  # 强制获取笔
                self.bi_list.append(bi)  # 添加到笔列表
                # 更新未完成笔序列
                self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
                self.check_bi_after = True  # 设置检查标记
            else:  # 如果不满足条件
                self.bi_list.pop(-1)  # 删除最后一个笔
                if len(self.bi_list) == 0:  # 如果笔列表为空
                    # 重置未完成笔序列
                    self.bars_ubi = last_bi.bars + [x for x in self.bars_ubi if x.dt > last_bi.bars[-1].dt]
                    return

                # 更新未完成笔序列
                self.bars_ubi = [x for x in last_bi.bars if self.bi_list[-1].fx_b.get_right_dt() < x.dt < self.bars_ubi[0].dt] + \
                                self.bars_ubi
        # 处理向下笔的延伸
        elif last_bi.direction == Direction.Down and min_low_ubi <= last_bi.low:
            if max_high_ubi >= last_bi.high and len(self.bi_list) > 2:  # 如果满足条件
                bi = must_get_bibi(last_bi.fx_b, self.bars_ubi)  # 强制获取笔
                self.bi_list.append(bi)  # 添加到笔列表
                # 更新未完成笔序列
                self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
                self.check_bi_after = True  # 设置检查标记
            else:  # 如果不满足条件
                self.bi_list.pop(-1)  # 删除最后一个笔
                if len(self.bi_list) == 0:  # 如果笔列表为空
                    # 重置未完成笔序列
                    self.bars_ubi = last_bi.bars + [x for x in self.bars_ubi if x.dt > last_bi.bars[-1].dt]
                    return

                # 更新未完成笔序列
                self.bars_ubi = [x for x in last_bi.bars if self.bi_list[-1].fx_b.get_right_dt() < x.dt < self.bars_ubi[0].dt] + \
                                self.bars_ubi

    def reset_bar_idx(self, bars):
        """
        重置K线索引
        :param bars: K线数据列表
        :return: 索引位置
        """
        # 获取最后一个笔的最后K线时间
        last_raw_bar_dt = self.bi_list[-1].bars[-1].dt
        # 删除超过时间的K线
        while self.bars_raw[-1].dt > last_raw_bar_dt:
            self.bars_raw.pop(-1)
            self.bars_ubi.pop(-1)

        # 查找对应的索引位置
        for i in range(0, len(bars)):
            if bars[i].dt == last_raw_bar_dt:
                return i

    def bi_num(self, need_fake=False):
        """
        获取笔的数量
        :param need_fake: 是否包含假笔
        :return: 笔的数量
        """
        if need_fake:  # 如果需要包含假笔
            return len(self.bi_list)  # 返回所有笔的数量
        else:  # 如果不需要包含假笔
            if len(self.bi_list) == 0:  # 如果没有笔
                return 0  # 返回0
            if self.bi_list[-1].is_fake():  # 如果最后一个笔是假笔
                return len(self.bi_list) - 1  # 返回真实笔的数量
            else:  # 如果最后一个笔不是假笔
                return len(self.bi_list)  # 返回所有笔的数量

    def update_fake_bi(self):
        """
        更新假笔
        :return: None
        """
        if len(self.bi_list) <= 0 or len(self.bars_ubi) == 0:  # 如果没有笔或没有未完成K线
            return  # 直接返回

        fx_a = self.bi_list[-1].fx_b  # 获取最后一个笔的分型B
        # 检查是否需要更新假笔
        if (fx_a.mark == Mark.G and min(bar.low for bar in self.bars_ubi) < fx_a.low) or \
                (fx_a.mark == Mark.D and max(bar.high for bar in self.bars_ubi) > fx_a.high):
            # 强制获取笔
            bi = must_get_bibi(fx_a, self.bars_ubi)
            bi.fx_b.set_not_complete()  # 标记为未完成
            self.bi_list.append(bi)  # 添加到笔列表

            # 检查笔是否完成
            inner_idx = 0
            for i in range(1, len(self.bars_ubi)):
                if bi.is_up():  # 如果是向上笔
                    if self.bars_ubi[i].high >= self.bars_ubi[inner_idx].high:
                        inner_idx = i
                    else:
                        fx_b = find_fx(self.bars_ubi, inner_idx, Mark.G)
                        if fx_b and fx_b.low > fx_a.high:
                            bi.has_complete_bi = True
                            break
                else:  # 如果是向下笔
                    if self.bars_ubi[i].low <= self.bars_ubi[inner_idx].low:
                        inner_idx = i
                    else:
                        fx_b = find_fx(self.bars_ubi, inner_idx, Mark.D)
                        if fx_b and fx_b.high < fx_a.low:
                            bi.has_complete_bi = True
                            break

    def to_echarts_1(self, file_name, width: str = "1400px", height: str = '580px'):
        """
        生成ECharts图表
        :param file_name: 文件名
        :param width: 图表宽度
        :param height: 图表高度
        :return: None
        """
        # 准备K线数据
        kline = [x.__dict__ for x in self.bars_raw]
        # 准备笔数据
        if len(self.bi_list) > 0:
            bi = [{'dt': x.fx_a.dt, "bi": x.fx_a.fx} for x in self.bi_list] + \
                 [{'dt': self.bi_list[-1].fx_b.dt, "bi": self.bi_list[-1].fx_b.fx}]
        else:
            bi = None
        # 创建图表
        chart = kline_pro(kline, bi=bi, width=width, height=height, title="{}-{}".format(self.symbol, self.freq))
        # 设置文件路径
        file_html = os.path.join("/home/czsc/static", file_name)
        # 渲染图表
        chart.render(file_html)
