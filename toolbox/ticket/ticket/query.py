"""12306 leftTicket API 解析与表格输出（B1 行为）— 实现"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# 车型优先级：G 高铁 → D 动车 → C 城际 → 其他
TRAIN_TYPE_PRIORITY = {
    "G": 0,
    "D": 1,
    "C": 2,
    "O": 3,
    "K": 4,
    "T": 5,
    "Z": 6,
}


# 12306 响应里座位字段的固定索引 → 业务名称
SEAT_INDEX = {
    32: "商务座",
    31: "一等座",
    30: "二等座",
    26: "高级软卧",
    33: "动卧",
}


@dataclass
class TrainInfo:
    train_no: str
    train_type: str
    from_station_code: str
    to_station_code: str
    from_station_name: str
    to_station_name: str
    depart_time: str
    arrive_time: str
    duration: str
    seats: Dict[str, str] = field(default_factory=dict)


def parse_train_row(row: str, station_map: dict[str, str] | None = None) -> TrainInfo:
    """把 12306 一行 | 分隔的字段解析成 TrainInfo

    station_map: 电报码 → 中文名 映射（来自 12306 响应的 data.map）
                用于把 fields[6]/[7] 的电报码转成中文站名
    """
    fields = row.split("|")
    train_no = fields[3] if len(fields) > 3 else ""

    from_code = fields[6] if len(fields) > 6 else ""
    to_code = fields[7] if len(fields) > 7 else ""

    # 用 station_map 把电报码转中文名；没有就 fallback 到电报码
    station_map = station_map or {}
    from_name = station_map.get(from_code, from_code)
    to_name = station_map.get(to_code, to_code)

    seats: Dict[str, str] = {}
    for idx, name in SEAT_INDEX.items():
        seats[name] = fields[idx] if idx < len(fields) and fields[idx] else "无"

    return TrainInfo(
        train_no=train_no,
        train_type=train_no[0] if train_no else "",
        from_station_code=from_code,
        to_station_code=to_code,
        from_station_name=from_name,
        to_station_name=to_name,
        depart_time=fields[8] if len(fields) > 8 else "",
        arrive_time=fields[9] if len(fields) > 9 else "",
        duration=fields[10] if len(fields) > 10 else "",
        seats=seats,
    )


def sort_trains(trains: List[TrainInfo]) -> List[TrainInfo]:
    """按车型优先级排序：G → D → C → 其他；同车型按出发时间升序"""
    return sorted(
        trains,
        key=lambda t: (TRAIN_TYPE_PRIORITY.get(t.train_type, 99), t.depart_time),
    )


def format_table(trains: List[TrainInfo]) -> str:
    """格式化为可读表格（终端等宽对齐）"""
    headers = ["车次", "出发", "到达", "时段", "历时", "商务座", "一等座", "二等座", "高级软卧", "动卧"]
    rows = [
        [
            t.train_no,
            t.from_station_name,
            t.to_station_name,
            f"{t.depart_time}→{t.arrive_time}",
            t.duration,
            t.seats.get("商务座", "无") or "无",
            t.seats.get("一等座", "无") or "无",
            t.seats.get("二等座", "无") or "无",
            t.seats.get("高级软卧", "无") or "无",
            t.seats.get("动卧", "无") or "无",
        ]
        for t in trains
    ]

    col_widths = [
        max(len(headers[i]), max((len(r[i]) for r in rows), default=0))
        for i in range(len(headers))
    ]

    def fmt_row(cells: List[str]) -> str:
        return "  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(cells))

    sep = "  ".join("-" * w for w in col_widths)
    lines = [fmt_row(headers), sep]
    lines.extend(fmt_row(r) for r in rows)
    return "\n".join(lines)
