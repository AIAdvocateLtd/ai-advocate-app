# Helper: create / reset / delete the synthetic UI 2FA user in preview Mongo
import asyncio, sys, uuid, os
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

EMAIL = "synthetic-ui-2fa@synthetic-test.co.uk"
PW = "Synthetic-Pass-123!"


async def main(cmd):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    u = await db.users.find_one({"email": EMAIL})
    if cmd == "create":
        if u:
            print("exists", u["id"]); return
        uid = str(uuid.uuid4())
        await db.users.insert_one({"id": uid, "email": EMAIL, "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode(),
                                   "full_name": "Synthetic", "email_verified": True, "subscription_status": "free",
                                   "terms_accepted": True, "created_at": "2026-11-19"})
        print("created", uid)
    elif cmd == "reset":
        await db.users.update_one({"email": EMAIL}, {"$set": {"totp_enabled": False, "email_2fa_enabled": False},
                                                     "$unset": {"totp_secret": "", "totp_backup_codes": "", "totp_secret_pending": ""}})
        print("reset")
    elif cmd == "show":
        print({k: v for k, v in (u or {}).items() if k not in ("_id", "password_hash", "totp_backup_codes")},
              "backups:", len((u or {}).get("totp_backup_codes") or []))
    elif cmd == "delete":
        if u:
            uid = u["id"]
            r1 = await db.users.delete_one({"id": uid})
            r2 = await db.auth_codes.delete_many({"user_id": uid})
            r3 = await db.login_attempts.delete_many({"key": {"$in": [uid, EMAIL, EMAIL.lower()]}})
            r4 = await db.security_events.delete_many({"user_id": uid})
            print("deleted", r1.deleted_count, r2.deleted_count, r3.deleted_count, r4.deleted_count)
        else:
            print("none")

asyncio.run(main(sys.argv[1]))
