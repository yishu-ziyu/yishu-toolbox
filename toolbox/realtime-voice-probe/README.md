# Realtime Voice Probe

一个基于 Step Plan `stepaudio-2.5-realtime` 的本地 BYOK 能力探针，用来验证实时语音对话链路是否可用。它不是独立产品。

## 启动

```bash
npm install
npm start
```

然后打开 <http://127.0.0.1:4173>。

页面里的 API Key 只通过本机代理转发到 Step Plan WebSocket（默认 `wss://api.stepfun.com/step_plan/v1/realtime`）；浏览器端不能直接设置 `Authorization` 请求头，所以没有把 Key 写进前端 URL 或服务端日志。

如果使用开放平台而不是 Step Plan，可启动时覆盖端点：

```bash
STEPFUN_REALTIME_BASE=wss://api.stepfun.com/v1/realtime npm start
```

## 当前支持

- WebSocket 实时语音通话
- 账号已复刻音色列表加载与自定义 `voice_id`
- PCM16 音频上传与播放
- Server VAD（自动识别一轮说话结束）
- 文字输入 + 语音输出
- 结构化人设：名字、身份、性格标签、说话方式、边界与补充规则
- 语音转写消息与回复文字流式展示
- 本地健康检查：`GET /api/health`
- 本地账号音色代理：`GET /api/voices`（Key 只在请求内存中转发）

这是一个最小可运行的本地页面，服务端只负责静态文件和 WebSocket 鉴权代理；API Key、对话内容和音频都不落盘。
