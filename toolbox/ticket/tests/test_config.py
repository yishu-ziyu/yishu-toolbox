"""B3 行为：默认配置 ~/.ticketrc

业务规则：
- 用户可以把常用线路写进 ~/.ticketrc
- 不带参数运行 `ticket` 时，自动用配置的第一条线路
- 配置文件用 TOML 格式（最常见的 Python 配置格式）
- 配置文件不存在时用空默认
"""
from pathlib import Path
import textwrap

from ticket.config import Config, Route, load_config


def test_load_config_returns_empty_when_file_missing(tmp_path: Path):
    # Given: 配置路径指向不存在的文件
    missing = tmp_path / "no_such_file.toml"

    # When: 加载配置
    cfg = load_config(missing)

    # Then: 返回空配置，不抛错
    assert cfg.routes == []


def test_load_config_parses_default_routes(tmp_path: Path):
    # Given: 一份真实的 ~/.ticketrc
    config_file = tmp_path / ".ticketrc"
    config_file.write_text(textwrap.dedent("""
        [[route]]
        name = "泉州东到杭州东"
        from_station = "泉州东"
        to_station = "杭州东"

        [[route]]
        name = "杭州东到泉州东"
        from_station = "杭州东"
        to_station = "泉州东"
    """).strip())

    # When: 加载
    cfg = load_config(config_file)

    # Then: 两条线路都读到
    assert len(cfg.routes) == 2
    assert cfg.routes[0].name == "泉州东到杭州东"
    assert cfg.routes[0].from_station == "泉州东"
    assert cfg.routes[0].to_station == "杭州东"
    assert cfg.routes[1].from_station == "杭州东"
    assert cfg.routes[1].to_station == "泉州东"


def test_load_config_parses_default_filter(tmp_path: Path):
    # Given: 配置里指定了默认车型过滤
    config_file = tmp_path / ".ticketrc"
    config_file.write_text(textwrap.dedent("""
        default_filter = "G"

        [[route]]
        from_station = "泉州东"
        to_station = "杭州东"
    """).strip())

    # When: 加载
    cfg = load_config(config_file)

    # Then: 默认过滤被读到
    assert cfg.default_filter == "G"


def test_route_uses_name_or_falls_back_to_stations():
    # Given: 一条没有 name 的 route
    route = Route(from_station="泉州东", to_station="杭州东")

    # Then: 自动生成的 name 是 "起点→终点"
    assert route.display_name == "泉州东→杭州东"
