"""B2 行为：中文站名自动转电报码

业务规则：
- 站名可以是中文（"北京"）、拼音（"beijing"）、电报码（"BJP"）三种形式输入
- 输出统一是电报码（"BJP"）
- 站名拼错时给出提示（前 5 个相似站名），不抛异常
- 站名数据从 12306 station_name.js 来，不依赖本地手工维护
"""
from pathlib import Path
import json

import pytest

from ticket.stations import (
    StationIndex,
    parse_station_js,
    find_telecode,
    suggest_similar,
)


# ---------- 真实数据解析 ----------

# 业务规则：12306 的 station_name.js 形如 "var station_names ='@bjb|北京北|beijingbei|bjb|0|...';"
# 我们要能从这段文本里抽出所有 "中文名|拼音|电报码|..." 三元组

def test_parse_station_js_extracts_chinese_name_and_telecode():
    # Given: 一段真实的 station_name.js 截取（新版格式：电报码大写）
    sample_js = (
        "var station_names ='@bjb|北京北|VAP|beijingbei|bjb|0|0357|北京|null|null|null|"
        "@shq|上海虹桥|AOH|shanghaihongqiao|shq|0|0359|上海|null|null|null|"
        "@qzd|泉州东|QRS|quanzhoudong|qzd|0|0595|泉州|null|null|null'"
    )

    # When: 解析这段 JS
    stations = parse_station_js(sample_js)

    # Then: 中文名和拼音都能查到电报码（电报码统一大写）
    assert stations["北京北"] == "VAP"
    assert stations["上海虹桥"] == "AOH"
    assert stations["泉州东"] == "QRS"
    # 拼音也作为 key
    assert stations["beijingbei"] == "VAP"
    assert stations["quanzhoudong"] == "QRS"


def test_parse_station_js_normalizes_pinyin_to_lowercase():
    # Given: 12306 数据里拼音可能是大写（BEIJING）
    sample_js = "@aaa|北京|BJP|BEIJING|bj|0|0|北京|||"

    # When: 解析
    stations = parse_station_js(sample_js)

    # Then: 拼音 key 统一存为小写
    assert stations["beijing"] == "BJP"


# ---------- 站名查找 ----------

def test_find_telecode_accepts_chinese_name():
    # Given: 加载好站名索引
    index = StationIndex({"北京北": "bjb", "上海虹桥": "shh", "泉州东": "qos"})

    # When: 用中文查
    code = find_telecode("北京北", index)

    # Then: 拿到电报码
    assert code == "bjb"


def test_find_telecode_accepts_already_a_telecode():
    # Given: 输入本身就是电报码
    index = StationIndex({"北京北": "VAP", "上海虹桥": "AOH"})

    # When: 用电报码查
    code = find_telecode("VAP", index)

    # Then: 原样返回（不要抛错）
    assert code == "VAP"


def test_find_telecode_accepts_lowercase_telecode():
    # Given: 用户输入小写电报码
    index = StationIndex({"北京北": "VAP"})

    # When: 用小写查
    code = find_telecode("vap", index)

    # Then: 仍然找到（大小写不敏感）
    assert code == "VAP"


def test_find_telecode_accepts_pinyin():
    # Given: 索引里同时存了中文和拼音 key（parse_station_js 会这样生成）
    index = StationIndex({
        "北京北": "VAP",
        "上海虹桥": "AOH",
        "beijingbei": "VAP",
    })

    # When: 用拼音查
    code = find_telecode("beijingbei", index)

    # Then: 拿到电报码
    assert code == "VAP"


def test_find_telecode_returns_none_for_unknown_station():
    # Given: 一个不存在的站名
    index = StationIndex({"北京北": "VAP"})

    # When: 查不存在的站
    code = find_telecode("不存在的站", index)

    # Then: 返回 None（让调用方决定怎么处理）
    assert code is None


def test_suggest_similar_returns_close_matches():
    # Given: 站名索引和一个拼错的站名
    index = StationIndex({"北京北": "VAP", "北京南": "VNP", "北京西": "BXP", "上海虹桥": "AOH"})

    # When: 找相似站名
    suggestions = suggest_similar("北京", index, limit=5)

    # Then: 三个带"北京"的站都返回，按名字长度升序
    assert "北京北" in suggestions
    assert "北京南" in suggestions
    assert "北京西" in suggestions
    assert "上海虹桥" not in suggestions


# ---------- 加载与缓存 ----------

def test_station_index_can_be_loaded_from_cached_json(tmp_path: Path):
    # Given: 缓存文件已经存在
    cache_file = tmp_path / "stations.json"
    cache_file.write_text(json.dumps({"北京北": "bjb", "泉州东": "qos"}, ensure_ascii=False))

    # When: 从缓存加载
    index = StationIndex.load_from_cache(cache_file)

    # Then: 加载到内容
    assert index.mapping == {"北京北": "bjb", "泉州东": "qos"}


def test_station_index_save_and_reload_roundtrip(tmp_path: Path):
    # Given: 一个索引
    original = StationIndex({"北京北": "bjb", "上海虹桥": "shh"})

    # When: 保存到文件再加载
    cache_file = tmp_path / "stations.json"
    original.save_to(cache_file)
    reloaded = StationIndex.load_from_cache(cache_file)

    # Then: 数据一致
    assert reloaded.mapping == original.mapping
