# ticket — 12306 快速查票工具

> 一个学习项目：5 行 BDD、22 个 TDD 测试、4 个 Python 模块，把 12306 的实时余票装进 `~/ticket` 一行命令。

## 安装

```bash
git clone <repo> ~/Developer/ticket
cd ~/Developer/ticket
pip install -e .
```

## 一次性配置

```bash
# 1) 抓 12306 全部车站数据到本地缓存
ticket --update-stations

# 2) 写常用线路到 ~/.ticketrc
cat > ~/.ticketrc <<'EOF'
[[route]]
name = "泉州东到杭州东"
from_station = "泉州东"
to_station = "杭州东"

[[route]]
name = "杭州东到泉州东"
from_station = "杭州东"
to_station = "泉州东"

[[route]]
name = "杭州东到南京南"
from_station = "杭州东"
to_station = "南京南"
EOF
```

## 用法

```bash
# 三种位置参数
ticket 2026-06-15 泉州东 杭州东
ticket 2026-06-15 quanzhoudong hangzhoudong   # 拼音
ticket 2026-06-15 QRS HGH                       # 电报码

# 车型过滤（只看高铁）
ticket 2026-06-15 泉州东 杭州东 -t G

# 无参数：用 ~/.ticketrc 第一条线路 + 明天日期
ticket
```

## 跑测试

```bash
cd ~/Developer/ticket
python3 -m pytest tests/ -v
```

## 数据来源

- **车站数据**：`https://kyfw.12306.cn/otn/resources/js/framework/station_name.js`（6584 站）
- **余票数据**：`https://kyfw.12306.cn/otn/leftTicket/query`（公开匿名接口，不需要登录）

## 项目结构

```
ticket/
├── pyproject.toml          # 包配置 + ticket 命令入口
├── ticket/
│   ├── cli.py              # 命令行入口
│   ├── stations.py         # 站名→电报码索引
│   ├── config.py           # ~/.ticketrc 加载
│   └── query.py            # 12306 响应解析 + 表格
├── tests/
│   ├── test_stations.py    # B2 行为
│   ├── test_config.py      # B3 行为
│   └── test_query.py       # B1 行为
└── README.md
```

## 学到的（设计要点）

- **TDD 红灯→绿灯循环**：先写测试看到 18 fail，再写实现让 22 pass
- **Python 字符串字面量自动合并的坑**：用 `[]` + `.join` 显式分隔
- **12306 字段索引易变**：把索引和 SAMPLE_ROW 集中到一处（`query.py` 顶部），方便 12306 改版时改
- **数据不内嵌**：`SAMPLE_ROW` 用 `|".join([...])` 显式分隔，不写 Python 多行字符串

## 后续 roadmap

- [ ] 自然语言输入（"下周一北京到上海的高铁"）
- [ ] 严格匹配出发/到达（12306 默认返回经过两站的所有车次）
- [ ] 跨夜车显示（24:00 / 次日）
