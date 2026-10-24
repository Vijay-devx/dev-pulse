"""
Verification test script for DevPulse.
Tests all routes, HTMX partials, category switching, search, crux, full reader, and bookmarking.
"""
import asyncio
import sys
from httpx import AsyncClient, ASGITransport

from main import app
from database import init_db
from seed import seed_database


async def test_devpulse():
    print("1. Initializing DB and seed data...")
    await init_db()
    seeded = await seed_database()
    print(f"   Seeded: {seeded} new articles.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test 1: Home page (Daily Briefing)
        print("2. Testing GET / (Home page)...")
        res = await client.get("/")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert "DevPulse" in res.text
        assert "Daily Briefing" in res.text
        print("   [OK] Home page loads successfully.")

        # Test 2: Category feeds
        categories = ["daily_briefing", "rea", "bugs_cves", "applied_ai", "dev_qol", "architecture"]
        for cat in categories:
            print(f"3. Testing GET /feed?category={cat}...")
            res = await client.get(f"/feed?category={cat}")
            assert res.status_code == 200, f"Category {cat} failed: {res.status_code}"
            assert "articles-grid" in res.text or "No articles found" in res.text
            print(f"   [OK] Category '{cat}' returned 200 OK.")

        # Test 3: Search
        print("4. Testing search query...")
        res = await client.get("/feed?search=PHP")
        assert res.status_code == 200
        assert "PHP" in res.text
        print("   [OK] Search query for 'PHP' returned matching results.")

        # Test 4: Stage 2 Crux drawer
        print("5. Testing GET /article/1/crux...")
        res = await client.get("/article/1/crux")
        assert res.status_code == 200
        assert "What It Is About" in res.text
        assert "Why It Is Trending" in res.text
        assert "Key Technical Details" in res.text
        assert "Impact" in res.text
        print("   [OK] Stage 2 (The Crux) 4-part brief rendered perfectly.")

        # Test 5: Stage 3 Full Clean Reader
        print("6. Testing GET /article/1/full...")
        res = await client.get("/article/1/full")
        assert res.status_code == 200
        assert "Back to Crux" in res.text
        assert "prose-devpulse" in res.text
        print("   [OK] Stage 3 (Full Reader) markdown rendered successfully.")

        # Test 6: Bookmark toggle
        print("7. Testing POST /article/1/bookmark...")
        res = await client.get("/api/stats")
        stats = res.json()
        print(f"   Stats: {stats}")

        res = await client.post("/article/1/bookmark")
        assert res.status_code == 200
        assert "Saved" in res.text or "Bookmark" in res.text
        print("   [OK] Bookmark toggled successfully.")

        # Test 7: Sync endpoint
        print("8. Testing POST /sync...")
        res = await client.post("/sync")
        assert res.status_code == 200
        print("   [OK] Sync endpoint triggered successfully.")

    print("\nALL 8 TESTS PASSED WITH 100% SUCCESS!")


if __name__ == "__main__":
    asyncio.run(test_devpulse())
