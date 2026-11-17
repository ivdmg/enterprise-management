from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CATALOG = {
    "overview": "Обзор",
    "contracts": "Контракты",
    "engineer_documents": "Документы инженеров",
    "projects": "Тендеры и объекты",
    "finance": "Финансы",
    "procurement": "Снабжение",
    "dispatch": "Диспетчерская",
    "tasks": "Задачи",
    "sources": "Источники",
    "files": "Файлы",
    "settings": "Настройки",
}

# Legacy raw-file and aggregate endpoints combine multiple business domains.
# Hide those entries when enabling them would bypass a domain restriction.
DOMAINS = frozenset({"contracts", "engineer_documents", "projects", "finance", "procurement", "dispatch", "tasks"})
DEPENDENCIES = {
    "overview": {"contracts", "projects", "finance", "procurement"},
    "files": DOMAINS,
}
DEFAULT_MODULES = [
    {"id": module, "label": name, "order": index, "enabled": True, "settings": {}}
    for index, (module, name) in enumerate(CATALOG.items())
]


def effective_modules(modules):
    enabled = {module["id"] for module in modules if module["enabled"]}
    return [module for module in modules
            if module["enabled"] and DEPENDENCIES.get(module["id"], set()) <= enabled]


async def current_revision(db: AsyncSession, company_id):
    row = (await db.execute(text("""
        SELECT revision,state,modules FROM company_config_revisions WHERE company_id=:company AND state='active'
    """), {"company": company_id})).mappings().one_or_none()
    if not row:
        return {"revision": 0, "version": 0, "state": "active", "modules": DEFAULT_MODULES}
    return dict(row) | {"version": row["revision"]}


async def require_modules(db, company_id, required):
    from app.services.platform_auth import auth_error

    config = await current_revision(db, company_id)
    enabled = {module["id"] for module in effective_modules(config["modules"])}
    if not set(required) <= enabled:
        raise auth_error(403, "MODULE_DISABLED", "Раздел не подключён к этой компании")


def module_requirements(path: str, method: str):
    """Return alternative sets of modules for the existing domain routes."""
    parts = path.strip("/").split("/")
    section = parts[0]
    if section == "dashboard" and len(parts) > 1:
        if parts[1] in ("finance", "payroll"):
            return [{"finance"}]
        if parts[1] == "projects":
            return [{"projects"}, {"contracts"}] if method == "GET" else [{"projects"}]
        return [{"overview", *DOMAINS}] if parts[1] == "alerts" else [{"overview"}]
    if section == "customer-tenders":
        return [{"projects"}, {"contracts"}]
    if section in ("drive-catalog", "sync"):
        return [{"sources", *DOMAINS}]
    if section == "alerts":
        return [{"overview", *DOMAINS}]
    if section in ("integrations", "settings"):
        return [{"settings"}]
    standard = {
        "engineer-documents": "engineer_documents",
        "procurement": "procurement",
        "dispatch": "dispatch",
        "tasks": "tasks",
        "files": "files",
    }
    return [{standard[section]}] if section in standard else []


async def enforce_route_modules(db, company_id, path, method):
    choices = module_requirements(path, method)
    if not choices:
        return
    from app.services.platform_auth import auth_error

    config = await current_revision(db, company_id)
    enabled = {module["id"] for module in effective_modules(config["modules"])}
    if not any(choice <= enabled for choice in choices):
        raise auth_error(403, "MODULE_DISABLED", "Раздел не подключён к этой компании")
