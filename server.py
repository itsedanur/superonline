"""
Turkcell Superonline Enterprise - Real Data REST API Server (Phase 2.3 - Checkpoints & Multi-Page Support)
"""

import http.server
import socketserver
import urllib.parse
import json
import os
import threading
import uuid
from datetime import datetime
from nlp_engine import SuperonlineEnterpriseAIEngine
from scraper import SuperonlinePrototypeScraper
from database import EnterpriseDatabase

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

ai_engine = SuperonlineEnterpriseAIEngine()
scraper = SuperonlinePrototypeScraper()
db = EnterpriseDatabase()

active_runs = {}
ALLOWED_PRODUCTS = ["Fiber", "Superbox", "ADSL"]

class SuperonlineRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # GET /api/v1/config
        if path in ["/api/config", "/api/v1/config"]:
            self.send_json_response({
                "publicWebPrototypeEnabled": scraper.is_enabled()
            })

        # GET /api/v1/products/compare
        elif path in ["/api/products/compare", "/api/v1/products/compare"]:
            inc_leg = query.get("include_legacy", ["false"])[0].lower() in ["true", "1"]
            self.send_json_response(db.get_products_comparison(include_legacy=inc_leg))

        # GET /api/v1/products/{product}/*
        elif path.startswith("/api/v1/products/") or path.startswith("/api/products/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 4:
                prod = urllib.parse.unquote(parts[3])
                action = parts[4] if len(parts) >= 5 else "summary"

                if prod not in ALLOWED_PRODUCTS:
                    self.send_json_response({"error": f"Geçersiz ürün kategorisi: '{prod}'"}, status=400)
                    return

                inc_leg = query.get("include_legacy", ["false"])[0].lower() in ["true", "1"]

                if action == "summary":
                    self.send_json_response(db.get_product_summary(prod, include_legacy=inc_leg))
                elif action == "trend":
                    days = int(query.get("days", [30])[0])
                    self.send_json_response(db.get_product_trend(prod, days=days, include_legacy=inc_leg))
                elif action == "categories":
                    self.send_json_response(db.get_product_categories(prod, include_legacy=inc_leg))
                elif action == "sentiment":
                    self.send_json_response(db.get_product_sentiment(prod, include_legacy=inc_leg))
                elif action == "urgency":
                    self.send_json_response(db.get_product_urgency(prod, include_legacy=inc_leg))
                elif action == "accuracy":
                    self.send_json_response(db.get_product_accuracy(prod, include_legacy=inc_leg))
                elif action == "complaints":
                    complaints = db.get_all_complaints(product_filter=prod)
                    formatted = [self.format_complaint_dict(c) for c in complaints if inc_leg or not c.get("legacy_record")]
                    self.send_json_response(formatted)
                else:
                    self.send_json_response({"error": f"Geçersiz eylem: '{action}'"}, status=400)
                return

        # GET /api/v1/review-queue
        elif path in ["/api/review-queue", "/api/v1/review-queue"]:
            prod = query.get("product", ["ALL"])[0]
            cat = query.get("category", ["ALL"])[0]
            urgency = query.get("urgency", ["ALL"])[0]
            sentiment = query.get("sentiment", ["ALL"])[0]
            search = query.get("search", [None])[0]
            preset = query.get("preset", [None])[0]

            queue_items = db.get_review_queue(product_filter=prod, category_filter=cat, urgency_filter=urgency, sentiment_filter=sentiment, search_term=search, preset=preset)
            stats = db.get_review_stats()

            formatted = [self.format_complaint_dict(c) for c in queue_items]
            self.send_json_response({
                "queue": formatted,
                "stats": stats
            })

        # GET /api/v1/reviewed-complaints
        elif path == "/api/v1/reviewed-complaints":
            prod = query.get("product", ["ALL"])[0]
            status = query.get("status", ["ALL"])[0]
            date_range = query.get("date_range", ["ALL"])[0]

            reviewed_items = db.get_reviewed_complaints(product_filter=prod, status_filter=status, date_range=date_range)
            formatted = [self.format_complaint_dict(c) for c in reviewed_items]
            self.send_json_response(formatted)

        # GET /api/v1/review-stats
        elif path in ["/api/review-stats", "/api/v1/review-stats"]:
            self.send_json_response(db.get_review_stats())

        # GET /api/v1/scrape-runs/{runId}
        elif path.startswith("/api/v1/scrape-runs/"):
            run_id = path.replace("/api/v1/scrape-runs/", "").strip()
            run_info = db.get_scrape_run(run_id)
            if not run_info:
                self.send_json_response({"error": f"Scrape Run '{run_id}' bulunamadı."}, status=404)
                return
            items = db.get_scrape_run_items(run_id)
            self.send_json_response({"run": run_info, "items": items})

        # GET /api/v1/prototype-scrape/{runId} (Legacy compat)
        elif path.startswith("/api/v1/prototype-scrape/"):
            run_id = path.replace("/api/v1/prototype-scrape/", "").strip()
            run_info = db.get_scrape_run(run_id) or active_runs.get(run_id)
            if not run_info:
                self.send_json_response({"error": f"Scrape Run '{run_id}' bulunamadı."}, status=404)
                return
            self.send_json_response(run_info)

        # GET /api/v1/complaints/{id}/review-history
        elif path.startswith("/api/v1/complaints/") and path.endswith("/review-history"):
            cid = path.replace("/api/v1/complaints/", "").replace("/review-history", "").strip()
            history = db.get_review_history(cid)
            self.send_json_response(history)

        # GET /api/v1/complaints/{id}
        elif path.startswith("/api/v1/complaints/") or path.startswith("/api/complaints/"):
            cid = path.split("/")[-1].strip()
            complaints = db.get_all_complaints()
            found = next((c for c in complaints if c["id"] == cid), None)
            if not found:
                self.send_json_response({"error": f"Şikayet '{cid}' bulunamadı."}, status=404)
                return
            self.send_json_response(self.format_complaint_dict(found))

        # GET /api/v1/complaints
        elif path in ["/api/complaints", "/api/v1/complaints"]:
            prod_filter = query.get("product", ["ALL"])[0]
            date_range = query.get("date_range", ["ALL"])[0]
            sort_order = query.get("sort", ["DESC"])[0]

            complaints = db.get_all_complaints(product_filter=prod_filter, date_range=date_range, sort_order=sort_order)
            formatted = [self.format_complaint_dict(c) for c in complaints]
            self.send_json_response(formatted)

        # GET /api/v1/executive/summary
        elif path in ["/api/executive/summary", "/api/v1/executive/summary"]:
            exec_summary = db.get_executive_summary()
            exec_summary["ai_insights"] = ai_engine.generate_executive_insights(exec_summary)
            self.send_json_response(exec_summary)

        # GET /api/v1/executive/trends
        elif path in ["/api/executive/trends", "/api/v1/executive/trends"]:
            try:
                days = int(query.get("days", [30])[0])
            except ValueError:
                days = 30
            trends = db.get_executive_trends(days=days)
            self.send_json_response(trends)

        # GET /api/v1/executive/insights
        elif path in ["/api/executive/insights", "/api/v1/executive/insights"]:
            exec_summary = db.get_executive_summary()
            insights = ai_engine.generate_executive_insights(exec_summary)
            self.send_json_response(insights)

        # GET /api/v1/stats
        elif path in ["/api/stats", "/api/v1/stats"]:
            db_stats = db.get_stats()
            review_stats = db.get_review_stats()
            total = db_stats["total_complaints"] or 0
            counts = db_stats["product_counts"]

            total_calc = total if total > 0 else 1
            stats = {
                "total_complaints": total,
                "product_counts": counts,
                "product_percentages": {
                    "Fiber": round((counts.get("Fiber", 0) / total_calc) * 100),
                    "Superbox": round((counts.get("Superbox", 0) / total_calc) * 100),
                    "ADSL": round((counts.get("ADSL", 0) / total_calc) * 100),
                    "Ürün Bağımsız Genel Şikâyet": round((counts.get("Ürün Bağımsız Genel Şikâyet", 0) / total_calc) * 100),
                    "Belirlenemedi": round((counts.get("Belirlenemedi", 0) / total_calc) * 100),
                },
                "topic_breakdown": db_stats["topic_counts"],
                "review_stats": review_stats,
                "database_status": "SQLite Persistent Active (Phase 2.3 Product Details Ready)"
            }
            self.send_json_response(stats)

        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        body = self.read_json_body()

        # POST /api/v1/analyze
        if path in ["/api/analyze", "/api/v1/analyze"]:
            text = body.get("text", "") or body.get("comment", "")
            if not text:
                self.send_json_response({"error": "Metin boş olamaz"}, status=400)
                return

            result = ai_engine.analyze(text)
            self.send_json_response(result)

        # POST /api/v1/prototype-scrape
        elif path in ["/api/prototype-scrape", "/api/v1/prototype-scrape"]:
            if not scraper.is_enabled():
                self.send_json_response({
                    "error": "Prototip veri kaynağı devre dışı (ENABLE_PUBLIC_WEB_PROTOTYPE=false veya tanımsız)."
                }, status=403)
                return

            prods = body.get("products", ["Fiber", "Superbox", "ADSL"])
            scan_mode = body.get("scanMode", "STANDARD").upper()
            strategy = body.get("strategy", "INCREMENTAL").upper()

            if scan_mode == "FAST":
                max_pages = 1
                limit = 20
            elif scan_mode == "DEEP":
                max_pages = 5
                limit = 250
            else: # STANDARD
                max_pages = int(body.get("maxPagesPerProduct", 3))
                limit = int(body.get("limitPerProduct", 100))

            run_id = f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
            
            active_runs[run_id] = {
                "id": run_id,
                "status": "RUNNING",
                "requested_limit": limit * len(prods),
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            def background_scrape_worker():
                res = scraper.run_prototype_scrape(
                    run_id,
                    requested_products=prods,
                    limit_per_product=limit,
                    max_pages_per_product=max_pages,
                    strategy=strategy
                )
                active_runs[run_id] = res

            t = threading.Thread(target=background_scrape_worker)
            t.daemon = True
            t.start()

            self.send_json_response({
                "runId": run_id,
                "status": "RUNNING",
                "scanMode": scan_mode,
                "strategy": strategy,
                "maxPagesPerProduct": max_pages,
                "limitPerProduct": limit,
                "message": "Prototip canlı veri toplama işlemi başlatıldı."
            })

        # POST /api/v1/complaints/{id}/approve
        elif path.startswith("/api/v1/complaints/") and path.endswith("/approve"):
            cid = path.replace("/api/v1/complaints/", "").replace("/approve", "").strip()
            ok, msg = db.approve_complaint(cid)
            if ok:
                self.send_json_response({"message": msg, "id": cid})
            else:
                self.send_json_response({"error": msg}, status=400)

        # POST /api/v1/complaints/{id}/correct (was /review)
        elif path.startswith("/api/v1/complaints/") and path.endswith("/correct"):
            cid = path.replace("/api/v1/complaints/", "").replace("/correct", "").strip()
            ok, msg = db.review_and_correct_complaint(cid, body)
            if ok:
                self.send_json_response({"message": msg, "id": cid})
            else:
                self.send_json_response({"error": msg}, status=400)

        # POST /api/v1/complaints/{id}/reject
        elif path.startswith("/api/v1/complaints/") and path.endswith("/reject"):
            cid = path.replace("/api/v1/complaints/", "").replace("/reject", "").strip()
            note = body.get("note", "Kayıt reddedildi")
            ok, msg = db.reject_complaint(cid, note=note)
            if ok:
                self.send_json_response({"message": msg, "id": cid})
            else:
                self.send_json_response({"error": msg}, status=400)

        # POST /api/v1/complaints/{id}/defer
        elif path.startswith("/api/v1/complaints/") and path.endswith("/defer"):
            cid = path.replace("/api/v1/complaints/", "").replace("/defer", "").strip()
            note = body.get("note", "İnceleme ertelendi")
            ok, msg = db.defer_complaint(cid, note=note)
            if ok:
                self.send_json_response({"message": msg, "id": cid})
            else:
                self.send_json_response({"error": msg}, status=400)

        # POST /api/v1/complaints/{id}/reanalyze
        elif path.startswith("/api/v1/complaints/") and path.endswith("/reanalyze"):
            cid = path.replace("/api/v1/complaints/", "").replace("/reanalyze", "").strip()
            complaints = db.get_all_complaints()
            found = next((c for c in complaints if c["id"] == cid), None)
            if not found:
                self.send_json_response({"error": f"Kayıt '{cid}' bulunamadı."}, status=404)
                return

            text = found["masked_content"] or found["raw_content"]
            new_res = ai_engine.analyze(text)
            
            # Save the new result as REANALYZED
            update_dict = {
                "primaryProduct": new_res["primaryProduct"],
                "mainCategory": new_res["mainCategory"],
                "sentiment": new_res["sentiment"],
                "urgency": new_res.get("urgency", "Medium"),
                "emotion": new_res.get("emotion", "Nötr"),
                "reviewNote": "Yeniden analiz yapıldı ve kaydedildi."
            }
            db.review_and_correct_complaint(cid, update_dict, reviewed_by="AI Engine")
            # Update status to REANALYZED
            with db.get_connection() as conn:
                conn.execute("UPDATE complaints SET review_status = 'REANALYZED' WHERE id = ?", (cid,))
                conn.commit()
            db.add_review_history(cid, "REANALYZE", old_values={"primaryProduct": found["primary_product"]}, new_values={"primaryProduct": new_res["primaryProduct"]}, note="AI yeniden analizi yapıldı ve kaydedildi.")

            old_res = {
                "primaryProduct": found["primary_product"],
                "mainCategory": found["main_category"],
                "confidence": found["confidence_score"]
            }

            self.send_json_response({
                "message": "Yeniden analiz yapıldı ve kaydedildi.",
                "oldResult": old_res,
                "newResult": new_res
            })

        else:
            self.send_error(404, "Endpoint Bulunamadı")

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode('utf-8')) if body else {}
        except Exception:
            return {}

    def format_complaint_dict(self, c):
        prod = c.get("primary_product") or c.get("product_category") or "Belirlenemedi"
        prods_list = c.get("products")
        if not prods_list and c.get("products_json"):
            try: prods_list = json.loads(c["products_json"])
            except Exception: pass
        if not prods_list: prods_list = [prod]

        return {
            "id": c["id"],
            "source": c.get("source", "Şikayetvar"),
            "sourceType": c.get("source_type", "public_web_prototype"),
            "sourceUrl": c.get("source_url"),
            "externalId": c.get("external_id"),
            "masked_content": c.get("masked_content", c.get("raw_content", "")),
            "maskedText": c.get("masked_content", c.get("raw_content", "")),
            "primaryProduct": prod,
            "product": prod,
            "products": prods_list,
            "sourceProduct": c.get("source_product"),
            "productConflict": bool(c.get("product_conflict", 0)),
            "isMultiProduct": bool(c.get("is_multi_product", len(prods_list) > 1)),
            "mainCategory": c.get("main_category", c.get("topic_category", "Diğer")),
            "subCategory": c.get("sub_category", "Sınıflandırılamayan Genel Konular"),
            "topic": c.get("main_category", c.get("topic_category", "Diğer")),
            "sentiment": c.get("sentiment", "Negative"),
            "sentimentScore": float(c.get("sentiment_score", -0.85)),
            "emotion": c.get("emotion", "Hayal Kırıklığı"),
            "urgency": c.get("urgency", "Medium"),
            "confidence": float(c.get("confidence_score", 0.95)),
            "evidence": c.get("evidence", []),
            "needsHumanReview": bool(c.get("needs_human_review", 0)),
            "reviewStatus": c.get("review_status", "PENDING"),
            "reviewNote": c.get("review_note"),
            "reviewedBy": c.get("reviewed_by"),
            "reviewedAt": str(c.get("reviewed_at")) if c.get("reviewed_at") else None,
            "originalAiResult": c.get("original_ai_result_json"),
            "correctedFields": c.get("corrected_fields_json"),
            "legacyRecord": bool(c.get("legacy_record", 0)),
            "aiModel": c.get("ai_model", "savasy/bert-base-turkish-sentiment-cased"),
            "engineType": c.get("engine_type", "local_semantic_engine"),
            "promptVersion": c.get("prompt_version", "v3.2-enterprise-context"),
            "recordHash": c.get("record_hash"),
            "date": str(c.get("created_at", ""))
        }

    def send_json_response(self, data, status=200):
        response_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

def run_server():
    print(f"🚀 Turkcell Superonline Enterprise REST API Sunucusu (Phase 2.3 Product Details Mode) Başlatılıyor...")
    print(f"🔗 Arayüz: http://localhost:{PORT}\n")
    with socketserver.TCPServer(("", PORT), SuperonlineRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nSunucu kapatıldı.")

if __name__ == "__main__":
    run_server()
