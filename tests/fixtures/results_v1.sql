BEGIN TRANSACTION;
CREATE TABLE checks (
    run_id   TEXT NOT NULL REFERENCES run_records (run_id),
    position INTEGER NOT NULL,
    name     TEXT NOT NULL,
    passed   INTEGER NOT NULL CHECK (passed IN (0, 1)),
    reason   TEXT NOT NULL,
    PRIMARY KEY (run_id, position)
);
INSERT INTO "checks" VALUES('3c84c7ddb42145f48fb650a2291bdec6',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('3c84c7ddb42145f48fb650a2291bdec6',1,'answer:number',1,'found 30 (the only number); matches expected 30');
INSERT INTO "checks" VALUES('3c84c7ddb42145f48fb650a2291bdec6',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('d9ab1686202a4322a2eedc287f45882d',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('d9ab1686202a4322a2eedc287f45882d',1,'answer:contains',1,'''June'' contains ''June''');
INSERT INTO "checks" VALUES('d9ab1686202a4322a2eedc287f45882d',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('abe6f7f2bd14450a92a684156bcc18dc',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('abe6f7f2bd14450a92a684156bcc18dc',1,'answer:number',1,'found 3 (the only number); matches expected 3');
INSERT INTO "checks" VALUES('abe6f7f2bd14450a92a684156bcc18dc',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('863c7a925a4a43eab9e12103df403b00',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('863c7a925a4a43eab9e12103df403b00',1,'answer:contains',1,'''Noise-Cancelling Headphones'' contains ''Noise-Cancelling Headphones''');
INSERT INTO "checks" VALUES('863c7a925a4a43eab9e12103df403b00',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('3cabb601934e40cc96a52a5a4d2b20eb',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('3cabb601934e40cc96a52a5a4d2b20eb',1,'answer:contains',1,'''Jaipur'' contains ''Jaipur''');
INSERT INTO "checks" VALUES('3cabb601934e40cc96a52a5a4d2b20eb',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('2be607467c1b4e1eaba5b02d9538880a',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('2be607467c1b4e1eaba5b02d9538880a',1,'answer:number',1,'found 268721 (the only number); matches expected 268721');
INSERT INTO "checks" VALUES('2be607467c1b4e1eaba5b02d9538880a',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('f661e418cc8f439e8470474cd30b4a4a',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('f661e418cc8f439e8470474cd30b4a4a',1,'answer:contains',1,'''Noise-Cancelling Headphones'' contains ''Noise-Cancelling Headphones''');
INSERT INTO "checks" VALUES('f661e418cc8f439e8470474cd30b4a4a',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('385e97c8315e4da0b6a8e8e484e6c77b',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('385e97c8315e4da0b6a8e8e484e6c77b',1,'answer:contains',1,'''Ananya Iyer'' contains ''Ananya Iyer''');
INSERT INTO "checks" VALUES('385e97c8315e4da0b6a8e8e484e6c77b',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('744708749fcf4747b3069a802441c22f',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('744708749fcf4747b3069a802441c22f',1,'answer:number',1,'found 23.8 (the only number); matches expected 23.8');
INSERT INTO "checks" VALUES('744708749fcf4747b3069a802441c22f',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('5d8de7db04d742e89010fd8c2cbe792d',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('5d8de7db04d742e89010fd8c2cbe792d',1,'answer:number',1,'found 16107 (the only number); matches expected 16107');
INSERT INTO "checks" VALUES('5d8de7db04d742e89010fd8c2cbe792d',2,'required_tools',1,'used: sql_query (2 successful call(s))');
INSERT INTO "checks" VALUES('225c8981a50244bb95dbee063935e4b0',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('225c8981a50244bb95dbee063935e4b0',1,'answer:number',1,'found 30 (the only number); matches expected 30');
INSERT INTO "checks" VALUES('225c8981a50244bb95dbee063935e4b0',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('148aae1ae20640bf9f5aefd63e3f7d4e',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('148aae1ae20640bf9f5aefd63e3f7d4e',1,'answer:contains',1,'''June'' contains ''June''');
INSERT INTO "checks" VALUES('148aae1ae20640bf9f5aefd63e3f7d4e',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('d805a0bddd8d4fa9aa448f552abd6ef2',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('d805a0bddd8d4fa9aa448f552abd6ef2',1,'answer:number',0,'found 0 (the only number); expected 3 (difference 3 > allowed 0)');
INSERT INTO "checks" VALUES('d805a0bddd8d4fa9aa448f552abd6ef2',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('ca6448e2772341caae32c07358056f81',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('ca6448e2772341caae32c07358056f81',1,'answer:contains',0,'''Smart Watch'' does not contain ''Noise-Cancelling Headphones'' as whole words');
INSERT INTO "checks" VALUES('ca6448e2772341caae32c07358056f81',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('06410cd86d8e45ab835a4c4fe954e059',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('06410cd86d8e45ab835a4c4fe954e059',1,'answer:contains',1,'''Jaipur'' contains ''Jaipur''');
INSERT INTO "checks" VALUES('06410cd86d8e45ab835a4c4fe954e059',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('f2afad4be8a14acea8695a5ce3bb0c3b',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('f2afad4be8a14acea8695a5ce3bb0c3b',1,'answer:number',1,'found 268721 (the only number); matches expected 268721');
INSERT INTO "checks" VALUES('f2afad4be8a14acea8695a5ce3bb0c3b',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('9d36678fb6bc473d8ed0bba80b0d4f58',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('9d36678fb6bc473d8ed0bba80b0d4f58',1,'answer:contains',0,'''Denim Jeans'' does not contain ''Noise-Cancelling Headphones'' as whole words');
INSERT INTO "checks" VALUES('9d36678fb6bc473d8ed0bba80b0d4f58',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('dc7677460fe84a1580fbc16746178632',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('dc7677460fe84a1580fbc16746178632',1,'answer:contains',1,'''Ananya Iyer'' contains ''Ananya Iyer''');
INSERT INTO "checks" VALUES('dc7677460fe84a1580fbc16746178632',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('3a4493eb32fd480aacc6ee684716438c',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('3a4493eb32fd480aacc6ee684716438c',1,'answer:number',0,'found -19.2 (the only number); expected 23.8 (difference 43 > allowed 0.05)');
INSERT INTO "checks" VALUES('3a4493eb32fd480aacc6ee684716438c',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('7b93fa97e84b4bfd9f60bb379c155612',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('7b93fa97e84b4bfd9f60bb379c155612',1,'answer:number',1,'found 16107 (the only number); matches expected 16107');
INSERT INTO "checks" VALUES('7b93fa97e84b4bfd9f60bb379c155612',2,'required_tools',1,'used: sql_query (2 successful call(s))');
INSERT INTO "checks" VALUES('00bbfb9809f14385b7e9c4091bdb9fe4',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('00bbfb9809f14385b7e9c4091bdb9fe4',1,'answer:number',1,'found 30 (the only number); matches expected 30');
INSERT INTO "checks" VALUES('00bbfb9809f14385b7e9c4091bdb9fe4',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('0dd6c842e79141fb853f5989ca8306ee',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('0dd6c842e79141fb853f5989ca8306ee',1,'answer:contains',1,'''June'' contains ''June''');
INSERT INTO "checks" VALUES('0dd6c842e79141fb853f5989ca8306ee',2,'required_tools',1,'used: sql_query (1 successful call(s))');
CREATE TABLE run_records (
    run_id            TEXT PRIMARY KEY,
    suite_id          TEXT NOT NULL,
    position          INTEGER NOT NULL,
    task_id           TEXT NOT NULL,
    repeat_index      INTEGER NOT NULL CHECK (repeat_index >= 0),
    difficulty        TEXT,
    outcome           TEXT NOT NULL CHECK (outcome IN ('passed', 'failed', 'infra_error')),
    status            TEXT NOT NULL,
    final_answer      TEXT,
    duration_seconds  REAL NOT NULL,
    error             TEXT,
    error_kind        TEXT,
    llm_calls         INTEGER NOT NULL,
    evaluation_passed INTEGER CHECK (evaluation_passed IN (0, 1)),  -- NULL = not evaluated
    FOREIGN KEY (suite_id, task_id) REFERENCES suite_tasks (suite_id, task_id),
    UNIQUE (suite_id, position),
    UNIQUE (suite_id, task_id, repeat_index)
);
INSERT INTO "run_records" VALUES('3c84c7ddb42145f48fb650a2291bdec6','2cf16c36de14452bb71b5adfdb68de85',0,'shop-001',0,'easy','passed','completed','30',4.150000004301546141e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('d9ab1686202a4322a2eedc287f45882d','2cf16c36de14452bb71b5adfdb68de85',1,'shop-002',0,'easy','passed','completed','June',6.32600000244565308e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('abe6f7f2bd14450a92a684156bcc18dc','2cf16c36de14452bb71b5adfdb68de85',2,'shop-003',0,'medium','passed','completed','3',0.000505199999679462,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('863c7a925a4a43eab9e12103df403b00','2cf16c36de14452bb71b5adfdb68de85',3,'shop-004',0,'medium','passed','completed','Noise-Cancelling Headphones',5.865000002813758329e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('3cabb601934e40cc96a52a5a4d2b20eb','2cf16c36de14452bb71b5adfdb68de85',4,'shop-005',0,'medium','passed','completed','Jaipur',9.143000006588408724e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('2be607467c1b4e1eaba5b02d9538880a','2cf16c36de14452bb71b5adfdb68de85',5,'shop-006',0,'medium','passed','completed','268721',1.232500000696745702e-03,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('f661e418cc8f439e8470474cd30b4a4a','2cf16c36de14452bb71b5adfdb68de85',6,'shop-007',0,'hard','passed','completed','Noise-Cancelling Headphones',1.255099999980302528e-03,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('385e97c8315e4da0b6a8e8e484e6c77b','2cf16c36de14452bb71b5adfdb68de85',7,'shop-008',0,'hard','passed','completed','Ananya Iyer',1.11169999945559539e-03,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('744708749fcf4747b3069a802441c22f','2cf16c36de14452bb71b5adfdb68de85',8,'shop-009',0,'hard','passed','completed','23.8',9.12999999854946509e-04,NULL,NULL,3,1);
INSERT INTO "run_records" VALUES('5d8de7db04d742e89010fd8c2cbe792d','2cf16c36de14452bb71b5adfdb68de85',9,'shop-010',0,'hard','passed','completed','16107',8.835999997245380654e-04,NULL,NULL,4,1);
INSERT INTO "run_records" VALUES('225c8981a50244bb95dbee063935e4b0','624fcdafc5794f0f997dc9b2747a2255',0,'shop-001',0,'easy','passed','completed','30',3.952000006393063814e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('148aae1ae20640bf9f5aefd63e3f7d4e','624fcdafc5794f0f997dc9b2747a2255',1,'shop-002',0,'easy','passed','completed','June',5.326000009517883881e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('d805a0bddd8d4fa9aa448f552abd6ef2','624fcdafc5794f0f997dc9b2747a2255',2,'shop-003',0,'medium','failed','completed','0',4.119999994145473466e-04,NULL,NULL,2,0);
INSERT INTO "run_records" VALUES('ca6448e2772341caae32c07358056f81','624fcdafc5794f0f997dc9b2747a2255',3,'shop-004',0,'medium','failed','completed','Smart Watch',5.811999999423278495e-04,NULL,NULL,2,0);
INSERT INTO "run_records" VALUES('06410cd86d8e45ab835a4c4fe954e059','624fcdafc5794f0f997dc9b2747a2255',4,'shop-005',0,'medium','passed','completed','Jaipur',3.87199999750009738e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('f2afad4be8a14acea8695a5ce3bb0c3b','624fcdafc5794f0f997dc9b2747a2255',5,'shop-006',0,'medium','passed','completed','268721',3.840999997919425369e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('9d36678fb6bc473d8ed0bba80b0d4f58','624fcdafc5794f0f997dc9b2747a2255',6,'shop-007',0,'hard','failed','completed','Denim Jeans',0.00065080000058515,NULL,NULL,2,0);
INSERT INTO "run_records" VALUES('dc7677460fe84a1580fbc16746178632','624fcdafc5794f0f997dc9b2747a2255',7,'shop-008',0,'hard','passed','completed','Ananya Iyer',6.539000005432171747e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('3a4493eb32fd480aacc6ee684716438c','624fcdafc5794f0f997dc9b2747a2255',8,'shop-009',0,'hard','failed','completed','-19.2',5.102999984956113622e-04,NULL,NULL,3,0);
INSERT INTO "run_records" VALUES('7b93fa97e84b4bfd9f60bb379c155612','624fcdafc5794f0f997dc9b2747a2255',9,'shop-010',0,'hard','passed','completed','16107',6.511999999929685145e-04,NULL,NULL,4,1);
INSERT INTO "run_records" VALUES('00bbfb9809f14385b7e9c4091bdb9fe4','18fbd8d9822342b098f577712791a459',0,'shop-001',0,'easy','passed','completed','30',2.644000014697667211e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('0dd6c842e79141fb853f5989ca8306ee','18fbd8d9822342b098f577712791a459',1,'shop-002',0,'easy','passed','completed','June',4.518999994616024196e-04,NULL,NULL,2,1);
INSERT INTO "run_records" VALUES('20a3c7d3f05b42998c6a57626fd8973d','18fbd8d9822342b098f577712791a459',2,'shop-003',0,'medium','infra_error','error',NULL,3.300000025774352253e-05,'daily quota','quota_exhausted',1,NULL);
CREATE TABLE skipped_runs (
    suite_id     TEXT NOT NULL REFERENCES suite_runs (suite_id),
    position     INTEGER NOT NULL,
    task_id      TEXT NOT NULL,
    repeat_index INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    PRIMARY KEY (suite_id, position),
    FOREIGN KEY (suite_id, task_id) REFERENCES suite_tasks (suite_id, task_id)
);
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',0,'shop-004',0,'quota_exhausted in shop-003');
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',1,'shop-005',0,'quota_exhausted in shop-003');
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',2,'shop-006',0,'quota_exhausted in shop-003');
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',3,'shop-007',0,'quota_exhausted in shop-003');
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',4,'shop-008',0,'quota_exhausted in shop-003');
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',5,'shop-009',0,'quota_exhausted in shop-003');
INSERT INTO "skipped_runs" VALUES('18fbd8d9822342b098f577712791a459',6,'shop-010',0,'quota_exhausted in shop-003');
CREATE TABLE steps (
    run_id              TEXT NOT NULL REFERENCES run_records (run_id),
    step_index          INTEGER NOT NULL CHECK (step_index >= 0),
    llm_output          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    tool_name           TEXT,                     -- NULL = this step called no tool
    tool_arguments_json TEXT,                     -- free-form arguments: JSON
    tool_output         TEXT,
    tool_error          TEXT,
    PRIMARY KEY (run_id, step_index),
    CHECK (tool_name IS NOT NULL
           OR (tool_arguments_json IS NULL AND tool_output IS NULL AND tool_error IS NULL))
);
INSERT INTO "steps" VALUES('3c84c7ddb42145f48fb650a2291bdec6',0,'','2026-11-13T07:00:31.760846+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers"}','COUNT(*)
30
(1 row)',NULL);
INSERT INTO "steps" VALUES('3c84c7ddb42145f48fb650a2291bdec6',1,'30','2026-11-13T07:00:31.760846+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('d9ab1686202a4322a2eedc287f45882d',0,'','2026-11-13T07:00:31.761904+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) AS n FROM orders GROUP BY m ORDER BY n DESC LIMIT 1"}','m | n
06 | 30
(1 row)',NULL);
INSERT INTO "steps" VALUES('d9ab1686202a4322a2eedc287f45882d',1,'June','2026-11-13T07:00:31.761904+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('abe6f7f2bd14450a92a684156bcc18dc',0,'','2026-11-13T07:00:31.761904+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"}','COUNT(*)
3
(1 row)',NULL);
INSERT INTO "steps" VALUES('abe6f7f2bd14450a92a684156bcc18dc',1,'3','2026-11-13T07:00:31.761904+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('863c7a925a4a43eab9e12103df403b00',0,'','2026-11-13T07:00:31.763598+00:00',NULL,NULL,'sql_query','{"query": "SELECT p.name, p.price FROM products p WHERE p.id IN (SELECT product_id FROM order_items) ORDER BY p.price DESC LIMIT 1"}','name | price
Noise-Cancelling Headphones | 8999
(1 row)',NULL);
INSERT INTO "steps" VALUES('863c7a925a4a43eab9e12103df403b00',1,'Noise-Cancelling Headphones','2026-11-13T07:00:31.763598+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('3cabb601934e40cc96a52a5a4d2b20eb',0,'','2026-11-13T07:00:31.763598+00:00',NULL,NULL,'sql_query','{"query": "SELECT c.city, COUNT(*) AS n FROM orders o JOIN customers c ON c.id = o.customer_id GROUP BY c.city ORDER BY n DESC LIMIT 1"}','city | n
Jaipur | 38
(1 row)',NULL);
INSERT INTO "steps" VALUES('3cabb601934e40cc96a52a5a4d2b20eb',1,'Jaipur','2026-11-13T07:00:31.763598+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('2be607467c1b4e1eaba5b02d9538880a',0,'','2026-11-13T07:00:31.765273+00:00',NULL,NULL,'sql_query','{"query": "SELECT SUM(i.quantity * p.price) FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id WHERE o.order_date LIKE ''2026-01-%''"}','SUM(i.quantity * p.price)
268721
(1 row)',NULL);
INSERT INTO "steps" VALUES('2be607467c1b4e1eaba5b02d9538880a',1,'268721','2026-11-13T07:00:31.765273+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('f661e418cc8f439e8470474cd30b4a4a',0,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'sql_query','{"query": "SELECT p.name, SUM(i.quantity * p.price) AS revenue FROM order_items i JOIN products p ON p.id = i.product_id GROUP BY p.id ORDER BY revenue DESC LIMIT 1"}','name | revenue
Noise-Cancelling Headphones | 935896
(1 row)',NULL);
INSERT INTO "steps" VALUES('f661e418cc8f439e8470474cd30b4a4a',1,'Noise-Cancelling Headphones','2026-11-13T07:00:31.767877+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('385e97c8315e4da0b6a8e8e484e6c77b',0,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'sql_query','{"query": "SELECT c.name, SUM(i.quantity * p.price) AS spent FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id JOIN customers c ON c.id = o.customer_id GROUP BY c.id ORDER BY spent DESC LIMIT 1"}','name | spent
Ananya Iyer | 206335
(1 row)',NULL);
INSERT INTO "steps" VALUES('385e97c8315e4da0b6a8e8e484e6c77b',1,'Ananya Iyer','2026-11-13T07:00:31.767877+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('744708749fcf4747b3069a802441c22f',0,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) FROM orders WHERE m IN (''01'', ''02'') GROUP BY m"}','m | COUNT(*)
01 | 21
02 | 26
(2 rows)',NULL);
INSERT INTO "steps" VALUES('744708749fcf4747b3069a802441c22f',1,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'calculator','{"expression": "(26 - 21) / 21 * 100"}','23.809523809523807',NULL);
INSERT INTO "steps" VALUES('744708749fcf4747b3069a802441c22f',2,'23.8','2026-11-13T07:00:31.767877+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('5d8de7db04d742e89010fd8c2cbe792d',0,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'sql_query','{"query": "SELECT SUM(i.quantity * p.price) FROM order_items i JOIN products p ON p.id = i.product_id"}','SUM(i.quantity * p.price)
2416098
(1 row)',NULL);
INSERT INTO "steps" VALUES('5d8de7db04d742e89010fd8c2cbe792d',1,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM orders"}','COUNT(*)
150
(1 row)',NULL);
INSERT INTO "steps" VALUES('5d8de7db04d742e89010fd8c2cbe792d',2,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'calculator','{"expression": "2416098 / 150"}','16107.32',NULL);
INSERT INTO "steps" VALUES('5d8de7db04d742e89010fd8c2cbe792d',3,'16107','2026-11-13T07:00:31.767877+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('225c8981a50244bb95dbee063935e4b0',0,'','2026-11-13T07:00:31.767877+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers"}','COUNT(*)
30
(1 row)',NULL);
INSERT INTO "steps" VALUES('225c8981a50244bb95dbee063935e4b0',1,'30','2026-11-13T07:00:31.767877+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('148aae1ae20640bf9f5aefd63e3f7d4e',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) AS n FROM orders GROUP BY m ORDER BY n DESC LIMIT 1"}','m | n
06 | 30
(1 row)',NULL);
INSERT INTO "steps" VALUES('148aae1ae20640bf9f5aefd63e3f7d4e',1,'June','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('d805a0bddd8d4fa9aa448f552abd6ef2',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"}','COUNT(*)
0
(1 row)',NULL);
INSERT INTO "steps" VALUES('d805a0bddd8d4fa9aa448f552abd6ef2',1,'0','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('ca6448e2772341caae32c07358056f81',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT name, price FROM products ORDER BY price DESC LIMIT 1"}','name | price
Smart Watch | 12999
(1 row)',NULL);
INSERT INTO "steps" VALUES('ca6448e2772341caae32c07358056f81',1,'Smart Watch','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('06410cd86d8e45ab835a4c4fe954e059',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT c.city, COUNT(*) AS n FROM orders o JOIN customers c ON c.id = o.customer_id GROUP BY c.city ORDER BY n DESC LIMIT 1"}','city | n
Jaipur | 38
(1 row)',NULL);
INSERT INTO "steps" VALUES('06410cd86d8e45ab835a4c4fe954e059',1,'Jaipur','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('f2afad4be8a14acea8695a5ce3bb0c3b',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT SUM(i.quantity * p.price) FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id WHERE o.order_date LIKE ''2026-01-%''"}','SUM(i.quantity * p.price)
268721
(1 row)',NULL);
INSERT INTO "steps" VALUES('f2afad4be8a14acea8695a5ce3bb0c3b',1,'268721','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('9d36678fb6bc473d8ed0bba80b0d4f58',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT p.name, SUM(i.quantity) AS units FROM order_items i JOIN products p ON p.id = i.product_id GROUP BY p.id ORDER BY units DESC LIMIT 1"}','name | units
Denim Jeans | 118
(1 row)',NULL);
INSERT INTO "steps" VALUES('9d36678fb6bc473d8ed0bba80b0d4f58',1,'Denim Jeans','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('dc7677460fe84a1580fbc16746178632',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT c.name, SUM(i.quantity * p.price) AS spent FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id JOIN customers c ON c.id = o.customer_id GROUP BY c.id ORDER BY spent DESC LIMIT 1"}','name | spent
Ananya Iyer | 206335
(1 row)',NULL);
INSERT INTO "steps" VALUES('dc7677460fe84a1580fbc16746178632',1,'Ananya Iyer','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('3a4493eb32fd480aacc6ee684716438c',0,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) FROM orders WHERE m IN (''01'', ''02'') GROUP BY m"}','m | COUNT(*)
01 | 21
02 | 26
(2 rows)',NULL);
INSERT INTO "steps" VALUES('3a4493eb32fd480aacc6ee684716438c',1,'','2026-11-13T07:00:31.773468+00:00',NULL,NULL,'calculator','{"expression": "(21 - 26) / 26 * 100"}','-19.230769230769234',NULL);
INSERT INTO "steps" VALUES('3a4493eb32fd480aacc6ee684716438c',2,'-19.2','2026-11-13T07:00:31.773468+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('7b93fa97e84b4bfd9f60bb379c155612',0,'','2026-11-13T07:00:31.778811+00:00',NULL,NULL,'sql_query','{"query": "SELECT SUM(i.quantity * p.price) FROM order_items i JOIN products p ON p.id = i.product_id"}','SUM(i.quantity * p.price)
2416098
(1 row)',NULL);
INSERT INTO "steps" VALUES('7b93fa97e84b4bfd9f60bb379c155612',1,'','2026-11-13T07:00:31.778811+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM orders"}','COUNT(*)
150
(1 row)',NULL);
INSERT INTO "steps" VALUES('7b93fa97e84b4bfd9f60bb379c155612',2,'','2026-11-13T07:00:31.778811+00:00',NULL,NULL,'calculator','{"expression": "2416098 / 150"}','16107.32',NULL);
INSERT INTO "steps" VALUES('7b93fa97e84b4bfd9f60bb379c155612',3,'16107','2026-11-13T07:00:31.778811+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('00bbfb9809f14385b7e9c4091bdb9fe4',0,'','2026-11-13T07:00:31.778811+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers"}','COUNT(*)
30
(1 row)',NULL);
INSERT INTO "steps" VALUES('00bbfb9809f14385b7e9c4091bdb9fe4',1,'30','2026-11-13T07:00:31.778811+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('0dd6c842e79141fb853f5989ca8306ee',0,'','2026-11-13T07:00:31.778811+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) AS n FROM orders GROUP BY m ORDER BY n DESC LIMIT 1"}','m | n
06 | 30
(1 row)',NULL);
INSERT INTO "steps" VALUES('0dd6c842e79141fb853f5989ca8306ee',1,'June','2026-11-13T07:00:31.778811+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
CREATE TABLE suite_runs (
    suite_id             TEXT PRIMARY KEY,
    suite_name           TEXT NOT NULL,
    config_name          TEXT NOT NULL,
    provider             TEXT NOT NULL,
    model                TEXT NOT NULL,
    system_prompt        TEXT NOT NULL,
    prompt_hash          TEXT NOT NULL,
    max_attempts         INTEGER NOT NULL,
    min_interval_seconds REAL NOT NULL,
    repeats              INTEGER NOT NULL CHECK (repeats >= 1),
    started_at           TEXT NOT NULL,          -- ISO 8601, UTC
    finished_at          TEXT,
    dataset              TEXT,
    request_budget       INTEGER,
    estimated_requests   INTEGER,
    stop_reason          TEXT,
    saved_at             TEXT NOT NULL
);
INSERT INTO "suite_runs" VALUES('2cf16c36de14452bb71b5adfdb68de85','shop','careful-script','fake','scripted-careful-v1','You are a careful assistant that solves tasks step by step. Use the provided tools whenever they help, especially for arithmetic. When you know the final answer, reply with the answer only.','396a9e3fe29c',3,0.0,1,'2026-11-13T07:00:31.760846+00:00','2026-11-13T07:00:31.767877+00:00','shop.db sha256:fixture',NULL,NULL,NULL,'2026-11-13T07:00:31.790664+00:00');
INSERT INTO "suite_runs" VALUES('624fcdafc5794f0f997dc9b2747a2255','shop','sloppy-script','fake','scripted-sloppy-v1','You are a careful assistant that solves tasks step by step. Use the provided tools whenever they help, especially for arithmetic. When you know the final answer, reply with the answer only.','396a9e3fe29c',3,0.0,1,'2026-11-13T07:00:31.767877+00:00','2026-11-13T07:00:31.778811+00:00','shop.db sha256:fixture',NULL,NULL,NULL,'2026-11-13T07:00:31.798511+00:00');
INSERT INTO "suite_runs" VALUES('18fbd8d9822342b098f577712791a459','shop','gemini-default','gemini','gemini-fixture','fixture prompt','194713ad972b',3,6.0,1,'2026-11-13T07:00:31.778811+00:00','2026-11-13T07:00:31.780531+00:00','shop.db sha256:fixture',80,50,'quota_exhausted in shop-003','2026-11-13T07:00:31.813997+00:00');
CREATE TABLE suite_tasks (
    suite_id  TEXT NOT NULL REFERENCES suite_runs (suite_id),
    position  INTEGER NOT NULL,
    task_id   TEXT NOT NULL,
    task_hash TEXT REFERENCES task_versions (task_hash),  -- NULL = definition not recorded
    PRIMARY KEY (suite_id, position),
    UNIQUE (suite_id, task_id)
);
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',0,'shop-001','9e84d65d50fcbb472e1a2b694a4a930e31acdae327dd3d9f0383704384825875');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',1,'shop-002','60bcb4296d31fb4891d40b48eba873742fc1ca8db311279fb5d82421fb34a561');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',2,'shop-003','0f77f48d147374ab8cf2af9b44866f33ab76663aeac7f8697bda4d0ead1050d3');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',3,'shop-004','bb8aa300f439601858d9d09a81a0edd5838b21dbb9311116207efed042c72b6b');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',4,'shop-005','14e9769475c741472720aef8bae9fd49a2125a479e459ba59d73087aa5f928b9');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',5,'shop-006','56665aa81a68643d980ff376afe7dc12fbc2f4958b03bab04040a8ef3d924b7f');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',6,'shop-007','ffd5283ee038ef8c6e787522a2950f9be293114bd5e916c3a2695105f85ca2f3');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',7,'shop-008','79a9ad25bed33c6725014d7154c029f846f887db890ef3e6d232a0966b673ef9');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',8,'shop-009','ea578e518fe67d31cf7ec2dd6889a4a04651b0b6d564b574b07c7c38858223e0');
INSERT INTO "suite_tasks" VALUES('2cf16c36de14452bb71b5adfdb68de85',9,'shop-010','fb8b608c18bca833d16c15768ff2c58d3694499ea4ddadc22f05e3fbfe675951');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',0,'shop-001','9e84d65d50fcbb472e1a2b694a4a930e31acdae327dd3d9f0383704384825875');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',1,'shop-002','60bcb4296d31fb4891d40b48eba873742fc1ca8db311279fb5d82421fb34a561');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',2,'shop-003','0f77f48d147374ab8cf2af9b44866f33ab76663aeac7f8697bda4d0ead1050d3');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',3,'shop-004','bb8aa300f439601858d9d09a81a0edd5838b21dbb9311116207efed042c72b6b');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',4,'shop-005','14e9769475c741472720aef8bae9fd49a2125a479e459ba59d73087aa5f928b9');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',5,'shop-006','56665aa81a68643d980ff376afe7dc12fbc2f4958b03bab04040a8ef3d924b7f');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',6,'shop-007','ffd5283ee038ef8c6e787522a2950f9be293114bd5e916c3a2695105f85ca2f3');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',7,'shop-008','79a9ad25bed33c6725014d7154c029f846f887db890ef3e6d232a0966b673ef9');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',8,'shop-009','ea578e518fe67d31cf7ec2dd6889a4a04651b0b6d564b574b07c7c38858223e0');
INSERT INTO "suite_tasks" VALUES('624fcdafc5794f0f997dc9b2747a2255',9,'shop-010','fb8b608c18bca833d16c15768ff2c58d3694499ea4ddadc22f05e3fbfe675951');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',0,'shop-001','9e84d65d50fcbb472e1a2b694a4a930e31acdae327dd3d9f0383704384825875');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',1,'shop-002','60bcb4296d31fb4891d40b48eba873742fc1ca8db311279fb5d82421fb34a561');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',2,'shop-003','0f77f48d147374ab8cf2af9b44866f33ab76663aeac7f8697bda4d0ead1050d3');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',3,'shop-004','bb8aa300f439601858d9d09a81a0edd5838b21dbb9311116207efed042c72b6b');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',4,'shop-005','14e9769475c741472720aef8bae9fd49a2125a479e459ba59d73087aa5f928b9');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',5,'shop-006','56665aa81a68643d980ff376afe7dc12fbc2f4958b03bab04040a8ef3d924b7f');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',6,'shop-007','ffd5283ee038ef8c6e787522a2950f9be293114bd5e916c3a2695105f85ca2f3');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',7,'shop-008','79a9ad25bed33c6725014d7154c029f846f887db890ef3e6d232a0966b673ef9');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',8,'shop-009','ea578e518fe67d31cf7ec2dd6889a4a04651b0b6d564b574b07c7c38858223e0');
INSERT INTO "suite_tasks" VALUES('18fbd8d9822342b098f577712791a459',9,'shop-010','fb8b608c18bca833d16c15768ff2c58d3694499ea4ddadc22f05e3fbfe675951');
CREATE TABLE task_versions (
    task_hash       TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    definition_json TEXT NOT NULL
);
INSERT INTO "task_versions" VALUES('9e84d65d50fcbb472e1a2b694a4a930e31acdae327dd3d9f0383704384825875','shop-001','{"id":"shop-001","prompt":"How many customers are there? Answer with the number only.","expected_answer":"30","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"easy","answer_type":"number","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('60bcb4296d31fb4891d40b48eba873742fc1ca8db311279fb5d82421fb34a561','shop-002','{"id":"shop-002","prompt":"Which month of 2026 had the most orders? Answer with the month name only.","expected_answer":"June","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"easy","answer_type":"contains","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('0f77f48d147374ab8cf2af9b44866f33ab76663aeac7f8697bda4d0ead1050d3','shop-003','{"id":"shop-003","prompt":"How many customers have never placed an order? Answer with the number only.","expected_answer":"3","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"medium","answer_type":"number","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('bb8aa300f439601858d9d09a81a0edd5838b21dbb9311116207efed042c72b6b','shop-004','{"id":"shop-004","prompt":"Name the most expensive product that has been ordered at least once. Answer with the exact name only, as stored in the database.","expected_answer":"Noise-Cancelling Headphones","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"medium","answer_type":"contains","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('14e9769475c741472720aef8bae9fd49a2125a479e459ba59d73087aa5f928b9','shop-005','{"id":"shop-005","prompt":"Which city''s customers placed the most orders? Answer with the city name only.","expected_answer":"Jaipur","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"medium","answer_type":"contains","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('56665aa81a68643d980ff376afe7dc12fbc2f4958b03bab04040a8ef3d924b7f','shop-006','{"id":"shop-006","prompt":"What was the total revenue, in rupees, from orders placed in January 2026? Revenue means quantity x product price. Answer with the number only.","expected_answer":"268721","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"medium","answer_type":"number","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('ffd5283ee038ef8c6e787522a2950f9be293114bd5e916c3a2695105f85ca2f3','shop-007','{"id":"shop-007","prompt":"Which product earned the most total revenue? Revenue means quantity x product price. Answer with the exact name only, as stored in the database.","expected_answer":"Noise-Cancelling Headphones","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"hard","answer_type":"contains","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('79a9ad25bed33c6725014d7154c029f846f887db890ef3e6d232a0966b673ef9','shop-008','{"id":"shop-008","prompt":"Which customer spent the most in total? Revenue means quantity x product price. Answer with the exact name only, as stored in the database.","expected_answer":"Ananya Iyer","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"hard","answer_type":"contains","abs_tolerance":0.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('ea578e518fe67d31cf7ec2dd6889a4a04651b0b6d564b574b07c7c38858223e0','shop-009','{"id":"shop-009","prompt":"What was the percentage growth in the number of orders from January 2026 to February 2026? Answer with the percentage to one decimal place, number only.","expected_answer":"23.8","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"hard","answer_type":"number","abs_tolerance":0.05,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
INSERT INTO "task_versions" VALUES('fb8b608c18bca833d16c15768ff2c58d3694499ea4ddadc22f05e3fbfe675951','shop-010','{"id":"shop-010","prompt":"What was the average order value across all orders, in rupees, rounded to the nearest rupee? Revenue means quantity x product price. Answer with the number only.","expected_answer":"16107","allowed_tools":["list_tables","describe_table","sql_query","calculator"],"max_steps":8,"difficulty":"hard","answer_type":"number","abs_tolerance":1.0,"rel_tolerance":0.0,"required_tools":["sql_query"]}');
CREATE INDEX idx_suite_runs_started ON suite_runs (started_at);
CREATE INDEX idx_task_versions_task ON task_versions (task_id);
CREATE INDEX idx_run_records_task ON run_records (task_id);
COMMIT;
PRAGMA user_version = 1;
