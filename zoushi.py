# coding: utf-8
"""
缠论分析系统 - 走势分析模块
用于识别和分析K线走势，包括中枢、笔和走势的识别
"""

# 导入必要的模块和类
from czsc.objects import Direction, ZsEnd, List  # 导入方向、中枢结束类型和列表类型
from czsc.objects import Zhongshu, Zoushi  # 导入中枢和走势类
from czsc.tools import macd_helper  # 导入MACD计算工具


def find_zhongshu(bi_list):
    """
    在笔序列中查找中枢
    
    根据缠论的定义，中枢是由至少三笔重叠部分形成的区间。
    该函数从笔序列中识别出可能形成中枢的部分。
    
    :param bi_list: 笔的列表
    :return: 如果找到中枢则返回中枢对象，否则返回None
    """
    end_idx = 0  # 初始化结束索引

    # 遍历笔序列，查找可能的结束点
    for i in range(1, len(bi_list)):
        # 检查是否满足中枢形成的条件
        if (bi_list[0].direction == Direction.Down and bi_list[i].direction == Direction.Up and
            bi_list[i].high > bi_list[end_idx].high) or \
                (bi_list[0].direction == Direction.Up and bi_list[i].direction == Direction.Down and
                 bi_list[i].low < bi_list[end_idx].low):
            end_idx = i  # 更新结束索引

    if end_idx == 0:  # 如果没有找到合适的中枢
        return None
    else:
        return form_zhongshu(bi_list[:end_idx])  # 形成中枢对象


def form_zhongshu(bi_list):
    """
    根据笔序列形成中枢对象
    
    计算中枢的关键参数，包括：
    - 中枢的笔数
    - 中枢的最高点(gg)
    - 中枢的最低点(dd)
    - 中枢的重叠区间(zg, zd)
    
    :param bi_list: 笔的列表
    :return: 中枢对象
    """
    zhongshu = Zhongshu()  # 创建中枢对象
    zhongshu.bis = bi_list  # 设置中枢包含的笔
    zhongshu.bi_num = len(bi_list)  # 设置笔的数量
    zhongshu.gg = max(bi.high for bi in zhongshu.bis)  # 计算中枢最高点
    zhongshu.dd = min(bi.low for bi in zhongshu.bis)  # 计算中枢最低点
    zhongshu.zg = min(bi.high for bi in zhongshu.bis)  # 计算中枢重叠区间上沿
    zhongshu.zd = max(bi.low for bi in zhongshu.bis)  # 计算中枢重叠区间下沿
    return zhongshu


def update_zoushi(zoushi, zhongshu, bi_list, start_idx):
    """
    更新走势对象，添加新的中枢并更新笔序列
    
    该函数负责：
    1. 将新的中枢添加到走势中
    2. 更新走势的笔序列
    3. 处理剩余的笔序列
    
    :param zoushi: 当前走势对象
    :param zhongshu: 新识别出的中枢
    :param bi_list: 完整的笔序列
    :param start_idx: 当前处理的起始索引
    :return: 更新后的走势对象和剩余的笔序列
    """
    # 将新中枢添加到走势中
    zoushi.zhongshus.append(zhongshu)
    
    # 计算当前中枢包含的笔数
    zhongshu_bi_num = len(zhongshu.bis)
    
    # 更新走势的笔序列
    zoushi.bis = bi_list[:start_idx + zhongshu_bi_num + 1]
    
    # 返回更新后的走势和剩余的笔序列
    return zoushi, bi_list[start_idx + zhongshu_bi_num + 1:]


def get_bi_power(macd, begin_idx, end_idx, is_plus):
    """
    计算笔的力度
    
    通过MACD指标计算笔的力度，用于判断趋势的强弱。
    向上笔计算正MACD值的和，向下笔计算负MACD值的和。
    
    :param macd: MACD指标序列
    :param begin_idx: 起始索引
    :param end_idx: 结束索引
    :param is_plus: 是否计算正值（向上笔为True，向下笔为False）
    :return: 笔的力度值
    """
    power = 0  # 初始化力度值

    # 遍历MACD序列，计算力度
    for i in range(begin_idx, end_idx + 1):
        if is_plus and macd[i] > 0:  # 向上笔，计算正MACD值
            power += macd[i]
        elif not is_plus and macd[i] < 0:  # 向下笔，计算负MACD值
            power += macd[i]

    return abs(power)  # 返回力度的绝对值


def update_zoushi_power(zoushi, macd, date_to_bar_idx):
    """
    更新走势的力度
    
    计算走势中每个中枢的进入和离开力度，用于判断趋势的强弱。
    力度通过MACD指标计算，反映趋势的强度。
    
    :param zoushi: 走势对象
    :param macd: MACD指标序列
    :param date_to_bar_idx: 日期到K线索引的映射
    :return: 更新后的走势对象
    """
    enter_bi_idx = 0  # 进入笔的索引
    direction = Direction.Up if zoushi.bis[0].direction == Direction.Up else Direction.Down  # 确定走势方向
    zhongshus = []  # 存储更新后的中枢列表

    # 遍历每个中枢，计算力度
    for i in range(0, len(zoushi.zhongshus)):
        enter_bi = zoushi.bis[enter_bi_idx]  # 获取进入笔
        zhongshu = zoushi.zhongshus[i]  # 获取当前中枢
        
        # 确定离开笔
        if i == len(zoushi.zhongshus) - 1:  # 如果是最后一个中枢
            if zoushi.bis[-1].direction == direction and \
                    len(zoushi.bis) == sum(zhongshu.bi_num for zhongshu in zoushi.zhongshus) + len(
                zoushi.zhongshus) + 1:
                leave_bi = zoushi.bis[-1]  # 使用最后一笔作为离开笔
            else:
                leave_bi = None  # 没有合适的离开笔
        else:
            leave_bi = zoushi.bis[enter_bi_idx + zhongshu.bi_num + 1]  # 使用下一笔作为离开笔

        # 计算进入和离开力度
        is_plus = True if direction == Direction.Up else False
        zhongshu.enter_power = get_bi_power(macd, date_to_bar_idx[enter_bi.fx_a.dt],
                                            date_to_bar_idx[enter_bi.fx_b.dt], is_plus)
        if leave_bi:
            zhongshu.leave_power = get_bi_power(macd, date_to_bar_idx[leave_bi.fx_a.dt],
                                                date_to_bar_idx[leave_bi.fx_b.dt], is_plus)
        
        enter_bi_idx += zhongshu.bi_num + 1  # 更新进入笔索引
        zhongshus.append(zhongshu)  # 添加更新后的中枢

    zoushi.zhongshus = zhongshus  # 更新中枢列表
    return zoushi


def get_zoushi_only(bi_list, freq):
    """
    从笔序列中识别走势
    
    根据缠论的定义，识别笔序列中的走势结构，包括：
    1. 中枢的识别
    2. 走势的划分
    3. 特殊情况的处理（如三买、二卖等）
    
    :param bi_list: 笔的列表
    :param freq: 时间周期
    :return: 识别出的走势列表
    """
    zoushis = []  # 存储识别出的走势
    while len(bi_list) > 0:  # 循环处理笔序列
        first_bi = bi_list[0]  # 获取第一笔
        zoushi = Zoushi(zhongshus=[], freq=freq)  # 创建新的走势对象
        direction = first_bi.direction  # 确定走势方向

        if len(bi_list) < 2:  # 如果笔数量不足
            zoushi.bis = bi_list  # 直接使用当前笔
            zoushi.zhongshu_end = ZsEnd.LastBi  # 标记为最后一笔
            zoushis.append(zoushi)  # 添加到走势列表
            break

        i = 1
        while True:  # 循环查找中枢
            # 计算当前处理的笔序列
            start_idx = sum(len(zhongshu.bis) for zhongshu in zoushi.zhongshus) + len(zoushi.zhongshus)
            sub_bis = bi_list[start_idx + 1:start_idx + i + 1]

            # 确定限制条件
            if len(zoushi.zhongshus) == 0:
                limit = first_bi.low if first_bi.direction == Direction.Up else first_bi.high
            else:
                limit = zoushi.zhongshus[-1].gg if first_bi.direction == Direction.Up else zoushi.zhongshus[-1].dd

            # 检查是否满足下破条件
            if (direction == Direction.Up and sub_bis[-1].low < limit) or \
                    (direction == Direction.Down and sub_bis[-1].high > limit):
                zhongshu = find_zhongshu(sub_bis[:-1])  # 查找中枢
                zoushi.zhongshu_end = ZsEnd.DownLimit  # 标记为下破
                zoushi, bi_list = update_zoushi(zoushi, zhongshu, bi_list, start_idx)  # 更新走势
                break

            # 检查是否形成中枢
            min_high = min(bi.high for bi in sub_bis)
            max_low = max(bi.low for bi in sub_bis)
            if min_high < max_low:  # 如果形成中枢
                if direction == Direction.Up:
                    # 处理向上走势的特殊情况
                    if sub_bis[-1].low > max(bi.high for bi in sub_bis[:-2]):
                        # 三买情况
                        zhongshu = form_zhongshu(sub_bis[:-2])
                        zoushi.zhongshus.append(zhongshu)
                        i = 1
                    elif sub_bis[-1].high < min(bi.low for bi in sub_bis[:-2]):
                        # 二卖情况
                        zhongshu = find_zhongshu(sub_bis[:-2])
                        zoushi.zhongshu_end = ZsEnd.FSecondBuy
                        zoushi, bi_list = update_zoushi(zoushi, zhongshu, bi_list, start_idx)
                        break
                    else:
                        # 扩展情况
                        zhongshu = find_zhongshu(sub_bis[:-1])
                        zoushi.zhongshu_end = ZsEnd.Spread
                        zoushi, bi_list = update_zoushi(zoushi, zhongshu, bi_list, start_idx)
                        break
                else:
                    # 处理向下走势的特殊情况
                    if sub_bis[-1].high < min(bi.low for bi in sub_bis[:-2]):
                        # 三买情况
                        zhongshu = form_zhongshu(sub_bis[:-2])
                        zoushi.zhongshus.append(zhongshu)
                        i = 1
                    elif sub_bis[-1].low > max(bi.high for bi in sub_bis[:-2]):
                        # 二卖情况
                        zhongshu = find_zhongshu(sub_bis[:-2])
                        zoushi.zhongshu_end = ZsEnd.FSecondBuy
                        zoushi, bi_list = update_zoushi(zoushi, zhongshu, bi_list, start_idx)
                        break
                    else:
                        # 扩展情况
                        zhongshu = find_zhongshu(sub_bis[:-1])
                        zoushi.zhongshu_end = ZsEnd.Spread
                        zoushi, bi_list = update_zoushi(zoushi, zhongshu, bi_list, start_idx)
                        break
            else:
                # 处理走势结束的情况
                if start_idx + i + 1 == len(bi_list):
                    if bi_list[-1].direction == direction and \
                            ((bi_list[-1].direction == Direction.Up and
                              bi_list[-1].high >= max(bi.high for bi in sub_bis[:-1])) or
                             (bi_list[-1].direction == Direction.Down and
                              bi_list[-1].low <= min(bi.low for bi in sub_bis[:-1]))):
                        zhongshu = form_zhongshu(sub_bis[:-1])
                    else:
                        zhongshu = form_zhongshu(sub_bis)
                    zoushi.zhongshus.append(zhongshu)
                    zoushi.bis = bi_list
                    bi_list = []
                    break
                i += 1

        # 处理特殊情况：扩展后只有一笔
        if len(zoushis) > 0 and zoushis[-1].zhongshu_end == ZsEnd.Spread and len(zoushi.bis) == 1:
            continue

        zoushis.append(zoushi)  # 添加走势到列表

    if len(zoushis) == 0:
        return zoushis

    # 处理最后一个走势的特殊情况
    last_zoushi = zoushis[-1]
    if len(last_zoushi.zhongshus) > 0:
        extra_zoushi = None
        if last_zoushi.is_down():
            # 处理向下走势的额外走势
            idx = 0
            for i in range(2, len(last_zoushi.bis), 2):
                if last_zoushi.bis[i].low <= last_zoushi.bis[idx].low:
                    idx = i
            if len(last_zoushi.bis[idx + 1:]) >= 1:
                extra_zoushi = Zoushi(bis=last_zoushi.bis[idx + 1:], zhongshus=[])
                if len(last_zoushi.bis[idx + 1:]) >= 3:
                    if extra_zoushi.bis[-1].direction == Direction.Up and \
                            extra_zoushi.bis[-1].high >= max(bi.high for bi in extra_zoushi.bis[:-1]):
                        zhongshu = form_zhongshu(last_zoushi.bis[1:-1])
                        extra_zoushi.zhongshus = [zhongshu]
                    else:
                        zhongshu = form_zhongshu(last_zoushi.bis[1:])
                        extra_zoushi.zhongshus = [zhongshu]
        elif last_zoushi.is_up():
            # 处理向上走势的额外走势
            idx = 0
            for i in range(2, len(last_zoushi.bis), 2):
                if last_zoushi.bis[i].high >= last_zoushi.bis[idx].high:
                    idx = i

            if len(last_zoushi.bis[idx + 1:]) >= 3 and last_zoushi.bis[-1].low < last_zoushi.bis[idx + 1].low:
                extra_zoushi = Zoushi(bis=last_zoushi.bis[idx + 1:], zhongshus=[], freq=freq)
                zhongshu = form_zhongshu(last_zoushi.bis[idx + 2:-1])
                extra_zoushi.zhongshus = [zhongshu]

        if extra_zoushi:
            # 更新最后一个走势和额外走势
            if last_zoushi.zhongshus[-1].bi_num == len(extra_zoushi.bis):
                last_zoushi.zhongshus.pop(-1)
            else:
                zhongshu = form_zhongshu(last_zoushi.zhongshus[-1].bis[:-len(extra_zoushi.bis) - 1])
                last_zoushi.zhongshus[-1] = zhongshu

            last_zoushi.zhongshu_end = ZsEnd.Reverse
            last_zoushi.bis = last_zoushi.bis[:-len(extra_zoushi.bis)]

            zoushis[-1] = last_zoushi
            zoushis.append(extra_zoushi)

    return zoushis


def get_zoushis(bi_list):
    """
    从笔序列中识别走势
    
    该函数负责：
    1. 遍历笔序列，识别可能的中枢
    2. 根据中枢构建走势
    3. 返回所有识别出的走势对象
    
    :param bi_list: 笔序列
    :return: 识别出的走势对象列表
    """
    zoushis = []
    start_idx = 0
    
    # 遍历笔序列，寻找中枢
    while start_idx < len(bi_list):
        # 尝试识别中枢
        zhongshu = get_zhongshu(bi_list, start_idx)
        
        if zhongshu is None:
            # 如果没有找到中枢，继续向后查找
            start_idx += 1
            continue
            
        # 如果找到了中枢，创建新的走势对象
        zoushi = Zoushi(
            start_bi=zhongshu.start_bi,
            end_bi=zhongshu.end_bi,
            zhongshus=[zhongshu],
            bis=bi_list[start_idx:start_idx + 4]
        )
        
        # 更新起始索引，继续查找下一个中枢
        start_idx += 4
        zoushis.append(zoushi)
    
    return zoushis


def get_zhongshus(bis):
    """
    从笔序列中识别中枢
    
    中枢的识别标准：
    1. 至少包含3笔
    2. 笔之间必须有重叠区间
    3. 中枢的高点是所有笔的最高点
    4. 中枢的低点是所有笔的最低点
    
    :param bis: 笔序列
    :return: 中枢列表
    """
    zhongshus = []
    if len(bis) < 3:
        return zhongshus
        
    # 遍历笔序列，寻找可能的中枢
    i = 0
    while i < len(bis) - 2:
        # 获取当前笔和后续两笔
        bi1 = bis[i]
        bi2 = bis[i+1]
        bi3 = bis[i+2]
        
        # 检查是否有重叠区间
        if bi1.low <= bi2.high and bi2.low <= bi1.high and \
           bi2.low <= bi3.high and bi3.low <= bi2.high:
            # 找到中枢的起始笔和结束笔
            start_bi = bi1
            end_bi = bi3
            
            # 收集中枢内的所有笔
            zhongshu_bis = [bi1, bi2, bi3]
            
            # 继续向后查找，直到没有重叠区间
            j = i + 3
            while j < len(bis):
                next_bi = bis[j]
                if next_bi.low <= max([bi.high for bi in zhongshu_bis]) and \
                   next_bi.high >= min([bi.low for bi in zhongshu_bis]):
                    zhongshu_bis.append(next_bi)
                    end_bi = next_bi
                    j += 1
                else:
                    break
                    
            # 创建中枢对象
            zhongshu = Zhongshu(start_bi, end_bi, zhongshu_bis)
            zhongshus.append(zhongshu)
            
            # 更新索引，继续查找下一个中枢
            i = j
        else:
            i += 1
            
    return zhongshus


class Zoushi:
    """
    走势类，用于表示缠论中的走势
    
    一个走势包含：
    1. 起始笔和结束笔
    2. 中枢序列
    3. 笔序列
    4. 走势类型（上涨、下跌、盘整）
    """
    
    def __init__(self, start_bi, end_bi, zhongshus, bis):
        """
        初始化走势对象
        
        :param start_bi: 起始笔
        :param end_bi: 结束笔
        :param zhongshus: 中枢序列
        :param bis: 笔序列
        """
        self.start_bi = start_bi
        self.end_bi = end_bi
        self.zhongshus = zhongshus
        self.bis = bis
        
        # 计算走势类型
        self.type = self._calculate_type()
        
    def _calculate_type(self):
        """
        计算走势类型
        
        根据笔的方向和中枢的位置判断走势类型：
        1. 上涨：笔的方向向上，且中枢位置逐渐抬高
        2. 下跌：笔的方向向下，且中枢位置逐渐降低
        3. 盘整：中枢位置无明显趋势
        
        :return: 走势类型
        """
        if len(self.zhongshus) < 2:
            return "盘整"
            
        # 判断中枢位置趋势
        highs = [z.high for z in self.zhongshus]
        lows = [z.low for z in self.zhongshus]
        
        if highs[-1] > highs[0] and lows[-1] > lows[0]:
            return "上涨"
        elif highs[-1] < highs[0] and lows[-1] < lows[0]:
            return "下跌"
        else:
            return "盘整"


class Zhongshu:
    """
    中枢类，用于表示缠论中的中枢
    
    一个中枢包含：
    1. 起始笔和结束笔
    2. 笔序列
    3. 中枢的高点和低点
    4. 中枢的方向（上涨、下跌、盘整）
    """
    
    def __init__(self, start_bi, end_bi, bis):
        """
        初始化中枢对象
        
        :param start_bi: 起始笔
        :param end_bi: 结束笔
        :param bis: 笔序列
        """
        self.start_bi = start_bi
        self.end_bi = end_bi
        self.bis = bis
        
        # 计算中枢的高点和低点
        self.high = max([bi.high for bi in bis])
        self.low = min([bi.low for bi in bis])
        
        # 计算中枢方向
        self.direction = self._calculate_direction()
        
    def _calculate_direction(self):
        """
        计算中枢方向
        
        根据笔的方向和中枢的位置判断中枢方向：
        1. 上涨：笔的方向向上，且中枢位置逐渐抬高
        2. 下跌：笔的方向向下，且中枢位置逐渐降低
        3. 盘整：中枢位置无明显趋势
        
        :return: 中枢方向
        """
        if len(self.bis) < 2:
            return "盘整"
            
        # 判断笔的方向
        first_bi = self.bis[0]
        last_bi = self.bis[-1]
        
        if first_bi.direction == "up" and last_bi.direction == "up":
            return "上涨"
        elif first_bi.direction == "down" and last_bi.direction == "down":
            return "下跌"
        else:
            return "盘整"
