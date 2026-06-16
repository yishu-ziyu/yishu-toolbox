"""站名→电报码索引（B2 行为）— 实现"""
from __future__ import annotations

import json
import re
from pathlib import Path


# 12306 station_name.js 新格式：
#   @secret|chinese|TELECODE|pinyin|short|seq|city_code|city|...
# 例: @bjb|北京北|VAP|beijingbei|bjb|0|0357|北京|...
# 关键约束：中文含中文字符，TELECODE 和拼音都接受任意大小写
# 捕获 group(1)=secret(丢弃), group(2)=中文, group(3)=TELECODE, group(4)=拼音
STATION_ROW_RE = re.compile(
    r"@(\w+)\|([\u4e00-\u9fff][^|]*)\|([A-Za-z]+)\|([A-Za-z]+)\|"
)


class StationIndex:
    """站名索引：mapping 的 key 可以是中文名、拼音或电报码"""

    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    @classmethod
    def load_from_cache(cls, path: Path) -> "StationIndex":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    def save_to(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def parse_station_js(js_text: str) -> dict[str, str]:
    """从 12306 station_name.js 解析出 (中文名|拼音) → 电报码 映射

    存储规则：
    - 中文名原样存（"北京北"）
    - 拼音 lowercase 后存（"beijingbei"）
    - 电报码 uppercase 后存（"VAP"）
    """
    mapping: dict[str, str] = {}
    for m in STATION_ROW_RE.finditer(js_text):
        chinese = m.group(2)
        telecode = m.group(3).upper()  # VAP
        pinyin = m.group(4).lower()    # beijingbei
        mapping[chinese] = telecode
        mapping[pinyin] = telecode
    return mapping


def find_telecode(name: str, index: StationIndex) -> str | None:
    """根据站名找电报码（支持中文、拼音、电报码三种输入）

    接受任意大小写的电报码输入（"qys" 和 "QYS" 都行）
    """
    # 1. 直接查（中文 / 拼音）
    if name in index.mapping:
        return index.mapping[name]
    if name.lower() in index.mapping:
        return index.mapping[name.lower()]
    # 2. 大小写不敏感的电报码
    if re.match(r"^[A-Za-z]+$", name):
        upper = name.upper()
        if upper in set(index.mapping.values()):
            return upper
    return None


def suggest_similar(name: str, index: StationIndex, limit: int = 5) -> list[str]:
    """拼错时给前 N 个相似站名（按名字长度升序）"""
    matches = [s for s in index.mapping if name in s and re.search(r"[\u4e00-\u9fff]", s)]
    return sorted(matches, key=len)[:limit]
