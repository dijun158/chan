# coding: utf-8
"""
缠论分析系统主文件
包含缠论分析的核心算法和实现
"""

# 导入必要的模块和类
import os  # 导入操作系统相关功能
from typing import List, Optional  # 导入类型提示功能
from .objects import Mark, Direction, BI, FX, RawBar, NewBar, InnerBI  # 导入自定义对象类
from .utils.echarts_plot import kline_pro  # 导入K线图绘制工具
from czsc.enum import BiReason  # 导入笔的原因枚举
from datetime import timedelta, datetime  # 导入日期时间处理模块
from copy import deepcopy  # 导入深拷贝功能
from .zoushi import get_zoushis  # 导入走势分析功能

# 全局变量定义
inner_can_be_bi = {}  # 存储内部笔的缓存，用于优化性能
show_inner = False    # 控制是否显示内部笔的标记
check_one_min_after = None  # 记录需要在一分钟后检查的时间点
today = datetime.now()  # 记录当前系统时间
only_qiangbi = False   # 控制是否只显示强笔


def copy_newbar(bar):
    """
    复制K线对象
    :param bar: 原始K线对象
    :return: 新的K线对象
    """
    newbar = deepcopy(bar)  # 深拷贝K线对象
    newbar.elements = [bar]  # 设置元素列表
    return newbar  # 返回新的K线对象


def set_only_qiangbi():
    """
    设置只显示强笔
    :return: None
    """
    global only_qiangbi  # 声明使用全局变量
    only_qiangbi = True  # 将全局变量设置为True


def merge(bars, target_bar, mark, to_left, idx):
    """
    合并K线
    :param bars: K线列表
    :param target_bar: 目标K线
    :param mark: 分型标记
    :param to_left: 是否向左合并
    :param idx: 当前索引
    :return: 合并后的索引
    """
    i = None  # 初始化索引
    if to_left:  # 如果向左合并
        for i in range(idx, -1, -1):  # 从当前索引向左遍历
            if mark == Mark.G and target_bar.low < bars[i].low:  # 如果是顶分型且目标K线低点更低
                target_bar.low = bars[i].low  # 更新低点
                target_bar.elements.insert(0, bars[i])  # 在开头插入K线
            elif mark == Mark.D and target_bar.high > bars[i].high:  # 如果是底分型且目标K线高点更高
                target_bar.high = bars[i].high  # 更新高点
                target_bar.elements.insert(0, bars[i])  # 在开头插入K线
            else:  # 如果不满足合并条件
                break  # 退出循环
    else:  # 如果向右合并
        for i in range(idx, len(bars)):  # 从当前索引向右遍历
            if mark == Mark.G and target_bar.low < bars[i].low:  # 如果是顶分型且目标K线低点更低
                target_bar.low = bars[i].low  # 更新低点
                target_bar.elements.append(bars[i])  # 在末尾添加K线
            elif mark == Mark.D and target_bar.high > bars[i].high:  # 如果是底分型且目标K线高点更高
                target_bar.high = bars[i].high  # 更新高点
                target_bar.elements.append(bars[i])  # 在末尾添加K线
            else:  # 如果不满足合并条件
                break  # 退出循环

    return i  # 返回合并后的索引


def find_inner_bis(bars: List[NewBar], direction: Direction):
    """
    查找内部笔
    :param bars: K线列表
    :param direction: 方向
    :return: 内部笔列表
    """
    # 如果K线数量不足，返回空列表
    if len(bars) < 3:
        return []

    # 初始化变量
    inner_bis = []  # 内部笔列表
    inner_bars = []  # 内部K线列表
    inner_mark = Mark.G if direction == Direction.Up else Mark.D  # 根据方向确定标记类型

    # 遍历K线
    for bar in bars:
        # 添加K线到内部K线列表
        inner_bars.append(bar)

        # 如果内部K线数量不足3根，继续循环
        if len(inner_bars) < 3:
            continue

        # 查找分型
        fx = find_fx(inner_bars, len(inner_bars) - 1, inner_mark)
        if not fx:  # 如果没有找到分型，继续循环
            continue

        # 如果找到分型，创建内部笔
        if not inner_bis:  # 如果是第一笔
            inner_bis.append(BI(symbol=bar.symbol, freq=bar.freq, mark=inner_mark,
                              high=max(bar.high for bar in inner_bars),
                              low=min(bar.low for bar in inner_bars),
                              fx_a=fx, fx_b=None, elements=inner_bars))
        else:  # 如果不是第一笔
            # 检查是否满足笔笔关系
            if check_bibi(inner_bars, inner_bis, inner_mark, [fx]):
                # 创建新的内部笔
                inner_bis.append(BI(symbol=bar.symbol, freq=bar.freq, mark=inner_mark,
                                  high=max(bar.high for bar in inner_bars),
                                  low=min(bar.low for bar in inner_bars),
                                  fx_a=fx, fx_b=None, elements=inner_bars))

        # 更新内部K线列表和标记类型
        inner_bars = [bar]  # 重置内部K线列表
        inner_mark = Mark.G if inner_mark == Mark.D else Mark.D  # 切换标记类型

    return inner_bis  # 返回内部笔列表


def be_duan(bis: List[BI]):
    """
    判断是否构成段
    :param bis: 笔列表
    :return: 是否构成段
    """
    # 如果笔的数量不足3个，返回False
    if len(bis) < 3:
        return False

    # 获取最后三笔的信息
    last_bi = bis[-1]  # 最后一笔
    last_2_bi = bis[-2]  # 倒数第二笔
    last_3_bi = bis[-3]  # 倒数第三笔

    # 判断是否构成段
    if last_bi.direction == Direction.Up:  # 如果最后一笔是向上的
        # 检查是否满足向上段的条件
        if last_2_bi.low < last_3_bi.low and last_bi.high > last_3_bi.high:
            return True
    else:  # 如果最后一笔是向下的
        # 检查是否满足向下段的条件
        if last_2_bi.high > last_3_bi.high and last_bi.low < last_3_bi.low:
            return True

    return False  # 不满足段的条件，返回False


def find_fx(bars: List[NewBar], idx: int, mark: Mark) -> Optional[FX]:
    """查找分型

    :param bars: K线序列
    :param idx: 中心点索引
    :param mark: 分型标记，G为顶分型，D为底分型
    :return: 分型对象
    """
    if len(bars) < 3:
        return None

    # 顶分型的条件
    if mark == Mark.G:
        # 中心点必须是最高点
        if bars[idx].high <= bars[idx-1].high or bars[idx].high <= bars[idx+1].high:
            return None

        # 构建顶分型对象
        fx = FX(mark=mark, dt=bars[idx].dt, fx=bars[idx].high,
                high=bars[idx].high, low=min(bars[idx-1].low, bars[idx+1].low),
                bars=[bars[idx-1], bars[idx], bars[idx+1]])
        return fx

    # 底分型的条件
    elif mark == Mark.D:
        # 中心点必须是最低点
        if bars[idx].low >= bars[idx-1].low or bars[idx].low >= bars[idx+1].low:
            return None

        # 构建底分型对象
        fx = FX(mark=mark, dt=bars[idx].dt, fx=bars[idx].low,
                high=max(bars[idx-1].high, bars[idx+1].high), low=bars[idx].low,
                bars=[bars[idx-1], bars[idx], bars[idx+1]])
        return fx

    return None


def find_fx1(bars: List[NewBar], inner_idx, mark, use_weak_fx=False):
    inner_bar = copy_newbar(bars[inner_idx])
    left_idx = merge(bars, inner_bar, mark, True, inner_idx - 1)
    right_idx = merge(bars, inner_bar, mark, False, inner_idx + 1)

    if left_idx is None or right_idx is None:
        return None

    left_bar = None
    right_bar = None

    while True:
        if left_bar is None:
            if left_idx >= 0:
                left_bar = copy_newbar(bars[left_idx])
                left_idx -= 1
                if left_idx >= 0:
                    left_idx = merge(bars, left_bar, mark, True, left_idx)
            else:
                break

        if right_bar is None:
            if right_idx <= len(bars) - 1:
                right_bar = copy_newbar(bars[right_idx])
                right_idx += 1
                if right_idx <= len(bars) - 1:
                    right_idx = merge(bars, right_bar, mark, False, right_idx)
            else:
                break

        if mark == Mark.G:
            if inner_bar.low <= left_bar.low:
                inner_bar.low = left_bar.low
                inner_bar.elements = left_bar.elements + inner_bar.elements
                left_bar = None
            if inner_bar.low <= right_bar.low:
                inner_bar.low = right_bar.low
                inner_bar.elements += right_bar.elements
                right_bar = None
        else:
            if inner_bar.high >= left_bar.high:
                inner_bar.high = left_bar.high
                inner_bar.elements = left_bar.elements + inner_bar.elements
                left_bar = None
            if inner_bar.high >= right_bar.high:
                inner_bar.high = right_bar.high
                inner_bar.elements += right_bar.elements
                right_bar = None

        if left_bar and right_bar:
            bar = bars[inner_idx]
            if mark == Mark.G:
                high = bar.high
                low = min(left_bar.low, right_bar.low)
                fx = high
            else:
                high = max(left_bar.high, right_bar.high)
                low = bar.low
                fx = low

            return FX(symbol=bar.symbol, dt=bar.dt, mark=mark, high=high, low=low, fx=fx,
                      elements=[left_bar, inner_bar, right_bar])

    if use_weak_fx:
        bar = bars[inner_idx]
        fx = inner_bar.high if mark == Mark.G else inner_bar.low
        return FX(symbol=bar.symbol, dt=bar.dt, mark=mark, high=inner_bar.high, low=inner_bar.low, fx=fx,
                  elements=[inner_bar])

    return None


def check_bibi(bars: List[NewBar], bis: List[BI], mark, bi_points: List[FX], weak_left=False, weak_right=False):
    """
    检查笔笔关系
    :param bars: K线列表
    :param bis: 已有的笔列表
    :param mark: 分型标记
    :param bi_points: 笔的端点列表
    :param weak_left: 是否允许左侧弱分型
    :param weak_right: 是否允许右侧弱分型
    :return: 是否满足笔笔关系
    """
    # 如果没有已有的笔，直接返回True
    if not bis:
        return True

    # 获取最后一笔的信息
    last_bi = bis[-1]  # 最后一笔
    last_mark = last_bi.mark  # 最后一笔的标记
    last_high = last_bi.high  # 最后一笔的最高价
    last_low = last_bi.low  # 最后一笔的最低价

    # 检查笔笔关系
    if mark == Mark.G:  # 如果当前是顶分型
        # 如果最后一笔是顶分型，不满足笔笔关系
        if last_mark == Mark.G:
            return False
        # 如果最后一笔是底分型，检查当前笔的高点是否高于最后一笔的高点
        if last_mark == Mark.D:
            if last_high >= max(bar.high for bar in bars):
                return False
    else:  # 如果当前是底分型
        # 如果最后一笔是底分型，不满足笔笔关系
        if last_mark == Mark.D:
            return False
        # 如果最后一笔是顶分型，检查当前笔的低点是否低于最后一笔的低点
        if last_mark == Mark.G:
            if last_low <= min(bar.low for bar in bars):
                return False

    # 检查是否满足笔的条件
    fx = find_fx(bars, len(bars) - 1, mark, weak_left=weak_left, weak_right=weak_right)  # 查找分型
    if not fx:  # 如果没有找到分型，返回False
        return False

    # 检查分型是否已经存在于笔的端点列表中
    if fx in bi_points:  # 如果分型已存在，返回False
        return False

    return True  # 满足所有条件，返回True


def must_get_bibi(bars: List[NewBar], bis: List[BI], mark, bi_points: List[FX], weak_left=False, weak_right=False):
    """
    强制获取笔笔关系
    :param bars: K线列表
    :param bis: 已有的笔列表
    :param mark: 分型标记
    :param bi_points: 笔的端点列表
    :param weak_left: 是否允许左侧弱分型
    :param weak_right: 是否允许右侧弱分型
    :return: 笔对象
    """
    # 如果没有已有的笔，直接返回None
    if not bis:
        return None

    # 获取最后一笔的信息
    last_bi = bis[-1]  # 最后一笔
    last_mark = last_bi.mark  # 最后一笔的标记
    last_high = last_bi.high  # 最后一笔的最高价
    last_low = last_bi.low  # 最后一笔的最低价

    # 检查笔笔关系
    if mark == Mark.G:  # 如果当前是顶分型
        # 如果最后一笔是顶分型，不满足笔笔关系
        if last_mark == Mark.G:
            return None
        # 如果最后一笔是底分型，检查当前笔的高点是否高于最后一笔的高点
        if last_mark == Mark.D:
            if last_high >= max(bar.high for bar in bars):
                return None
    else:  # 如果当前是底分型
        # 如果最后一笔是底分型，不满足笔笔关系
        if last_mark == Mark.D:
            return None
        # 如果最后一笔是顶分型，检查当前笔的低点是否低于最后一笔的低点
        if last_mark == Mark.G:
            if last_low <= min(bar.low for bar in bars):
                return None

    # 查找分型
    fx = find_fx(bars, len(bars) - 1, mark, weak_left=weak_left, weak_right=weak_right)
    if not fx:  # 如果没有找到分型，返回None
        return None

    # 检查分型是否已经存在于笔的端点列表中
    if fx in bi_points:  # 如果分型已存在，返回None
        return None

    # 创建并返回笔对象
    return BI(symbol=bars[0].symbol, freq=bars[0].freq, mark=mark, high=max(bar.high for bar in bars),
              low=min(bar.low for bar in bars), fx_a=bi_points[-1], fx_b=fx, elements=bars)


class CZSC:
    def __init__(self, bars: List[RawBar], freq: str, specified_start_left=None, specified_direction=None):
        """

        :param bars: K线数据
        :param freq: K线级别
        :param max_bi_count: 最大保存的笔数量
            默认值为 30，仅使用内置的信号和因子，不需要调整这个参数。
            如果进行新的信号计算需要用到更多的笔，可以适当调大这个参数。
        """
        self.bars_raw = []  # 原始K线序列
        self.bars_ubi = []  # 未完成笔的无包含K线序列
        self.bi_list: List[BI] = []
        self.symbol = bars[0].symbol
        self.freq = freq
        self.specified_start_left = specified_start_left
        self.specified_direction = specified_direction
        self.check_bi_after = None

        i = 0
        while i < len(bars):
            # print(i)
            bar = bars[i]
            self.update(bar)
            if self.check_bi_after:
                i = self.reset_bar_idx(bars)
                self.check_bi_after = None

            if False and len(self.bars_raw) > 40 and len(self.bars_raw) % 10 == 0:
                file_name = '%s-%s-%s-%d.html' % (self.symbol[:6], freq, datetime.now().strftime("%Y%m%d-%H%M"), len(self.bars_raw))
                url = "http://81.69.252.8:32000/chart?name=%s" % file_name
                self.to_echarts_1(file_name)
                print(url)

            i += 1

    def __repr__(self):
        return "<CZSC for {}>".format(self.symbol)

    def update(self, bar: RawBar):
        self.bars_raw.append(bar)
        new_bar = NewBar(symbol=bar.symbol, freq=bar.freq, dt=bar.dt, open=bar.open, close=bar.close, high=bar.high, low=bar.low,
                         vol=bar.vol, elements=[bar])
        self.bars_ubi.append(new_bar)

        if not self.bi_list:
            if len(self.bars_ubi) < 7:
                return None

            fx = None
            if self.specified_start_left and self.specified_start_left <= self.bars_ubi[-1].dt:
                if self.specified_direction == Direction.Up:
                    low_idx = 0
                    high_idx = 0
                    for i in range(1, len(self.bars_ubi)):
                        if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                            low_idx = i
                            high_idx = i

                        if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                            high_idx = i

                    if high_idx > low_idx:
                        fx = find_fx(self.bars_ubi, low_idx, Mark.D)
                else:
                    low_idx = 0
                    high_idx = 0
                    for i in range(1, len(self.bars_ubi)):
                        if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                            high_idx = i
                            low_idx = i

                        if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                            low_idx = i

                    if low_idx > high_idx:
                        fx = find_fx(self.bars_ubi, high_idx, Mark.G)
            else:
                low_idx = 0
                high_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                        low_idx = i

                    if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                        high_idx = i

                if high_idx < low_idx:
                    fx = find_fx(self.bars_ubi, high_idx, Mark.G)

                    if not fx:
                        fx = find_fx(self.bars_ubi, low_idx, Mark.D)
                else:
                    fx = find_fx(self.bars_ubi, low_idx, Mark.D)

                    if not fx:
                        fx = find_fx(self.bars_ubi, high_idx, Mark.G)

            if fx:
                for i in range(0, len(self.bars_ubi)):
                    if self.bars_ubi[i].dt == fx.dt:
                        break

                bi = check_bibi(self.bars_ubi[i:], self.bi_list, fx.mark, [fx], weak_left=False, weak_right=False)
                if isinstance(bi, BI):
                    self.bi_list.append(bi)
                    self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]

            return

        zoushis = get_zoushis(self)
        last_zhongshu = None
        if len(zoushis) > 0:
            last_zoushi = zoushis[-1]
            if len(last_zoushi.zhongshus) > 0:
                last_zhongshu = last_zoushi.zhongshus[-1]

        bi = check_bibi(self.bars_ubi, self.bi_list, self.bi_list[-1].fx_b.mark, [x for x in self.bi_list[-1].fx_b.get_all_bars()], weak_left=False, weak_right=False)
        if bi:
            self.bars_ubi = [x for x in self.bars_ubi if x.dt >= bi.fx_b.get_right_dt()]
            self.bi_list.append(bi)
            return

        min_low_ubi = min(bar.low for bar in self.bars_ubi)
        max_high_ubi = max(bar.high for bar in self.bars_ubi)
        last_bi = self.bi_list[-1]
        if last_bi.direction == Direction.Up and max_high_ubi >= last_bi.high:
            if min_low_ubi <= last_bi.low and len(self.bi_list) > 2:
                bi = must_get_bibi(self.bars_ubi, self.bi_list, self.bi_list[-1].fx_b.mark, [x for x in self.bi_list[-1].fx_b.get_all_bars()], weak_left=False, weak_right=False)
                self.bi_list.append(bi)
                self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
                self.check_bi_after = True
            else:
                self.bi_list.pop(-1)
                if len(self.bi_list) == 0:
                    self.bars_ubi = last_bi.bars + [x for x in self.bars_ubi if x.dt > last_bi.bars[-1].dt]
                    return

                self.bars_ubi = [x for x in last_bi.bars if self.bi_list[-1].fx_b.get_right_dt() < x.dt < self.bars_ubi[0].dt] + \
                                self.bars_ubi
        elif last_bi.direction == Direction.Down and min_low_ubi <= last_bi.low:
            if max_high_ubi >= last_bi.high and len(self.bi_list) > 2:
                bi = must_get_bibi(self.bars_ubi, self.bi_list, self.bi_list[-1].fx_b.mark, [x for x in self.bi_list[-1].fx_b.get_all_bars()], weak_left=False, weak_right=False)
                self.bi_list.append(bi)
                self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
                self.check_bi_after = True
            else:
                self.bi_list.pop(-1)
                if len(self.bi_list) == 0:
                    self.bars_ubi = last_bi.bars + [x for x in self.bars_ubi if x.dt > last_bi.bars[-1].dt]
                    return

                self.bars_ubi = [x for x in last_bi.bars if self.bi_list[-1].fx_b.get_right_dt() < x.dt < self.bars_ubi[0].dt] + \
                                self.bars_ubi

    def reset_bar_idx(self, bars):
        last_raw_bar_dt = self.bi_list[-1].bars[-1].dt
        while self.bars_raw[-1].dt > last_raw_bar_dt:
            self.bars_raw.pop(-1)
            self.bars_ubi.pop(-1)

        for i in range(0, len(bars)):
            if bars[i].dt == last_raw_bar_dt:
                return i

    def bi_num(self, need_fake=False):
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
        if len(self.bars_ubi) == 0:
            return

        bi = None
        if self.bi_num() > 0:
            fx_a = self.bi_list[-1].fx_b
            if (fx_a.mark == Mark.G and min(bar.low for bar in self.bars_ubi) < fx_a.low) or \
                    (fx_a.mark == Mark.D and max(bar.high for bar in self.bars_ubi) > fx_a.high):
                bi = must_get_bibi(self.bars_ubi, self.bi_list, fx_a.mark, [x for x in fx_a.get_all_bars()], weak_left=False, weak_right=False)
        elif self.specified_start_left and self.specified_start_left <= self.bars_ubi[-1].dt:
            if self.specified_direction == Direction.Up:
                low_idx = 0
                high_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                        low_idx = i
                        high_idx = i

                    if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                        high_idx = i

                if high_idx > low_idx:
                    fx_a = find_fx(self.bars_ubi, low_idx, Mark.D)
                    if fx_a:
                        fx_b = find_fx(self.bars_ubi, high_idx, Mark.G, weak_right=True)
                        if fx_b:
                            bi = BI(symbol=self.symbol, fx_a=fx_a, fx_b=fx_b, direction=Direction.Up, high=fx_b.high, low=fx_a.low,
                                    bars=self.bars_ubi)
            else:
                low_idx = 0
                high_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                        high_idx = i
                        low_idx = i

                    if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                        low_idx = i

                if low_idx > high_idx:
                    fx_a = find_fx(self.bars_ubi, high_idx, Mark.G)
                    if fx_a:
                        fx_b = find_fx(self.bars_ubi, low_idx, Mark.D, weak_right=True)
                        if fx_b:
                            bi = BI(symbol=self.symbol, fx_a=fx_a, fx_b=fx_b, direction=Direction.Down, high=fx_a.high, low=fx_b.low,
                                    bars=self.bars_ubi)
        if bi:
            bi.fx_b.set_not_complete()

            inner_idx = 0
            for i in range(1, len(self.bars_ubi)):
                if bi.is_up():
                    if self.bars_ubi[i].high >= self.bars_ubi[inner_idx].high:
                        inner_idx = i
                    else:
                        fx = find_fx(self.bars_ubi, inner_idx, Mark.G)
                        if fx and fx.low > bi.fx_a.high:
                            bi.has_complete_bi = True
                            break
                else:
                    if self.bars_ubi[i].low <= self.bars_ubi[inner_idx].low:
                        inner_idx = i
                    else:
                        fx = find_fx(self.bars_ubi, inner_idx, Mark.D)
                        if fx and fx.high < bi.fx_a.low:
                            bi.has_complete_bi = True
                            break

            self.bi_list.append(bi)

    def to_echarts_1(self, file_name, width: str = "1400px", height: str = '580px'):
        kline = [x.__dict__ for x in self.bars_raw]
        if len(self.bi_list) > 0:
            bi = [{'dt': x.fx_a.dt, "bi": x.fx_a.fx} for x in self.bi_list] + \
                 [{'dt': self.bi_list[-1].fx_b.dt, "bi": self.bi_list[-1].fx_b.fx}]
        else:
            bi = None
        chart = kline_pro(kline, bi=bi, width=width, height=height, title="{}-{}".format(self.symbol, self.freq))
        file_html = os.path.join("/home/czsc/static", file_name)
        chart.render(file_html)

def find_bi_points(bars: List[NewBar], fx_a: FX) -> List[BI]:
    """寻找从起始分型开始的所有笔
    
    从给定的起始分型开始，在K线序列中寻找所有可能的笔。
    笔的生成遵循缠论的标准定义，包括分型交替、价格关系等规则。

    :param bars: K线序列
    :param fx_a: 起始分型
    :return: 笔列表，按时间顺序排列
    """
    # 存储找到的所有笔
    bis = []
    # 当前处理的K线序列
    cur_bars = bars
    # 当前的起始分型
    cur_fx_a = fx_a

    while True:
        # 尝试从当前位置找到一笔
        bi = check_bibi(cur_bars, cur_fx_a)
        if not bi:
            # 如果无法找到标准的笔，且已有笔被找到，则强制生成最后一笔
            if bis:
                bi = must_get_bibi(cur_fx_a, cur_bars)
                bis.append(bi)
            break

        # 将找到的笔添加到列表中
        bis.append(bi)
        # 更新下一轮搜索的起始位置
        cur_bars = [x for x in cur_bars if x.dt > bi.fx_b.bars[-1].dt]
        cur_fx_a = bi.fx_b
        
        # 如果剩余K线不足，结束搜索
        if len(cur_bars) < 4:
            break

    return bis

def find_inner_bis(bars: List[NewBar]) -> List[BI]:
    """在K线序列中寻找所有内部笔
    
    从K线序列的开始到结束，寻找所有符合缠论定义的笔。
    这个函数会首先寻找第一个有效的分型，然后从该分型开始寻找所有笔。

    :param bars: K线序列
    :return: 所有找到的笔的列表
    """
    if len(bars) < 3:
        return []

    # 寻找第一个分型
    fx_a = None
    # 从第二个K线开始检查，因为分型至少需要3根K线
    for i in range(1, len(bars)-1):
        # 优先尝试找底分型
        fx = find_fx(bars[:i+2], i, Mark.D)
        if fx:
            fx_a = fx
            break
        # 如果找不到底分型，尝试找顶分型
        fx = find_fx(bars[:i+2], i, Mark.G)
        if fx:
            fx_a = fx
            break

    # 如果找不到起始分型，返回空列表
    if not fx_a:
        return []

    # 从找到的第一个分型开始寻找所有笔
    bars_after_fx = [x for x in bars if x.dt >= fx_a.bars[0].dt]
    return find_bi_points(bars_after_fx, fx_a)

def find_duan_points(bis: List[BI]) -> List[FD]:
    """在一组笔中寻找所有段
    
    根据缠论定义，从一组笔中识别出所有的段。段是比笔更大的结构，
    需要满足特定的价格关系和分型关系。

    :param bis: 笔的列表
    :return: 段的列表
    """
    # 如果笔的数量不足，无法构成段
    if len(bis) < 2:
        return []

    # 存储找到的所有段
    fds = []
    # 当前处理的笔序列
    cur_bis = bis
    # 当前段的起始笔
    cur_bi_a = bis[0]

    while True:
        # 尝试从当前位置找到一段
        fd = be_duan(cur_bis, cur_bi_a)
        if not fd:
            break

        # 将找到的段添加到列表中
        fds.append(fd)
        # 更新下一轮搜索的起始位置
        cur_bis = [x for x in cur_bis if x.fx_b.dt > fd.bi_b.fx_b.dt]
        if not cur_bis:
            break
        cur_bi_a = cur_bis[0]

    return fds

def find_duans(bis: List[BI]) -> List[FD]:
    """寻找所有段
    
    这是一个包装函数，用于在一组笔中寻找所有可能的段。
    它会处理一些边界情况，并确保返回的段满足缠论的要求。

    :param bis: 笔的列表
    :return: 所有找到的段的列表
    """
    if len(bis) < 4:
        return []

    # 寻找第一个有效的起始笔
    bi_a = None
    # 从第一笔开始检查
    for i in range(len(bis)-2):
        # 检查是否可以构成段
        fd = be_duan(bis[i:], bis[i])
        if fd:
            bi_a = bis[i]
            break

    if not bi_a:
        return []

    # 从找到的第一个有效笔开始寻找所有段
    bis_after = [x for x in bis if x.fx_a.dt >= bi_a.fx_a.dt]
    return find_duan_points(bis_after)

def check_standard_bi(bars: List[RawBar], bi: BI) -> bool:
    """检查一笔是否是标准笔
    
    标准笔需要满足以下条件：
    1. 笔的方向必须明确（向上或向下）
    2. 笔中的K线数量必须满足最小要求
    3. 笔的高低点必须符合缠论的要求

    :param bars: K线列表
    :param bi: 待检查的笔
    :return: 是否为标准笔
    """
    # 获取笔中包含的所有K线
    bars_in_bi = [x for x in bars if bi.fx_a.bars[0].dt <= x.dt <= bi.fx_b.bars[-1].dt]
    
    # 如果K线数量不足，不是标准笔
    if len(bars_in_bi) < 4:
        return False

    # 判断笔的方向和价格关系是否符合要求
    if bi.direction == Direction.Up:
        # 向上笔要求结束分型的最高点大于起始分型的最高点
        if bi.fx_b.high <= bi.fx_a.high:
            return False
    else:
        # 向下笔要求结束分型的最低点小于起始分型的最低点
        if bi.fx_b.low >= bi.fx_a.low:
            return False

    return True

def check_strong_bi(bars: List[RawBar], bi: BI) -> bool:
    """检查是否为强笔
    
    强笔是一种特殊的笔，它不仅满足标准笔的要求，
    还需要满足更严格的价格关系要求。

    :param bars: K线列表
    :param bi: 待检查的笔
    :return: 是否为强笔
    """
    # 首先必须是标准笔
    if not check_standard_bi(bars, bi):
        return False

    # 获取笔中的所有K线
    bars_in_bi = [x for x in bars if bi.fx_a.bars[0].dt <= x.dt <= bi.fx_b.bars[-1].dt]
    if not bars_in_bi:
        return False

    # 计算笔中K线的最高点和最低点
    high = max([x.high for x in bars_in_bi])
    low = min([x.low for x in bars_in_bi])

    # 根据笔的方向判断是否满足强笔的条件
    if bi.direction == Direction.Up:
        # 向上笔要求最高点大于结束分型的最高点
        if high > bi.fx_b.high:
            return True
    else:
        # 向下笔要求最低点小于结束分型的最低点
        if low < bi.fx_b.low:
            return True

    return False

def find_bi_end_point(bars: List[RawBar], bis: List[BI], debug=False) -> Optional[FX]:
    """寻找笔的结束点
    
    在K线序列中寻找可能的笔结束点，这是形成新笔的关键步骤。
    
    :param bars: K线列表
    :param bis: 已有的笔列表
    :param debug: 是否开启调试模式
    :return: 返回找到的分型作为笔的结束点，如果未找到则返回None
    """
    # 如果K线不足，无法形成分型
    if len(bars) < 3:
        return None
        
    # 获取最后一笔的信息
    last_bi = bis[-1] if bis else None
    last_direction = last_bi.direction if last_bi else None
    
    # 从现有K线中寻找分型
    fxs = find_fx(bars)
    if not fxs:
        return None
        
    # 根据最后一笔的方向寻找合适的分型
    if last_direction == Direction.Up:
        # 向上笔后需要向下分型
        for fx in reversed(fxs):
            if fx.mark == Mark.D:
                return fx
    else:
        # 向下笔后需要向上分型
        for fx in reversed(fxs):
            if fx.mark == Mark.G:
                return fx
                
    return None

def find_bi_start_point(bars: List[RawBar], bis: List[BI], debug=False) -> Optional[FX]:
    """寻找笔的起始点
    
    在K线序列中寻找可能的笔起始点，这是形成新笔的第一步。
    
    :param bars: K线列表
    :param bis: 已有的笔列表
    :param debug: 是否开启调试模式
    :return: 返回找到的分型作为笔的起始点，如果未找到则返回None
    """
    # 如果没有已有的笔，从第一个分型开始
    if not bis:
        fxs = find_fx(bars)
        return fxs[0] if fxs else None
        
    # 获取最后一笔的结束分型作为新笔的起始点
    last_bi = bis[-1]
    return last_bi.fx_b

def get_potential_bi(bars: List[RawBar], bis: List[BI], debug=False) -> Optional[BI]:
    """获取潜在的笔
    
    根据现有K线和已有的笔，尝试构建新的潜在笔。这个函数会检查各种条件确保新笔的有效性。
    
    :param bars: K线列表
    :param bis: 已有的笔列表
    :param debug: 是否开启调试模式
    :return: 返回新构建的笔，如果无法构建则返回None
    """
    # 获取笔的起始点
    fx_start = find_bi_start_point(bars, bis, debug)
    if not fx_start:
        return None
        
    # 确定笔的方向
    if fx_start.mark == Mark.D:
        direction = Direction.Up
    else:
        direction = Direction.Down
        
    # 寻找符合条件的终点分型
    fx_end = find_bi_end_point(bars, bis, debug)
    if not fx_end:
        return None
        
    # 构建新的笔
    bi = BI(
        symbol=bars[0].symbol,
        direction=direction,
        bars=bars,
        fx_a=fx_start,
        fx_b=fx_end
    )
    
    # 检查笔是否有效
    if not check_bi_valid(bars, bi):
        return None
        
    return bi

def find_fx(bars: List[RawBar]) -> List[FX]:
    """在K线列表中寻找分型
    
    根据K线序列识别顶分型和底分型。分型是构成笔的基本单位。
    
    :param bars: K线列表
    :return: 返回找到的分型列表
    """
    # 如果K线数量不足以形成分型，返回空列表
    if len(bars) < 3:
        return []
        
    # 用于存储找到的分型
    fxs = []
    
    # 从第二个K线开始检查，到倒数第二个K线结束
    for i in range(1, len(bars)-1):
        current_bar = bars[i]
        pre_bar = bars[i-1]
        next_bar = bars[i+1]
        
        # 检查顶分型
        if (pre_bar.high <= current_bar.high and current_bar.high > next_bar.high):
            fx = FX(
                symbol=bars[0].symbol,
                mark=Mark.G,  # 顶分型
                dt=current_bar.dt,
                fx=current_bar.high,
                elements=[pre_bar, current_bar, next_bar]
            )
            fxs.append(fx)
            
        # 检查底分型
        elif (pre_bar.low >= current_bar.low and current_bar.low < next_bar.low):
            fx = FX(
                symbol=bars[0].symbol,
                mark=Mark.D,  # 底分型
                dt=current_bar.dt,
                fx=current_bar.low,
                elements=[pre_bar, current_bar, next_bar]
            )
            fxs.append(fx)
            
    return fxs

def check_bi_end(bars: List[RawBar], bis: List[BI], debug=False) -> bool:
    """检查最后一笔是否已经结束
    
    通过分析K线走势，判断最后一笔是否已经完成。这个判断对于后续笔的生成非常重要。
    
    :param bars: K线列表
    :param bis: 已有的笔列表
    :param debug: 是否开启调试模式
    :return: 如果最后一笔已结束返回True，否则返回False
    """
    # 如果没有已存在的笔，直接返回True表示可以开始寻找新笔
    if not bis:
        return True
        
    # 获取最后一笔的方向
    last_direction = bis[-1].direction
    
    # 获取最后一笔结束后的所有K线
    bars_after_last_bi = get_bars_after_last_bi(bars, bis)
    if not bars_after_last_bi:
        return False
        
    # 分析这些K线是否形成了足够的反向走势
    # 如果最后一笔是向上笔，检查是否有足够的下跌
    if last_direction == Direction.Up:
        lowest_bar = min(bars_after_last_bi, key=lambda x: x.low)
        highest_after_lowest = max(bars_after_last_bi[bars_after_last_bi.index(lowest_bar):], 
                                 key=lambda x: x.high)
        return lowest_bar.low < bis[-1].high * 0.97  # 下跌超过3%
        
    # 如果最后一笔是向下笔，检查是否有足够的上涨
    else:
        highest_bar = max(bars_after_last_bi, key=lambda x: x.high)
        lowest_after_highest = min(bars_after_last_bi[bars_after_last_bi.index(highest_bar):], 
                                 key=lambda x: x.low)
        return highest_bar.high > bis[-1].low * 1.03  # 上涨超过3%

def get_bars_after_last_bi(bars: List[RawBar], bis: List[BI]) -> List[RawBar]:
    """获取最后一笔之后的所有K线
    
    从K线列表中提取最后一笔结束后的所有K线，这些K线用于判断新的走势。
    
    :param bars: K线列表
    :param bis: 已有的笔列表
    :return: 最后一笔之后的K线列表
    """
    # 如果没有已存在的笔，返回所有K线
    if not bis:
        return bars
        
    # 获取最后一笔的结束时间
    last_bi_end_dt = bis[-1].end_dt
    
    # 找出最后一笔结束后的所有K线
    bars_after = [bar for bar in bars if bar.dt > last_bi_end_dt]
    return bars_after

def check_bi_valid(bars: List[RawBar], bi: BI) -> bool:
    """检查笔的有效性
    
    根据缠论的笔定义，检查一个笔是否满足有效性要求。主要检查以下几点：
    1. 笔的方向是否明确（上升或下降）
    2. 笔的长度是否满足要求（至少包含3根K线）
    3. 笔中间不能有重叠（上升笔中不能有更低点，下降笔中不能有更高点）
    4. 笔的力度是否足够（振幅满足要求）
    
    :param bars: K线列表，用于检查笔内部的K线走势
    :param bi: 待检查的笔对象
    :return: True表示笔有效，False表示笔无效
    """
    # 获取笔内的所有K线
    bi_bars = [bar for bar in bars if bi.start_dt <= bar.dt <= bi.end_dt]
    
    # 检查K线数量是否满足要求
    if len(bi_bars) < 3:
        return False
        
    # 根据笔的方向进行相应检查
    if bi.direction == Direction.Up:
        # 上升笔：检查中间是否有比起点更低的点
        if any(bar.low < bi.low for bar in bi_bars[1:-1]):
            return False
        # 检查终点是否比起点高
        if bi.high <= bi.low:
            return False
            
    else:  # Direction.Down
        # 下降笔：检查中间是否有比起点更高的点
        if any(bar.high > bi.high for bar in bi_bars[1:-1]):
            return False
        # 检查终点是否比起点低
        if bi.low >= bi.high:
            return False
            
    # 检查笔的振幅是否足够
    amplitude = abs(bi.high - bi.low) / bi.low
    if amplitude < 0.01:  # 振幅至少要达到1%
        return False
        
    return True
