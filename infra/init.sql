-- 医疗文件检索与报表统计 Agent — 初始 schema
-- 规则：所有业务表 / AI 表均带 tenant_id；Java 层做权限过滤，AI 层 SQL Guard 强制注入 tenant_id

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ========== 业务表 ==========

CREATE TABLE hospital (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  VARCHAR(64)  NOT NULL,
    name       VARCHAR(128) NOT NULL,
    level      VARCHAR(32),
    region     VARCHAR(64),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE department (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   VARCHAR(64)  NOT NULL,
    hospital_id BIGINT       NOT NULL REFERENCES hospital (id),
    name        VARCHAR(128) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE supplier (
    id               BIGSERIAL PRIMARY KEY,
    tenant_id        VARCHAR(64)  NOT NULL,
    name             VARCHAR(128) NOT NULL,
    contract_id      VARCHAR(64),
    fulfillment_rate NUMERIC(5, 2),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE item (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  VARCHAR(64)   NOT NULL,
    name       VARCHAR(128)  NOT NULL,
    category   VARCHAR(64),
    spec       VARCHAR(128),
    unit_price NUMERIC(14, 2),
    sku        VARCHAR(64)   NOT NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sku)
);

CREATE TABLE inventory (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   VARCHAR(64) NOT NULL,
    hospital_id BIGINT      NOT NULL REFERENCES hospital (id),
    item_id     BIGINT      NOT NULL REFERENCES item (id),
    batch_no    VARCHAR(64),
    qty         NUMERIC(14, 2) NOT NULL DEFAULT 0,
    expiry_date DATE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, hospital_id, item_id, batch_no)
);

CREATE TABLE purchase_order (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   VARCHAR(64) NOT NULL,
    hospital_id BIGINT      NOT NULL REFERENCES hospital (id),
    supplier_id BIGINT      NOT NULL REFERENCES supplier (id),
    status      VARCHAR(32) NOT NULL,
    amount      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    order_date  DATE        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE consumption (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    VARCHAR(64) NOT NULL,
    hospital_id  BIGINT      NOT NULL REFERENCES hospital (id),
    dept_id      BIGINT      NOT NULL REFERENCES department (id),
    item_id      BIGINT      NOT NULL REFERENCES item (id),
    qty          NUMERIC(14, 2) NOT NULL DEFAULT 0,
    amount       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    consume_date DATE        NOT NULL
);

CREATE TABLE invoice (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   VARCHAR(64) NOT NULL,
    hospital_id BIGINT      NOT NULL REFERENCES hospital (id),
    supplier_id BIGINT      NOT NULL REFERENCES supplier (id),
    amount      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    status      VARCHAR(32) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== 认证表 ==========

CREATE TABLE app_user (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     VARCHAR(64)  NOT NULL,
    username      VARCHAR(64)  NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    display_name  VARCHAR(128),
    role          VARCHAR(32)  NOT NULL DEFAULT 'doctor',
    status        VARCHAR(16)  NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, username)
);

-- 内置演示账号（密码使用 BCrypt）
INSERT INTO app_user (tenant_id, username, password_hash, display_name, role)
VALUES ('hospital-demo', 'admin', crypt('admin123', gen_salt('bf', 10)), '系统管理员', 'admin')
ON CONFLICT (tenant_id, username) DO NOTHING;

INSERT INTO app_user (tenant_id, username, password_hash, display_name, role)
VALUES ('hospital-demo', 'doctor', crypt('doctor123', gen_salt('bf', 10)), '演示医生', 'doctor')
ON CONFLICT (tenant_id, username) DO NOTHING;

-- ========== AI 表 ==========

CREATE TABLE document (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   VARCHAR(64)  NOT NULL,
    file_name   VARCHAR(256) NOT NULL,
    object_key  VARCHAR(512) NOT NULL,
    doc_type    VARCHAR(32)  NOT NULL DEFAULT 'unknown',
    status      VARCHAR(32)  NOT NULL DEFAULT 'pending',
    page_count  INT          NOT NULL DEFAULT 0,
    chunk_count INT          NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE document_chunk (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    VARCHAR(64) NOT NULL,
    doc_id       BIGINT      NOT NULL REFERENCES document (id) ON DELETE CASCADE,
    page_no      INT         NOT NULL DEFAULT 1,
    section      VARCHAR(256),
    content      TEXT        NOT NULL,
    embedding_id UUID,
    chunk_type   VARCHAR(16) NOT NULL DEFAULT 'text',
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_session (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  VARCHAR(64) NOT NULL,
    user_id    BIGINT      NOT NULL,
    title      VARCHAR(256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE message (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  VARCHAR(64) NOT NULL,
    session_id BIGINT      NOT NULL REFERENCES chat_session (id) ON DELETE CASCADE,
    role       VARCHAR(16) NOT NULL,
    content    TEXT        NOT NULL,
    citations  JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE report_query (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  VARCHAR(64) NOT NULL,
    user_id    BIGINT      NOT NULL,
    question   TEXT        NOT NULL,
    sql        TEXT,
    status     VARCHAR(32) NOT NULL DEFAULT 'pending',
    chart_type VARCHAR(32),
    result     JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  VARCHAR(64) NOT NULL,
    user_id    BIGINT      NOT NULL,
    action     VARCHAR(64) NOT NULL,
    sql_hash   VARCHAR(64),
    result     VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_call_log (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      VARCHAR(64) NOT NULL,
    provider       VARCHAR(64),
    model          VARCHAR(64) NOT NULL,
    task_type      VARCHAR(32),
    trace_id       VARCHAR(64),
    tokens         INT         NOT NULL DEFAULT 0,
    latency_ms     INT         NOT NULL DEFAULT 0,
    first_token_ms INT         NOT NULL DEFAULT 0,
    cost           NUMERIC(10, 6) NOT NULL DEFAULT 0,
    status         VARCHAR(32) NOT NULL DEFAULT 'success',
    error          TEXT,
    fallback_from  VARCHAR(64),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== 索引 ==========

CREATE INDEX idx_app_user_tenant ON app_user (tenant_id, username);
CREATE INDEX idx_department_tenant ON department (tenant_id, hospital_id);
CREATE INDEX idx_inventory_tenant ON inventory (tenant_id, hospital_id, item_id);
CREATE INDEX idx_consumption_tenant ON consumption (tenant_id, consume_date, dept_id);
CREATE INDEX idx_purchase_order_tenant ON purchase_order (tenant_id, order_date);
CREATE INDEX idx_document_tenant_status ON document (tenant_id, status);
CREATE INDEX idx_chunk_doc ON document_chunk (doc_id, page_no);
CREATE INDEX idx_message_session ON message (session_id, created_at);
CREATE INDEX idx_report_query_tenant ON report_query (tenant_id, created_at);
CREATE INDEX idx_audit_log_tenant ON audit_log (tenant_id, created_at);
CREATE INDEX idx_model_call_log_tenant ON model_call_log (tenant_id, created_at);
CREATE INDEX idx_model_call_log_trace ON model_call_log (trace_id);
CREATE INDEX idx_model_call_log_status ON model_call_log (status, created_at);
