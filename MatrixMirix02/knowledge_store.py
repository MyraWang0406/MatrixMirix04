"""
复盘知识库：结构 → 指标表现 → 适用场景（换人不断）。
SQLite 持久化。
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
    """初始化表结构"""
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
            motivation_bucket TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            exp_id TEXT PRIMARY KEY,
            card_id TEXT,
            created_at TEXT,
            channel TEXT,
            objective TEXT,
            os TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS variant_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            variant_id TEXT,
            os TEXT,
            impressions INTEGER,
            installs INTEGER,
            spend REAL,
            ipm REAL,
            cpi REAL,
            early_roas REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            failure_type TEXT,
            primary_signal TEXT,
            next_action TEXT,
            detail TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS element_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            element_type TEXT,
            element_value TEXT,
            avg_ipm_delta REAL,
            avg_cpi_delta REAL,
            confidence TEXT,
            cross_os TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exp_id TEXT,
            summary_action TEXT,
            scale_step TEXT,
            stop_loss TEXT,
            risk_notes TEXT
        )
    """)

    for t in ("variant_metrics", "diagnosis", "element_scores", "decisions"):
        c.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_exp_id ON {t}(exp_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_experiments_card ON experiments(card_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cards_vertical ON cards(vertical)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cards_mb ON cards(motivation_bucket)")

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
    """
    将一次评测结果写入知识库。返回 exp_id。
    """
    init_schema()
    conn = _get_conn()
    exp_id = _next_exp_id()
    now = datetime.now().isoformat()

    try:
        c = conn.cursor()
        # cards
        c.execute(
            "INSERT OR REPLACE INTO cards (card_id, version, vertical, country, segment, motivation_bucket, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                getattr(card, "card_id", ""),
                getattr(card, "version", "1.0"),
                getattr(card, "vertical", ""),
                getattr(card, "country", ""),
                getattr(card, "segment", ""),
                getattr(card, "motivation_bucket", ""),
                now,
            ),
        )
        # experiments
        c.execute(
            "INSERT INTO experiments (exp_id, card_id, created_at, channel, objective, os) VALUES (?,?,?,?,?,?)",
            (exp_id, getattr(card, "card_id", ""), now, "app_demo", getattr(card, "objective", "install"), "all"),
        )
        # variant_metrics
        for m in metrics or []:
            obj = m if hasattr(m, "variant_id") else type("M", (), m)()
            c.execute(
                "INSERT INTO variant_metrics (exp_id, variant_id, os, impressions, installs, spend, ipm, cpi, early_roas) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    exp_id,
                    getattr(obj, "variant_id", ""),
                    getattr(obj, "os", ""),
                    getattr(obj, "impressions", 0),
                    getattr(obj, "installs", 0),
                    getattr(obj, "spend", 0),
                    getattr(obj, "ipm", 0),
                    getattr(obj, "cpi", 0),
                    getattr(obj, "early_roas", 0),
                ),
            )
        # diagnosis
        if diagnosis:
            diag = diagnosis
            ft = ""
            ps = ""
            na = ""
            detail = ""
            if hasattr(diag, "failure_type"):
                ft = getattr(diag, "failure_type", "")
                ps = getattr(diag, "primary_signal", "")
                detail = getattr(diag, "detail", "")
                ra = getattr(diag, "recommended_actions", []) or []
                na = ra[0].action if ra and hasattr(ra[0], "action") else ""
            elif isinstance(diag, dict):
                ft = diag.get("failure_type", "")
                ps = diag.get("primary_signal", "")
                detail = diag.get("detail", "")
                ra = diag.get("recommended_actions", []) or []
                na = ra[0].get("action", "") if ra else ""
            c.execute(
                "INSERT INTO diagnosis (exp_id, failure_type, primary_signal, next_action, detail) VALUES (?,?,?,?,?)",
                (exp_id, ft, ps, na, detail),
            )
        # element_scores
        for s in element_scores or []:
            obj = s if hasattr(s, "element_type") else type("S", (), s)()
            c.execute(
                "INSERT INTO element_scores (exp_id, element_type, element_value, avg_ipm_delta, avg_cpi_delta, confidence, cross_os) VALUES (?,?,?,?,?,?,?)",
                (
                    exp_id,
                    getattr(obj, "element_type", ""),
                    getattr(obj, "element_value", ""),
                    getattr(obj, "avg_IPM_delta_vs_card_mean", 0) or getattr(obj, "avg_ipm_delta", 0),
                    getattr(obj, "avg_CPI_delta_vs_card_mean", 0) or getattr(obj, "avg_cpi_delta", 0),
                    getattr(obj, "confidence_level", ""),
                    getattr(obj, "cross_os_consistency", ""),
                ),
            )
        # decisions
        d = decision_summary or {}
        risk = d.get("risk", "")
        if isinstance(risk, list):
            risk = json.dumps(risk, ensure_ascii=False)
        c.execute(
            "INSERT INTO decisions (exp_id, summary_action, scale_step, stop_loss, risk_notes) VALUES (?,?,?,?,?)",
            (exp_id, d.get("next_step", ""), "", "", risk),
        )
        conn.commit()
    finally:
        conn.close()
    return exp_id


def query_review(
    vertical: str | None = None,
    motivation_bucket: str | None = None,
    segment: str | None = None,
    os_filter: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    复盘检索：按 vertical/motivation_bucket/segment/os 查询。
    返回：结构胜率、failure_type 分布、Top underperform elements。
    """
    init_schema()
    conn = _get_conn()
    try:
        c = conn.cursor()
        where_parts: list[str] = []
        params: list[Any] = []
        if vertical:
            where_parts.append("c.vertical=?")
            params.append(vertical)
        if motivation_bucket:
            where_parts.append("c.motivation_bucket=?")
            params.append(motivation_bucket)
        if segment:
            where_parts.append("c.segment LIKE ?")
            params.append(f"%{segment}%")
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"

        # 实验列表（join cards 以筛选）
        c.execute(
            f"""
            SELECT e.exp_id, d.failure_type
            FROM experiments e
            LEFT JOIN cards c ON e.card_id=c.card_id
            LEFT JOIN diagnosis d ON e.exp_id=d.exp_id
            WHERE {where_sql}
            LIMIT ?
            """,
            params + [limit],
        )
        rows = c.fetchall()
        total = len(rows)
        exp_pass = 0
        val_pass = 0
        for row in rows:
            ft = row["failure_type"] or ""
            if ft in ("", "INCONCLUSIVE"):
                val_pass += 1
            if ft not in ("EFFICIENCY_FAIL", "QUALITY_FAIL", "HANDOFF_MISMATCH", "OS_DIVERGENCE", "MIXED_SIGNALS"):
                exp_pass += 1
        explore_pass_rate = exp_pass / total if total else 0
        validate_pass_rate = val_pass / total if total else 0

        # failure_type 分布
        c.execute(
            f"""
            SELECT d.failure_type, COUNT(*) as cnt
            FROM diagnosis d
            JOIN experiments e ON d.exp_id=e.exp_id
            LEFT JOIN cards c ON e.card_id=c.card_id
            WHERE {where_sql}
            GROUP BY d.failure_type
            """,
            params,
        )
        failure_dist = {str(row["failure_type"] or "_empty"): row["cnt"] for row in c.fetchall()}

        # Top underperform elements
        c.execute(
            f"""
            SELECT es.element_type, es.element_value, es.avg_ipm_delta, es.avg_cpi_delta
            FROM element_scores es
            JOIN experiments e ON es.exp_id=e.exp_id
            LEFT JOIN cards c ON e.card_id=c.card_id
            WHERE {where_sql} AND (es.avg_ipm_delta < 0 OR es.avg_cpi_delta > 0)
            """,
            params,
        )
        elem_rows = c.fetchall()
        underperform: list[dict] = []
        for r in elem_rows:
            ipm_d = r["avg_ipm_delta"] or 0
            cpi_d = r["avg_cpi_delta"] or 0
            underperform.append({
                "element_type": r["element_type"] or "",
                "element_value": ((r["element_value"] or "")[:50]),
                "avg_ipm_delta": ipm_d,
                "avg_cpi_delta": cpi_d,
            })
        underperform.sort(key=lambda x: (-x["avg_cpi_delta"], x["avg_ipm_delta"]))
        top_underperform = underperform[:10]

        return {
            "explore_pass_rate": round(explore_pass_rate, 2),
            "validate_pass_rate": round(validate_pass_rate, 2),
            "total_experiments": total,
            "failure_type_distribution": failure_dist,
            "top_underperform_elements": top_underperform,
        }
    finally:
        conn.close()
