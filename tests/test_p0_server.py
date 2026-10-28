"""P0: server skeleton, security guard, settings, library, queue."""
from __future__ import annotations

import time

from conftest import wait_job


def test_status_and_guard(client):
    st = client.get("/api/system/status").json()
    assert st["app"] == "SIGN2MV" and st["api_level"] >= 1
    # other hosts are refused (DNS rebinding)
    assert client.get("/api/system/status", headers={"host": "evil.example"}).status_code == 403
    # changing requests need the control header
    r = client.post("/api/songs", json={"title": "x"}, headers={"X-SIGN2MV": ""})
    assert r.status_code == 403


def test_settings_language(client):
    s = client.put("/api/settings", json={"language": "en"}).json()
    assert s["language"] == "en" and s["effective_language"] == "en"
    assert client.put("/api/settings", json={"language": "fr"}).status_code == 400
    assert client.put("/api/settings", json={"nope": 1}).status_code == 400


def test_library_crud(client):
    s = client.post("/api/songs", json={"title": "  南都夜曲  "}).json()
    assert s["title"] == "南都夜曲" and s["song_id"].startswith("s")
    assert client.post("/api/songs", json={"title": ""}).status_code == 400
    s2 = client.patch(f"/api/songs/{s['song_id']}", json={"title": "改名"}).json()
    assert s2["title"] == "改名"
    assert [x["title"] for x in client.get("/api/songs").json()["songs"]] == ["改名"]
    assert client.get("/api/songs/../../etc").status_code in (400, 404)
    assert client.delete(f"/api/songs/{s['song_id']}").json()["ok"]
    assert client.get("/api/songs").json()["songs"] == []


def test_queue_order_cancel_timeout(client):
    a = client.post("/api/jobs", json={"kind": "demo", "lane": "gpu", "seconds": 1.2}).json()
    b = client.post("/api/jobs", json={"kind": "demo", "lane": "gpu", "seconds": 5}).json()
    c = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 0.5}).json()
    time.sleep(0.4)
    assert client.get(f"/api/jobs/{b['id']}").json()["position"] == 1  # waits for the GPU lane
    assert wait_job(client, c["id"], 10)["status"] == "succeeded"  # cpu lane runs in parallel
    assert wait_job(client, a["id"], 10)["status"] == "succeeded"
    client.post(f"/api/jobs/{b['id']}/cancel")
    assert wait_job(client, b["id"], 10)["status"] == "cancelled"
    t = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 20, "timeout_s": 1}).json()
    assert wait_job(client, t["id"], 10)["status"] == "timeout"
    f = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 0.3, "fail": True}).json()
    done = wait_job(client, f["id"], 10)
    assert done["status"] == "failed" and done["error_code"] == "demo_failure"


def test_shutdown_requires_force_when_busy(client):
    j = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 10}).json()
    r = client.post("/api/system/shutdown", json={})
    assert r.status_code == 409 and r.json()["error"] == "jobs_running"
    client.post(f"/api/jobs/{j['id']}/cancel")
