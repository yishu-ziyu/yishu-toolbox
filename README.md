# yishu-toolbox

奕枢的小工具箱。每个子目录一个独立小工具——可以整体 clone，也可以单独复制某个目录使用。

## 工具列表

| 工具 | 简介 | 技术栈 |
|---|---|---|
| [`ticket`](./toolbox/ticket) | 12306 实时余票查询 CLI，22 个 TDD 测试全过 | Python · requests |
| [`realtime-voice-probe`](./toolbox/realtime-voice-probe) | 验证 Step Plan `stepaudio-2.5-realtime` 的 BYOK 实时语音通话链路 | Node.js · WebSocket |

## 目录结构

```
yishu-toolbox/
├── README.md        # 本文件
├── LICENSE          # MIT
├── .gitignore
└── toolbox/         # 所有工具的容器
    ├── ticket/      # 12306 查票工具
    │   ├── pyproject.toml
    │   ├── README.md
    │   ├── ticket/  # 源码
    │   └── tests/
    └── realtime-voice-probe/ # StepFun 实时语音能力探针
        ├── package.json
        ├── server.mjs
        └── public/
```

## 新增工具

在 `toolbox/` 下新建一个子目录，README 里补一行表格即可。每个工具独立 `pyproject.toml` / `package.json` / `Cargo.toml`，互不依赖。
