import http from 'node:http'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { WebSocketServer, WebSocket } from 'ws'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const publicDir = path.join(__dirname, 'public')
const port = Number(process.env.PORT || 4173)
const upstreamBase = process.env.STEPFUN_REALTIME_BASE || 'wss://api.stepfun.com/step_plan/v1/realtime'
const voicesBase = process.env.STEPFUN_VOICES_BASE || upstreamBase
  .replace(/^wss:/, 'https:')
  .replace(/^ws:/, 'http:')
  .replace(/\/realtime(?:\?.*)?$/, '/audio/voices')
const supportedModels = new Set(['stepaudio-2.5-realtime'])

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
}

function sendJson(response, statusCode, payload) {
  const body = JSON.stringify(payload)
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  })
  response.end(body)
}

async function serveFile(request, response) {
  const requestPath = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
  const relativePath = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '')
  const resolvedPath = path.resolve(publicDir, relativePath)

  if (!resolvedPath.startsWith(`${publicDir}${path.sep}`)) {
    sendJson(response, 403, { error: 'forbidden' })
    return
  }

  try {
    const file = await readFile(resolvedPath)
    const extension = path.extname(resolvedPath).toLowerCase()
    response.writeHead(200, {
      'Content-Type': contentTypes[extension] || 'application/octet-stream',
      'Content-Length': file.byteLength,
      'Cache-Control': extension === '.html' ? 'no-store' : 'public, max-age=3600',
    })
    response.end(file)
  } catch (error) {
    if (error.code === 'ENOENT') {
      sendJson(response, 404, { error: 'not_found' })
      return
    }
    sendJson(response, 500, { error: 'file_read_failed' })
  }
}

async function proxyVoices(request, response) {
  const authorization = request.headers.authorization
  if (typeof authorization !== 'string' || !/^Bearer\s+\S+$/i.test(authorization)) {
    sendJson(response, 401, { error: 'missing_authorization' })
    return
  }

  try {
    const voicesUrl = new URL(voicesBase)
    voicesUrl.searchParams.set('limit', '100')
    const upstreamResponse = await fetch(voicesUrl, {
      headers: { Authorization: authorization },
      signal: AbortSignal.timeout(20_000),
    })
    const body = await upstreamResponse.text()
    response.writeHead(upstreamResponse.status, {
      'Content-Type': upstreamResponse.headers.get('content-type') || 'application/json; charset=utf-8',
      'Content-Length': Buffer.byteLength(body),
      'Cache-Control': 'no-store',
    })
    response.end(body)
  } catch {
    sendJson(response, 502, { error: 'voice_list_unavailable', message: '音色列表暂时无法获取，请稍后重试。' })
  }
}

const server = http.createServer(async (request, response) => {
  if (request.method !== 'GET') {
    sendJson(response, 405, { error: 'method_not_allowed' })
    return
  }

  const requestUrl = new URL(request.url, `http://${request.headers.host || 'localhost'}`)
  if (requestUrl.pathname === '/api/health') {
    sendJson(response, 200, { ok: true, service: 'voice-field-proxy' })
    return
  }

  if (requestUrl.pathname === '/api/voices') {
    await proxyVoices(request, response)
    return
  }

  await serveFile(request, response)
})

const realtimeWss = new WebSocketServer({ noServer: true, maxPayload: 16 * 1024 * 1024 })

server.on('upgrade', (request, socket, head) => {
  const requestUrl = new URL(request.url, `http://${request.headers.host || 'localhost'}`)
  if (requestUrl.pathname !== '/realtime') {
    socket.destroy()
    return
  }

  realtimeWss.handleUpgrade(request, socket, head, (client) => {
    realtimeWss.emit('connection', client, request)
  })
})

realtimeWss.on('connection', (client) => {
  let upstream = null
  let authenticated = false
  let closed = false
  const queuedEvents = []

  const sendToClient = (payload) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(payload))
    }
  }

  const closeConnection = () => {
    if (closed) return
    closed = true
    if (upstream && upstream.readyState === WebSocket.OPEN) {
      upstream.close(1000, 'client disconnected')
    }
    if (client.readyState === WebSocket.OPEN || client.readyState === WebSocket.CONNECTING) {
      client.close(1000, 'connection closed')
    }
  }

  const fail = (message, code = 'proxy_error') => {
    sendToClient({ type: 'proxy.error', code, message })
    closeConnection()
  }

  const connectUpstream = (apiKey, model) => {
    const upstreamUrl = `${upstreamBase}?model=${encodeURIComponent(model)}`
    upstream = new WebSocket(upstreamUrl, {
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
    })

    upstream.on('open', () => {
      sendToClient({ type: 'proxy.connected' })
      for (const event of queuedEvents.splice(0)) {
        if (upstream.readyState === WebSocket.OPEN) upstream.send(event)
      }
    })

    upstream.on('message', (data) => {
      if (client.readyState === WebSocket.OPEN) client.send(data.toString())
    })

    upstream.on('error', () => {
      if (!closed) fail('上游实时服务连接失败，请检查 Key、额度或网络。', 'upstream_error')
    })

    upstream.on('close', (code, reason) => {
      if (closed) return
      const reasonText = reason?.toString() || ''
      sendToClient({
        type: 'proxy.closed',
        code,
        reason: reasonText || '上游连接已结束',
      })
      if (client.readyState === WebSocket.OPEN) client.close(1000, 'upstream closed')
      closed = true
    })
  }

  const authTimeout = setTimeout(() => {
    if (!authenticated) fail('连接已超时，请重新点击连接。', 'auth_timeout')
  }, 12_000)

  client.on('message', (rawData) => {
    if (closed) return
    const raw = rawData.toString()
    let message
    try {
      message = JSON.parse(raw)
    } catch {
      fail('收到无法识别的消息。', 'invalid_json')
      return
    }

    if (!authenticated) {
      if (message?.type !== 'auth') {
        fail('连接尚未完成鉴权。', 'not_authenticated')
        return
      }

      const apiKey = typeof message.apiKey === 'string' ? message.apiKey.trim() : ''
      const model = typeof message.model === 'string' ? message.model : ''
      if (apiKey.length < 12 || apiKey.length > 512) {
        fail('请输入有效的 StepFun API Key。', 'invalid_api_key')
        return
      }
      if (!supportedModels.has(model)) {
        fail('当前页面只支持 StepAudio 2.5 Realtime。', 'unsupported_model')
        return
      }

      authenticated = true
      clearTimeout(authTimeout)
      connectUpstream(apiKey, model)
      return
    }

    if (message?.type === 'auth') return
    if (upstream?.readyState === WebSocket.OPEN) {
      upstream.send(raw)
    } else {
      queuedEvents.push(raw)
      if (queuedEvents.length > 120) fail('连接初始化过慢，请重新连接。', 'upstream_timeout')
    }
  })

  client.on('close', () => {
    clearTimeout(authTimeout)
    closed = true
    if (upstream && upstream.readyState === WebSocket.OPEN) upstream.close(1000, 'client disconnected')
  })

  client.on('error', () => {
    closeConnection()
  })
})

server.listen(port, '127.0.0.1', () => {
  console.log(`Voice Field running at http://127.0.0.1:${port}`)
})

const shutdown = () => {
  realtimeWss.close()
  server.close(() => process.exit(0))
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
