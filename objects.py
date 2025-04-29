# coding: utf-8
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
from .enum import Mark, Direction, DirectionView, Signal, Buy, ZsEnd, BiReason


@dataclass
class Tick:
    symbol: str
    name: str = ""
    price: float = 0
    vol: float = 0


@dataclass
class RawBar:
    """原始K线元素"""
    symbol: str
    dt: datetime = None
    freq: str = None
    open: [float, int] = None
    close: [float, int] = None
    high: [float, int] = None
    low: [float, int] = None
    vol: [float, int] = None
    money: [float, int] = None

    def get_left(self):
        td = get_time_delta(self.freq)
        if td:
            return self.dt - td
        else:
            return self.dt

    def get_right(self):
        td = get_time_delta(self.freq, False)
        if td:
            return self.dt + td
        else:
            return self.dt


def init_raw_bar_from_json_dict(json_dict):
    bar = RawBar(symbol=json_dict["symbol"], open=json_dict["open"], dt=json_dict["dt"],
                 close=json_dict["close"], high=json_dict["high"], low=json_dict["low"], vol=json_dict["vol"])
    return bar


def get_time_delta(freq, left=True):
    if left:
        if freq == "1m":
            return timedelta(minutes=1)
        elif freq == "5m":
            return timedelta(minutes=5)
        elif freq == "15m":
            return timedelta(minutes=15)
        elif freq == "30m":
            return timedelta(minutes=30)
        elif freq == "60m":
            return timedelta(minutes=60)
        elif freq == "120m":
            return timedelta(minutes=120)
        elif freq == "w":
            return timedelta(days=7)
    else:
        if freq == "w":
            return timedelta(days=7)
        return timedelta(days=1)

    return None


@dataclass
class NewBar:
    """去除包含关系的K线元素"""
    symbol: str
    dt: datetime = None
    freq: str = None
    open: [float, int] = None
    close: [float, int] = None
    high: [float, int] = None
    low: [float, int] = None
    vol: [float, int] = None
    money: [float, int] = None
    elements: List[RawBar] = None  # 存入具有包含关系的原始K线

    def get_left(self):
        td = get_time_delta(self.freq)
        if td:
            return self.dt - td
        else:
            return self.dt

    def get_right(self):
        td = get_time_delta(self.freq, False)
        if td:
            return self.dt + td
        else:
            return self.dt


@dataclass
class FX:
    symbol: str
    dt: datetime = None
    mark: Mark = None
    high: float = None
    low: float = None
    fx: float = None
    is_complete: bool = True
    elements: List[NewBar] = None
    is_must_get: bool = False

    def set_not_complete(self):
        self.is_complete = False

    def get_left_dt(self):
        dt = self.elements[0].elements[0].dt
        freq = self.elements[0].elements[0].freq
        td = get_time_delta(freq)
        if td:
            return dt - td
        else:
            return dt

    def get_right_dt(self, for_inner=False):
        if for_inner:
            dt = self.dt
            freq = self.elements[0].elements[0].freq
            td = get_time_delta(freq, False)
            if td:
                return dt + td
            else:
                return dt
        else:
            return self.elements[-1].elements[-1].dt

    def get_fx_left_dt(self):
        dt = self.dt
        freq = self.elements[0].elements[0].freq
        td = get_time_delta(freq)
        if td:
            return dt - td
        else:
            return dt

    def get_fx_right_dt(self):
        dt = self.dt
        freq = self.elements[-1].elements[-1].freq
        td = get_time_delta(freq, left=False)
        if td:
            return dt + td
        else:
            return dt

    def get_all_bars(self):
        bars = []
        for elem in self.elements:
            for bar in elem.elements:
                bars.append(bar)

        return bars


@dataclass
class BI:
    symbol: str = None
    fx_a: FX = None  # 笔开始的分型
    fx_b: FX = None  # 笔结束的分型
    direction: Direction = None
    high: float = None
    low: float = None
    bars: List[NewBar] = None
    reason: BiReason = None
    has_complete_bi: bool = False
    inner_bis: List['BI'] = None

    def is_fake(self):
        return not self.fx_b.is_complete

    def is_up(self):
        return self.direction == Direction.Up

    def is_down(self):
        return self.direction == Direction.Down

    def bar_num(self):
        return len([bar for bar in self.bars if self.fx_a.dt <= bar.dt <= self.fx_b.dt])

    def get_spread(self):
        return self.high - self.low

    def check_complete_bi(self):
        return self.has_complete_bi


@dataclass
class InnerBI:
    left: int
    left_date: datetime
    right: int
    right_date: datetime
    high: float
    low: float
    direction: Direction = None

    def get_len(self):
        return self.right - self.left + 1


@dataclass
class Cha:
    ma5: float
    ma10: float
    type_: str
    index: int
    dt: datetime = None


@dataclass
class Zhongshu:
    bis: List[BI] = None
    bi_num: int = 0
    gg: float = None
    dd: float = None
    zg: float = None
    zd: float = None
    direction: str = None
    not_complete_reason: str = ""
    enter_power: float = None
    leave_power: float = None


@dataclass
class Zoushi:
    zhongshus: List[Zhongshu] = List[Zhongshu]
    bis: List[BI] = List[BI]
    freq: str = None
    bars: List[NewBar] = None
    zhongshu_end: ZsEnd = ZsEnd.No
    last_zoushi: 'Zoushi' = None

    def last_bi_fake(self):
        return self.bis[-1].is_fake()

    def has_qushi(self, need_beichi=False):
        cnt = 0
        for zhongshu in self.zhongshus:
            if zhongshu.bi_num > 1:
                cnt += 1

        if cnt < 2:
            return False

        if need_beichi:
            last_zhongshu = self.zhongshus[-1]
            if last_zhongshu.enter_power < last_zhongshu.leave_power:
                return False

        return True

    def has_valid_zhongshu(self):
        if len(self.zhongshus) == 0:
            return False

        for zhongshu in self.zhongshus:
            if zhongshu.bi_num > 1:
                return True

        return False

    def get_signal(self):
        if len(self.zhongshus) == 0:
            return None

        last_zhongshu = self.zhongshus[-1]
        # if last_zhongshu.leave_power is None:
        if last_zhongshu.leave_power is None or last_zhongshu.enter_power < last_zhongshu.leave_power:
            return None

        if len(self.zhongshus) == 1:
            return Signal.Panbei
        else:
            if len(self.zhongshus[-1].bis) > 1 and len(self.zhongshus[-2].bis) > 1:
                return Signal.Beichi
            else:
                return Signal.LeiBeichi

    def get_view(self):
        direction = self.bis[0].direction
        direction_view = DirectionView.Up.value if direction == Direction.Up else DirectionView.Down.value

        if len(self.zhongshus) == 0:
            return "%s%d(%s: %d|%s)" % (
                direction_view, len(self.bis), self.bis[0].fx_a.elements[0].dt.strftime('%Y-%m-%d'),
                sum(len(bi.bars) for bi in self.bis), self.zhongshu_end.value)

        max_power = max(zhongshu.enter_power for zhongshu in self.zhongshus)
        if self.zhongshus[-1].leave_power and self.zhongshus[-1].leave_power > max_power:
            max_power = self.zhongshus[-1].leave_power
        yinzi = 100 / max_power

        zoushi_view = []
        for zhongshu in self.zhongshus:
            zoushi_view.append("b%d" % int(zhongshu.enter_power * yinzi))
            zoushi_view.append("Z%d" % len(zhongshu.bis))
        if self.zhongshus[-1].leave_power:
            zoushi_view.append("b%d" % int(self.zhongshus[-1].leave_power * yinzi))

        if self.zhongshu_end in [ZsEnd.Spread, ZsEnd.Reverse]:
            return "%s%s(%s: %d|%s)" % (
                direction_view, '+'.join(zoushi_view), self.bis[0].fx_a.elements[0].dt.strftime('%Y-%m-%d'),
                (sum(len(bi.bars) for bi in self.bis)), self.zhongshu_end.value)
        else:
            return "%s%s(%s: %d)" % (
                direction_view, '+'.join(zoushi_view), self.bis[0].fx_a.elements[0].dt.strftime('%Y-%m-%d'),
                (sum(len(bi.bars) for bi in self.bis)))

    def is_up(self):
        return self.bis[0].direction == Direction.Up

    def is_down(self):
        return self.bis[0].direction == Direction.Down

    def direction(self):
        return self.bis[0].direction

    def bi_num(self):
        return len(self.bis)

    def has_struct(self):
        if self.get_signal() is None:
            return False

        if len(self.zhongshus) == 1 and len(self.zhongshus[0].bis) == 1:
            return False

        if len(self.zhongshus) > 1 and len(self.zhongshus[-1].bis) == 1 and len(self.zhongshus[-2].bis) == 1:
            return False

        return True

    def maybe_third(self):
        if self.bis != 5:
            return False

        if self.bis[1].high < self.bis[3].low or self.bis[1].low > self.bis[3].high:
            return False

        if (self.is_up() and self.bis[-1].high > self.bis[0].high and self.bis[-1].high > self.bis[2].high) or \
                (self.is_down() and self.bis[-1].low < self.bis[0].low and self.bis[-1].low < self.bis[2].low):
            return True
        return False

    def get_buy(self):
        last_bi = self.bis[-1]
        if self.bis[0].direction == Direction.Up:
            if len(self.bis) == 1 and last_bi.is_fake():
                # 如果是一笔未成就确认一买点，如果成笔，就没有买点
                return Buy.First
            elif len(self.bis) == 2:
                # 如果是两笔未成就是二买预，成了就是二买
                if last_bi.is_fake():
                    return Buy.SecondPre
                else:
                    return Buy.Second
            elif len(self.bis) == 3 and last_bi.is_fake():
                # 如果是三笔未成就是二买
                return Buy.Second
            else:
                # 大于等于三笔，那么肯定有中枢 TODO 确认一下
                if len(self.zhongshus) > 1 and self.zhongshus[-1].bi_num <= 2:
                    last_bi = self.bis[-1]
                    if last_bi.direction == Direction.Down and last_bi.is_fake():
                        return Buy.SThirdPre
                    elif (last_bi.direction == Direction.Down and not last_bi.is_fake()) or \
                            (last_bi.direction == Direction.Up and last_bi.is_fake()):
                        return Buy.SThird
                else:
                    if last_bi.direction == Direction.Down and last_bi.is_fake():
                        return Buy.QibaoPre
                    elif (last_bi.direction == Direction.Down and not last_bi.is_fake()) or \
                            (last_bi.direction == Direction.Up and last_bi.is_fake()):
                        return Buy.Qibao
        else:
            if len(self.bis) == 1 or last_bi.low < min(bi.low for bi in self.bis[:-1]):
                # 最后一个走势是下跌的来找买点，肯定最后一笔是最低
                if last_bi.is_fake():
                    return Buy.FirstPre
                else:
                    return Buy.First

        return Buy.No

    def get_buy_by_bi_num(self):
        last_bi = self.bis[-1]
        if self.bis[0].is_up():
            if self.bi_num() == 1:
                return Buy.First
            elif self.bi_num() == 2 or (self.bi_num() == 3 and self.bis[2].high < self.bis[1].high):
                return Buy.Second
            else:
                # 大于等于三笔，那么肯定有中枢，注意，中枢数量大于1，表示最后一个三买就处于最后一个中枢，即可能只有一笔
                if len(self.zhongshus) > 1 and self.zhongshus[-1].bi_num <= 2:
                    return Buy.SThird
                else:
                    if len(self.zhongshus) == 1 and self.zhongshus[-1].bi_num >= 3:
                        if self.bis[-1].is_up() and self.bis[-1].high > max(bi.high for bi in self.bis[:-1]):
                            return Buy.ZhongshuTupo
                        else:
                            return Buy.Qibao

        else:
            if len(self.bis) == 1 or last_bi.low < min(bi.low for bi in self.bis[:-1]):
                return Buy.First

        return Buy.No
