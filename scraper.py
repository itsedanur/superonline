"""
Turkcell Superonline - Enterprise Multi-Page Prototype Scraper (Phase 2.3 - Checkpoints & Strategy Modes)
Controlled by `ENABLE_PUBLIC_WEB_PROTOTYPE=true` environment variable.
"""

import urllib.request
import urllib.error
import ssl
import re
import json
import time
import os
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from nlp_engine import SuperonlineEnterpriseAIEngine
from database import EnterpriseDatabase

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

class PrototypeWebScraperException(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

class SuperonlinePrototypeScraper:
    def __init__(self):
        self.ai = SuperonlineEnterpriseAIEngine()
        self.db = EnterpriseDatabase()
        self.source_pages = {
            "Fiber": "https://www.sikayetvar.com/superonline/fiber-internet",
            "Superbox": "https://www.sikayetvar.com/turkcell/superbox",
            "ADSL": "https://www.sikayetvar.com/superonline/adsl"
        }
        self.product_visible_totals = {
            "Fiber": "10.000+",
            "Superbox": "4.498",
            "ADSL": "5.000+"
        }

    def is_enabled(self):
        env_val = os.environ.get("ENABLE_PUBLIC_WEB_PROTOTYPE", "true").lower()
        return env_val in ["true", "1", "yes"]

    def fetch_url(self, url, delay=0.5, max_retries=4):
        if not self.is_enabled():
            raise PrototypeWebScraperException("Prototip veri kaynağı devre dışı (ENABLE_PUBLIC_WEB_PROTOTYPE=false)", 403)

        if delay > 0:
            time.sleep(delay)

        backoff_delays = [1.0, 2.0, 4.0, 8.0]
        last_error = None
        last_status = None

        for attempt in range(1, max_retries + 1):
            start_t = time.time()
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, context=ssl_context, timeout=12) as res:
                    elapsed_ms = int((time.time() - start_t) * 1000)
                    body = res.read().decode('utf-8', errors='ignore')
                    telemetry = {
                        "url": url,
                        "status": res.status,
                        "size": len(body),
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt,
                        "cloudflare": "cloudflare" in res.headers.get("Server", "").lower()
                    }
                    print(f"[HTTP GET OK] {url} -> Status {res.status} ({len(body)} bytes, {elapsed_ms}ms)")
                    return res.url, body, telemetry
            except urllib.error.HTTPError as e:
                elapsed_ms = int((time.time() - start_t) * 1000)
                last_status = e.code
                last_headers = dict(e.headers)
                server_hdr = last_headers.get("Server", "").lower()
                is_cf = "cloudflare" in server_hdr
                retry_after = last_headers.get("Retry-After")
                
                print(f"[HTTP ERROR] Attempt {attempt}/{max_retries} | GET {url} -> Status {e.code} ({e.reason}) | CF: {is_cf} | RetryAfter: {retry_after} | Time: {elapsed_ms}ms")
                
                if e.code in [403, 429] and attempt < max_retries:
                    retry_wait = int(retry_after) if retry_after and retry_after.isdigit() else backoff_delays[attempt - 1]
                    print(f"  └─ Rate limit / Block detected (HTTP {e.code}). Exponential backoff waiting {retry_wait}s...")
                    time.sleep(retry_wait)
                else:
                    last_error = f"HTTP {e.code} {e.reason}"
                    if e.code in [403, 429]:
                        raise PrototypeWebScraperException(f"Erişim engeli/Rate Limit (HTTP {e.code} - Cloudflare: {is_cf}). URL: {url}", e.code)
            except Exception as e:
                elapsed_ms = int((time.time() - start_t) * 1000)
                last_status = 500
                print(f"[HTTP EXCEPTION] Attempt {attempt}/{max_retries} | GET {url} -> {type(e).__name__}: {str(e)} | Time: {elapsed_ms}ms")
                if attempt < max_retries:
                    time.sleep(backoff_delays[attempt - 1])
                else:
                    last_error = str(e)

        raise PrototypeWebScraperException(f"HTTP Bağlantı Hatası: {last_error} (Status: {last_status})", last_status)

    def extract_external_id(self, canonical_url, slug):
        explicit_id = re.search(r'/(?:sikayet|complaint|c)-?(\d{5,})', canonical_url, re.IGNORECASE)
        if explicit_id:
            return f"SK-{explicit_id.group(1)}"

        sha_hash = hashlib.sha256(canonical_url.strip().lower().encode('utf-8')).hexdigest()[:16].upper()
        return f"SK-URL-{sha_hash}"

    def parse_source_date(self, soup, now_dt=None):
        if now_dt is None:
            now_dt = datetime.now()

        date_el = soup.find('div', class_=re.compile(r'time|date|post-time', re.I)) or soup.find('time')
        if not date_el:
            return None, "FAILED"

        raw_txt = date_el.get_text(strip=True)
        if not raw_txt:
            return None, "FAILED"

        parsed_dt = None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d %B %Y", "%Y-%m-%d"]:
            try:
                parsed_dt = datetime.strptime(raw_txt, fmt)
                break
            except Exception:
                pass

        if parsed_dt is None:
            match = re.search(r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})', raw_txt)
            if match:
                try:
                    parsed_dt = datetime.strptime(match.group(1), "%d.%m.%Y %H:%M")
                except Exception:
                    pass

        if parsed_dt is None:
            return None, "FAILED"

        if parsed_dt > (now_dt + timedelta(minutes=5)):
            return None, "FAILED"

        return parsed_dt.strftime("%Y-%m-%d %H:%M:%S"), "SUCCESS"

    def scrape_product_list_page(self, product_key, base_url, page_num=1, delay=0.5):
        target_url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
        final_url, html, telemetry = self.fetch_url(target_url, delay=delay)
        if not html: return final_url, [], "", telemetry
        
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=True)
        items = []
        seen = set()

        for a in links:
            href = a['href']
            if (href.startswith('/superonline/') or href.startswith('/turkcell/')) and href.count('-') >= 2:
                if href not in seen and not any(x in href for x in ['/fiber-internet', '/adsl', '/superbox-500-gb', '/superbox-200-gb', '/yurt-disi-paketleri', '/paketleri']):
                    title = a.get_text(strip=True)
                    if len(title) > 15 and not title.isdigit() and "Şikayet" not in title and "Marka" not in title:
                        seen.add(href)
                        slug = href.split('/')[-1]
                        canonical_url = f"https://www.sikayetvar.com{href}"
                        ext_id = self.extract_external_id(canonical_url, slug)
                        items.append({
                            "sourceProduct": product_key,
                            "sourceUrl": canonical_url,
                            "externalId": ext_id,
                            "title": title,
                            "page_number": page_num
                        })

        fingerprint = hashlib.md5("".join([i["sourceUrl"] for i in items[:3]]).encode('utf-8')).hexdigest()
        return final_url, items, fingerprint, telemetry

    def process_item(self, item, run_id):
        full_text = ""
        now_dt = datetime.now()
        scraped_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            final_url, html, telemetry = self.fetch_url(item["sourceUrl"], delay=0.3)
            source_published_at = None
            date_status = "FAILED"

            if html:
                soup = BeautifulSoup(html, 'html.parser')
                source_published_at, date_status = self.parse_source_date(soup, now_dt=now_dt)

                desc_divs = soup.find_all(['div', 'p'], class_=re.compile(r'description|detail|text|content', re.I))
                for d in desc_divs:
                    txt = d.get_text(strip=True)
                    if len(txt) > 40 and "Toplam çözüm" not in txt and "Aydınlatma" not in txt:
                        full_text = txt
                        break
        except Exception:
            source_published_at = None
            date_status = "FAILED"

        if not full_text:
            full_text = item["title"]

        raw_text = f"{item['title']}. {full_text}"
        record_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()

        masked_text = self.ai.mask_kvkk(raw_text)
        source_product = item["sourceProduct"]
        ai_res = self.ai.analyze(masked_text, source_page_product=source_product, title=item["title"])

        ai_product = ai_res["primaryProduct"]
        final_product = ai_res.get("finalProduct", ai_product)
        product_conflict = ai_res.get("productConflict", False)
        product_decision_source = ai_res.get("productDecisionSource", "LOCAL_RULES")
        needs_human_review = ai_res["needsHumanReview"] or (date_status == "FAILED")

        evidence = ai_res["evidence"]
        if product_conflict:
            evidence.append(f"⚠️ Sayfa ürünü ({source_product}) ile AI tespiti ({ai_product}) çelişiyor.")
        if date_status == "FAILED":
            evidence.append("⚠️ Kaynak yayın tarihi parse edilemedi veya geçersiz.")

        return {
            "id": item["externalId"],
            "source": "Şikayetvar",
            "sourceType": "public_web_prototype",
            "sourceUrl": item["sourceUrl"],
            "externalId": item["externalId"],
            "title": item["title"],
            "rawText": raw_text,
            "maskedText": masked_text,
            "sourceProduct": source_product,
            "primaryProduct": ai_product,
            "finalProduct": final_product,
            "productDecisionSource": product_decision_source,
            "products": ai_res["products"],
            "productConflict": product_conflict,
            "mainCategory": ai_res["mainCategory"],
            "subCategory": ai_res["subCategory"],
            "sentiment": ai_res["sentiment"],
            "sentimentScore": ai_res["sentimentScore"],
            "emotion": ai_res["emotion"],
            "urgency": ai_res["urgency"],
            "confidence": ai_res["confidence"],
            "evidence": evidence,
            "needsHumanReview": needs_human_review,
            "aiModel": ai_res["aiModel"],
            "engineType": ai_res["engineType"],
            "sourcePublishedAt": source_published_at,
            "dateParseStatus": date_status,
            "scrapedAt": scraped_at,
            "importBatchId": run_id,
            "recordHash": record_hash,
            "legacyRecord": 0
        }

    def run_prototype_scrape(self, run_id, requested_products=None, limit_per_product=100, max_pages_per_product=3, strategy="INCREMENTAL", request_delay=0.5):
        if not self.is_enabled():
            self.db.update_scrape_run(run_id, "FAILED", error_msg="Prototip veri kaynağı devre dışı")
            return {
                "runId": run_id,
                "status": "FAILED",
                "error": "Prototip veri kaynağı devre dışı",
                "stats": {"found": 0, "inserted": 0, "duplicate": 0, "failed": 0}
            }

        if requested_products is None:
            requested_products = ["Fiber", "Superbox", "ADSL"]

        self.db.create_scrape_run(run_id, strategy=strategy, requested_products=requested_products, requested_pages=max_pages_per_product)

        found_total = 0
        inserted_total = 0
        duplicate_total = 0
        failed_total = 0
        conflict_total = 0

        product_metrics = {}
        details_list = []
        start_time = time.time()

        global_pages_scanned = 0
        global_raw_cards = 0
        global_details_fetched = 0
        global_parsed_success = 0
        global_stop_reason = "COMPLETED"

        try:
            for prod_key in requested_products:
                if prod_key not in self.source_pages: continue
                base_url = self.source_pages[prod_key]

                checkpoint = self.db.get_checkpoint(prod_key)
                
                if strategy == "BACKFILL":
                    start_page = checkpoint.get("next_page", 1) if checkpoint else 1
                else:
                    start_page = 1

                pages_scanned = 0
                seen_fingerprints = set()
                stop_reason = "MAX_PAGES_REACHED"
                
                # Phase 1: Pagination Loop - Gather all items across requested pages
                all_complaints = []
                last_seen_url = None
                last_seen_date = None

                product_page_details = []
                for page_offset in range(max_pages_per_product):
                    current_page = start_page + page_offset
                    
                    try:
                        final_url, items, fingerprint, telemetry = self.scrape_product_list_page(prod_key, base_url, page_num=current_page, delay=request_delay)
                        product_page_details.append({
                            "page": current_page,
                            "url": final_url,
                            "http_status": telemetry["status"],
                            "response_size": telemetry["size"],
                            "elapsed_ms": telemetry["elapsed_ms"],
                            "cards_found": len(items)
                        })
                    except PrototypeWebScraperException as pe:
                        status_code = getattr(pe, 'status_code', None)
                        status_str = "STOPPED_RATE_LIMIT" if status_code in [403, 429] else "FAILED"
                        stop_reason = status_str
                        product_page_details.append({
                            "page": current_page,
                            "url": f"{base_url}?page={current_page}" if current_page > 1 else base_url,
                            "http_status": status_code or 500,
                            "response_size": 0,
                            "elapsed_ms": 0,
                            "cards_found": 0,
                            "error": str(pe)
                        })
                        break
                    except Exception as e:
                        stop_reason = "ERROR"
                        product_page_details.append({
                            "page": current_page,
                            "url": f"{base_url}?page={current_page}" if current_page > 1 else base_url,
                            "http_status": 500,
                            "response_size": 0,
                            "elapsed_ms": 0,
                            "cards_found": 0,
                            "error": str(e)
                        })
                        break

                    if not items:
                        stop_reason = "NO_MORE_PAGES"
                        break

                    if fingerprint in seen_fingerprints:
                        stop_reason = "STOPPED_REPEATED_PAGE"
                        break

                    seen_fingerprints.add(fingerprint)
                    pages_scanned += 1
                    global_pages_scanned += 1
                    global_raw_cards += len(items)

                    if not last_seen_url and items:
                        last_seen_url = items[0]["sourceUrl"]

                    all_complaints.extend(items)

                # Phase 2: Run-Level Cross-Page Deduplication
                unique_by_url = {}
                cross_page_duplicates_items = []
                cross_page_duplicate_count = 0

                for item in all_complaints:
                    canonical = item["sourceUrl"]
                    if canonical in unique_by_url:
                        cross_page_duplicate_count += 1
                        cross_page_duplicates_items.append(item)
                    else:
                        unique_by_url[canonical] = item

                # Log Cross-Page Duplicates to scrape_run_items
                for cp_item in cross_page_duplicates_items:
                    self.db.insert_scrape_run_item(
                        run_id=run_id,
                        product_source_page=prod_key,
                        page_number=cp_item.get("page_number"),
                        list_url=f"{base_url}?page={cp_item.get('page_number', 1)}",
                        complaint_url=cp_item["sourceUrl"],
                        title=cp_item["title"],
                        source_published_at=None,
                        external_id=cp_item.get("externalId"),
                        detected_product=prod_key,
                        product_confidence=1.0,
                        product_evidence="Aynı run içerisinde birden fazla sayfada tekrar eden URL",
                        status="DUPLICATE",
                        complaint_id=cp_item.get("externalId"),
                        duplicate_match_reason="CROSS_PAGE_DUPLICATE",
                        error_message=None
                    )

                prod_found = len(unique_by_url)
                found_total += prod_found
                
                prod_inserted = 0
                prod_duplicate = 0
                prod_failed = 0
                consecutive_duplicates = 0

                # Phase 3: Detail Fetch and DB Insert
                items_to_process = list(unique_by_url.values())
                
                for item in items_to_process:
                    if limit_per_product and prod_inserted >= limit_per_product:
                        stop_reason = "LIMIT_REACHED"
                        break

                    try:
                        global_details_fetched += 1
                        processed = self.process_item(item, run_id)
                        global_parsed_success += 1
                        if not last_seen_date:
                            last_seen_date = processed["sourcePublishedAt"]

                        is_dup, reason, matched_id = self.db.check_is_duplicate(
                            external_id=processed["externalId"],
                            source_url=processed["sourceUrl"],
                            record_hash=processed["recordHash"],
                            masked_content=processed["maskedText"],
                            title=processed["title"],
                            date_str=processed["sourcePublishedAt"]
                        )

                        item_status = "DUPLICATE" if is_dup else "NEW_INSERTED"
                        match_reason_str = reason if is_dup else "NONE"

                        if is_dup:
                            prod_duplicate += 1
                            duplicate_total += 1
                            consecutive_duplicates += 1
                        else:
                            processed["duplicateMatchReason"] = None
                            processed["matchedComplaintId"] = None
                            self.db.insert_complaint(processed)
                            prod_inserted += 1
                            inserted_total += 1
                            consecutive_duplicates = 0
                            if processed.get("productConflict"):
                                conflict_total += 1

                        self.db.insert_scrape_run_item(
                            run_id=run_id,
                            product_source_page=prod_key,
                            page_number=item.get("page_number"),
                            list_url=final_url,
                            complaint_url=processed["sourceUrl"],
                            title=processed["title"],
                            source_published_at=processed["sourcePublishedAt"],
                            external_id=processed["externalId"],
                            detected_product=processed.get("finalProduct", processed.get("primaryProduct")),
                            product_confidence=processed.get("confidence", 0.0),
                            product_evidence="\n".join(processed.get("evidence", [])),
                            status=item_status,
                            complaint_id=processed.get("id"),
                            duplicate_match_reason=match_reason_str,
                            error_message=None
                        )

                    except Exception as e:
                        prod_failed += 1
                        failed_total += 1
                        self.db.insert_scrape_run_item(
                            run_id=run_id,
                            product_source_page=prod_key,
                            page_number=item.get("page_number"),
                            list_url=final_url if 'final_url' in locals() else base_url,
                            complaint_url=item["sourceUrl"],
                            title=item["title"],
                            source_published_at=None,
                            external_id=item.get("externalId"),
                            detected_product=None,
                            product_confidence=0.0,
                            product_evidence=None,
                            status="FAILED",
                            complaint_id=None,
                            duplicate_match_reason=None,
                            error_message=str(e)
                        )

                    if strategy == "INCREMENTAL" and consecutive_duplicates >= 20:
                        stop_reason = "CONSECUTIVE_DUPLICATES_REACHED"
                        break

                if strategy == "BACKFILL" and pages_scanned > 0:
                    self.db.update_checkpoint(prod_key, base_url, last_page=start_page + pages_scanned - 1, last_seen_url=last_seen_url, last_seen_date=last_seen_date, status="IDLE")

                final_ck = self.db.get_checkpoint(prod_key)
                next_page_val = final_ck.get("next_page", 2) if final_ck else 2

                product_metrics[prod_key] = {
                    "total_visible_on_site": self.product_visible_totals.get(prod_key, "1.000+"),
                    "strategy": strategy,
                    "start_page": start_page,
                    "end_page": start_page + pages_scanned - 1 if pages_scanned > 0 else start_page,
                    "pages_scanned": pages_scanned,
                    "cards_seen": prod_found + cross_page_duplicate_count,
                    "unique_urls": prod_found,
                    "cross_page_duplicates": cross_page_duplicate_count,
                    "inserted": prod_inserted,
                    "duplicate": prod_duplicate,
                    "failed": prod_failed,
                    "stop_reason": stop_reason,
                    "checkpoint_next_page": next_page_val,
                    "pages": product_page_details
                }

                if stop_reason in ["STOPPED_RATE_LIMIT", "FAILED", "ERROR"]:
                    global_stop_reason = stop_reason
                    for remaining_prod in requested_products:
                        if remaining_prod not in product_metrics and remaining_prod in self.source_pages:
                            rem_ck = self.db.get_checkpoint(remaining_prod)
                            rem_next = rem_ck.get("next_page", 2) if rem_ck else 2
                            product_metrics[remaining_prod] = {
                                "total_visible_on_site": self.product_visible_totals.get(remaining_prod, "1.000+"),
                                "strategy": strategy,
                                "start_page": rem_ck.get("next_page", 1) if strategy == "BACKFILL" and rem_ck else 1,
                                "end_page": rem_ck.get("next_page", 1) if strategy == "BACKFILL" and rem_ck else 1,
                                "pages_scanned": 0,
                                "cards_seen": 0,
                                "unique_urls": 0,
                                "cross_page_duplicates": 0,
                                "inserted": 0,
                                "duplicate": 0,
                                "failed": 0,
                                "stop_reason": stop_reason,
                                "checkpoint_next_page": rem_next
                            }
                    duration = round(time.time() - start_time, 2)
                    self.db.update_scrape_run(run_id, global_stop_reason, pages_scanned=global_pages_scanned, raw_cards=global_raw_cards, unique_urls=found_total, details_fetched=global_details_fetched, parsed_success=global_parsed_success, inserted=inserted_total, duplicate=duplicate_total, failed=failed_total, conflict_count=conflict_total, stop_reason=global_stop_reason, error_msg=f"Scraper stopped early: {global_stop_reason}", details=details_list)
                    return {
                        "runId": run_id,
                        "status": global_stop_reason,
                        "durationSeconds": duration,
                        "strategy": strategy,
                        "productMetrics": product_metrics,
                        "stats": {"found": found_total, "inserted": inserted_total, "duplicate": duplicate_total, "failed": failed_total},
                        "details": details_list
                    }

            duration = round(time.time() - start_time, 2)
            self.db.update_scrape_run(run_id, "COMPLETED", pages_scanned=global_pages_scanned, raw_cards=global_raw_cards, unique_urls=found_total, details_fetched=global_details_fetched, parsed_success=global_parsed_success, inserted=inserted_total, duplicate=duplicate_total, failed=failed_total, conflict_count=conflict_total, stop_reason=global_stop_reason, details=details_list)

            return {
                "runId": run_id,
                "status": "COMPLETED",
                "durationSeconds": duration,
                "strategy": strategy,
                "productMetrics": product_metrics,
                "stats": {
                    "found": found_total,
                    "inserted": inserted_total,
                    "duplicate": duplicate_total,
                    "failed": failed_total
                },
                "details": details_list
            }

        except Exception as global_ex:
            for remaining_prod in requested_products:
                if remaining_prod not in product_metrics and remaining_prod in self.source_pages:
                    rem_ck = self.db.get_checkpoint(remaining_prod)
                    rem_next = rem_ck.get("next_page", 2) if rem_ck else 2
                    product_metrics[remaining_prod] = {
                        "total_visible_on_site": self.product_visible_totals.get(remaining_prod, "1.000+"),
                        "strategy": strategy,
                        "start_page": rem_ck.get("next_page", 1) if strategy == "BACKFILL" and rem_ck else 1,
                        "end_page": rem_ck.get("next_page", 1) if strategy == "BACKFILL" and rem_ck else 1,
                        "pages_scanned": 0,
                        "cards_seen": 0,
                        "unique_urls": 0,
                        "cross_page_duplicates": 0,
                        "inserted": 0,
                        "duplicate": 0,
                        "failed": 0,
                        "stop_reason": "FAILED_ERROR",
                        "checkpoint_next_page": rem_next
                    }
            self.db.update_scrape_run(run_id, "FAILED", pages_scanned=global_pages_scanned, raw_cards=global_raw_cards, unique_urls=found_total, details_fetched=global_details_fetched, parsed_success=global_parsed_success, inserted=inserted_total, duplicate=duplicate_total, failed=failed_total, conflict_count=conflict_total, stop_reason="FAILED_ERROR", error_msg=str(global_ex), details=details_list)
            return {
                "runId": run_id,
                "status": "FAILED",
                "error": str(global_ex),
                "strategy": strategy,
                "productMetrics": product_metrics,
                "stats": {"found": found_total, "inserted": inserted_total, "duplicate": duplicate_total, "failed": failed_total},
                "details": details_list
            }

SuperonlineLiveScraper = SuperonlinePrototypeScraper
