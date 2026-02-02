"""
复盘知识库：结构 → 指标表现 → 适用场景（换人不断）。
SQLite 持久化，标准库 sqlite3。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "data" / "knowledge.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection | None = None) -> None:
    """初始化表结构（符合 spec）"""
    created = conn is None
    if conn is None:
        conn = _get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            card_id TEXT PRIMARY KEY,
            version TEXT,
            vertical TEXT,
            country TEXT,
            segment TEXT,
            os TEXT,
            channel TEXT,
            motivation_bucket TEXT,
            hook_type TEXT,
            why_now_trigger TEXT,
            cta TEXT,
            proof_points_json TEXT,
            handoff_expectation TEXT,
            provenance_json TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            exp_id TEXT PRIMARY KEY,
            card_id TEXT,
            created_at TEXT,
            vertical TEXT,
            channel TEXT,
            country TEXT,
            segment TEXT,
            motivation_bucket TEXT,
            objective TEXT,
            notes TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS variant_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            variant_id TEXT,
            os TEXT,
            window TEXT,
            impressions INTEGER,
            installs INTEGER,
            spend REAL,
            ipm REAL,
            cpi REAL,
            ctr REAL,
            early_roas REAL,
            updated_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            os_scope TEXT,
            failure_type TEXT,
            primary_signal TEXT,
            next_action TEXT,
            detail_json TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS element_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            element_type TEXT,
            element_value TEXT,
            metric TEXT,
            delta REAL,
            confidence TEXT,
            cross_os TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            action TEXT,
            scale_step TEXT,
            stop_loss TEXT,
            risk_notes TEXT,
            created_at TEXT
        )
    """)

    for t in ("variant_metrics", "diagnosis", "element_scores", "decisions"):
        c.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_exp_id ON {t}(exp_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_experiments_vertical ON experiments(vertical)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_experiments_channel ON experiments(channel)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cards_vertical ON cards(vertical)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cards_channel ON cards(channel)")

    conn.commit()
    if created:
        conn.close()


def _next_exp_id() -> str:
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM experiments")
        n = c.fetchone()[0]
        return f"exp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{n+1}"
    finally:
        conn.close()


def write_experiment(
    card: Any,
    variants: list[Any],
    metrics: list[Any],
    explore_ios: Any,
    explore_android: Any,
    validate_result: Any | None,
    diagnosis: Any | None,
    element_scores: list[Any],
    decision_summary: dict,
) -> str:
    """将一次评测结果写入知识库。"""
    init_schema()
    conn = _get_conn()
    exp_id = _next_exp_id()
    now = datetime.now().isoformat()

    try:
        c = conn.cursor()
        prov = {
            "source_channel": getattr(card, "source_channel", "") or getattr(card, "channel", ""),
            "source_country": getattr(card, "source_country", "") or getattr(card, "country", ""),
            "source_date": getattr(card, "source_date", ""),
            "source_ref": getattr(card, "source_ref", ""),
        }
        c.execute("""
            INSERT OR REPLACE INTO cards (card_id, version, vertical, country, segment, os, channel, motivation_bucket,
                hook_type, why_now_trigger, cta, proof_points_json, handoff_expectation, provenance_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            getattr(card, "card_id", ""),
            getattr(card, "version", "1.0"),
            getattr(card, "vertical", ""),
            getattr(card, "country", ""),
            getattr(card, "segment", ""),
            getattr(card, "os", "all"),
            getattr(card, "channel", "") or getattr(card, "source_channel", "") or "Meta",
            getattr(card, "motivation_bucket", ""),
            getattr(variants[0], "hook_type", "") if variants else "",
            getattr(card, "why_now_trigger", "") or getattr(card, "why_now_phrase", ""),
            getattr(variants[0], "cta_type", "") if variants else "",
            json.dumps(getattr(card, "proof_points", []) or [], ensure_ascii=False),
            getattr(card, "handoff_expectation", ""),
            json.dumps(prov, ensure_ascii=False),
            now,
        ))
        c.execute("""
            INSERT INTO experiments (exp_id, card_id, created_at, vertical, channel, country, segment, motivation_bucket, objective, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (exp_id, getattr(card, "card_id", ""), now, getattr(card, "vertical", ""),
              getattr(card, "channel", "") or getattr(card, "source_channel", "") or "Meta",
              getattr(card, "country", "") or "US", getattr(card, "segment", ""),
              getattr(card, "motivation_bucket", ""), getattr(card, "objective", "install"), ""))

        for m in metrics or []:
            obj = m if hasattr(m, "variant_id") else type("M", (), m)()
            c.execute("""
                INSERT INTO variant_metrics (exp_id, variant_id, os, window, impressions, installs, spend, ipm, cpi, ctr, early_roas, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                exp_id, getattr(obj, "variant_id", ""), getattr(obj, "os", ""), "Explore",
                getattr(obj, "impressions", 0), getattr(obj, "installs", 0), getattr(obj, "spend", 0),
                getattr(obj, "ipm", 0), getattr(obj, "cpi", 0), getattr(obj, "ctr", 0), getattr(obj, "early_roas", 0),
                now,
            ))

        if diagnosis:
            diag = diagnosis
            ft = ps = na = ""
            detail_dict = {}
            if hasattr(diag, "failure_type"):
                ft = getattr(diag, "failure_type", "")
                ps = getattr(diag, "primary_signal", "")
                na = getattr(diag, "recommended_actions", [{}])[0].action if getattr(diag, "recommended_actions", None) else ""
                detail_dict = {"detail": getattr(diag, "detail", "")}
            elif isinstance(diag, dict):
                ft = diag.get("failure_type", "")
                ps = diag.get("primary_signal", "")
                ra = diag.get("recommended_actions", []) or []
                na = ra[0].get("action", "") if ra else ""
                detail_dict = {"detail": diag.get("detail", "")}
            c.execute("""
                INSERT INTO diagnosis (exp_id, os_scope, failure_type, primary_signal, next_action, detail_json, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (exp_id, "all", ft, ps, na, json.dumps(detail_dict, ensure_ascii=False), now))

        for s in element_scores or []:
            obj = s if hasattr(s, "element_type") else type("S", (), s)()
            ipm_d = getattr(obj, "avg_IPM_delta_vs_card_mean", 0) or getattr(obj, "avg_ipm_delta", 0)
            cpi_d = getattr(obj, "avg_CPI_delta_vs_card_mean", 0) or getattr(obj, "avg_cpi_delta", 0)
            c.execute("""
                INSERT INTO element_scores (exp_id, element_type, element_value, metric, delta, confidence, cross_os, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (exp_id, getattr(obj, "element_type", ""), getattr(obj, "element_value", ""),
                  "IPM", ipm_d, getattr(obj, "confidence_level", ""), getattr(obj, "cross_os_consistency", ""), now))

        d = decision_summary or {}
        risk = d.get("risk", "")
        if isinstance(risk, list):
            risk = json.dumps(risk, ensure_ascii=False)
        c.execute("""
            INSERT INTO decisions (exp_id, action, scale_step, stop_loss, risk_notes, created_at)
            VALUES (?,?,?,?,?,?)
        """, (exp_id, d.get("next_step", ""), "", "", risk, now))

        conn.commit()
    finally:
        conn.close()
    return exp_id


def query_review(
    vertical: str | None = None,
    channel: str | None = None,
    country: str | None = None,
    segment: str | None = None,
    os_filter: str | None = None,
    motivation_bucket: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """
    复盘检索：按 vertical/channel/country/segment/os/motivation_bucket 筛选。
    返回：Explore PASS 率、Validate PASS 率、failure_type 分布、表现最稳结构 Top10。
    """
    init_schema()
    conn = _get_conn()
    try:
        c = conn.cursor()
        where_parts, params = [], []
        if vertical:
            where_parts.append("e.vertical=?")
            params.append(vertical)
        if channel:
            where_parts.append("e.channel=?")
            params.append(channel)
        if country:
            where_parts.append("e.country=?")
            params.append(country)
        if segment:
            where_parts.append("e.segment LIKE ?")
            params.append(f"%{segment}%")
        if motivation_bucket:
            where_parts.append("e.motivation_bucket LIKE ?")
            params.append(f"%{motivation_bucket}%")
        if os_filter:
            where_parts.append("e.exp_id IN (SELECT exp_id FROM variant_metrics WHERE os=?)")
            params.append(os_filter)
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"

        c.execute(f"""
            SELECT e.exp_id, d.failure_type, d.next_action
            FROM experiments e
            LEFT JOIN diagnosis d ON e.exp_id=d.exp_id
            WHERE {where_sql}
            LIMIT ?
        """, params + [limit])
        rows = c.fetchall()
        total = len(rows)
        exp_pass = val_pass = 0
        for row in rows:
            ft = row["failure_type"] or ""
            if ft in ("", "INCONCLUSIVE"):
                val_pass += 1
            if ft not in ("EFFICIENCY_FAIL", "QUALITY_FAIL", "HANDOFF_MISMATCH", "OS_DIVERGENCE", "MIXED_SIGNALS"):
                exp_pass += 1

        c.execute(f"""
            SELECT d.failure_type, COUNT(*) as cnt
            FROM diagnosis d
            JOIN experiments e ON d.exp_id=e.exp_id
            WHERE {where_sql}
            GROUP BY d.failure_type
        """, params)
        failure_dist = {str(row["failure_type"] or "_empty"): row["cnt"] for row in c.fetchall()}
        top3_failure = sorted(failure_dist.items(), key=lambda x: -x[1])[:3]

        c.execute(f"""
            SELECT e.card_id, e.vertical, e.channel, e.motivation_bucket,
                   SUM(CASE WHEN d.failure_type IS NULL OR d.failure_type NOT IN ('EFFICIENCY_FAIL','QUALITY_FAIL','HANDOFF_MISMATCH','OS_DIVERGENCE','MIXED_SIGNALS') THEN 1 ELSE 0 END) as pass_cnt,
                   COUNT(*) as total_cnt
            FROM experiments e
            LEFT JOIN diagnosis d ON e.exp_id=d.exp_id
            WHERE {where_sql}
            GROUP BY e.card_id, e.vertical, e.channel, e.motivation_bucket
            HAVING total_cnt >= 1
            ORDER BY pass_cnt DESC, total_cnt DESC
            LIMIT 10
        """, params)
        top_structures = [dict(row) for row in c.fetchall()]

        return {
            "explore_pass_rate": round(exp_pass / total, 2) if total else 0,
            "validate_pass_rate": round(val_pass / total, 2) if total else 0,
            "total_experiments": total,
            "failure_type_distribution": failure_dist,
            "top3_failure_type": top3_failure,
            "top_structures_by_pass": top_structures,
        }
    finally:
        conn.close()
