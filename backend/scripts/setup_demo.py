"""Provision two demo users without inserting business data. Run from backend/."""
import asyncio
import json
import os
from pathlib import Path
import secrets
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.company import Company
from app.models.user import User
from app.models.enums import UserRole
from app.models.alert import IntegrationSetting

async def main():
    root = Path(__file__).resolve().parents[2]
    access_path = root / ".demo" / "access.json"
    access_path.parent.mkdir(exist_ok=True)
    saved = json.loads(access_path.read_text(encoding="utf-8")) if access_path.exists() else {}
    async with AsyncSessionLocal() as db:
        admin_email = os.getenv("DEMO_ADMIN_EMAIL", "demo-admin@example.com")
        admin = (await db.execute(select(User).where(User.email == admin_email))).scalar_one_or_none()
        company = await db.get(Company, admin.company_id) if admin else Company(name="Демо строительного холдинга", timezone="Europe/Astrakhan", is_active=True)
        if not admin:
            db.add(company)
            await db.flush()
            db.add(IntegrationSetting(company_id=company.id, telegram_bot_enabled=False))
        users = []
        for email, name, role in [(admin_email, "Администратор демо", UserRole.ADMIN),
            (os.getenv("DEMO_CUSTOMER_EMAIL", "demo-customer@example.com"), "Заказчик", UserRole.MANAGER)]:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            password = saved.get(email, {}).get("password") or secrets.token_urlsafe(18)
            if not user:
                db.add(User(company_id=company.id, email=email, full_name=name, role=role,
                    password_hash=get_password_hash(password), is_active=True))
                saved[email] = {"password":password, "name":name}
            users.append(email)
        await db.commit()
        saved["company_id"] = str(company.id)
        access_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        env_path = Path(".env")
        if env_path.exists():
            text = env_path.read_text(encoding="utf-8")
            import re
            for key, value in {"GOOGLE_DRIVE_COMPANY_ID":str(company.id), "ALLOW_REGISTRATION":"false"}.items():
                text = re.sub(rf"(?m)^{key}=.*$", f"{key}={value}", text) if re.search(rf"(?m)^{key}=", text) else text.rstrip()+f"\n{key}={value}\n"
            env_path.write_text(text, encoding="utf-8")
        print("Demo users provisioned:", ", ".join(users))
        print("Credentials saved locally to .demo/access.json; no business data seeded.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
