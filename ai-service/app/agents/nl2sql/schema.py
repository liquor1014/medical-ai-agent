"""NL2SQL 使用的业务表结构描述（供 LLM 生成 SQL 时参考）。"""
from __future__ import annotations

SCHEMA_DESCRIPTION = """
可用业务表（PostgreSQL，均已按租户隔离，无需自行添加 tenant_id 条件）：

hospital(id, name, level, region)                       -- 医院
department(id, hospital_id, name)                       -- 科室
supplier(id, name, contract_id, fulfillment_rate)       -- 供应商，fulfillment_rate 为履约率(0-100)
item(id, name, category, spec, unit_price, sku)         -- 物资，unit_price 为单价
inventory(id, hospital_id, item_id, batch_no, qty, expiry_date)   -- 库存，qty 为批次库存量
purchase_order(id, hospital_id, supplier_id, status, amount, order_date)  -- 采购订单，amount 为金额
consumption(id, hospital_id, dept_id, item_id, qty, amount, consume_date)  -- 科室消耗
invoice(id, hospital_id, supplier_id, amount, status, created_at)          -- 发票
"""

SQL_RULES = """
生成规则：
1. 只能生成一条以 SELECT 开头的查询语句，禁止 INSERT/UPDATE/DELETE/DDL/UNION/子查询外的写操作。
2. 禁止出现 tenant_id 条件（系统会自动注入租户过滤），禁止查询 pg_catalog / information_schema。
3. 只能使用上面列出的表和字段；中文列别名用双引号包裹，例如 "科室"。
4. 聚合查询需要写 GROUP BY；趋势类问题按月份聚合，使用 to_char(date_col, 'YYYY-MM')。
5. 结果行数不超过 100 行，必要时加 LIMIT。
6. 只输出 SQL 本身，不要输出解释、不要用 ``` 包裹。
"""



