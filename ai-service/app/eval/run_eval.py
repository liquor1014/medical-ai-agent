"""Day 8 评测脚本：Recall@5 / SQL 执行准确率 / 答案准确率 / P95。

用法（在 ai-service 目录下执行）：
    python -m app.eval.seed_eval_corpus          # 首次或重置评测语料
    python -m app.eval.run_eval                  # 默认写 data/eval/eval_results_v1.json
    python -m app.eval.run_eval --out data/eval/eval_results_v1_repeat.json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import platform
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg

from app.agents.nl2sql.nl2sql_agent import ExecutionError, execute_sql, run_nl2sql
from app.agents.nl2sql.sql_guard import GuardError, guard_sql
from app.agents.retrieval.retrieval_agent import (
    _extract_keywords,
    format_context,
    retrieve,
)
from app.agents.router.router_agent import Intent, classify
from app.config import settings
from app.llm.providers import llm

logging.basicConfig(level=logging.WARNING)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = REPO_ROOT / "data" / "eval" / "eval_v1.jsonl"
DEFAULT_OUT = REPO_ROOT / "data" / "eval" / "eval_results_v1.json"

TOP_K = 5


def load_dataset(path: Path) -> list[dict]:
    items = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm_value(value):
    """数值/日期归一化，消除 Decimal 与 float 的表示差异。"""
    if isinstance(value, Decimal):
        return round(float(value), 2)
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row_key(row: list) -> tuple:
    return tuple(_norm_value(v) for v in row)


def result_sets_equal(
    gen_columns: list[str], gen_rows: list[dict],
    gold_columns: list[str], gold_rows: list[dict],
) -> tuple[bool, str]:
    """比较两个结果集：忽略列名与行序，按行多重集合比较。"""
    if len(gen_columns) != len(gold_columns):
        return False, f"列数不一致: 生成 {len(gen_columns)} / 标准 {len(gold_columns)}"
    gen_set = sorted(_row_key([r[c] for c in gen_columns]) for r in gen_rows)
    gold_set = sorted(_row_key([r[c] for c in gold_columns]) for r in gold_rows)
    if gen_set != gold_set:
        return False, f"结果行不一致: 生成 {len(gen_set)} 行 / 标准 {len(gold_set)} 行"
    return True, ""


def percentile(values: list[float], p: float) -> float:
    """最近秩法计算分位数。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, math.ceil(p / 100 * len(ordered)) - 1)
    return round(ordered[idx], 1)


def latency_stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 1),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": round(max(values), 1),
    }


def _normalize_text(text: str) -> str:
    return "".join(text.lower().split())


def keyword_coverage(answer: str, patterns: list[str]) -> tuple[float, list[str]]:
    """关键词覆盖率：每个 pattern 用 | 分隔同义写法，命中任一即算通过。"""
    text = _normalize_text(answer)
    missing = []
    for pattern in patterns:
        alternatives = [_normalize_text(p) for p in pattern.split("|") if p.strip()]
        if not any(alt in text for alt in alternatives):
            missing.append(pattern)
    total = len(patterns) or 1
    return round((total - len(missing)) / total, 3), missing


def _gold_result(item: dict) -> tuple[list[str], list[dict]]:
    guarded = guard_sql(item["gold_sql"], item["tenant_id"])
    return execute_sql(guarded)


def _overlap_top_ids(question: str, tenant_id: str, top_k: int = TOP_K) -> list[int]:
    """诊断用：按关键词命中数排序的检索结果（不改动生产检索实现）。"""
    keywords = _extract_keywords(question)
    if not keywords:
        return []
    conditions = " OR ".join(["content ILIKE %s"] * len(keywords))
    params = [f"%{kw}%" for kw in keywords] + [tenant_id]
    with psycopg.connect(settings.postgres_dsn) as conn:
        rows = conn.execute(
            f"SELECT id, content FROM document_chunk "
            f"WHERE ({conditions}) AND tenant_id = %s",
            params,
        ).fetchall()
    scored = [
        (sum(1 for kw in keywords if kw.lower() in content.lower()), cid)
        for cid, content in rows
    ]
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [cid for _, cid in scored[:top_k]]


async def eval_retrieval(item: dict) -> dict:
    started = time.perf_counter()
    chunks = await asyncio.to_thread(retrieve, item["question"], item["tenant_id"], TOP_K)
    latency = (time.perf_counter() - started) * 1000
    got_ids = [c["id"] for c in chunks]
    gold_ids = set(item["gold_chunk_ids"])
    hit_ids = [i for i in got_ids if i in gold_ids]
    recall = round(len(hit_ids) / len(gold_ids), 3) if gold_ids else 0.0

    overlap_ids = await asyncio.to_thread(
        _overlap_top_ids, item["question"], item["tenant_id"], TOP_K
    )
    overlap_hits = [i for i in overlap_ids if i in gold_ids]
    overlap_recall = round(len(overlap_hits) / len(gold_ids), 3) if gold_ids else 0.0

    return {
        "passed": bool(hit_ids),
        "score": recall,
        "latency_ms": round(latency, 1),
        "detail": {
            "retrieved_ids": got_ids,
            "gold_ids": sorted(gold_ids),
            "hit_ids": hit_ids,
            "diagnostic_overlap_ids": overlap_ids,
            "diagnostic_overlap_recall": overlap_recall,
        },
    }


async def eval_sql(item: dict) -> dict:
    trace_id = f"eval-{item['id']}-{time.time_ns()}"
    started = time.perf_counter()
    try:
        gold_columns, gold_rows = await asyncio.to_thread(_gold_result, item)
    except (GuardError, ExecutionError) as e:
        return {
            "passed": False,
            "score": 0.0,
            "latency_ms": 0.0,
            "error": f"标准 SQL 执行失败: {e}",
            "detail": {},
        }

    result = await run_nl2sql(item["question"], item["tenant_id"], trace_id=trace_id)
    latency = (time.perf_counter() - started) * 1000
    trace = llm.get_trace(trace_id) or {}

    if result["status"] != "success":
        return {
            "passed": False,
            "score": 0.0,
            "latency_ms": round(latency, 1),
            "model": trace.get("provider"),
            "error": result.get("answer", "")[:200],
            "detail": {"generated_sql": result.get("sql", "")},
        }

    equal, reason = result_sets_equal(
        result["columns"], result["rows"], gold_columns, gold_rows
    )
    return {
        "passed": equal,
        "score": 1.0 if equal else 0.0,
        "latency_ms": round(latency, 1),
        "model": trace.get("provider"),
        "error": reason if not equal else "",
        "detail": {
            "generated_sql": result["sql"],
            "gold_sql": item["gold_sql"],
            "generated_rows": result["rows"][:3],
            "gold_rows": gold_rows[:3],
        },
    }


async def eval_answer(item: dict) -> dict:
    """答案准确率：走 RAG 答题路径（检索 → LLM 生成），排除意图路由影响。"""
    trace_id = f"eval-{item['id']}-{time.time_ns()}"
    started = time.perf_counter()
    chunks = await asyncio.to_thread(retrieve, item["question"], item["tenant_id"], TOP_K)
    context = format_context(chunks)
    messages = [
        {"role": "system", "content": "你是医疗物资管理智能助手，基于文档内容回答问题，必须引用来源。"},
        {"role": "user", "content": item["question"]},
    ]
    answer = ""
    async for token in llm.chat_stream(
        messages, context, task="chat", tenant_id=item["tenant_id"], trace_id=trace_id
    ):
        answer += token
    latency = (time.perf_counter() - started) * 1000
    coverage, missing = keyword_coverage(answer, item["expected_keywords"])
    trace = llm.get_trace(trace_id) or {}
    return {
        "passed": coverage >= 1.0,
        "score": coverage,
        "latency_ms": round(latency, 1),
        "model": trace.get("provider"),
        "detail": {
            "intent": classify(item["question"]).value,
            "answer": answer[:500],
            "missing_keywords": missing,
            "citation_ids": [c.get("id") for c in chunks],
        },
    }


async def run(dataset: Path, out: Path) -> dict:
    items = load_dataset(dataset)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    results = []

    for idx, item in enumerate(items, 1):
        kind = item["type"]
        try:
            if kind == "retrieval":
                res = await eval_retrieval(item)
            elif kind == "sql":
                res = await eval_sql(item)
            elif kind == "answer":
                res = await eval_answer(item)
            else:
                res = {"passed": False, "score": 0.0, "latency_ms": 0.0,
                       "error": f"未知题型: {kind}"}
        except Exception as e:  # 单条失败不中断整轮评测
            res = {"passed": False, "score": 0.0, "latency_ms": 0.0,
                   "error": f"{type(e).__name__}: {e}"}

        results.append({"id": item["id"], "type": kind,
                        "question": item["question"], **res})
        mark = "PASS" if res["passed"] else "FAIL"
        print(f"[{idx:3d}/{len(items)}] {item['id']} {kind:9s} {mark} "
              f"score={res['score']:.3f} {res['latency_ms']:.0f}ms"
              + (f" err={res.get('error', '')[:60]}" if not res["passed"] else ""),
              flush=True)

    by_type = {t: [r for r in results if r["type"] == t] for t in ("retrieval", "sql", "answer")}
    retrieval_items = by_type["retrieval"]
    sql_items = by_type["sql"]
    answer_items = by_type["answer"]

    recall_at_5 = round(
        sum(r["score"] for r in retrieval_items) / len(retrieval_items), 4
    ) if retrieval_items else 0.0
    hit_rate_at_5 = round(
        sum(1 for r in retrieval_items if r["passed"]) / len(retrieval_items), 4
    ) if retrieval_items else 0.0
    sql_accuracy = round(
        sum(1 for r in sql_items if r["passed"]) / len(sql_items), 4
    ) if sql_items else 0.0
    answer_accuracy = round(
        sum(1 for r in answer_items if r["passed"]) / len(answer_items), 4
    ) if answer_items else 0.0
    answer_coverage = round(
        sum(r["score"] for r in answer_items) / len(answer_items), 4
    ) if answer_items else 0.0
    overlap_recall = round(
        sum(r["detail"]["diagnostic_overlap_recall"] for r in retrieval_items)
        / len(retrieval_items), 4
    ) if retrieval_items else 0.0
    sql_routing = round(
        sum(1 for r in sql_items if classify(r["question"]) == Intent.NL2SQL) / len(sql_items), 4
    ) if sql_items else 0.0
    answer_routing = round(
        sum(1 for r in answer_items if classify(r["question"]) == Intent.RETRIEVAL)
        / len(answer_items), 4
    ) if answer_items else 0.0
    retrieval_routing = round(
        sum(1 for r in retrieval_items if classify(r["question"]) == Intent.RETRIEVAL)
        / len(retrieval_items), 4
    ) if retrieval_items else 0.0

    summary = {
        "item_count": len(results),
        "recall_at_5": recall_at_5,
        "retrieval_hit_rate_at_5": hit_rate_at_5,
        "sql_execution_accuracy": sql_accuracy,
        "answer_accuracy": answer_accuracy,
        "answer_mean_keyword_coverage": answer_coverage,
        "diagnostic_recall_at_5_by_keyword_overlap": overlap_recall,
        "routing_accuracy": {
            "sql_expected_nl2sql": sql_routing,
            "answer_expected_retrieval": answer_routing,
            "retrieval_expected_retrieval": retrieval_routing,
        },
        "latency_ms": latency_stats([r["latency_ms"] for r in results]),
        "latency_by_type_ms": {
            t: latency_stats([r["latency_ms"] for r in items_]) for t, items_ in by_type.items()
        },
        "passed_by_type": {
            t: sum(1 for r in items_ if r["passed"]) for t, items_ in by_type.items()
        },
        "failed_by_type": {
            t: sum(1 for r in items_ if not r["passed"]) for t, items_ in by_type.items()
        },
    }

    payload = {
        "meta": {
            "run_id": run_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dataset": str(dataset),
            "dataset_sha256": sha256_of(dataset),
            "dataset_items": len(items),
            "top_k": TOP_K,
            "tenant_ids": sorted({i["tenant_id"] for i in items}),
            "python": platform.python_version(),
            "model_routes": {
                "chat": getattr(settings, "llm_route_chat", ""),
                "nl2sql": getattr(settings, "llm_route_nl2sql", ""),
                "report": getattr(settings, "llm_route_report", ""),
            },
            "models_seen": sorted({r.get("model") for r in results if r.get("model")}),
        },
        "summary": summary,
        "items": results,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n结果已写入: {out}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="医疗 Agent Day 8 评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.dataset.exists():
        print(f"数据集不存在: {args.dataset}", file=sys.stderr)
        return 1
    asyncio.run(run(args.dataset, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
