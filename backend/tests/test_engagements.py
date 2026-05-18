"""End-to-end test of new Engagements API.
Runs full flow: firm signup -> tier bump (DB) -> invite client -> accept -> message -> upload file -> Lex assist.
"""
import os, requests, time, asyncio, json, base64
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ["API_URL"].rstrip("/") + "/api"
FIRM_EMAIL = f"firm_test_{int(time.time())}@advocate.app"
CLIENT_EMAIL = "test@advocate.app"
CLIENT_PWD = "Test12345!"

def must(r, label):
    assert r.status_code < 400, f"{label} failed [{r.status_code}]: {r.text[:300]}"
    print(f"✅ {label}: {r.status_code}")
    return r.json() if r.text else {}

# 1. Firm signup
r = requests.post(f"{API}/firm/signup", json={
    "firm_name": "Test & Co Solicitors", "contact_name": "Jane Doe",
    "email": FIRM_EMAIL, "password": "FirmPass123!", "country": "GB", "city": "London",
    "specialties": ["employment"],
})
firm_data = must(r, "Firm signup")
firm_token = firm_data["access_token"]
firm_id = firm_data["firm"]["id"]
F_HDRS = {"Authorization": f"Bearer {firm_token}"}

# 2. Bump firm to premium in DB (bypass Stripe)
async def bump():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    r = await db.firm_accounts.update_one({"id": firm_id}, {"$set": {"tier": "premium", "status": "approved"}})
    print(f"✅ Firm tier bumped to premium: {r.modified_count}")
asyncio.run(bump())

# 3. Firm invites the client
r = requests.post(f"{API}/firm/engagements", headers=F_HDRS, json={
    "client_email": CLIENT_EMAIL, "matter": "Employment",
    "case_summary": "Unfair dismissal — hearing in 4 weeks",
})
inv = must(r, "Firm creates invite")
eng_id, token = inv["id"], inv["invite_token"]
print(f"  invite_url={inv['invite_url']}")

# 4. Public invite preview (no auth)
must(requests.get(f"{API}/engagements/invite/{token}"), "Public invite preview")

# 5. Client logs in
r = requests.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PWD})
cd = must(r, "Client login")
client_token = cd.get("token") or cd.get("access_token")
C_HDRS = {"Authorization": f"Bearer {client_token}"}

# 6. Client accepts
must(requests.post(f"{API}/engagements/accept/{token}", headers=C_HDRS), "Client accepts invite")

# 7. Client lists engagements
ce = must(requests.get(f"{API}/engagements", headers=C_HDRS), "Client lists engagements")
print(f"  has engagements: {len(ce['engagements'])}")

# 8. Firm lists engagements
fe = must(requests.get(f"{API}/firm/engagements", headers=F_HDRS), "Firm lists engagements")
print(f"  firm has: {fe['active_count']} active of limit {fe['limit']}")

# 9. Client posts message
must(requests.post(f"{API}/engagements/{eng_id}/messages", headers=C_HDRS,
    json={"body": "Hi Jane — could you confirm the hearing date?"}), "Client posts message")
# 10. Firm replies
must(requests.post(f"{API}/engagements/{eng_id}/messages", headers=F_HDRS,
    json={"body": "Confirmed — 14 March, 10am Reading Tribunal. Prep notes by Friday."}), "Firm replies")

# 11. List thread (decrypts on read)
msgs = must(requests.get(f"{API}/engagements/{eng_id}/messages", headers=C_HDRS), "Client reads thread")
assert len(msgs["messages"]) == 2
assert "hearing date" in msgs["messages"][0]["body"].lower()
assert "Confirmed" in msgs["messages"][1]["body"]
print(f"  thread has {len(msgs['messages'])} messages, both decrypted ✓")

# 12. Client uploads a shared file
file_b64 = base64.b64encode(b"P45 dummy PDF content " * 50).decode()
fr = must(requests.post(f"{API}/engagements/{eng_id}/files", headers=C_HDRS,
    json={"title": "P45.pdf", "mime_type": "application/pdf", "file_b64": file_b64, "note": "P45 from old employer"}),
    "Client uploads shared file")
fid = fr["id"]

# 13. Firm lists files
ff = must(requests.get(f"{API}/engagements/{eng_id}/files", headers=F_HDRS), "Firm lists shared files")
assert any(f["id"] == fid for f in ff["files"])

# 14. Firm downloads the file
dl = must(requests.get(f"{API}/engagements/{eng_id}/files/{fid}", headers=F_HDRS), "Firm downloads file")
recovered = base64.b64decode(dl["file_b64"])
assert recovered.startswith(b"P45 dummy PDF content")
print(f"  file decrypted on download ✓ ({len(recovered)} bytes)")

# 15. Lex assist — client asks Lex to draft a reply
lr = must(requests.post(f"{API}/engagements/{eng_id}/lex-assist", headers=C_HDRS,
    json={"kind": "draft_reply"}), "Lex assists client draft reply")
print(f"  Lex draft (first 100 chars): {lr['output'][:100]}...")

# 16. Lex assist — firm asks Lex to summarise
ls = must(requests.post(f"{API}/engagements/{eng_id}/lex-assist", headers=F_HDRS,
    json={"kind": "summarise"}), "Lex summarises for firm")
print(f"  Lex summary (first 100): {ls['output'][:100]}...")

# 17. Close engagement (firm side)
must(requests.patch(f"{API}/engagements/{eng_id}/close", headers=F_HDRS), "Firm closes engagement")

# 18. Sending a message after close should fail
r = requests.post(f"{API}/engagements/{eng_id}/messages", headers=C_HDRS, json={"body": "Last word"})
assert r.status_code == 403, f"Expected 403 on closed engagement, got {r.status_code}"
print(f"✅ Closed-engagement write blocked: {r.status_code}")

print("\n🎉 ALL ENGAGEMENT TESTS PASSED")
