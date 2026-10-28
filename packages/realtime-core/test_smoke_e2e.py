# smoke_e2e_local.py — 本地全链冒烟（09-29 审计 A2）：
# 假网关(9878,SSE) → 本地 server(9877, indextts 通道) → 第二桥(连本地 /tts-bridge) → 真 8766 合成
# 覆盖：长句细切流水（多段 audio）、标记行 parts 协议（deep/pause/laughs 单段下发）、无 error
# 跑法：cd packages/realtime-core && python -X utf8 test_smoke_e2e.py  （需 8766 已在跑）
import asyncio
import json
import os
import sys

import aiohttp
from aiohttp import web
import websockets

TEST_TOKEN = "smoke-token-0929"
LONG_LINE = ('"This is a deliberately long line with more than twelve words in it, '
             'so the sub-clause pipeline should kick in, and you should receive '
             'multiple audio segments, not one single big blob."')
MARK_LINE = '"[deep] Stay there. (pause) Take a look. [laughs] Nice work."'

results = {"long": {"audio_end": 0, "audio": 0, "errors": []},
           "mark": {"audio_end": 0, "audio": 0, "errors": []}}
current = "long"


async def fake_gateway(request):
    """OpenAI SSE 兼容：按收到的 transcript 回固定台词。"""
    body = await request.json()
    text = body["messages"][0]["content"]
    resp = web.StreamResponse(headers={"content-type": "text/event-stream"})
    await resp.prepare(request)
    line = LONG_LINE if "smoke-long" in text else MARK_LINE
    for piece in (line[:40], line[40:90], line[90:]):
        await resp.write(b"data: " + json.dumps(
            {"choices": [{"delta": {"content": piece}}]}).encode() + b"\n\n")
        await asyncio.sleep(0.05)
    await resp.write(b"data: [DONE]\n\n")
    return resp


async def start_local_server():
    env = dict(os.environ)
    env.update({
        "PAIVOICE_PORT": "9877", "PAIVOICE_HOST": "127.0.0.1",
        "PAIVOICE_TOKEN": TEST_TOKEN,
        "PAIVOICE_GATEWAY_URL": "http://127.0.0.1:9878/gw",
        "PAIVOICE_TTS_PROVIDER": "indextts",
        "PAIVOICE_TTS_BRIDGE_VOICE": "k",
        "PAIVOICE_STREAM_TTS": "1",
        "PAIVOICE_ARCHIVE_URL": "",
        "PAIVOICE_ASR_PROVIDER": "mock",
    })
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-X", "utf8", "server.py", env=env, cwd=".")
    await asyncio.sleep(4)
    return proc


async def start_local_bridge():
    env = dict(os.environ)
    env.update({
        "PAIVOICE_BRIDGE_WS": "ws://127.0.0.1:9877/tts-bridge",
        "PAIVOICE_BRIDGE_TOKEN": TEST_TOKEN,
    })
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-X", "utf8", "-u", "tts_bridge_local.py", env=env, cwd=".")
    await asyncio.sleep(3)
    return proc


async def run_client():
    global current
    async with websockets.connect(f"ws://127.0.0.1:9877/voice/ws?token={TEST_TOKEN}",
                                   max_size=1 << 20) as ws:
        await ws.send(json.dumps({"type": "start", "tts_provider": "indextts",
                                  "client_build": "smoke-0929"}))
        for phase, msg_text in (("long", "smoke-long"), ("mark", "smoke-mark")):
            current = phase
            await ws.send(json.dumps({"type": "text", "text": msg_text}))
            deadline = asyncio.get_event_loop().time() + 180
            done = False
            while not done and asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    results[phase]["errors"].append("30s 无消息")
                    break
                m = json.loads(raw)
                t = m.get("type")
                if t == "audio":
                    results[phase]["audio"] += 1
                elif t == "audio_sentence_end":
                    results[phase]["audio_end"] += 1
                elif t == "generation_end":
                    done = True
                elif t == "error":
                    results[phase]["errors"].append(m.get("error", "")[:120])
                    done = True


async def main():
    gw = web.Application()
    gw.router.add_post("/gw", fake_gateway)
    runner = web.AppRunner(gw)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 9878).start()

    srv = await start_local_server()
    brg = await start_local_bridge()
    try:
        await run_client()
    finally:
        for p in (srv, brg):
            try: p.kill()
            except Exception: pass
        await runner.cleanup()

    ok_all = True
    L, M = results["long"], results["mark"]
    print(f"[细切长句] audio={L['audio']} sentence_end={L['audio_end']} errors={L['errors']}")
    if L["audio_end"] < 3 or L["errors"] or L["audio"] != L["audio_end"]:
        ok_all = False; print("  ✗ 长句应细切成≥3段且 audio/sentence_end 成对")
    else:
        print("  ✓ 细切流水生效（多段成对下发）")
    print(f"[标记行]   audio={M['audio']} sentence_end={M['audio_end']} errors={M['errors']}")
    if M["audio_end"] != 1 or M["errors"]:
        ok_all = False; print("  ✗ 标记行应 parts 单段下发且无错")
    else:
        print("  ✓ parts 协议单段下发（deep/pause/laugh 桥内拼接）")
    print("SMOKE " + ("PASS" if ok_all else "FAIL"))
    sys.exit(0 if ok_all else 1)


asyncio.run(main())
