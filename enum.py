# coding: utf-8

from enum import Enum


class Mark(Enum):
    D = "底分型"
    G = "顶分型"


class BiReason(Enum):
    QiangBi = "强笔"  # 即顶底部触碰
    ChengDuan = "成段"  # 成段
    Qiaohu = "巧虎"


class Direction(Enum):
    Up = "向上"
    Down = "向下"
    Forward = "向前"
    Backward = "向后"


class DirectionView(Enum):
    Up = "↗️ "
    Down = "↘️ "


class Signal(Enum):
    Panbei = "盘背"
    Beichi = "背驰"
    LeiBeichi = "类背驰"


class Factor(Enum):
    Zhh = "三高高"
    Zhl = "三高低"
    Jiaodu = "角度大于45-55"
    Fb35 = "涨幅不大"
    Sb50 = "回调不深"
    Third20d = "20均"
    HasVol = "放量"
    Zhangting = "涨停"
    MultiZhangting = "多个涨停"
    GoodVolZhangting = "正常涨停"
    UpZhangting = "站上涨停"
    VsIndex = "是否比大盘强，还是一样"
    SectionStrong = "板块强弱"
    MacdUp = "零上"
    Qiwen = "企稳"


class BiRule(Enum):
    Mohu = "模糊"
    Standard = "标准"


class Buy(Enum):
    First = "一买"
    FirstPre = "一买预"
    Second = "二买"
    SecondPre = "二买预"
    SThird = "强三买"
    SThirdPre = "强三买预"
    WThird = "弱三买"
    WThirdPre = "弱三买预"
    Qibao = "起爆点"
    QibaoPre = "起爆点预"
    ZhongshuTupo = "中枢突破"
    No = "无买点"
    Third = "三买"
    LikeThird = "类三买"
    SecTrd = "二三合买"
    SecTrdPre = "二三合买预"


class ZsEnd(Enum):
    Thirdbuy = "三买"
    FSecondBuy = "反向二买"
    Spread = "扩展"
    LastBi = "最后一笔"
    FewBi = "笔数不足"
    DownLimit = "破限制"
    Reverse = "反向处理"
    No = "无"


class Freq(Enum):
    F1 = "1分钟"
    F5 = "5分钟"
    F15 = "15分钟"
    F30 = "30分钟"
    F60 = "60分钟"
    D = "日线"
    W = "周线"
    M = "月线"
