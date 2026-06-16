"""~/.ticketrc 配置加载（B3 行为）— 实现"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]


@dataclass
class Route:
    from_station: str
    to_station: str
    name: str | None = None

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        return f"{self.from_station}→{self.to_station}"


@dataclass
class Config:
    routes: List[Route] = field(default_factory=list)
    default_filter: str | None = None


def load_config(path: Path) -> Config:
    """从 TOML 文件加载配置；文件不存在时返回空配置"""
    if not path.exists():
        return Config()

    with path.open("rb") as f:
        data = tomllib.load(f)

    routes = [
        Route(
            from_station=r["from_station"],
            to_station=r["to_station"],
            name=r.get("name"),
        )
        for r in data.get("route", [])
    ]

    return Config(
        routes=routes,
        default_filter=data.get("default_filter"),
    )
