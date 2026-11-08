"""SQL Guard：NL2SQL 生成结果的安全校验与租户隔离注入。"""
from __future__ import annotations

import re

ALLOWED_TABLES = {
    "hospital",
    "department",
    "supplier",
    "item",
    "inventory",
    "purchase_order",
    "consumption",
    "invoice",
}

_FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "COPY", "VACUUM", "CALL", "EXECUTE", "MERGE",
    "UNION", "INTERSECT", "EXCEPT", "INTO", "WITH",
]
_FORBIDDEN_FUNCTIONS = [
    "pg_sleep", "pg_read_file", "pg_ls_dir", "lo_import", "lo_export",
    "dblink", "current_setting", "set_config", "pg_terminate_backend",
]
_FORBIDDEN_SCHEMAS = ["pg_catalog", "information_schema"]

_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# FROM/JOIN 后的表名，可选别名（不吞掉 WHERE/ON/GROUP 等关键字）
_TABLE_REF_PATTERN = re.compile(
    r"\b(FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?(?!WHERE\b|ON\b|GROUP\b|ORDER\b|LIMIT\b|HAVING\b|USING\b"
    r"|LEFT\b|RIGHT\b|INNER\b|OUTER\b|CROSS\b|NATURAL\b|JOIN\b)"
    r"([A-Za-z_][A-Za-z0-9_]*))?",
    re.IGNORECASE,
)

MAX_ROWS = 200


class GuardError(Exception):
    """SQL 未通过安全校验。"""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def guard_sql(raw_sql: str, tenant_id: str) -> str:
    """校验 SQL 并注入租户过滤，返回可直接执行的 SQL。

    Raises:
        GuardError: SQL 不合法或试图越权访问。
    """
    if not _TENANT_PATTERN.match(tenant_id or ""):
        raise GuardError(f"非法租户标识: {tenant_id!r}")
    if not raw_sql or not raw_sql.strip():
        raise GuardError("生成的 SQL 为空")

    sql = _strip_comments(raw_sql).strip()
    # 去掉代码块包裹残留
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
    sql = re.sub(r"\s*```$", "", sql)

    # 只允许单条语句
    sql = sql.rstrip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    if ";" in sql:
        raise GuardError("不允许多条 SQL 语句")

    if not re.match(r"^\s*SELECT\b", sql, flags=re.I):
        raise GuardError("只允许 SELECT 查询")

    upper = sql.upper()
    for kw in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper):
            raise GuardError(f"SQL 包含禁止关键字: {kw}")
    for fn in _FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{fn}\b", sql, flags=re.I):
            raise GuardError(f"SQL 包含禁止函数: {fn}")
    for schema in _FORBIDDEN_SCHEMAS:
        if re.search(rf"\b{schema}\b", sql, flags=re.I):
            raise GuardError(f"禁止访问系统 schema: {schema}")

    tables = {m.group(2).lower() for m in _TABLE_REF_PATTERN.finditer(sql)}
    if not tables:
        raise GuardError("SQL 未引用任何业务表")
    illegal = tables - ALLOWED_TABLES
    if illegal:
        raise GuardError(f"引用未授权表: {', '.join(sorted(illegal))}")

    # 注入租户过滤：将 FROM/JOIN table 改写为 FROM (SELECT * FROM table WHERE tenant_id = 'x') AS alias
    def _rewrite(match: re.Match) -> str:
        join_kw = match.group(1)
        table = match.group(2)
        alias = match.group(3) or table
        return (
            f"{join_kw} (SELECT * FROM {table} WHERE tenant_id = '{tenant_id}') AS {alias}"
        )

    guarded = _TABLE_REF_PATTERN.sub(_rewrite, sql)

    # 行数限制
    limit_match = re.search(r"\bLIMIT\s+(\d+)\s*$", guarded, flags=re.I)
    if limit_match:
        if int(limit_match.group(1)) > MAX_ROWS:
            guarded = guarded[: limit_match.start(1)] + str(MAX_ROWS) + guarded[limit_match.end(1):]
    else:
        guarded = f"{guarded} LIMIT {MAX_ROWS}"

    return guarded
