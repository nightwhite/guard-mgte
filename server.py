# -*- coding: utf-8 -*-
# Jev 兼容 API 服务：请求/响应格式与 typesafe/jev（CF AI Gateway 口径）逐字段对齐
# 并发模型：HTTP 全异步；推理按 CONCURRENCY 路数并行（默认 1），超出排队
import asyncio
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

MODEL_DIR = os.environ.get("MGTE_MODEL_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "model"))
BASE_DIR = os.environ.get("MGTE_BASE_DIR", "Alibaba-NLP/gte-multilingual-base")
def _auto_threads(default=4):
    # torch 数的是整机物理核，看不见 K8s 的 CFS 配额（cpu.max），必须自己读配额换算
    try:
        q, p = open("/sys/fs/cgroup/cpu.max").read().split()
        if q != "max":
            return max(1, int(int(q) / int(p)))
    except Exception:
        pass
    try:
        q = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        p = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        if q > 0:
            return max(1, q // p)
    except Exception:
        pass
    return default

THREADS = int(os.environ["GUARD_THREADS"]) if os.environ.get("GUARD_THREADS") else _auto_threads()
CONCURRENCY = int(os.environ.get("GUARD_CONCURRENCY", "1"))
GUARD_TOKEN = os.environ.get("GUARD_TOKEN", "")

from scanner import Scanner

app = FastAPI(title="guard-mgte", docs_url=None, redoc_url=None, openapi_url=None)

_scanner = Scanner(MODEL_DIR, base_dir=BASE_DIR or None, threads=THREADS)
_sem = asyncio.Semaphore(CONCURRENCY)
import concurrent.futures
_pool = concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="infer")

_stats = {"served": 0, "queued": 0, "infer_ms": 0.0, "texts": 0}

TEXT_RE = re.compile(r"TEXT-(\d+):\s*(.*?)(?=\n\nTEXT-\d+:|\Z)", re.S)


def _extract_texts(state):
    hits = TEXT_RE.findall(state)
    if hits:
        return [t.strip() for _, t in hits]
    return [state.strip()] if state.strip() else []


def _blocking_scores(texts):
    return [_scanner.scan(t) for t in texts]


@app.post("/{path:path}")
async def decide(path: str, request: Request):
    if GUARD_TOKEN:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {GUARD_TOKEN}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        state = body["input"]["state"]
        questions = body["input"]["questions"]
    except Exception:
        return JSONResponse({"error": "invalid request, expect Jev format: model + input.state + input.questions"}, status_code=400)

    texts = _extract_texts(state)
    if not texts:
        return JSONResponse({"error": "empty state"}, status_code=400)

    _stats["queued"] += 1
    t0 = time.time()
    async with _sem:
        scores = await asyncio.get_running_loop().run_in_executor(_pool, _blocking_scores, texts)
    _stats["queued"] -= 1
    _stats["served"] += 1
    _stats["texts"] += len(texts)
    _stats["infer_ms"] += (time.time() - t0) * 1000

    answers = {}
    for k in questions:
        try:
            idx = int(k.lstrip("q")) - 1
        except ValueError:
            idx = 0
        r = scores[min(max(idx, 0), len(scores) - 1)]
        a = {"noul": r["score"]}
        if "category" in r:
            a["category"] = r["category"]
            a["category_top3"] = r["category_top3"]
        answers[k] = a

    return {"success": True, "result": {"result": {"answers": answers}}}


@app.get("/healthz")
async def healthz():
    return {
        "ok": True, "model": "guard-mgte",
        "concurrency": CONCURRENCY, "threads": THREADS,
        "waiting": _stats["queued"],
        "served": _stats["served"], "texts": _stats["texts"],
        "avg_ms_per_request": round(_stats["infer_ms"] / _stats["served"], 1) if _stats["served"] else 0,
    }
