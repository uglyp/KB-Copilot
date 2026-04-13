"""校验 NL 生成或工具层 SQL 仅为只读 SELECT（单语句）。"""

from __future__ import annotations

import re

import sqlparse
from sqlparse.sql import Statement, Token
from sqlparse.tokens import DML


def assert_select_only(sql: str) -> None:
    """拒绝非 SELECT 或多语句。用于管理员 NL2SQL 执行前兜底（视图已脱敏，仍需防删改）。"""
    raw = (sql or "").strip()
    if not raw:
        raise ValueError("SQL 为空")
    # 去掉末尾分号后解析
    stripped = raw.rstrip().rstrip(";")
    parts = [p for p in sqlparse.split(stripped) if p.strip()]
    if len(parts) != 1:
        raise ValueError("仅允许单条 SQL 语句")
    parsed = sqlparse.parse(stripped)
    if not parsed:
        raise ValueError("无法解析 SQL")
    stmt: Statement = parsed[0]
    first = _first_meaningful_token(stmt)
    if first is None or first.ttype != DML or first.value.upper() != "SELECT":
        raise ValueError("仅允许 SELECT")
    lowered = stripped.lower()
    if re.search(r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b", lowered):
        raise ValueError("检测到禁止的关键字")


def _first_meaningful_token(stmt: Statement) -> Token | None:
    for tok in stmt.flatten():
        if tok.ttype is None and str(tok.value).strip():
            return tok
        if tok.ttype is not None and tok.ttype != sqlparse.tokens.Whitespace:
            return tok
    return None
