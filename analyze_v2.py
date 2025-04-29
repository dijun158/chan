# coding: utf-8
"""
缠论分析系统V2版本
包含缠论分析的核心算法和实现，用于处理K线数据并识别笔、分型等结构
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


def copy_newbar(bar):
    """
    创建K线对象的深拷贝
    
    该函数用于创建一个新的K线对象，并保持原始K线的所有属性。
    主要用于在分析过程中创建K线的副本，避免修改原始数据。
    
    :param bar: 原始K线对象
    :return: 新的K线对象，包含原始K线的所有属性
    """
    newbar = deepcopy(bar)  # 创建原始K线的深拷贝
    newbar.elements = [bar]  # 设置新K线的元素列表，只包含原始K线
    return newbar


def set_only_qiangbi():
    """
    设置只显示强笔的标志
    
    该函数用于设置全局变量，控制是否只显示强笔。
    强笔是指满足特定条件的笔，通常具有更强的趋势特征。
    """
    global only_qiangbi  # 声明使用全局变量
    only_qiangbi = True  # 将全局变量设置为True


def merge(bars, target_bar, mark, to_left, idx):
    """
    合并K线数据
    
    根据指定的方向（向左或向右）和标记（顶分型或底分型），
    将相邻的K线合并到目标K线中。
    
    :param bars: K线列表
    :param target_bar: 目标K线，用于合并其他K线
    :param mark: 分型标记（顶分型或底分型）
    :param to_left: 是否向左合并
    :param idx: 当前K线的索引
    :return: 合并后的K线索引
    """
    i = None
    if to_left:  # 向左合并
        for i in range(idx, -1, -1):
            if mark == Mark.G and target_bar.low < bars[i].low:
                target_bar.low = bars[i].low
                target_bar.elements.insert(0, bars[i])
            elif mark == Mark.D and target_bar.high > bars[i].high:
                target_bar.high = bars[i].high
                target_bar.elements.insert(0, bars[i])
            else:
                break
    else:  # 向右合并
        for i in range(idx, len(bars)):
            if mark == Mark.G and target_bar.low < bars[i].low:
                target_bar.low = bars[i].low
                target_bar.elements.append(bars[i])
            elif mark == Mark.D and target_bar.high > bars[i].high:
                target_bar.high = bars[i].high
                target_bar.elements.append(bars[i])
            else:
                break

    return i


def find_max_reverse(bi):
    """
    查找笔中的最大反向波动
    
    该函数用于计算一个笔中最大的反向波动区间，
    用于判断笔的延伸和结束条件。
    
    :param bi: 笔对象
    :return: 最大反向波动的K线数量
    """
    left = 0  # 左边界索引
    right = 0  # 右边界索引
    max_gap = 0  # 最大间隔
    is_extend = True  # 是否在延伸状态

    i = len(bi.fx_a.get_all_bars())  # 从分型A的K线开始
    while i < len(bi.bars):
        if is_extend:
            if (bi.is_up() and bi.bars[i].high >= bi.bars[left].high) or \
               (bi.is_down() and bi.bars[i].low <= bi.bars[left].low):
                left = i
            else:
                right = i
                is_extend = False
        else:
            if (bi.is_up() and bi.bars[i].high >= bi.bars[left].high) or \
               (bi.is_down() and bi.bars[i].low <= bi.bars[left].low):
                if right - left + 1 > max_gap:
                    max_gap = right - left + 1

                i = right
                left = right
                is_extend = True
            elif (bi.is_up() and bi.bars[i].low <= bi.bars[right].low) or \
                 (bi.is_down() and bi.bars[i].high >= bi.bars[right].high):
                right = i

        i += 1

    return max_gap


def find_fx(bars: List[NewBar], inner_idx, mark, use_weak_fx=False):
    """
    查找分型
    
    根据指定的标记（顶分型或底分型）在K线序列中查找分型。
    支持查找标准分型和弱分型。
    
    :param bars: K线列表
    :param inner_idx: 起始索引
    :param mark: 分型标记（顶分型或底分型）
    :param use_weak_fx: 是否使用弱分型
    :return: 找到的分型对象，如果未找到则返回None
    """
    inner_bar = copy_newbar(bars[inner_idx])  # 创建当前K线的副本
    left_idx = merge(bars, inner_bar, mark, True, inner_idx - 1)  # 向左合并
    right_idx = merge(bars, inner_bar, mark, False, inner_idx + 1)  # 向右合并

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

        if mark == Mark.G:  # 顶分型处理
            if inner_bar.low <= left_bar.low:
                inner_bar.low = left_bar.low
                inner_bar.elements = left_bar.elements + inner_bar.elements
                left_bar = None
            if inner_bar.low <= right_bar.low:
                inner_bar.low = right_bar.low
                inner_bar.elements += right_bar.elements
                right_bar = None
        else:  # 底分型处理
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

    if use_weak_fx:  # 使用弱分型
        bar = bars[inner_idx]
        fx = inner_bar.high if mark == Mark.G else inner_bar.low
        return FX(symbol=bar.symbol, dt=bar.dt, mark=mark, high=inner_bar.high, low=inner_bar.low, fx=fx,
                  elements=[inner_bar])

    return None


def be_duan(inner_bis):
    """
    判断是否形成段
    
    根据缠论的定义，判断一组笔是否形成段。
    段是由至少三个笔组成的结构，具有特定的方向特征。
    
    :param inner_bis: 内部笔列表
    :return: True表示形成段，False表示未形成段
    """
    if len(inner_bis) < 3:  # 笔数量不足3个，无法形成段
        return False

    for left in range(0, len(inner_bis) - 2):
        for right in range(left + 1, len(inner_bis)):
            if (inner_bis[left].direction == Direction.Up and inner_bis[right].direction == Direction.Down and
                inner_bis[right].low <= inner_bis[left].low) or \
                    (inner_bis[left].direction == Direction.Down and inner_bis[right].direction == Direction.Up and
                     inner_bis[right].high >= inner_bis[left].high):
                break
            elif (inner_bis[left].direction == inner_bis[right].direction == Direction.Up and
                  inner_bis[right].high > inner_bis[left].high) or \
                    (inner_bis[left].direction == inner_bis[right].direction == Direction.Down and
                     inner_bis[right].low < inner_bis[left].low):
                return True

    return False


def check_bibi(bars: List[NewBar], fx_a: FX):
    """
    检查笔的连续性
    
    根据缠论的定义，检查两个分型之间是否形成有效的笔。
    需要考虑分型的方向、价格关系等因素。
    
    :param bars: K线列表
    :param fx_a: 起始分型
    :return: 如果形成有效笔则返回笔对象，否则返回None
    """
    if len(bars) < 3:  # K线数量不足3根，无法形成笔
        return None

    idx = 0
    for i in range(1, len(bars)):
        if (fx_a.mark == Mark.G and bars[i].low <= bars[idx].low) or \
           (fx_a.mark == Mark.D and bars[i].high >= bars[idx].high):
            idx = i

    mark = Mark.G if fx_a.mark == Mark.D else Mark.D  # 确定下一个分型的标记
    fx_b = find_fx(bars, idx, mark)  # 查找下一个分型
    if fx_b is None:
        return None

    bar = bars[idx]

    # 获取笔的所有K线
    bars_a = [x for x in fx_a.get_all_bars()] + \
             [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    
    # 确定笔的方向和高低点
    direction = Direction.Up if fx_a.mark == Mark.D else Direction.Down
    high = fx_b.high if direction == Direction.Up else fx_a.high
    low = fx_a.low if direction == Direction.Up else fx_b.low
    
    # 创建笔对象
    bi = BI(symbol=bar.symbol, fx_a=fx_a, fx_b=fx_b, direction=direction, high=high, low=low, bars=bars_a)

    # 检查是否有独立的K线
    has_separate_k = len([x for x in bars if fx_a.get_right_dt() < x.dt < fx_b.get_left_dt()]) > 0
    if fx_a.high < fx_b.low or fx_a.low > fx_b.high and has_separate_k:
        return bi

    return None


def must_get_bibi(fx_a: FX, bars: List[NewBar]):
    """
    强制获取笔
    
    在某些特殊情况下，即使不满足标准笔的条件，
    也需要强制获取一个笔对象。主要用于处理笔的延伸和特殊情况。
    
    :param fx_a: 起始分型
    :param bars: K线列表
    :return: 笔对象
    """
    idx = 0
    for i in range(1, len(bars)):
        if (fx_a.mark == Mark.G and bars[i].low <= bars[idx].low) or \
           (fx_a.mark == Mark.D and bars[i].high >= bars[idx].high):
            idx = i

    mark = Mark.G if fx_a.mark == Mark.D else Mark.D  # 确定下一个分型的标记

    bar = bars[idx]
    elements = bars[idx - 1:idx + 1]  # 获取相邻的K线
    if idx + 1 < len(bars):
        elements.append(bars[idx + 1])

    # 根据分型类型确定高低点和分型值
    if mark == Mark.G:  # 顶分型
        high = bar.high
        low = min(e.high for e in elements)
        fx = high
    else:  # 底分型
        high = max(e.high for e in elements)
        low = bar.low
        fx = low
        
    # 创建分型B对象
    fx_b = FX(symbol=bar.symbol, dt=bar.dt, mark=mark, high=high, low=low, fx=fx, elements=elements)

    # 获取所有相关K线并创建笔对象
    bars_a = [x for x in fx_a.get_all_bars()] + \
             [x for x in bars if fx_a.get_right_dt() < x.dt <= fx_b.get_right_dt()]
    direction = Direction.Up if fx_a.mark == Mark.D else Direction.Down
    high = fx_b.high if direction == Direction.Up else fx_a.high
    low = fx_a.low if direction == Direction.Up else fx_b.low
    bi = BI(symbol=bar.symbol, fx_a=fx_a, fx_b=fx_b, direction=direction, high=high, low=low, bars=bars_a)
    return bi


class CZSC:
    """
    缠论分析系统主类
    
    用于实现缠论分析的核心功能，包括：
    1. K线数据的处理和管理
    2. 笔的识别和更新
    3. 分型的查找和处理
    4. 段的形成判断
    """
    def __init__(self, bars: List[RawBar], freq: str, specified_direction=None):
        """
        初始化缠论分析系统
        
        :param bars: K线数据列表
        :param freq: K线级别（如1分钟、5分钟等）
        :param specified_direction: 指定的起始方向（可选）
        """
        self.bars_raw = []  # 原始K线序列
        self.bars_ubi = []  # 未完成笔的无包含K线序列
        self.bi_list: List[BI] = []  # 笔列表
        self.symbol = bars[0].symbol  # 交易品种代码
        self.freq = freq  # K线级别
        self.specified_direction = specified_direction  # 指定的起始方向
        self.check_bi_after = None  # 需要检查的时间点

        # 初始化处理所有K线
        i = 0
        while i < len(bars):
            bar = bars[i]
            self.update(bar)  # 更新分析
            if self.check_bi_after:  # 如果需要检查
                i = self.reset_bar_idx(bars)  # 重置索引
                self.check_bi_after = None  # 清除检查标记
            i += 1

    def __repr__(self):
        """
        返回对象的字符串表示
        
        :return: 包含交易品种代码的字符串
        """
        return "<CZSC for {}>".format(self.symbol)

    def update(self, bar: RawBar):
        """
        更新K线数据并进行分析
        
        处理新的K线数据，更新笔的识别结果。
        包括处理第一个笔的形成、笔的延伸和结束等逻辑。
        
        :param bar: 新的K线数据
        """
        self.bars_raw.append(bar)  # 添加新的K线到原始序列
        new_bar = NewBar(symbol=bar.symbol, dt=bar.dt, open=bar.open, close=bar.close, 
                        high=bar.high, low=bar.low, vol=bar.vol, elements=[bar])
        self.bars_ubi.append(new_bar)  # 添加新的K线到未完成笔序列

        if not self.bi_list:  # 处理第一个笔
            if len(self.bars_ubi) < 7:  # K线数量不足，无法形成笔
                return None

            # 根据指定的方向查找起始分型
            if self.specified_direction == Direction.Up:
                low_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                        low_idx = i
                high_idx = low_idx
                for j in range(low_idx + 1, len(self.bars_ubi)):
                    if self.bars_ubi[j].high >= self.bars_ubi[high_idx].high:
                        high_idx = j

                if high_idx == low_idx:
                    return
            elif self.specified_direction == Direction.Down:
                high_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                        high_idx = i

                low_idx = high_idx
                for j in range(high_idx + 1, len(self.bars_ubi)):
                    if self.bars_ubi[j].low <= self.bars_ubi[low_idx].low:
                        low_idx = j

                if high_idx == low_idx:
                    return
            else:
                high_idx = 0
                low_idx = 0
                for i in range(1, len(self.bars_ubi)):
                    if self.bars_ubi[i].high >= self.bars_ubi[high_idx].high:
                        high_idx = i
                    if self.bars_ubi[i].low <= self.bars_ubi[low_idx].low:
                        low_idx = i

            # 确定起始分型
            if high_idx < low_idx:
                fx = find_fx(self.bars_ubi, high_idx, Mark.G)
            else:
                fx = find_fx(self.bars_ubi, low_idx, Mark.D)

            if fx:
                for i in range(0, len(self.bars_ubi)):
                    if self.bars_ubi[i].dt == fx.dt:
                        break

                bi = check_bibi(self.bars_ubi[i:], fx)
                if isinstance(bi, BI):
                    self.bi_list.append(bi)
                    self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]

            return

        # 处理笔的延伸和结束
        last_bi_max_reverse = find_max_reverse(self.bi_list[-1])

        inner_idx = 0
        for i in range(0, len(self.bars_ubi)):
            if (self.bi_list[-1].is_up() and self.bars_ubi[i].low <= self.bars_ubi[inner_idx].low) or \
                    (self.bi_list[-1].is_down() and self.bars_ubi[i].high >= self.bars_ubi[inner_idx].high):
                inner_idx = i

        if last_bi_max_reverse * 1.5 < len(self.bars_ubi) - inner_idx:
            mark = Mark.G if self.bi_list[-1].fx_b.mark == Mark.D else Mark.D
            fx = find_fx(self.bars_ubi, inner_idx, mark, True)
            if fx:
                for i in range(0, len(self.bars_ubi)):
                    if self.bars_ubi[i].dt == fx.dt:
                        break

                bi = check_bibi(self.bars_ubi[i:], fx)
                if bi:
                    bars_a = [x for x in self.bi_list[-1].fx_b.get_all_bars()] + \
                             [x for x in self.bars_ubi if self.bi_list[-1].fx_b.get_right_dt() < x.dt <= fx.get_right_dt()]
                    direction = Direction.Down if fx.mark == Mark.D else Direction.Up
                    high = fx.high if direction == Direction.Up else self.bi_list[-1].high
                    low = self.bi_list[-1].low if direction == Direction.Up else fx.low

                    self.bi_list.append(
                        BI(symbol=bar.symbol, fx_a=self.bi_list[-1].fx_b, fx_b=fx, direction=direction, 
                           high=high, low=low, bars=bars_a, reason=BiReason.Qiaohu))
                    self.bi_list.append(bi)
                    self.bars_ubi = [x for x in self.bars_ubi if x.dt >= bi.fx_b.get_right_dt()]
                    return

        bi = check_bibi(self.bars_ubi, self.bi_list[-1].fx_b)
        if bi:
            if last_bi_max_reverse * 1.5 >= len([bar for bar in bi.bars if bi.fx_a.dt <= bar.dt <= bi.fx_b.dt]):
                return

            if self.bi_list[-1].reason == BiReason.Qiaohu and find_max_reverse(bi) * 1.5 > self.bi_list[-1].bar_num():
                bi.fx_a = self.bi_list[-2].fx_a
                bi.bars = self.bi_list[-2].bars + \
                          [x for x in self.bi_list[-1].bars if x.dt > self.bi_list[-2].fx_b.get_right_dt()] + \
                          [x for x in bi.bars if x.dt > self.bi_list[-1].fx_b.get_right_dt()]
                if bi.is_up():
                    bi.low = bi.fx_a.low
                else:
                    bi.high = bi.fx_a.high
                self.bi_list.pop(-1)
                self.bi_list.pop(-1)

            self.bi_list.append(bi)
            self.bars_ubi = [x for x in self.bars_ubi if x.dt > bi.fx_b.get_right_dt()]
            return

        # 处理笔的延伸
        min_low_ubi = min(bar.low for bar in self.bars_ubi)
        max_high_ubi = max(bar.high for bar in self.bars_ubi)
        last_bi = self.bi_list[-1]
        if last_bi.direction == Direction.Up and max_high_ubi >= last_bi.high:
            if min_low_ubi <= last_bi.low and len(self.bi_list) > 2:
                bi = must_get_bibi(last_bi.fx_b, self.bars_ubi)
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
                bi = must_get_bibi(last_bi.fx_b, self.bars_ubi)
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
        """
        重置K线索引
        
        当需要重新处理K线时，重置索引到指定位置。
        
        :param bars: K线列表
        :return: 新的索引位置
        """
        last_raw_bar_dt = self.bi_list[-1].bars[-1].dt
        while self.bars_raw[-1].dt > last_raw_bar_dt:
            self.bars_raw.pop(-1)
            self.bars_ubi.pop(-1)

        for i in range(0, len(bars)):
            if bars[i].dt == last_raw_bar_dt:
                return i

    def update_fake_bi(self):
        """
        更新假笔
        
        在某些情况下，需要更新假笔的状态。
        假笔是指不满足标准笔条件但需要特殊处理的笔。
        """
        if len(self.bi_list) <= 0 or len(self.bars_ubi) == 0:
            return

        fx_a = self.bi_list[-1].fx_b
        if (fx_a.mark == Mark.G and min(bar.low for bar in self.bars_ubi) < fx_a.low) or \
                (fx_a.mark == Mark.D and max(bar.high for bar in self.bars_ubi) > fx_a.high):
            bi = must_get_bibi(fx_a, self.bars_ubi)
            bi.fx_b.set_not_complete()
            self.bi_list.append(bi)

    def to_echarts_1(self, file_name, width: str = "1400px", height: str = '580px'):
        """
        生成ECharts图表
        
        将K线和笔的数据转换为ECharts图表格式并保存。
        
        :param file_name: 输出文件名
        :param width: 图表宽度
        :param height: 图表高度
        """
        kline = [x.__dict__ for x in self.bars_raw]  # 转换K线数据
        if len(self.bi_list) > 0:
            bi = [{'dt': x.fx_a.dt, "bi": x.fx_a.fx} for x in self.bi_list] + \
                 [{'dt': self.bi_list[-1].fx_b.dt, "bi": self.bi_list[-1].fx_b.fx}]
        else:
            bi = None
        chart = kline_pro(kline, bi=bi, width=width, height=height, 
                         title="{}-{}".format(self.symbol, self.freq))
        file_html = os.path.join("/home/czsc/static", file_name)
        chart.render(file_html)
