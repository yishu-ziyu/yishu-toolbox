"""CLI 入口（阶段 3）

设计原则：
- 简单胜过聪明：argparse + 几个函数，不引入复杂框架
- 网络和数据加载分两步：先看有没有缓存，没缓存提示用户更新
- 错误信息要"可执行"：站名拼错时给建议
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import requests

from ticket.config import Config, load_config
from ticket.stations import (
    StationIndex,
    find_telecode,
    parse_station_js,
    suggest_similar,
)
from ticket.query import (
    TrainInfo,
    format_table,
    parse_train_row,
    sort_trains,
)


# ---------- 路径配置 ----------
CONFIG_PATH = Path.home() / ".ticketrc"
STATIONS_CACHE_DIR = Path.home() / ".cache" / "ticket"
STATIONS_CACHE = STATIONS_CACHE_DIR / "stations.json"
STATIONS_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"

# 12306 leftTicket API（公开匿名查询，不需要登录）
LEFT_TICKET_URL = "https://kyfw.12306.cn/otn/leftTicket/query"


# ---------- 命令行参数 ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket",
        description="12306 快速查票工具",
    )
    parser.add_argument("date", nargs="?", help="出发日期 YYYY-MM-DD")
    parser.add_argument("from_station", nargs="?", help="出发站（中文/拼音/电报码）")
    parser.add_argument("to_station", nargs="?", help="到达站")
    parser.add_argument("-t", "--train-type", help="车型过滤: G/D/K/T/Z/C")
    parser.add_argument("--update-stations", action="store_true",
                        help="从 12306 刷新车站缓存")
    return parser


def resolve_from_config_if_empty(args: argparse.Namespace, config: Config) -> argparse.Namespace:
    """不带参数时，用 ~/.ticketrc 第一条线路 + 明天的日期

    为什么是明天：12306 通常卖未来 15 天的票，今天的票可能没放出
    """
    if not (args.date and args.from_station and args.to_station):
        if config.routes:
            args.date = args.date or (date.today() + timedelta(days=1)).isoformat()
            args.from_station = args.from_station or config.routes[0].from_station
            args.to_station = args.to_station or config.routes[0].to_station
    return args


# ---------- 站名数据 ----------

def download_stations() -> dict[str, str]:
    """从 12306 抓车站数据"""
    resp = requests.get(STATIONS_URL, timeout=10)
    resp.raise_for_status()
    return parse_station_js(resp.text)


def update_station_cache() -> int:
    """刷新站名缓存"""
    STATIONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    mapping = download_stations()
    index = StationIndex(mapping)
    index.save_to(STATIONS_CACHE)
    return len(mapping)


def load_station_index() -> StationIndex:
    if not STATIONS_CACHE.exists():
        raise FileNotFoundError(STATIONS_CACHE)
    return StationIndex.load_from_cache(STATIONS_CACHE)


# ---------- 12306 查询 ----------

def query_left_ticket(query_date: str, from_code: str, to_code: str) -> tuple[list[str], dict[str, str]]:
    """调 12306 leftTicket API，返回 (原始行列表, 电报码→中文名映射)"""
    session = requests.Session()
    # 12306 需要先访问主页拿 cookie
    session.get("https://kyfw.12306.cn/otn/leftTicket/init", timeout=10,
                headers={"User-Agent": "Mozilla/5.0"})

    resp = session.get(
        LEFT_TICKET_URL,
        params={
            "leftTicketDTO.train_date": query_date,
            "leftTicketDTO.from_station": from_code,
            "leftTicketDTO.to_station": to_code,
            "purpose_codes": "ADULT",
        },
        timeout=10,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://kyfw.12306.cn/otn/leftTicket/init",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    result = data.get("data", {}).get("result", [])
    station_map = data.get("data", {}).get("map", {})
    return result, station_map


# ---------- 错误报告 ----------

def report_unknown_station(name: str, index: StationIndex) -> int:
    print(f"错误：找不到车站「{name}」", file=sys.stderr)
    suggestions = suggest_similar(name, index)
    if suggestions:
        print(f"你是不是想找：{', '.join(suggestions)}", file=sys.stderr)
    return 1


# ---------- 主流程 ----------

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 特殊命令：刷新站名
    if args.update_stations:
        try:
            n = update_station_cache()
            print(f"已更新 {n} 个车站到 {STATIONS_CACHE}")
            return 0
        except Exception as e:
            print(f"更新失败：{e}", file=sys.stderr)
            return 1

    config = load_config(CONFIG_PATH)
    args = resolve_from_config_if_empty(args, config)

    if not (args.date and args.from_station and args.to_station):
        parser.print_help()
        print("\n错误：缺少参数或 ~/.ticketrc 配置", file=sys.stderr)
        return 1

    try:
        index = load_station_index()
    except FileNotFoundError:
        print(f"站名缓存不存在：{STATIONS_CACHE}", file=sys.stderr)
        print("请先运行：ticket --update-stations", file=sys.stderr)
        return 1

    from_code = find_telecode(args.from_station, index)
    if from_code is None:
        return report_unknown_station(args.from_station, index)

    to_code = find_telecode(args.to_station, index)
    if to_code is None:
        return report_unknown_station(args.to_station, index)

    try:
        raw, station_map = query_left_ticket(args.date, from_code, to_code)
    except Exception as e:
        print(f"查询失败：{e}", file=sys.stderr)
        return 1

    trains: list[TrainInfo] = [
        parse_train_row(line, station_map) for line in raw if "|" in line
    ]

    # 车型过滤
    if args.train_type:
        wanted = args.train_type.upper()
        trains = [t for t in trains if t.train_type == wanted]

    trains = sort_trains(trains)

    print(f"\n{args.date}  {args.from_station} → {args.to_station}  "
          f"({len(trains)} 班车)\n")
    if trains:
        print(format_table(trains))
    else:
        print("（没有符合条件的车次）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
