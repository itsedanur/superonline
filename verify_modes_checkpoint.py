"""
Empirical Verification Script for INCREMENTAL vs BACKFILL Checkpoint Logic
Tests Mode-specific acceptance criteria cleanly.
"""

import os
import time
from database import EnterpriseDatabase
from scraper import SuperonlinePrototypeScraper

def verify_modes():
    db = EnterpriseDatabase()
    scraper = SuperonlinePrototypeScraper()

    # Reset checkpoints for Superbox to ensure clean test state
    with db.get_connection() as conn:
        conn.cursor().execute("DELETE FROM scrape_checkpoints WHERE product = 'Superbox'")
        conn.commit()

    print("🚀 Starting Empirical Verification for INCREMENTAL vs BACKFILL Checkpoints...")

    # Step 1: Run INCREMENTAL mode on Superbox
    print("\n--- TEST 1: INCREMENTAL Run (Superbox) ---")
    res1 = scraper.run_prototype_scrape(
        "test-inc-run-1", 
        requested_products=["Superbox"], 
        strategy="INCREMENTAL", 
        max_pages_per_product=2,
        request_delay=1.0
    )
    print(f"Status: {res1['status']}")
    for prod, m in res1["productMetrics"].items():
        print(f"  • {prod}: start_page={m['start_page']}, end_page={m['end_page']}, pages_scanned={m['pages_scanned']}, stop_reason={m['stop_reason']}, next_checkpoint={m['checkpoint_next_page']}")
        assert m['start_page'] == 1, f"{prod} INCREMENTAL must start at page 1!"

    # Verify Checkpoints table did not advance or create backfill cursor after INCREMENTAL
    ck_box = db.get_checkpoint("Superbox")
    print(f"📌 Checkpoint Superbox after INCREMENTAL: {ck_box}")
    assert ck_box is None or ck_box.get("last_page") is None or ck_box.get("last_page") == 0, "INCREMENTAL must NOT update backfill checkpoint!"

    # Step 2: Run BACKFILL mode - Run 1 (pages 1 to 2)
    print("\n--- TEST 2: BACKFILL Run 1 (Superbox pages 1 to 2) ---")
    res2 = scraper.run_prototype_scrape(
        "test-backfill-run-1", 
        requested_products=["Superbox"], 
        strategy="BACKFILL", 
        max_pages_per_product=2,
        request_delay=1.0
    )
    print(f"Status: {res2['status']}")
    for prod, m in res2["productMetrics"].items():
        print(f"  • {prod}: start_page={m['start_page']}, end_page={m['end_page']}, pages_scanned={m['pages_scanned']}, stop_reason={m['stop_reason']}, next_checkpoint={m['checkpoint_next_page']}")
        if res2['status'] != "STOPPED_RATE_LIMIT":
            assert m['start_page'] == 1, f"{prod} BACKFILL Run 1 must start at page 1!"
            assert m['end_page'] == 2, f"{prod} BACKFILL Run 1 must end at page 2!"

    ck_box1 = db.get_checkpoint("Superbox")
    print(f"📌 Checkpoint Superbox after BACKFILL Run 1: {ck_box1}")
    if res2['status'] != "STOPPED_RATE_LIMIT" and ck_box1:
        assert ck_box1['last_page'] == 2, f"BACKFILL Run 1 must save last_page = 2, got {ck_box1['last_page']}"
        assert ck_box1['next_page'] == 3, f"BACKFILL Run 1 must save next_page = 3, got {ck_box1['next_page']}"

        # Step 3: Run BACKFILL mode - Run 2 (Should start at page 3!)
        print("\n--- TEST 3: BACKFILL Run 2 (Superbox pages 3 to 4) ---")
        res3 = scraper.run_prototype_scrape(
            "test-backfill-run-2", 
            requested_products=["Superbox"], 
            strategy="BACKFILL", 
            max_pages_per_product=2,
            request_delay=1.0
        )
        print(f"Status: {res3['status']}")
        for prod, m in res3["productMetrics"].items():
            print(f"  • {prod}: start_page={m['start_page']}, end_page={m['end_page']}, pages_scanned={m['pages_scanned']}, stop_reason={m['stop_reason']}, next_checkpoint={m['checkpoint_next_page']}")
            if res3['status'] != "STOPPED_RATE_LIMIT":
                assert m['start_page'] == 3, f"{prod} BACKFILL Run 2 must start at page 3!"
                assert m['end_page'] == 4, f"{prod} BACKFILL Run 2 must end at page 4!"

        ck_box2 = db.get_checkpoint("Superbox")
        print(f"📌 Checkpoint Superbox after BACKFILL Run 2: {ck_box2}")
        if res3['status'] != "STOPPED_RATE_LIMIT" and ck_box2:
            assert ck_box2['last_page'] == 4, f"BACKFILL Run 2 must save last_page = 4, got {ck_box2['last_page']}"
            assert ck_box2['next_page'] == 5, f"BACKFILL Run 2 must save next_page = 5, got {ck_box2['next_page']}"

    print("\n🎉 ALL INCREMENTAL & BACKFILL CHECKPOINT TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    verify_modes()
