BEGIN TRANSACTION;
CREATE TABLE checks (
    run_id   TEXT NOT NULL REFERENCES run_records (run_id),
    position INTEGER NOT NULL,
    name     TEXT NOT NULL,
    passed   INTEGER NOT NULL CHECK (passed IN (0, 1)),
    reason   TEXT NOT NULL,
    PRIMARY KEY (run_id, position)
);
INSERT INTO "checks" VALUES('13596c17716041c0b23cfd182d40fb03',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('13596c17716041c0b23cfd182d40fb03',1,'answer:number',1,'found 30 (the only number); matches expected 30');
INSERT INTO "checks" VALUES('13596c17716041c0b23cfd182d40fb03',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('837419ed3e6b43d58e561247adb0ebf5',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('837419ed3e6b43d58e561247adb0ebf5',1,'answer:contains',1,'''June'' contains ''June''');
INSERT INTO "checks" VALUES('837419ed3e6b43d58e561247adb0ebf5',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('34f931d1ac044943bbeaa11c9be5d208',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('34f931d1ac044943bbeaa11c9be5d208',1,'answer:number',1,'found 3 (the only number); matches expected 3');
INSERT INTO "checks" VALUES('34f931d1ac044943bbeaa11c9be5d208',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('18741602d4ab42b2935cf16262beb482',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('18741602d4ab42b2935cf16262beb482',1,'answer:contains',1,'''Noise-Cancelling Headphones'' contains ''Noise-Cancelling Headphones''');
INSERT INTO "checks" VALUES('18741602d4ab42b2935cf16262beb482',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('da4792d3ac5443f99ff14ddffdc0d503',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('da4792d3ac5443f99ff14ddffdc0d503',1,'answer:contains',1,'''Jaipur'' contains ''Jaipur''');
INSERT INTO "checks" VALUES('da4792d3ac5443f99ff14ddffdc0d503',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('f8d432de0a1840e1a9d07e4beda77ee7',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('f8d432de0a1840e1a9d07e4beda77ee7',1,'answer:number',1,'found 268721 (the only number); matches expected 268721');
INSERT INTO "checks" VALUES('f8d432de0a1840e1a9d07e4beda77ee7',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('1eb7f236df25494bac86322e4eabde05',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('1eb7f236df25494bac86322e4eabde05',1,'answer:contains',1,'''Noise-Cancelling Headphones'' contains ''Noise-Cancelling Headphones''');
INSERT INTO "checks" VALUES('1eb7f236df25494bac86322e4eabde05',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('699b6aecab234f408b4161764a6f252f',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('699b6aecab234f408b4161764a6f252f',1,'answer:contains',1,'''Ananya Iyer'' contains ''Ananya Iyer''');
INSERT INTO "checks" VALUES('699b6aecab234f408b4161764a6f252f',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('0ff88567670845fba56f8ffcf82f7bf8',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('0ff88567670845fba56f8ffcf82f7bf8',1,'answer:number',1,'found 23.8 (the only number); matches expected 23.8');
INSERT INTO "checks" VALUES('0ff88567670845fba56f8ffcf82f7bf8',2,'required_tools',1,'used: sql_query (1 successful call(s))');
INSERT INTO "checks" VALUES('b8e2616227a54b7ebf06eda26211894e',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('b8e2616227a54b7ebf06eda26211894e',1,'answer:number',1,'found 16107 (the only number); matches expected 16107');
INSERT INTO "checks" VALUES('b8e2616227a54b7ebf06eda26211894e',2,'required_tools',1,'used: sql_query (2 successful call(s))');
INSERT INTO "checks" VALUES('9a5b2cc452264495b22938d21d245a09',0,'status',1,'run completed');
INSERT INTO "checks" VALUES('9a5b2cc452264495b22938d21d245a09',1,'answer:number',1,'found 30 (the only number); matches expected 30');
INSERT INTO "checks" VALUES('9a5b2cc452264495b22938d21d245a09',2,'required_tools',1,'used: sql_query (1 successful call(s))');
CREATE TABLE retries (
        run_id         TEXT NOT NULL REFERENCES run_records (run_id),
        position       INTEGER NOT NULL,
        step_index     INTEGER NOT NULL CHECK (step_index >= 0),
        attempt        INTEGER NOT NULL CHECK (attempt >= 1),
        error_kind     TEXT NOT NULL,
        status_code    INTEGER,
        waited_seconds REAL NOT NULL CHECK (waited_seconds >= 0),
        request_id     TEXT,
        occurred_at    TEXT NOT NULL,
        succeeded      INTEGER NOT NULL CHECK (succeeded IN (0, 1)),
        PRIMARY KEY (run_id, position)
    );
INSERT INTO "retries" VALUES('9a5b2cc452264495b22938d21d245a09',0,0,1,'server',503,1.0,NULL,'2026-11-13T07:43:02.209379+00:00',1);
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
    evaluation_passed INTEGER CHECK (evaluation_passed IN (0, 1)), retries_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (retries_recorded IN (0, 1)),  -- NULL = not evaluated
    FOREIGN KEY (suite_id, task_id) REFERENCES suite_tasks (suite_id, task_id),
    UNIQUE (suite_id, position),
    UNIQUE (suite_id, task_id, repeat_index)
);
INSERT INTO "run_records" VALUES('13596c17716041c0b23cfd182d40fb03','de27536a42a1444fa7a5b56a5ae60fba',0,'shop-001',0,'easy','passed','completed','30',5.661000013787997887e-04,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('837419ed3e6b43d58e561247adb0ebf5','de27536a42a1444fa7a5b56a5ae60fba',1,'shop-002',0,'easy','passed','completed','June',1.088900000468129292e-03,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('34f931d1ac044943bbeaa11c9be5d208','de27536a42a1444fa7a5b56a5ae60fba',2,'shop-003',0,'medium','passed','completed','3',0.000976999999693362,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('18741602d4ab42b2935cf16262beb482','de27536a42a1444fa7a5b56a5ae60fba',3,'shop-004',0,'medium','passed','completed','Noise-Cancelling Headphones',7.438000011461554096e-04,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('da4792d3ac5443f99ff14ddffdc0d503','de27536a42a1444fa7a5b56a5ae60fba',4,'shop-005',0,'medium','passed','completed','Jaipur',8.821999999781837687e-04,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('f8d432de0a1840e1a9d07e4beda77ee7','de27536a42a1444fa7a5b56a5ae60fba',5,'shop-006',0,'medium','passed','completed','268721',0.00102109999897948,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('1eb7f236df25494bac86322e4eabde05','de27536a42a1444fa7a5b56a5ae60fba',6,'shop-007',0,'hard','passed','completed','Noise-Cancelling Headphones',1.223400000526453368e-03,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('699b6aecab234f408b4161764a6f252f','de27536a42a1444fa7a5b56a5ae60fba',7,'shop-008',0,'hard','passed','completed','Ananya Iyer',1.344399999652523547e-03,NULL,NULL,2,1,1);
INSERT INTO "run_records" VALUES('0ff88567670845fba56f8ffcf82f7bf8','de27536a42a1444fa7a5b56a5ae60fba',8,'shop-009',0,'hard','passed','completed','23.8',1.037400001223431901e-03,NULL,NULL,3,1,1);
INSERT INTO "run_records" VALUES('b8e2616227a54b7ebf06eda26211894e','de27536a42a1444fa7a5b56a5ae60fba',9,'shop-010',0,'hard','passed','completed','16107',1.180400000521331095e-03,NULL,NULL,4,1,1);
INSERT INTO "run_records" VALUES('9a5b2cc452264495b22938d21d245a09','535caeb86a0245e0bd440b139245a77b',0,'shop-001',0,'easy','passed','completed','30',1.349099999060854315e-03,NULL,NULL,3,1,1);
CREATE TABLE skipped_runs (
    suite_id     TEXT NOT NULL REFERENCES suite_runs (suite_id),
    position     INTEGER NOT NULL,
    task_id      TEXT NOT NULL,
    repeat_index INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    PRIMARY KEY (suite_id, position),
    FOREIGN KEY (suite_id, task_id) REFERENCES suite_tasks (suite_id, task_id)
);
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
INSERT INTO "steps" VALUES('13596c17716041c0b23cfd182d40fb03',0,'','2026-11-13T07:43:02.193197+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers"}','COUNT(*)
30
(1 row)',NULL);
INSERT INTO "steps" VALUES('13596c17716041c0b23cfd182d40fb03',1,'30','2026-11-13T07:43:02.193197+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('837419ed3e6b43d58e561247adb0ebf5',0,'','2026-11-13T07:43:02.196211+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) AS n FROM orders GROUP BY m ORDER BY n DESC LIMIT 1"}','m | n
06 | 30
(1 row)',NULL);
INSERT INTO "steps" VALUES('837419ed3e6b43d58e561247adb0ebf5',1,'June','2026-11-13T07:43:02.196211+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('34f931d1ac044943bbeaa11c9be5d208',0,'','2026-11-13T07:43:02.197729+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"}','COUNT(*)
3
(1 row)',NULL);
INSERT INTO "steps" VALUES('34f931d1ac044943bbeaa11c9be5d208',1,'3','2026-11-13T07:43:02.197729+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('18741602d4ab42b2935cf16262beb482',0,'','2026-11-13T07:43:02.199354+00:00',NULL,NULL,'sql_query','{"query": "SELECT p.name, p.price FROM products p WHERE p.id IN (SELECT product_id FROM order_items) ORDER BY p.price DESC LIMIT 1"}','name | price
Noise-Cancelling Headphones | 8999
(1 row)',NULL);
INSERT INTO "steps" VALUES('18741602d4ab42b2935cf16262beb482',1,'Noise-Cancelling Headphones','2026-11-13T07:43:02.199354+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('da4792d3ac5443f99ff14ddffdc0d503',0,'','2026-11-13T07:43:02.201373+00:00',NULL,NULL,'sql_query','{"query": "SELECT c.city, COUNT(*) AS n FROM orders o JOIN customers c ON c.id = o.customer_id GROUP BY c.city ORDER BY n DESC LIMIT 1"}','city | n
Jaipur | 38
(1 row)',NULL);
INSERT INTO "steps" VALUES('da4792d3ac5443f99ff14ddffdc0d503',1,'Jaipur','2026-11-13T07:43:02.201373+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('f8d432de0a1840e1a9d07e4beda77ee7',0,'','2026-11-13T07:43:02.202376+00:00',NULL,NULL,'sql_query','{"query": "SELECT SUM(i.quantity * p.price) FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id WHERE o.order_date LIKE ''2026-01-%''"}','SUM(i.quantity * p.price)
268721
(1 row)',NULL);
INSERT INTO "steps" VALUES('f8d432de0a1840e1a9d07e4beda77ee7',1,'268721','2026-11-13T07:43:02.202376+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('1eb7f236df25494bac86322e4eabde05',0,'','2026-11-13T07:43:02.204374+00:00',NULL,NULL,'sql_query','{"query": "SELECT p.name, SUM(i.quantity * p.price) AS revenue FROM order_items i JOIN products p ON p.id = i.product_id GROUP BY p.id ORDER BY revenue DESC LIMIT 1"}','name | revenue
Noise-Cancelling Headphones | 935896
(1 row)',NULL);
INSERT INTO "steps" VALUES('1eb7f236df25494bac86322e4eabde05',1,'Noise-Cancelling Headphones','2026-11-13T07:43:02.204374+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('699b6aecab234f408b4161764a6f252f',0,'','2026-11-13T07:43:02.205374+00:00',NULL,NULL,'sql_query','{"query": "SELECT c.name, SUM(i.quantity * p.price) AS spent FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id JOIN customers c ON c.id = o.customer_id GROUP BY c.id ORDER BY spent DESC LIMIT 1"}','name | spent
Ananya Iyer | 206335
(1 row)',NULL);
INSERT INTO "steps" VALUES('699b6aecab234f408b4161764a6f252f',1,'Ananya Iyer','2026-11-13T07:43:02.205374+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('0ff88567670845fba56f8ffcf82f7bf8',0,'','2026-11-13T07:43:02.207381+00:00',NULL,NULL,'sql_query','{"query": "SELECT strftime(''%m'', order_date) AS m, COUNT(*) FROM orders WHERE m IN (''01'', ''02'') GROUP BY m"}','m | COUNT(*)
01 | 21
02 | 26
(2 rows)',NULL);
INSERT INTO "steps" VALUES('0ff88567670845fba56f8ffcf82f7bf8',1,'','2026-11-13T07:43:02.207381+00:00',NULL,NULL,'calculator','{"expression": "(26 - 21) / 21 * 100"}','23.809523809523807',NULL);
INSERT INTO "steps" VALUES('0ff88567670845fba56f8ffcf82f7bf8',2,'23.8','2026-11-13T07:43:02.207381+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('b8e2616227a54b7ebf06eda26211894e',0,'','2026-11-13T07:43:02.208372+00:00',NULL,NULL,'sql_query','{"query": "SELECT SUM(i.quantity * p.price) FROM order_items i JOIN products p ON p.id = i.product_id"}','SUM(i.quantity * p.price)
2416098
(1 row)',NULL);
INSERT INTO "steps" VALUES('b8e2616227a54b7ebf06eda26211894e',1,'','2026-11-13T07:43:02.208372+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM orders"}','COUNT(*)
150
(1 row)',NULL);
INSERT INTO "steps" VALUES('b8e2616227a54b7ebf06eda26211894e',2,'','2026-11-13T07:43:02.209379+00:00',NULL,NULL,'calculator','{"expression": "2416098 / 150"}','16107.32',NULL);
INSERT INTO "steps" VALUES('b8e2616227a54b7ebf06eda26211894e',3,'16107','2026-11-13T07:43:02.209379+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "steps" VALUES('9a5b2cc452264495b22938d21d245a09',0,'','2026-11-13T07:43:02.210505+00:00',NULL,NULL,'sql_query','{"query": "SELECT COUNT(*) FROM customers"}','COUNT(*)
30
(1 row)',NULL);
INSERT INTO "steps" VALUES('9a5b2cc452264495b22938d21d245a09',1,'30','2026-11-13T07:43:02.210505+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
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
INSERT INTO "suite_runs" VALUES('de27536a42a1444fa7a5b56a5ae60fba','shop','careful-script','fake','scripted-careful-v1','You are a careful assistant that solves tasks step by step. Use the provided tools whenever they help, especially for arithmetic. When you know the final answer, reply with the answer only.','396a9e3fe29c',3,0.0,1,'2026-11-13T07:43:02.193197+00:00','2026-11-13T07:43:02.209379+00:00','shop.db sha256:fixture',NULL,NULL,NULL,'2026-11-13T07:43:02.229502+00:00');
INSERT INTO "suite_runs" VALUES('535caeb86a0245e0bd440b139245a77b','shop','careful-script','fake','scripted-careful-v1','You are a careful assistant that solves tasks step by step. Use the provided tools whenever they help, especially for arithmetic. When you know the final answer, reply with the answer only.','396a9e3fe29c',3,0.0,1,'2026-11-13T07:43:02.209379+00:00','2026-11-13T07:43:02.211372+00:00','shop.db sha256:fixture',NULL,NULL,NULL,'2026-11-13T07:43:02.251334+00:00');
CREATE TABLE suite_tasks (
    suite_id  TEXT NOT NULL REFERENCES suite_runs (suite_id),
    position  INTEGER NOT NULL,
    task_id   TEXT NOT NULL,
    task_hash TEXT REFERENCES task_versions (task_hash),  -- NULL = definition not recorded
    PRIMARY KEY (suite_id, position),
    UNIQUE (suite_id, task_id)
);
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',0,'shop-001','9e84d65d50fcbb472e1a2b694a4a930e31acdae327dd3d9f0383704384825875');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',1,'shop-002','60bcb4296d31fb4891d40b48eba873742fc1ca8db311279fb5d82421fb34a561');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',2,'shop-003','0f77f48d147374ab8cf2af9b44866f33ab76663aeac7f8697bda4d0ead1050d3');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',3,'shop-004','bb8aa300f439601858d9d09a81a0edd5838b21dbb9311116207efed042c72b6b');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',4,'shop-005','14e9769475c741472720aef8bae9fd49a2125a479e459ba59d73087aa5f928b9');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',5,'shop-006','56665aa81a68643d980ff376afe7dc12fbc2f4958b03bab04040a8ef3d924b7f');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',6,'shop-007','ffd5283ee038ef8c6e787522a2950f9be293114bd5e916c3a2695105f85ca2f3');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',7,'shop-008','79a9ad25bed33c6725014d7154c029f846f887db890ef3e6d232a0966b673ef9');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',8,'shop-009','ea578e518fe67d31cf7ec2dd6889a4a04651b0b6d564b574b07c7c38858223e0');
INSERT INTO "suite_tasks" VALUES('de27536a42a1444fa7a5b56a5ae60fba',9,'shop-010','fb8b608c18bca833d16c15768ff2c58d3694499ea4ddadc22f05e3fbfe675951');
INSERT INTO "suite_tasks" VALUES('535caeb86a0245e0bd440b139245a77b',0,'shop-001','9e84d65d50fcbb472e1a2b694a4a930e31acdae327dd3d9f0383704384825875');
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
PRAGMA user_version = 2;
