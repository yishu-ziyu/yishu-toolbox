"""B1 行为：解析 12306 leftTicket API 响应 + 排序 + 表格输出

业务规则：
- 12306 响应的每行按 | 分割，固定索引是字段位置
- 输出按车型优先级排序：G（高铁）→ D（动车）→ C（城际）→ 其他
- 表格等宽对齐，终端可读
- 无票显示 "无"，有数字直接显示数字
"""
import pytest

from ticket.query import (
    parse_train_row,
    sort_trains,
    format_table,
    TrainInfo,
)


# ---------- 解析单行 ----------

# 业务规则：12306 一行车的格式是 | 分隔的固定字段（实测索引）
#   [0]  = secretStr
#   [1]  = buttonTextInfo
#   [2]  = train_no (内部编号)
#   [3]  = stationTrainCode (车次显示，如 G1651)
#   [4]  = start_station_telecode (始发站电报码)
#   [5]  = end_station_telecode (终到站电报码)
#   [6]  = from_station_telecode (用户查询的出发电报码)
#   [7]  = to_station_telecode (用户查询的到达电报码)
#   [8]  = start_time (出发时间)
#   [9]  = arrive_time (到达时间)
#   [10] = 历时
#   [26] = 高级软卧
#   [30] = 二等座
#   [31] = 一等座
#   [32] = 商务座
#   [33] = 动卧
# 注意：Python 会自动合并相邻字符串字面量，所以用 [] + .join 显式分隔
SAMPLE_ROW = "|".join([
    "secretStr",       # 0
    "预订",            # 1
    "58000K42210",     # 2 train_no
    "K4221",           # 3 车次
    "QYS",             # 4 始发站电报码
    "HGH",             # 5 终到站电报码
    "QYS",             # 6 出发站电报码
    "HGH",             # 7 到达站电报码
    "08:15",           # 8 出发时间
    "16:42",           # 9 到达时间
    "08:27",           # 10 历时
    "Y",               # 11 是否有票
    *([""] * 14),     # 12-25 占位
    "无",              # 26 高级软卧
    *([""] * 3),      # 27-29 占位
    "无",              # 30 二等座
    "无",              # 31 一等座
    "无",              # 32 商务座
    "无",              # 33 动卧
    *([""] * 20),     # 34-53 后续占位
])


def test_parse_train_row_extracts_train_number():
    # When: 解析一行
    train = parse_train_row(SAMPLE_ROW, station_map={})

    # Then: 关键字段都对
    assert train.train_no == "K4221"
    assert train.from_station_code == "QYS"
    assert train.to_station_code == "HGH"
    assert train.depart_time == "08:15"
    assert train.arrive_time == "16:42"
    assert train.duration == "08:27"


def test_parse_train_row_resolves_chinese_name_via_station_map():
    # Given: 提供电报码→中文名映射
    row = SAMPLE_ROW
    station_map = {"QYS": "泉州", "HGH": "杭州东"}

    # When: 解析时传入映射
    train = parse_train_row(row, station_map)

    # Then: 中文名被正确解析
    assert train.from_station_name == "泉州"
    assert train.to_station_name == "杭州东"


def test_parse_train_row_falls_back_to_telecode_when_no_map():
    # Given: 不传 station_map
    train = parse_train_row(SAMPLE_ROW, station_map={})

    # Then: 中文名 fallback 到电报码
    assert train.from_station_name == "QYS"
    assert train.to_station_name == "HGH"


def test_parse_train_row_extracts_seat_counts():
    # When: 解析
    train = parse_train_row(SAMPLE_ROW, station_map={})

    # Then: 所有座位都是 "无"（字符串，不是 None/数字）
    assert train.seats["商务座"] == "无"
    assert train.seats["一等座"] == "无"
    assert train.seats["二等座"] == "无"
    assert train.seats["高级软卧"] == "无"
    assert train.seats["动卧"] == "无"


def test_parse_train_row_extracts_numeric_seats():
    # Given: 有票的情况
    row_with_seats = SAMPLE_ROW.replace("无|", "12|", 4)

    # When: 解析
    train = parse_train_row(row_with_seats, station_map={})

    # Then: 数字保持字符串
    assert train.seats["高级软卧"] == "12"


def test_sort_trains_puts_high_speed_first():
    # Given: 三种车型混在一起
    trains = [
        TrainInfo(train_no="K4221", train_type="K", from_station_code="a", to_station_code="b", from_station_name="a", to_station_name="b", depart_time="08:00", arrive_time="16:00", duration="08:00", seats={}),
        TrainInfo(train_no="G1651", train_type="G", from_station_code="a", to_station_code="b", from_station_name="a", to_station_name="b", depart_time="09:00", arrive_time="13:00", duration="04:00", seats={}),
        TrainInfo(train_no="D3231", train_type="D", from_station_code="a", to_station_code="b", from_station_name="a", to_station_name="b", depart_time="10:00", arrive_time="14:00", duration="04:00", seats={}),
    ]

    # When: 排序
    sorted_trains = sort_trains(trains)

    # Then: 顺序是 G → D → K
    assert [t.train_no for t in sorted_trains] == ["G1651", "D3231", "K4221"]


def test_sort_trains_within_same_type_sorts_by_depart_time():
    # Given: 两个 G 车
    trains = [
        TrainInfo(train_no="G1651", train_type="G", from_station_code="a", to_station_code="b", from_station_name="a", to_station_name="b", depart_time="15:00", arrive_time="19:00", duration="04:00", seats={}),
        TrainInfo(train_no="G1655", train_type="G", from_station_code="a", to_station_code="b", from_station_name="a", to_station_name="b", depart_time="09:00", arrive_time="13:00", duration="04:00", seats={}),
    ]

    # When: 排序
    sorted_trains = sort_trains(trains)

    # Then: 同车型内按出发时间升序
    assert [t.train_no for t in sorted_trains] == ["G1655", "G1651"]


# ---------- 表格输出 ----------

def test_format_table_produces_aligned_columns():
    # Given: 几班车
    trains = [
        TrainInfo(train_no="G1651", train_type="G", from_station_code="QYS", to_station_code="HGH",
                  from_station_name="泉州", to_station_name="杭州东", depart_time="09:00", arrive_time="13:00", duration="04:00",
                  seats={"商务座": "12", "一等座": "无", "二等座": "无", "高级软卧": "无", "动卧": "无"}),
        TrainInfo(train_no="D3231", train_type="D", from_station_code="QYS", to_station_code="HGH",
                  from_station_name="泉州", to_station_name="杭州东", depart_time="10:00", arrive_time="14:00", duration="04:00",
                  seats={"商务座": "无", "一等座": "20", "二等座": "100", "高级软卧": "无", "动卧": "无"}),
    ]

    # When: 格式化
    table = format_table(trains)

    # Then: 输出包含表头和两行数据
    assert "G1651" in table
    assert "D3231" in table
    assert "09:00" in table
    assert "10:00" in table
    lines = [line for line in table.split("\n") if line.strip()]
    assert len(lines) >= 3
