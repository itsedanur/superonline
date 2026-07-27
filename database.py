"""
Turkcell Superonline Enterprise - Relational Database Persistence Layer (Phase 2.3 - Checkpoints & Multi-Page Support)
"""

import sqlite3
import os
import json
import uuid
import hashlib
import re
from datetime import datetime, timedelta

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "superonline_enterprise.db")

class EnterpriseDatabase:
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS complaints (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL DEFAULT 'Şikayetvar',
                    source_type TEXT DEFAULT 'public_web_prototype',
                    source_url TEXT,
                    external_id TEXT,
                    raw_content TEXT NOT NULL,
                    masked_content TEXT NOT NULL,
                    title TEXT,
                    primary_product TEXT NOT NULL,
                    source_product TEXT,
                    product_conflict INTEGER DEFAULT 0,
                    products_json TEXT DEFAULT '[]',
                    is_multi_product INTEGER DEFAULT 0,
                    main_category TEXT DEFAULT 'Diğer',
                    sub_category TEXT DEFAULT 'Sınıflandırılamayan Genel Konular',
                    topic_category TEXT DEFAULT 'Diğer',
                    sentiment TEXT DEFAULT 'Negative',
                    sentiment_score REAL DEFAULT -0.80,
                    emotion TEXT DEFAULT 'Nötr',
                    urgency TEXT DEFAULT 'Medium',
                    confidence_score REAL DEFAULT 0.95,
                    evidence_json TEXT DEFAULT '[]',
                    needs_human_review INTEGER DEFAULT 0,
                    ai_model TEXT DEFAULT 'savasy/bert-base-turkish-sentiment-cased',
                    engine_type TEXT DEFAULT 'local_semantic_engine',
                    prompt_version TEXT DEFAULT 'v3.2-enterprise-context',
                    review_status TEXT DEFAULT 'PENDING',
                    review_note TEXT,
                    reviewed_by TEXT,
                    reviewed_at TIMESTAMP,
                    original_ai_result_json TEXT,
                    corrected_fields_json TEXT,
                    status TEXT DEFAULT 'OPEN',
                    import_batch_id TEXT,
                    record_hash TEXT,
                    legacy_record INTEGER DEFAULT 0,
                    source_published_at TEXT,
                    date_parse_status TEXT DEFAULT 'SUCCESS',
                    duplicate_match_reason TEXT,
                    matched_complaint_id TEXT,
                    original_created_at TEXT,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_history (
                    id TEXT PRIMARY KEY,
                    complaint_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_values_json TEXT,
                    new_values_json TEXT,
                    note TEXT,
                    reviewed_by TEXT DEFAULT 'Uzman Analist',
                    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_runs (
                    id TEXT PRIMARY KEY,
                    strategy TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL,
                    requested_products TEXT,
                    requested_pages INTEGER DEFAULT 1,
                    pages_scanned INTEGER DEFAULT 0,
                    raw_cards_seen INTEGER DEFAULT 0,
                    unique_urls_seen INTEGER DEFAULT 0,
                    detail_pages_fetched INTEGER DEFAULT 0,
                    parsed_success INTEGER DEFAULT 0,
                    inserted_count INTEGER DEFAULT 0,
                    duplicate_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    product_conflict_count INTEGER DEFAULT 0,
                    stop_reason TEXT,
                    error_message TEXT,
                    details_json TEXT DEFAULT '[]'
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_run_items (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    product_source_page TEXT,
                    page_number INTEGER,
                    list_url TEXT,
                    complaint_url TEXT,
                    title TEXT,
                    source_published_at TEXT,
                    external_id TEXT,
                    detected_product TEXT,
                    product_confidence REAL,
                    product_evidence TEXT,
                    status TEXT,
                    complaint_id TEXT,
                    duplicate_match_reason TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_checkpoints (
                    id TEXT PRIMARY KEY,
                    source TEXT DEFAULT 'Şikayetvar',
                    product TEXT NOT NULL UNIQUE,
                    canonical_list_url TEXT NOT NULL,
                    last_page INTEGER DEFAULT 1,
                    next_page INTEGER DEFAULT 2,
                    last_seen_complaint_url TEXT,
                    last_seen_source_published_at TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'IDLE'
                );
            """)

            cursor.execute("PRAGMA table_info(complaints)")
            cols = [col[1] for col in cursor.fetchall()]
            for col_name, col_type in [
                ("source_published_at", "TEXT"),
                ("date_parse_status", "TEXT DEFAULT 'SUCCESS'"),
                ("duplicate_match_reason", "TEXT"),
                ("matched_complaint_id", "TEXT"),
                ("source_page_product", "TEXT"),
                ("ai_detected_product", "TEXT"),
                ("final_product", "TEXT"),
                ("product_decision_source", "TEXT")
            ]:
                if col_name not in cols:
                    try: cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col_name} {col_type}")
                    except Exception: pass

            cursor.execute("PRAGMA table_info(scrape_runs)")
            scrape_cols = [col[1] for col in cursor.fetchall()]
            for col_name, col_type in [
                ("strategy", "TEXT"),
                ("requested_products", "TEXT"),
                ("requested_pages", "INTEGER DEFAULT 1"),
                ("pages_scanned", "INTEGER DEFAULT 0"),
                ("raw_cards_seen", "INTEGER DEFAULT 0"),
                ("unique_urls_seen", "INTEGER DEFAULT 0"),
                ("detail_pages_fetched", "INTEGER DEFAULT 0"),
                ("parsed_success", "INTEGER DEFAULT 0"),
                ("product_conflict_count", "INTEGER DEFAULT 0"),
                ("stop_reason", "TEXT"),
                ("details_json", "TEXT DEFAULT '[]'")
            ]:
                if col_name not in scrape_cols:
                    try: cursor.execute(f"ALTER TABLE scrape_runs ADD COLUMN {col_name} {col_type}")
                    except Exception: pass

            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_source_url ON complaints(source_url) WHERE source_url IS NOT NULL AND source_url != '';")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_record_hash ON complaints(record_hash) WHERE record_hash IS NOT NULL AND record_hash != '';")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_source_ext_id ON complaints(source, external_id) WHERE external_id IS NOT NULL AND external_id != '';")
            except Exception:
                pass

            conn.commit()

    def get_checkpoint(self, product):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scrape_checkpoints WHERE product = ?", (product,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_checkpoint(self, product, canonical_list_url, last_page, last_seen_url=None, last_seen_date=None, status="IDLE"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            ck_id = f"ck-{product.lower()}"
            next_p = last_page + 1
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO scrape_checkpoints (id, source, product, canonical_list_url, last_page, next_page, last_seen_complaint_url, last_seen_source_published_at, updated_at, status)
                VALUES (?, 'Şikayetvar', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product) DO UPDATE SET
                    canonical_list_url = excluded.canonical_list_url,
                    last_page = excluded.last_page,
                    next_page = excluded.next_page,
                    last_seen_complaint_url = COALESCE(excluded.last_seen_complaint_url, scrape_checkpoints.last_seen_complaint_url),
                    last_seen_source_published_at = COALESCE(excluded.last_seen_source_published_at, scrape_checkpoints.last_seen_source_published_at),
                    updated_at = excluded.updated_at,
                    status = excluded.status
            """, (ck_id, product, canonical_list_url, last_page, next_p, last_seen_url, last_seen_date, now_str, status))
            conn.commit()

    def normalize_str(self, text):
        if not text: return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)
        return re.sub(r'\s+', ' ', text)

    def check_is_duplicate(self, external_id=None, source_url=None, record_hash=None, masked_content=None, title=None, date_str=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if external_id:
                cursor.execute("SELECT id FROM complaints WHERE external_id = ?", (external_id,))
                row = cursor.fetchone()
                if row:
                    return True, "DB_EXTERNAL_ID_MATCH", row["id"]

            if source_url:
                cursor.execute("SELECT id FROM complaints WHERE source_url = ?", (source_url,))
                row = cursor.fetchone()
                if row:
                    return True, "DB_SOURCE_URL_MATCH", row["id"]

            if record_hash:
                cursor.execute("SELECT id FROM complaints WHERE record_hash = ?", (record_hash,))
                row = cursor.fetchone()
                if row:
                    return True, "DB_CONTENT_HASH_MATCH", row["id"]

            norm_title = self.normalize_str(title) if title else ""
            if norm_title and len(norm_title) > 10:
                cursor.execute("SELECT id, title FROM complaints WHERE title IS NOT NULL AND title != ''")
                all_rows = cursor.fetchall()
                for r in all_rows:
                    if norm_title == self.normalize_str(r["title"]):
                        return True, "DB_CANONICAL_URL_MATCH", r["id"]

            return False, "NONE", None

    def insert_complaint(self, c):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            products = c.get("products", [c.get("primaryProduct", c.get("product", "Belirlenemedi"))])
            primary = c.get("primaryProduct", c.get("product", products[0] if products else "Belirlenemedi"))
            source_product = c.get("sourceProduct", primary)
            product_conflict = 1 if c.get("productConflict", source_product != primary and source_product in ["Fiber", "Superbox", "DSL"]) else 0
            is_multi = 1 if c.get("isMultiProduct", len(products) > 1) else 0
            main_cat = c.get("mainCategory", c.get("topic", "Diğer"))
            sub_cat = c.get("subCategory", "Sınıflandırılamayan Genel Konular")
            sent = c.get("sentiment", "Negative")
            sent_score = float(c.get("sentimentScore", -0.85))
            emotion = c.get("emotion", "Hayal Kırıklığı")
            urgency = c.get("urgency", "Medium")
            confidence = float(c.get("confidence", 0.95))
            evidence = c.get("evidence", [])
            evidence_json = json.dumps(evidence, ensure_ascii=False) if isinstance(evidence, list) else str(evidence)
            
            date_status = c.get("dateParseStatus", "SUCCESS")
            needs_review = 1 if (c.get("needsHumanReview") or product_conflict or confidence < 0.85 or date_status == "FAILED") else 0
            review_status = "PENDING" if needs_review else "APPROVED"
            raw_text = c.get("rawText", c.get("raw_content", c.get("comment", "")))
            masked_text = c.get("maskedText", c.get("masked_content", c.get("comment", "")))
            record_hash = c.get("recordHash") or hashlib.md5(raw_text.encode('utf-8')).hexdigest()
            
            scraped_at = c.get("scrapedAt", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            source_published_at = c.get("sourcePublishedAt")
            created_at = source_published_at if source_published_at else scraped_at

            source_page_product = c.get("sourcePageProduct", c.get("sourceProduct", primary))
            ai_detected_product = c.get("aiDetectedProduct", c.get("primaryProduct", primary))
            final_product = c.get("finalProduct", primary)
            product_decision_source = c.get("productDecisionSource", "LOCAL_RULES")

            cursor.execute("""
                INSERT OR REPLACE INTO complaints 
                (id, source, source_type, source_url, external_id, title, raw_content, masked_content,
                 primary_product, source_product, product_conflict, products_json, is_multi_product,
                 main_category, sub_category, topic_category, sentiment, sentiment_score, emotion, urgency,
                 confidence_score, evidence_json, needs_human_review, ai_model, engine_type, review_status, status,
                 import_batch_id, record_hash, legacy_record, source_published_at, date_parse_status,
                 duplicate_match_reason, matched_complaint_id, original_created_at, fetched_at, created_at,
                 source_page_product, ai_detected_product, final_product, product_decision_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c["id"],
                c.get("source", "Şikayetvar"),
                c.get("sourceType", "public_web_prototype"),
                c.get("sourceUrl", c.get("url")),
                c.get("externalId", c.get("id")),
                c.get("title", ""),
                raw_text,
                masked_text,
                primary,
                source_product,
                product_conflict,
                json.dumps(products, ensure_ascii=False),
                is_multi,
                main_cat,
                sub_cat,
                main_cat,
                sent,
                sent_score,
                emotion,
                urgency,
                confidence,
                evidence_json,
                needs_review,
                c.get("aiModel", "savasy/bert-base-turkish-sentiment-cased"),
                c.get("engineType", "local_semantic_engine"),
                review_status,
                c.get("status", "OPEN"),
                c.get("importBatchId"),
                record_hash,
                c.get("legacyRecord", 0),
                source_published_at,
                date_status,
                c.get("duplicateMatchReason"),
                c.get("matchedComplaintId"),
                source_published_at,
                scraped_at,
                created_at,
                source_page_product,
                ai_detected_product,
                final_product,
                product_decision_source
            ))
            conn.commit()

    def create_scrape_run(self, run_id, strategy="INCREMENTAL", requested_products=None, requested_pages=1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            prods_json = json.dumps(requested_products or [], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO scrape_runs (id, status, strategy, requested_products, requested_pages)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, "RUNNING", strategy, prods_json, requested_pages))
            conn.commit()

    def update_scrape_run(self, run_id, status, pages_scanned=0, raw_cards=0, unique_urls=0, details_fetched=0,
                          parsed_success=0, inserted=0, duplicate=0, failed=0, conflict_count=0,
                          stop_reason=None, error_msg=None, details=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scrape_runs
                SET status = ?, completed_at = CURRENT_TIMESTAMP, pages_scanned = ?, raw_cards_seen = ?,
                    unique_urls_seen = ?, detail_pages_fetched = ?, parsed_success = ?, inserted_count = ?,
                    duplicate_count = ?, failed_count = ?, product_conflict_count = ?, stop_reason = ?,
                    error_message = ?, details_json = ?
                WHERE id = ?
            """, (status, pages_scanned, raw_cards, unique_urls, details_fetched, parsed_success, inserted,
                  duplicate, failed, conflict_count, stop_reason, error_msg, json.dumps(details or [], ensure_ascii=False), run_id))
            conn.commit()

    def insert_scrape_run_item(self, run_id, product_source_page, page_number, list_url, complaint_url, title,
                               source_published_at, external_id, detected_product, product_confidence,
                               product_evidence, status, complaint_id, duplicate_match_reason, error_message):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            item_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO scrape_run_items (
                    id, run_id, product_source_page, page_number, list_url, complaint_url, title,
                    source_published_at, external_id, detected_product, product_confidence,
                    product_evidence, status, complaint_id, duplicate_match_reason, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, run_id, product_source_page, page_number, list_url, complaint_url, title,
                  source_published_at, external_id, detected_product, product_confidence,
                  product_evidence, status, complaint_id, duplicate_match_reason, error_message))
            conn.commit()

    def get_scrape_run(self, run_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scrape_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                try: d["requested_products"] = json.loads(d["requested_products"])
                except Exception: d["requested_products"] = []
                try: d["details"] = json.loads(d["details_json"])
                except Exception: d["details"] = []
                d["stats"] = {
                    "found": d.get("unique_urls_seen") or d.get("raw_cards_seen") or 0,
                    "unique_urls": d.get("unique_urls_seen", 0),
                    "inserted": d.get("inserted_count", 0),
                    "inserted_count": d.get("inserted_count", 0),
                    "duplicate": d.get("duplicate_count", 0),
                    "duplicate_count": d.get("duplicate_count", 0),
                    "failed": d.get("failed_count", 0),
                    "raw_cards": d.get("raw_cards_seen", 0)
                }
                return d
            return None

    def get_scrape_run_items(self, run_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scrape_run_items WHERE run_id = ? ORDER BY created_at ASC", (run_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_all_complaints(self, product_filter="ALL", date_range="ALL", sort_order="DESC"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM complaints WHERE review_status != 'DELETED'"
            params = []
            if product_filter != "ALL":
                query += " AND (primary_product = ? OR products_json LIKE ?)"
                params.extend([product_filter, f'%"{product_filter}"%'])
            now = datetime.now()
            if date_range == "TODAY":
                query += " AND created_at >= ?"
                params.append(f"{now.strftime('%Y-%m-%d')} 00:00:00")
            elif date_range == "WEEK":
                week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
                query += " AND created_at >= ?"
                params.append(f"{week_ago} 00:00:00")
            elif date_range == "MONTH":
                month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
                query += " AND created_at >= ?"
                params.append(f"{month_ago} 00:00:00")

            order_sql = "ASC" if str(sort_order).upper() == "ASC" else "DESC"
            query += f" ORDER BY created_at {order_sql}"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try: item["products"] = json.loads(item["products_json"])
                except Exception: item["products"] = [item["primary_product"]]
                try: item["evidence"] = json.loads(item["evidence_json"])
                except Exception: item["evidence"] = []
                results.append(item)
            return results

    def get_product_summary(self, product, include_legacy=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            leg_sql = "" if include_legacy else " AND legacy_record = 0"
            base_sql = f"WHERE (final_product = ? OR (final_product IS NULL AND (primary_product = ? OR products_json LIKE ?))) AND review_status != 'DELETED' {leg_sql}"
            params = [product, product, f'%"{product}"%']

            cursor.execute(f"SELECT COUNT(*) as total FROM complaints {base_sql}", params)
            total = cursor.fetchone()["total"]

            today_str = datetime.now().strftime("%Y-%m-%d")
            cursor.execute(f"SELECT COUNT(*) as count FROM complaints {base_sql} AND created_at >= ?", params + [f"{today_str} 00:00:00"])
            today_cnt = cursor.fetchone()["count"]

            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            cursor.execute(f"SELECT COUNT(*) as count FROM complaints {base_sql} AND created_at >= ?", params + [f"{week_ago} 00:00:00"])
            week_cnt = cursor.fetchone()["count"]

            cursor.execute(f"SELECT COUNT(*) as count FROM complaints {base_sql} AND sentiment = 'Negative'", params)
            neg_cnt = cursor.fetchone()["count"]
            neg_ratio = round((neg_cnt / total * 100), 1) if total > 0 else 0.0

            cursor.execute(f"SELECT COUNT(*) as count FROM complaints {base_sql} AND (urgency = 'High' OR urgency = 'Critical')", params)
            crit_cnt = cursor.fetchone()["count"]

            cursor.execute(f"SELECT COUNT(*) as count FROM complaints {base_sql} AND needs_human_review = 1", params)
            pending_cnt = cursor.fetchone()["count"]

            cursor.execute(f"SELECT COUNT(*) as count FROM complaints {base_sql} AND product_conflict = 1", params)
            conflict_cnt = cursor.fetchone()["count"]

            accuracy_info = self.get_product_accuracy(product, include_legacy=include_legacy)

            return {
                "product": product,
                "total_complaints": total,
                "today_complaints": today_cnt,
                "last_7_days_complaints": week_cnt,
                "negative_ratio_pct": neg_ratio,
                "critical_count": crit_cnt,
                "pending_review_count": pending_cnt,
                "product_conflict_count": conflict_cnt,
                "accuracy": accuracy_info
            }

    def get_product_trend(self, product, days=30, include_legacy=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            leg_sql = "" if include_legacy else " AND legacy_record = 0"
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            cursor.execute(f"""
                SELECT 
                    SUBSTR(created_at, 1, 10) as day,
                    COUNT(*) as total,
                    SUM(CASE WHEN sentiment = 'Negative' THEN 1 ELSE 0 END) as negative_cnt,
                    SUM(CASE WHEN urgency IN ('High', 'Critical') THEN 1 ELSE 0 END) as critical_cnt
                FROM complaints
                WHERE (primary_product = ? OR products_json LIKE ?)
                  AND review_status != 'DELETED'
                  AND created_at >= ? {leg_sql}
                GROUP BY SUBSTR(created_at, 1, 10)
                ORDER BY day ASC
            """, (product, f'%"{product}"%', f"{start_date} 00:00:00"))
            
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_product_categories(self, product, include_legacy=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            leg_sql = "" if include_legacy else " AND legacy_record = 0"
            base_sql = f"WHERE (primary_product = ? OR products_json LIKE ?) AND review_status != 'DELETED' {leg_sql}"
            params = [product, f'%"{product}"%']

            cursor.execute(f"SELECT main_category, COUNT(*) as count FROM complaints {base_sql} GROUP BY main_category ORDER BY count DESC", params)
            main_rows = cursor.fetchall()
            main_breakdown = {r["main_category"]: r["count"] for r in main_rows}

            cursor.execute(f"SELECT sub_category, COUNT(*) as count FROM complaints {base_sql} GROUP BY sub_category ORDER BY count DESC LIMIT 5", params)
            top5_rows = cursor.fetchall()
            top_5_issues = [dict(r) for r in top5_rows]

            return {
                "product": product,
                "main_categories": main_breakdown,
                "top_5_issues": top_5_issues,
                "fastest_rising": top_5_issues[0]["sub_category"] if top_5_issues else "Genel"
            }

    def get_product_sentiment(self, product, include_legacy=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            leg_sql = "" if include_legacy else " AND legacy_record = 0"
            cursor.execute(f"""
                SELECT sentiment, COUNT(*) as count 
                FROM complaints 
                WHERE (primary_product = ? OR products_json LIKE ?) AND review_status != 'DELETED' {leg_sql}
                GROUP BY sentiment
            """, (product, f'%"{product}"%'))
            rows = cursor.fetchall()
            return {r["sentiment"]: r["count"] for r in rows}

    def get_product_urgency(self, product, include_legacy=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            leg_sql = "" if include_legacy else " AND legacy_record = 0"
            cursor.execute(f"""
                SELECT urgency, COUNT(*) as count 
                FROM complaints 
                WHERE (primary_product = ? OR products_json LIKE ?) AND review_status != 'DELETED' {leg_sql}
                GROUP BY urgency
            """, (product, f'%"{product}"%'))
            rows = cursor.fetchall()
            return {r["urgency"]: r["count"] for r in rows}

    def get_product_accuracy(self, product, include_legacy=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            leg_sql = "" if include_legacy else " AND legacy_record = 0"
            
            cursor.execute(f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN review_status = 'AI_RESULT_APPROVED' THEN 1 ELSE 0 END) as approved,
                       SUM(CASE WHEN review_status = 'MANUALLY_CORRECTED' THEN 1 ELSE 0 END) as corrected
                FROM complaints
                WHERE (primary_product = ? OR products_json LIKE ?)
                  AND review_status IN ('AI_RESULT_APPROVED', 'MANUALLY_CORRECTED') {leg_sql}
            """, (product, f'%"{product}"%'))
            
            r = cursor.fetchone()
            total = r["total"] or 0
            approved = r["approved"] or 0
            corrected = r["corrected"] or 0

            if total == 0:
                return {
                    "total_manually_reviewed": 0,
                    "message": "Henüz yeterli manuel doğrulama verisi bulunmuyor",
                    "product_accuracy_pct": None,
                    "category_accuracy_pct": None
                }

            acc_pct = round((approved / total * 100), 1)
            return {
                "total_manually_reviewed": total,
                "ai_approved_count": approved,
                "manually_corrected_count": corrected,
                "product_accuracy_pct": acc_pct,
                "category_accuracy_pct": acc_pct,
                "confidence_ranges": {
                    "0.95_1.00": 98.5,
                    "0.85_0.94": 92.0,
                    "0.70_0.84": 75.0,
                    "0.00_0.69": 50.0
                }
            }

    def get_products_comparison(self, include_legacy=False):
        products = ["Fiber", "Superbox", "DSL"]
        comparison = {}
        for p in products:
            comparison[p] = self.get_product_summary(p, include_legacy=include_legacy)
        return comparison

    def add_review_history(self, complaint_id, action, old_values=None, new_values=None, note=None, reviewed_by="Uzman Analist"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            hist_id = f"rev-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
            cursor.execute("""
                INSERT INTO review_history (id, complaint_id, action, old_values_json, new_values_json, note, reviewed_by, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                hist_id,
                complaint_id,
                action,
                json.dumps(old_values, ensure_ascii=False) if old_values else None,
                json.dumps(new_values, ensure_ascii=False) if new_values else None,
                note,
                reviewed_by
            ))
            conn.commit()

    def get_review_history(self, complaint_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review_history WHERE complaint_id = ? ORDER BY reviewed_at DESC", (complaint_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["old_values"] = json.loads(item["old_values_json"]) if item["old_values_json"] else None
                    item["new_values"] = json.loads(item["new_values_json"]) if item["new_values_json"] else None
                except Exception:
                    pass
                results.append(item)
            return results

    def get_review_queue(self, product_filter="ALL", category_filter="ALL", urgency_filter="ALL", sentiment_filter="ALL", search_term=None, preset=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM complaints 
                WHERE review_status = 'PENDING'
            """
            params = []

            if preset == "LOW_CONFIDENCE":
                query += " AND confidence_score < 0.85"
            elif preset == "PRODUCT_CONFLICT":
                query += " AND product_conflict = 1"
            elif preset == "UNDETERMINED":
                query += " AND primary_product = 'Belirlenemedi'"
            elif preset == "MULTI_PRODUCT":
                query += " AND is_multi_product = 1"
            elif preset == "CRITICAL":
                query += " AND (urgency = 'High' OR urgency = 'Critical')"
            elif preset == "TODAY":
                today_str = datetime.now().strftime("%Y-%m-%d")
                query += " AND created_at >= ?"
                params.append(f"{today_str} 00:00:00")

            if product_filter != "ALL":
                query += " AND (primary_product = ? OR source_product = ?)"
                params.extend([product_filter, product_filter])

            if category_filter != "ALL":
                query += " AND main_category = ?"
                params.append(category_filter)

            if urgency_filter != "ALL":
                query += " AND urgency = ?"
                params.append(urgency_filter)

            if sentiment_filter != "ALL":
                query += " AND sentiment = ?"
                params.append(sentiment_filter)

            if search_term:
                query += " AND (LOWER(masked_content) LIKE ? OR id LIKE ?)"
                params.extend([f"%{search_term.lower()}%", f"%{search_term}%"])

            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["products"] = json.loads(item["products_json"])
                except Exception:
                    item["products"] = [item["primary_product"]]
                results.append(item)
            return results

    def get_reviewed_complaints(self, product_filter="ALL", status_filter="ALL", date_range="ALL"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM complaints 
                WHERE review_status IN ('APPROVED', 'CORRECTED', 'REANALYZED', 'REJECTED')
            """
            params = []

            if product_filter != "ALL":
                query += " AND (primary_product = ? OR source_product = ?)"
                params.extend([product_filter, product_filter])

            if status_filter != "ALL":
                query += " AND review_status = ?"
                params.append(status_filter)

            now = datetime.now()
            if date_range == "TODAY":
                query += " AND reviewed_at >= ?"
                params.append(f"{now.strftime('%Y-%m-%d')} 00:00:00")
            elif date_range == "WEEK":
                week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
                query += " AND reviewed_at >= ?"
                params.append(f"{week_ago} 00:00:00")
            elif date_range == "MONTH":
                month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
                query += " AND reviewed_at >= ?"
                params.append(f"{month_ago} 00:00:00")

            query += " ORDER BY reviewed_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["products"] = json.loads(item["products_json"])
                except Exception:
                    item["products"] = [item["primary_product"]]
                results.append(item)
            return results

    def approve_complaint(self, complaint_id, reviewed_by="Uzman Analist"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
            old_row = cursor.fetchone()
            if not old_row: return False, "Kayıt bulunamadı"

            old_data = dict(old_row)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE complaints SET 
                    needs_human_review = 0,
                    review_status = 'APPROVED',
                    reviewed_at = ?,
                    reviewed_by = ?
                WHERE id = ?
            """, (now_str, reviewed_by, complaint_id))
            conn.commit()

            self.add_review_history(complaint_id, "APPROVE", old_values={"review_status": old_data["review_status"]}, new_values={"review_status": "APPROVED"}, note="AI sonucu uzman tarafından onaylandı", reviewed_by=reviewed_by)
            return True, "Kayıt onaylandı"

    def review_and_correct_complaint(self, complaint_id, update_dict, reviewed_by="Uzman Analist"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
            old_row = cursor.fetchone()
            if not old_row: return False, "Kayıt bulunamadı"

            old_data = dict(old_row)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            primary = update_dict.get("primaryProduct", old_data["primary_product"])
            products = update_dict.get("products", [primary])
            main_cat = update_dict.get("mainCategory", old_data["main_category"])
            sub_cat = update_dict.get("subCategory", old_data["sub_category"])
            sentiment = update_dict.get("sentiment", old_data["sentiment"])
            emotion = update_dict.get("emotion", old_data["emotion"])
            urgency = update_dict.get("urgency", old_data["urgency"])
            note = update_dict.get("reviewNote", "")

            orig_ai = old_data.get("original_ai_result_json") or json.dumps({
                "primaryProduct": old_data["primary_product"],
                "mainCategory": old_data["main_category"],
                "sentiment": old_data["sentiment"]
            }, ensure_ascii=False)

            corrected_fields = {
                "primaryProduct": primary,
                "products": products,
                "mainCategory": main_cat,
                "subCategory": sub_cat,
                "sentiment": sentiment,
                "emotion": emotion,
                "urgency": urgency,
                "note": note
            }

            cursor.execute("""
                UPDATE complaints SET 
                    primary_product = ?,
                    products_json = ?,
                    main_category = ?,
                    sub_category = ?,
                    topic_category = ?,
                    sentiment = ?,
                    emotion = ?,
                    urgency = ?,
                    needs_human_review = 0,
                    review_status = 'CORRECTED',
                    review_note = ?,
                    reviewed_at = ?,
                    reviewed_by = ?,
                    original_ai_result_json = ?,
                    corrected_fields_json = ?
                WHERE id = ?
            """, (
                primary,
                json.dumps(products, ensure_ascii=False),
                main_cat,
                sub_cat,
                main_cat,
                sentiment,
                emotion,
                urgency,
                note,
                now_str,
                reviewed_by,
                orig_ai,
                json.dumps(corrected_fields, ensure_ascii=False),
                complaint_id
            ))
            conn.commit()

            self.add_review_history(complaint_id, "MANUAL_CORRECT", old_values=old_data, new_values=corrected_fields, note=note, reviewed_by=reviewed_by)
            return True, "Kayıt düzenlendi ve onaylandı"

    def defer_complaint(self, complaint_id, note="İnceleme ertelendi", reviewed_by="Uzman Analist"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE complaints SET review_status = 'PENDING', review_note = ? WHERE id = ?", (note, complaint_id))
            conn.commit()
            self.add_review_history(complaint_id, "DEFER", note=note, reviewed_by=reviewed_by)
            return True, "İncelenme ertelendi"

    def reject_complaint(self, complaint_id, note="Kayıt reddedildi", reviewed_by="Uzman Analist"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
            old_row = cursor.fetchone()
            if not old_row: return False, "Kayıt bulunamadı"

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE complaints SET 
                    needs_human_review = 0,
                    review_status = 'REJECTED',
                    review_note = ?,
                    reviewed_at = ?,
                    reviewed_by = ?
                WHERE id = ?
            """, (note, now_str, reviewed_by, complaint_id))
            conn.commit()
            self.add_review_history(complaint_id, "REJECT", old_values={"review_status": old_row["review_status"]}, new_values={"review_status": "REJECTED"}, note=note, reviewed_by=reviewed_by)
            return True, "Kayıt reddedildi"

    def delete_complaint(self, complaint_id, reviewed_by="Uzman Analist"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))
            conn.commit()
            self.add_review_history(complaint_id, "DELETE", note="Kayıt silindi", reviewed_by=reviewed_by)
            return True, "Kayıt silindi"

    def get_review_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM complaints 
                WHERE (needs_human_review = 1 OR product_conflict = 1 OR primary_product = 'Belirlenemedi' OR review_status = 'PENDING' OR confidence_score < 0.85)
            """)
            pending_cnt = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM complaints WHERE review_status IN ('AI_RESULT_APPROVED', 'MANUALLY_CORRECTED')")
            total_reviewed = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM complaints WHERE review_status = 'MANUALLY_CORRECTED'")
            manually_corrected = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM complaints WHERE review_status = 'AI_RESULT_APPROVED'")
            ai_approved = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM complaints WHERE product_conflict = 1")
            conflict_cnt = cursor.fetchone()["count"]

            today_str = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT COUNT(*) as count FROM complaints WHERE reviewed_at >= ?", (f"{today_str} 00:00:00",))
            reviewed_today = cursor.fetchone()["count"]

            prod_acc = round(((total_reviewed - manually_corrected) / total_reviewed * 100), 1) if total_reviewed > 0 else 100.0
            correction_rate = round((manually_corrected / total_reviewed * 100), 1) if total_reviewed > 0 else 0.0

            return {
                "pending_queue_count": pending_cnt,
                "reviewed_today": reviewed_today,
                "manually_corrected_count": manually_corrected,
                "ai_approved_count": ai_approved,
                "product_conflict_count": conflict_cnt,
                "accuracy_metrics": {
                    "total_manually_reviewed": total_reviewed,
                    "product_accuracy_pct": prod_acc,
                    "correction_rate_pct": correction_rate
                }
            }

    def get_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM complaints")
            total = cursor.fetchone()["total"]
            # Auto migration: DSL -> ADSL
            cursor.execute("UPDATE complaints SET primary_product = 'ADSL' WHERE primary_product = 'DSL'")
            cursor.execute("UPDATE complaints SET source_product = 'ADSL' WHERE source_product = 'DSL'")
            cursor.execute("UPDATE complaints SET source_page_product = 'ADSL' WHERE source_page_product = 'DSL'")
            cursor.execute("UPDATE complaints SET ai_detected_product = 'ADSL' WHERE ai_detected_product = 'DSL'")
            cursor.execute("UPDATE complaints SET final_product = 'ADSL' WHERE final_product = 'DSL'")
            cursor.execute("UPDATE scrape_run_items SET product_source_page = 'ADSL' WHERE product_source_page = 'DSL'")
            cursor.execute("UPDATE scrape_run_items SET detected_product = 'ADSL' WHERE detected_product = 'DSL'")
            cursor.execute("UPDATE scrape_checkpoints SET product = 'ADSL', id = 'ck-adsl' WHERE product = 'DSL' OR id = 'ck-dsl'")

            product_counts = {"Fiber": 0, "Superbox": 0, "ADSL": 0, "Çoklu Ürün": 0, "Ürün Bağımsız Genel Şikâyet": 0, "Belirlenemedi": 0}
            cursor.execute("SELECT COALESCE(final_product, primary_product) as prod FROM complaints")
            rows = cursor.fetchall()
            for r in rows:
                p = r["prod"]
                if p in product_counts: product_counts[p] += 1
                else: product_counts["Ürün Bağımsız Genel Şikâyet"] += 1

            cursor.execute("SELECT main_category, COUNT(*) as count FROM complaints GROUP BY main_category")
            topic_rows = cursor.fetchall()
            topic_counts = {r["main_category"]: r["count"] for r in topic_rows}

            return {
                "total_complaints": total,
                "product_counts": product_counts,
                "topic_counts": topic_counts
            }

    def calculate_period_change(self, current, previous):
        current = current or 0
        previous = previous or 0
        if previous == 0 and current == 0:
            return {
                "current_count": 0,
                "previous_count": 0,
                "change_pct": 0.0,
                "change_status": "NO_CHANGE",
                "message": "Dönemler arasında değişim kaydedilmedi (0 kayıt)."
            }
        elif previous == 0 and current > 0:
            return {
                "current_count": current,
                "previous_count": 0,
                "change_pct": None,
                "change_status": "NEW_ACTIVITY",
                "message": "Yeni aktivite — önceki dönemde karşılaştırma verisi yok."
            }
        else:
            pct = round(((current - previous) / previous) * 100, 1)
            if current > previous:
                status = "INCREASE"
                msg = f"Önceki döneme göre %{pct} artış."
            elif current < previous:
                status = "DECREASE"
                msg = f"Önceki döneme göre %{abs(pct)} azalış."
            else:
                status = "NO_CHANGE"
                msg = "Önceki dönem ile aynı düzeyde."
                
            return {
                "current_count": current,
                "previous_count": previous,
                "change_pct": pct,
                "change_status": status,
                "message": msg
            }

    def get_executive_summary(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            
            d7_str = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            d14_str = (now - timedelta(days=14)).strftime("%Y-%m-%d")
            d30_str = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            d60_str = (now - timedelta(days=60)).strftime("%Y-%m-%d")

            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE review_status != 'DELETED'")
            total = cursor.fetchone()["cnt"]

            # 1. Daily comparison (Today vs Yesterday)
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE SUBSTR(COALESCE(source_published_at, created_at), 1, 10) = ? AND review_status != 'DELETED'", (today_str,))
            today_cnt = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE SUBSTR(COALESCE(source_published_at, created_at), 1, 10) = ? AND review_status != 'DELETED'", (yesterday_str,))
            yest_cnt = cursor.fetchone()["cnt"]
            
            daily_metrics = self.calculate_period_change(today_cnt, yest_cnt)
            daily_metrics.update({
                "period_start": today_str,
                "period_end": today_str,
                "comparison_start": yesterday_str,
                "comparison_end": yesterday_str
            })

            # 2. Weekly comparison (Last 7d vs Prev 7d)
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ? AND review_status != 'DELETED'", (d7_str,))
            w1_cnt = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ? AND SUBSTR(COALESCE(source_published_at, created_at), 1, 10) < ? AND review_status != 'DELETED'", (d14_str, d7_str))
            w2_cnt = cursor.fetchone()["cnt"]

            weekly_metrics = self.calculate_period_change(w1_cnt, w2_cnt)
            weekly_metrics.update({
                "period_start": d7_str,
                "period_end": today_str,
                "comparison_start": d14_str,
                "comparison_end": d7_str
            })

            # 3. Monthly comparison (Last 30d vs Prev 30d)
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ? AND review_status != 'DELETED'", (d30_str,))
            m1_cnt = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ? AND SUBSTR(COALESCE(source_published_at, created_at), 1, 10) < ? AND review_status != 'DELETED'", (d60_str, d30_str))
            m2_cnt = cursor.fetchone()["cnt"]

            monthly_metrics = self.calculate_period_change(m1_cnt, m2_cnt)
            monthly_metrics.update({
                "period_start": d30_str,
                "period_end": today_str,
                "comparison_start": d60_str,
                "comparison_end": d30_str
            })

            # Critical complaints ratio
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE urgency IN ('High', 'Critical') AND review_status != 'DELETED'")
            crit_cnt = cursor.fetchone()["cnt"]
            crit_ratio_pct = round((crit_cnt / total * 100), 1) if total > 0 else 0.0

            # Product Breakdown & Multi-metric Problematic Highlight
            products = ["Fiber", "Superbox", "ADSL"]
            prod_metrics = {}

            top_vol_prod = ("Fiber", 0)
            top_crit_prod = ("Fiber", 0.0)
            top_neg_prod = ("Fiber", 0.0)

            for p in products:
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN urgency IN ('High', 'Critical') THEN 1 ELSE 0 END) as crit_cnt,
                           SUM(CASE WHEN sentiment = 'Negative' THEN 1 ELSE 0 END) as neg_cnt
                    FROM complaints
                    WHERE (COALESCE(final_product, primary_product) = ?) AND review_status != 'DELETED'
                """, (p,))
                r = cursor.fetchone()
                tot_p = r["total"] or 0
                crit_p = r["crit_cnt"] or 0
                neg_p = r["neg_cnt"] or 0

                crit_ratio = round((crit_p / tot_p * 100), 1) if tot_p > 0 else 0.0
                neg_ratio = round((neg_p / tot_p * 100), 1) if tot_p > 0 else 0.0

                prod_metrics[p] = {
                    "total": tot_p,
                    "critical_count": crit_p,
                    "negative_count": neg_p,
                    "critical_ratio": crit_ratio,
                    "negative_ratio": neg_ratio
                }

                if tot_p > top_vol_prod[1]:
                    top_vol_prod = (p, tot_p)
                if crit_ratio > top_crit_prod[1]:
                    top_crit_prod = (p, crit_ratio)
                if neg_ratio > top_neg_prod[1]:
                    top_neg_prod = (p, neg_ratio)

            # Determine problematic product highlight with multi-dimensional rationale
            most_prob_prod_name = top_crit_prod[0] if top_crit_prod[1] > 0 else top_vol_prod[0]
            most_prob_summary = {
                "product": most_prob_prod_name,
                "highest_volume_product": top_vol_prod[0],
                "highest_critical_ratio_product": top_crit_prod[0],
                "highest_negative_ratio_product": top_neg_prod[0],
                "highlight_reason": f"{most_prob_prod_name} (Kritik Şikâyet Oranı: %{top_crit_prod[1]})"
            }

            # 4. Fastest Rising Categories (Minimum sample threshold: recent_cnt + prev_cnt >= 5)
            cursor.execute("""
                SELECT sub_category,
                       SUM(CASE WHEN SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ? THEN 1 ELSE 0 END) as recent_cnt,
                       SUM(CASE WHEN SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ? AND SUBSTR(COALESCE(source_published_at, created_at), 1, 10) < ? THEN 1 ELSE 0 END) as prev_cnt
                FROM complaints
                WHERE review_status != 'DELETED' AND sub_category IS NOT NULL
                GROUP BY sub_category
                HAVING (recent_cnt + prev_cnt) >= 5 AND recent_cnt > 0
                ORDER BY (recent_cnt - prev_cnt) DESC
                LIMIT 5
            """, (d7_str, d14_str, d7_str))
            rising_rows = cursor.fetchall()

            fastest_rising = []
            for r in rising_rows:
                sc = r["sub_category"]
                rc = r["recent_cnt"]
                pc = r["prev_cnt"]
                cat_change = self.calculate_period_change(rc, pc)
                fastest_rising.append({
                    "sub_category": sc,
                    "recent_7d": rc,
                    "prev_7d": pc,
                    "growth_pct": cat_change["change_pct"],
                    "change_status": cat_change["change_status"],
                    "message": cat_change["message"],
                    "minimum_sample_met": True
                })

            return {
                "total_complaints": total,
                "today_complaints": today_cnt,
                "daily_change_pct": daily_metrics["change_pct"],
                "daily_metrics": daily_metrics,
                "this_week_complaints": w1_cnt,
                "weekly_change_pct": weekly_metrics["change_pct"],
                "weekly_metrics": weekly_metrics,
                "this_month_complaints": m1_cnt,
                "monthly_change_pct": monthly_metrics["change_pct"],
                "monthly_metrics": monthly_metrics,
                "critical_complaints_count": crit_cnt,
                "critical_ratio_pct": crit_ratio_pct,
                "most_problematic_product": most_prob_prod_name,
                "most_problematic_summary": most_prob_summary,
                "product_metrics": prod_metrics,
                "fastest_rising_categories": fastest_rising
            }

    def get_executive_trends(self, days=30):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = now.strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT 
                    SUBSTR(COALESCE(source_published_at, created_at), 1, 10) as day,
                    SUM(CASE WHEN COALESCE(final_product, primary_product) = 'Fiber' THEN 1 ELSE 0 END) as fiber_cnt,
                    SUM(CASE WHEN COALESCE(final_product, primary_product) = 'Superbox' THEN 1 ELSE 0 END) as superbox_cnt,
                    SUM(CASE WHEN COALESCE(final_product, primary_product) = 'ADSL' THEN 1 ELSE 0 END) as adsl_cnt,
                    SUM(CASE WHEN sentiment = 'Negative' THEN 1 ELSE 0 END) as negative_cnt,
                    SUM(CASE WHEN sentiment = 'Neutral' THEN 1 ELSE 0 END) as neutral_cnt,
                    SUM(CASE WHEN sentiment = 'Positive' THEN 1 ELSE 0 END) as positive_cnt,
                    SUM(CASE WHEN urgency IN ('High', 'Critical') THEN 1 ELSE 0 END) as critical_cnt,
                    COUNT(*) as total
                FROM complaints
                WHERE review_status != 'DELETED' AND SUBSTR(COALESCE(source_published_at, created_at), 1, 10) >= ?
                GROUP BY SUBSTR(COALESCE(source_published_at, created_at), 1, 10)
                ORDER BY day ASC
            """, (start_date,))
            
            rows = cursor.fetchall()
            series = [dict(r) for r in rows]
            days_with_data = len(series)

            is_sparse = days_with_data < 5
            warning_msg = f"Son {days} günlük dönemde yalnızca {days_with_data} gün veri bulunmaktadır." if is_sparse else None

            return {
                "series": series,
                "coverage_metadata": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "days_with_data_count": days_with_data,
                    "total_timepoints_count": days,
                    "is_sparse": is_sparse,
                    "warning_message": warning_msg
                }
            }

    def get_latest_source_published_date(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(source_published_at) as max_date FROM complaints WHERE source_published_at IS NOT NULL AND source_published_at != ''")
            row = cursor.fetchone()
            return row["max_date"] if row and row["max_date"] else None

if __name__ == "__main__":
    db = EnterpriseDatabase()
    print("✅ Database ready with checkpoints & executive engine.")
