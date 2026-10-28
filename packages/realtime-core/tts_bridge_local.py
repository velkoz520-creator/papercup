"""papercup IndexTTS 本地桥（09-28 换嗓通道）：跑在她的 MSI 上，出站反连 papercup
服务器 /tts-bridge（家机桥同款，家里不开任何入站端口），把云端逐行 TTS 活转给
本地双声服务（127.0.0.1:8766，IndexTTS-2.5，模型只载一次）合成，wav 转成小体积
mp3 后回传（服务器 WS 帧 1MB 上限，长句 wav 裸传会爆；mp3 与前端 decodeAudioData
既有管线同族）。桥断了自动重连；启动时顺带把本地双声服务拉起（没起的话）。
用法：python tts_bridge_local.py （日常用 start-papercup-voice.cmd 一键拉起）
凭据：PAIVOICE_BRIDGE_TOKEN env 优先，否则读 papercup_bridge_token.txt（在仓库外）。
红线：token 与参考音频只住本地，不进仓库不上云。"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

SERVER_WS = os.getenv("PAIVOICE_BRIDGE_WS", "wss://your-deployment.example/tts-bridge")
LOCAL_TTS = os.getenv("PAIVOICE_LOCAL_TTS", "http://127.0.0.1:8766")
TOKEN_FILE = r"D:\Jester的家\jester-voice\papercup_bridge_token.txt"
INDEX_TTS_ROOT = os.getenv("PAIVOICE_INDEX_TTS_ROOT", r"D:\index-tts")
# ↑ ASCII junction（→ D:\软件下载\index-tts）：wetext 的 C++ fst 层打不开中文路径
# （traditional_to_simple.fst kaldi-io 744 桥拉起即崩的根因）；统一走 ASCII 路径根治
LAUGH_DIR = os.path.join(INDEX_TTS_ROOT, "refs", "laughs")   # B 方案真笑原声库（make_laugh_clips.py 生成）
# 拼接产物集中目录：与 8766 合成产物同住 outputs，时间戳可考古（10-03 插播案定版）
JOIN_DIR = r"D:\Jester的家\jester-voice\outputs"


def _token() -> str:
    t = os.getenv("PAIVOICE_BRIDGE_TOKEN", "").strip()
    if t:
        return t
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _health_ok() -> bool:
    try:
        with urllib.request.urlopen(LOCAL_TTS + "/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _ensure_local_tts() -> None:
    """双声服务没起就拉起（IndexTTS 模型只载一次，Jester/K 两个嗓音共享同一实例）。
    子进程 stdout/stderr 重定向到文件——CREATE_NO_WINDOW 下崩溃无声，日志是唯一尸检材料。"""
    if _health_ok():
        print("[bridge] local tts already up")
        return
    venv_py = r"D:\index-tts\.venv\Scripts\python.exe"
    script = r"D:\Jester的家\jester-voice\jester_voice_server.py"
    cwd = r"D:\index-tts"
    log_path = r"D:\Jester的家\jester-voice\srv_8766.log"
    print("[bridge] starting local tts service ...")
    log = open(log_path, "ab")
    subprocess.Popen([venv_py, "-X", "utf8", script], cwd=cwd,
                     stdout=log, stderr=subprocess.STDOUT,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    for attempt in range(2):   # 拉起失败重试一次（间歇性竞态：显存/端口未释放）
        for _ in range(45):
            if _health_ok():
                print("[bridge] local tts ready")
                return
            time.sleep(2)
        if attempt == 0:
            print("[bridge] first spawn failed; retrying (see srv_8766.log)", flush=True)
            log.close()
            log = open(log_path, "ab")
            subprocess.Popen([venv_py, "-X", "utf8", script], cwd=cwd,
                             stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    raise RuntimeError(f"local tts service did not come up (log: {log_path})")


def _wav_to_mp3(wav_path: str) -> str:
    mp3 = wav_path[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav_path,
                    "-ac", "1", "-ar", "24000", "-b:a", "64k", mp3], check=True)
    return mp3


async def _synth_one(text: str, lang: str, voice: str, emo: str = "") -> str:
    """单段合成，返回 wav 路径（不转 mp3——多段拼接统一在后处理做）。"""
    import requests   # 本机已装；走 127.0.0.1 不吃代理配置也无妨
    params = {"text": text, "lang": lang, "voice": voice, "play": "0"}
    if emo:
        params["emo"] = emo
    with requests.get(LOCAL_TTS + "/say", params=params, timeout=180) as r:
        r.raise_for_status()
        data = r.json()
    if not data.get("ok"):
        raise RuntimeError(str(data.get("error", "local tts error"))[:150])
    return data["file"]


def _concat_with_gaps(wavs: list, gap_ms: int) -> str:
    """多段 wav + 段间静音 → 一个 wav。IndexTTS 输出 22050Hz mono——全部 aformat
    统一到 22050 再 concat（静音源同 rate），段序=[段1][gap][段2][gap]…（首段前置）。"""
    if len(wavs) == 1:
        return wavs[0]
    gap_s = gap_ms / 1000.0
    SR = 22050
    filters = ""
    for i in range(1, len(wavs)):
        filters += f"aevalsrc=0:d={gap_s}:s={SR}:c=mono[ga{i}];"
    parts = ["[0:a]"]
    for i in range(1, len(wavs)):
        parts += [f"[ga{i}]", f"[{i}:a]"]
    fc = filters + "".join(parts) + f"concat=n={len(parts)}:v=0:a=1[acat];" \
        f"[acat]aformat=sample_rates={SR}:channel_layouts=mono[aout]"
    out = wavs[0][:-4] + "_concat_%d.wav" % int(time.time())
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for w in wavs:
        cmd += ["-i", w]
    cmd += ["-filter_complex", fc, "-map", "[aout]", out]
    subprocess.run(cmd, check=True)
    return out


def _make_silence(ms: int) -> str:
    """指定时长的静音 wav（22050 mono，与合成输出同参数）。"""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"anullsrc=r=22050:cl=mono", "-t", f"{ms/1000:.3f}",
                    path], check=True)
    return path


def _pick_laugh() -> str:
    """真笑原声库随机选一片（refs/laughs/laugh_*.wav，已响度归一 22050 mono）。
    拼接产物（_joined_/_concat_）绝不入池——10-03 插播案根因：拼接产物写回库目录
    被 glob 认成笑声片，旧台词整段插播进通话。文件名过滤是第二道闸。"""
    import glob as _glob
    import random as _random
    clips = [c for c in _glob.glob(os.path.join(LAUGH_DIR, "laugh_*.wav"))
             if "_joined_" not in os.path.basename(c) and "_concat_" not in os.path.basename(c)]
    if not clips:
        raise RuntimeError("laugh clip library empty — run make_laugh_clips.py")
    return _random.choice(clips)


def _concat_files(files: list) -> str:
    """顺序拼接任意 wav 列表（text 合成段/pause 静音/laugh 原声混排），统一 22050 mono。
    产物一律写 JOIN_DIR——绝不写回 files[0] 所在目录（旧版写在笑声片旁边=污染素材库）。"""
    if len(files) == 1:
        return files[0]
    SR = 22050
    parts = [f"[{i}:a]" for i in range(len(files))]
    fc = "".join(parts) + f"concat=n={len(files)}:v=0:a=1[acat];" \
        f"[acat]aformat=sample_rates={SR}:channel_layouts=mono[aout]"
    os.makedirs(JOIN_DIR, exist_ok=True)
    out = os.path.join(JOIN_DIR, "joined_%d.wav" % int(time.time()))
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f in files:
        cmd += ["-i", f]
    cmd += ["-filter_complex", fc, "-map", "[aout]", out]
    subprocess.run(cmd, check=True)
    return out


async def bridge_loop(token: str) -> None:
    import websockets
    url = f"{SERVER_WS}?token={urllib.parse.quote(token)}"
    while True:
        try:
            async with websockets.connect(url, ping_interval=25, ping_timeout=120,
                                          max_size=1 << 20) as ws:
                print("[bridge] connected to papercup", flush=True)
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") != "tts_job":
                        continue
                    job_id = event.get("job_id") or ""
                    t0 = time.time()
                    try:
                        lang = event.get("lang") or "EN"
                        voice = event.get("voice") or "k"
                        emo = event.get("emo") or ""
                        parts = event.get("parts")
                        segments = event.get("segments")
                        if parts and len(parts) > 1:
                            # parts 协议（B 方案）：text 合成 / pause 静音 / laugh 真笑原声，混排拼接
                            files = []
                            tmp_clean = []
                            for p in parts:
                                kind = p.get("kind")
                                if kind == "text":
                                    t = (p.get("text") or "").strip()
                                    if not t:
                                        continue  # 剥标记后的空壳段：不发（8766 对空 text 必 400，10-01 卡顿案）
                                    files.append(await _synth_one(t, lang, voice, emo))
                                elif kind == "pause":
                                    s = _make_silence(int(p.get("ms") or 450))
                                    files.append(s); tmp_clean.append(s)
                                elif kind == "laugh":
                                    files.append(_pick_laugh())
                            if not files:
                                raise RuntimeError("all parts empty")
                            merged = _concat_files(files)
                            mp3 = _wav_to_mp3(merged)
                            for t in tmp_clean:
                                try: os.remove(t)
                                except OSError: pass
                        elif segments and len(segments) > 1:
                            # 旧 segments 协议（兼容）：逐段合成 + 段间静音
                            gap_ms = int(event.get("gap_ms") or 450)
                            wavs = []
                            for seg in segments:
                                s = (seg or "").strip()
                                if not s:
                                    continue  # 空壳段跳过（同上）
                                wavs.append(await _synth_one(s, lang, voice, emo))
                            if not wavs:
                                raise RuntimeError("all segments empty")
                            merged = _concat_with_gaps(wavs, gap_ms)
                            mp3 = _wav_to_mp3(merged)
                        else:
                            text = (segments[0] if segments else event.get("text", "")) or ""
                            if not text.strip():
                                raise RuntimeError("empty text")
                            wav = await _synth_one(text, lang, voice, emo)
                            mp3 = _wav_to_mp3(wav)
                        with open(mp3, "rb") as f:
                            audio = f.read()
                        await ws.send(json.dumps({
                            "type": "tts_result", "job_id": job_id, "ok": True,
                            "audio_b64": base64.b64encode(audio).decode("ascii")}))
                        print(f"[bridge] job {job_id} ok ({len(audio)}B, "
                              f"{len(segments) if segments else 1}seg, {time.time() - t0:.1f}s)",
                              flush=True)
                    except Exception as e:
                        await ws.send(json.dumps({
                            "type": "tts_result", "job_id": job_id, "ok": False,
                            "error": str(e)[:200]}))
                        print(f"[bridge] job {job_id} FAILED: {str(e)[:120]}", flush=True)
        except Exception as e:
            print(f"[bridge] disconnected: {type(e).__name__}: {str(e)[:120]} ; retry in 5s",
                  flush=True)
            await asyncio.sleep(5)


BRIDGE_MUTEX_NAME = "Global\\papercup_local_voice_bridge_single"

def _bridge_singleton_lock() -> None:
    """桥层单例锁（10-01 她要求"点图标不双开打架"）：命名互斥体，非 PID 文件——
    PID 有复用误判风险（旧 pid 被分给别的进程=她双击直接没反应）；互斥体随进程
    死亡自动释放，无残留无复用。句柄故意不关：持有到进程退出为止。"""
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW(None, False, BRIDGE_MUTEX_NAME)
    if k32.GetLastError() == 183:   # ERROR_ALREADY_EXISTS
        print("[bridge] already running (mutex); exit")
        sys.exit(0)


def main() -> None:
    token = _token()
    if not token:
        print("缺少 token：设 PAIVOICE_BRIDGE_TOKEN env，或把 token 写入 " + TOKEN_FILE)
        sys.exit(1)
    _bridge_singleton_lock()
    _ensure_local_tts()
    asyncio.run(bridge_loop(token))


if __name__ == "__main__":
    main()
