-- 演示业务数据（租户 hospital-demo），用于 NL2SQL / 报表验证
SET client_encoding = 'UTF8';

DELETE FROM invoice        WHERE tenant_id = 'hospital-demo';
DELETE FROM purchase_order WHERE tenant_id = 'hospital-demo';
DELETE FROM consumption    WHERE tenant_id = 'hospital-demo';
DELETE FROM inventory      WHERE tenant_id = 'hospital-demo';
DELETE FROM department     WHERE tenant_id = 'hospital-demo';
DELETE FROM item           WHERE tenant_id = 'hospital-demo';
DELETE FROM supplier       WHERE tenant_id = 'hospital-demo';
DELETE FROM hospital       WHERE tenant_id = 'hospital-demo';

INSERT INTO hospital (id, tenant_id, name, level, region) VALUES
(100, 'hospital-demo', '仁和医院', '三级甲等', '上海');

INSERT INTO department (id, tenant_id, hospital_id, name) VALUES
(101, 'hospital-demo', 100, '内科'),
(102, 'hospital-demo', 100, '外科'),
(103, 'hospital-demo', 100, '药剂科'),
(104, 'hospital-demo', 100, '检验科');

INSERT INTO supplier (id, tenant_id, name, contract_id, fulfillment_rate) VALUES
(301, 'hospital-demo', '华康医疗', 'HT-2026-001', 98.50),
(302, 'hospital-demo', '瑞达生物', 'HT-2026-002', 92.00),
(303, 'hospital-demo', '康泰器械', 'HT-2026-003', 88.00);

INSERT INTO item (id, tenant_id, name, category, spec, unit_price, sku) VALUES
(201, 'hospital-demo', 'N95口罩',     '防护耗材', '头戴式',   2.50,  'SKU-MASK-001'),
(202, 'hospital-demo', '一次性注射器', '注射耗材', '5ml',      1.20,  'SKU-SYR-002'),
(203, 'hospital-demo', '生理盐水',    '输液耗材', '500ml',    4.80,  'SKU-SAL-003'),
(204, 'hospital-demo', '医用纱布',    '敷料耗材', '10x10cm',  3.60,  'SKU-GAU-004'),
(205, 'hospital-demo', '静脉输液器',  '输液耗材', '标准型',   6.50,  'SKU-INF-005'),
(206, 'hospital-demo', '血常规试剂',  '检验试剂', '200人份',  12.00, 'SKU-REA-006');

INSERT INTO inventory (id, tenant_id, hospital_id, item_id, batch_no, qty, expiry_date) VALUES
(401, 'hospital-demo', 100, 201, 'B20260601', 12000, '2027-06-30'),
(402, 'hospital-demo', 100, 202, 'B20260701',  8500, '2027-08-31'),
(403, 'hospital-demo', 100, 203, 'B20260401',  3200, '2027-03-31'),
(404, 'hospital-demo', 100, 204, 'B20251201',  1500, '2026-12-31'),
(405, 'hospital-demo', 100, 205, 'B20260501',  2400, '2027-05-31'),
(406, 'hospital-demo', 100, 206, 'B20251101',   800, '2026-11-30'),
(407, 'hospital-demo', 100, 201, 'B20260901',  5000, '2027-09-30');

INSERT INTO purchase_order (id, tenant_id, hospital_id, supplier_id, status, amount, order_date) VALUES
(501, 'hospital-demo', 100, 301, '已完成', 128000.00, '2026-06-15'),
(502, 'hospital-demo', 100, 302, '已完成',  96500.00, '2026-06-28'),
(503, 'hospital-demo', 100, 301, '已完成', 142000.00, '2026-07-18'),
(504, 'hospital-demo', 100, 303, '已完成',  78000.00, '2026-07-25'),
(505, 'hospital-demo', 100, 302, '已完成', 156000.00, '2026-08-12'),
(506, 'hospital-demo', 100, 301, '已完成', 110000.00, '2026-08-30'),
(507, 'hospital-demo', 100, 303, '已完成', 132500.00, '2026-09-10'),
(508, 'hospital-demo', 100, 301, '已完成',  98000.00, '2026-09-22'),
(509, 'hospital-demo', 100, 302, '已完成', 175000.00, '2026-10-08'),
(510, 'hospital-demo', 100, 303, '已完成',  89000.00, '2026-10-20'),
(511, 'hospital-demo', 100, 301, '已下单', 125000.00, '2026-11-03'),
(512, 'hospital-demo', 100, 302, '已下单',  64000.00, '2026-11-06');

INSERT INTO consumption (id, tenant_id, hospital_id, dept_id, item_id, qty, amount, consume_date) VALUES
(601, 'hospital-demo', 100, 101, 201, 400, 1000.00, '2026-09-05'),
(602, 'hospital-demo', 100, 102, 201, 600, 1500.00, '2026-09-12'),
(603, 'hospital-demo', 100, 101, 203, 300, 1440.00, '2026-09-20'),
(604, 'hospital-demo', 100, 102, 202, 800,  960.00, '2026-10-02'),
(605, 'hospital-demo', 100, 103, 203, 700, 3360.00, '2026-10-10'),
(606, 'hospital-demo', 100, 104, 206, 200, 2400.00, '2026-10-15'),
(607, 'hospital-demo', 100, 101, 201, 350,  875.00, '2026-10-25'),
(608, 'hospital-demo', 100, 102, 204, 500, 1800.00, '2026-11-01'),
(609, 'hospital-demo', 100, 103, 205, 300, 1950.00, '2026-11-04'),
(610, 'hospital-demo', 100, 104, 206, 150, 1800.00, '2026-11-06'),
(611, 'hospital-demo', 100, 101, 205, 200, 1300.00, '2026-11-07'),
(612, 'hospital-demo', 100, 102, 201, 450, 1125.00, '2026-11-08');

INSERT INTO invoice (id, tenant_id, hospital_id, supplier_id, amount, status) VALUES
(701, 'hospital-demo', 100, 301, 128000.00, '已开票'),
(702, 'hospital-demo', 100, 302,  96500.00, '已开票'),
(703, 'hospital-demo', 100, 303,  78000.00, '待开票');

-- 推进序列，避免后续自增主键冲突
SELECT setval('hospital_id_seq',       100, true);
SELECT setval('department_id_seq',     104, true);
SELECT setval('supplier_id_seq',       303, true);
SELECT setval('item_id_seq',           206, true);
SELECT setval('inventory_id_seq',      407, true);
SELECT setval('purchase_order_id_seq', 512, true);
SELECT setval('consumption_id_seq',    612, true);
SELECT setval('invoice_id_seq',        703, true);
