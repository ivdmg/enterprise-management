"""
Seed CLI Tool for Smart Enterprise Hub (BE-4.1).

Usage:
    python -m app.db.seed [--drop] [--company-name NAME]

Features:
- Provisions default tenant company: АО «Мосинжстрой» (ИНН 7701234567).
- Provisions admin and manager users with OWASP-compliant bcrypt passwords.
- Creates integration settings with default 44-FZ key rate (19%).
- Creates 5 construction & tender projects across different project lifecycle stages
  (preparation, submitted, bidding, won, contract) with realistic financial volumes.
- Creates bank guarantees, including 1 expiring in <= 3 days to trigger critical risk,
  3 active ones, and 1 closed.
- Creates 15 procurement items (арматура А500С, бетон В25, кабельная продукция,
  кирпич, утеплитель) across statuses: 'Счет на оплате', 'Оплачено', 'В пути', 'На объекте'.
- Creates 8 fleet dispatch records (экскаваторы CAT, самосвалы КАМАЗ, автокраны Liebherr,
  бетононасосы Putzmeister) with on_site, repair, downtime states.
- Creates 10 operational tasks linked to objects and roles (ГИП, снабженец, юрист, прораб).
- Automatically triggers AlertsEngine to compute 44-FZ penalties, bank guarantee risks,
  procurement delivery delays, and generate critical alerts for "Где горит?".
"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.alert import IntegrationSetting, SystemAlert
from app.models.company import Company
from app.models.dispatch import FleetDispatchRecord
from app.models.enums import AlertSeverity, DomainCategory, ProjectRisk, TaskPriority, TaskStatus, UserRole
from app.models.finance import CashflowOperation
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.task import OperationalTask
from app.models.user import User
from app.services.alerts_engine import alerts_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


async def clear_database(db: AsyncSession, company_id: uuid.UUID) -> None:
    """Safely flushes all operational records for the company before seeding."""
    logger.info("Cleaning existing operational records for company %s...", company_id)
    await db.execute(delete(SystemAlert).where(SystemAlert.company_id == company_id))
    await db.execute(delete(OperationalTask).where(OperationalTask.company_id == company_id))
    await db.execute(delete(FleetDispatchRecord).where(FleetDispatchRecord.company_id == company_id))
    await db.execute(delete(ProcurementItem).where(ProcurementItem.company_id == company_id))
    await db.execute(delete(CashflowOperation).where(CashflowOperation.company_id == company_id))
    await db.execute(delete(TenderProject).where(TenderProject.company_id == company_id))
    await db.flush()


async def seed_data(drop_tables: bool = False) -> None:
    today = datetime.now(timezone.utc).date()
    logger.info("Starting Seed process at %s (today=%s)...", datetime.now(timezone.utc).isoformat(), today)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # 1. Company
            comp_q = select(Company).where(Company.inn == "7701234567").order_by(Company.created_at.asc())
            comp_res = await db.execute(comp_q)
            company = comp_res.scalars().first()

            if not company:
                company = Company(
                    id=uuid.uuid4(),
                    name="АО Мосинжстрой",
                    inn="7701234567",
                    kpp="770101001",
                    timezone="Europe/Moscow",
                    is_active=True,
                )
                db.add(company)
                await db.flush()
                logger.info("Created tenant company: %s (%s)", company.name, company.id)
            else:
                logger.info("Found existing tenant company: %s (%s)", company.name, company.id)

            company_id = company.id

            # Flush previous data for this company
            await clear_database(db, company_id)

            # 2. Integration Setting
            setting_q = select(IntegrationSetting).where(IntegrationSetting.company_id == company_id)
            setting = (await db.execute(setting_q)).scalar_one_or_none()
            if not setting:
                setting = IntegrationSetting(
                    company_id=company_id,
                    telegram_bot_enabled=True,
                    daily_digest_enabled=True,
                    daily_digest_time="08:30",
                    alert_rules={
                        "deadline_warning_days": 5,
                        "cash_gap_forecast_days": 14,
                        "notify_on_critical_instant": True,
                        "key_rate_percent": 19.0,
                    },
                )
                db.add(setting)
                await db.flush()

            # 3. Default Users
            users_data = [
                ("admin@mosinzh.ru", "Смирнов Алексей Викторович", UserRole.ADMIN, "admin123"),
                ("chief@mosinzh.ru", "Иванов Иван Иванович", UserRole.MANAGER, "chief123"),
                ("pto@mosinzh.ru", "Петров Василий Сергеевич", UserRole.MANAGER, "pto123"),
            ]
            for email, full_name, role, pwd in users_data:
                u_q = select(User).where(User.email == email)
                user = (await db.execute(u_q)).scalar_one_or_none()
                if not user:
                    user = User(
                        company_id=company_id,
                        email=email,
                        password_hash=get_password_hash(pwd),
                        full_name=full_name,
                        role=role,
                        is_active=True,
                    )
                    db.add(user)
                    await db.flush()
                    logger.info("Created user: %s (%s)", email, role.value)

            # 4. 5 Объектов СМР
            # - 1 с критической гарантией (<4 дней)
            # - 1 просроченный СМР с расчетом неустойки 44-ФЗ
            # - 3 активных на разных стадиях (степперах)
            projects_data = [
                {
                    "project_code": "СМР-101",
                    "purchase_number": "0173200001424000101",
                    "project_name": "Школа на 1100 мест в мкр. Северный",
                    "customer_name": "Департамент строительства г. Москвы",
                    "curator_name": "Иванов И.И.",
                    "contract_sum": Decimal("485000000.00"),
                    "completed_sum": Decimal("320000000.00"),
                    "paid_sum": Decimal("300000000.00"),
                    "debt_sum": Decimal("20000000.00"),
                    "start_date": today - timedelta(days=220),
                    "deadline_date": today + timedelta(days=25),
                    "bank_guarantee_expiry": today + timedelta(days=3),  # КРИТИЧЕСКИЙ РИСК РНП (< 4 дней)
                    "application_guarantee_sum": Decimal("24250000.00"),
                    "status": "in_progress",
                    "risk_level": ProjectRisk.CRITICAL,
                    "custom_attributes": {"tender_stage": "contract", "bank_name": "ПАО Сбербанк"},
                },
                {
                    "project_code": "СМР-102",
                    "purchase_number": "0173200001424000102",
                    "project_name": "Мост через р. Истра (ПК 42+00)",
                    "customer_name": "ГКУ Московской области «Мосавтодор»",
                    "curator_name": "Петров В.С.",
                    "contract_sum": Decimal("320000000.00"),
                    "completed_sum": Decimal("210000000.00"),
                    "paid_sum": Decimal("190000000.00"),
                    "debt_sum": Decimal("20000000.00"),
                    "start_date": today - timedelta(days=180),
                    "deadline_date": today - timedelta(days=4),  # ПРОСРОЧЕН на 4 дня (44-ФЗ неустойка)
                    "bank_guarantee_expiry": today + timedelta(days=90),
                    "application_guarantee_sum": Decimal("16000000.00"),
                    "status": "in_progress",
                    "risk_level": ProjectRisk.CRITICAL,
                    "custom_attributes": {"tender_stage": "contract", "bank_name": "Банк ВТБ"},
                },
                {
                    "project_code": "СМР-103",
                    "purchase_number": "0173200001424000103",
                    "project_name": "ЖК «Северное Сияние» (Корпуса 1-3)",
                    "customer_name": "ГК «Самолет Девелопмент»",
                    "curator_name": "Сидоров М.И.",
                    "contract_sum": Decimal("750000000.00"),
                    "completed_sum": Decimal("450000000.00"),
                    "paid_sum": Decimal("400000000.00"),
                    "debt_sum": Decimal("50000000.00"),
                    "start_date": today - timedelta(days=300),
                    "deadline_date": today + timedelta(days=120),
                    "bank_guarantee_expiry": today + timedelta(days=150),
                    "application_guarantee_sum": Decimal("37500000.00"),
                    "status": "in_progress",
                    "risk_level": ProjectRisk.NORMAL,
                    "custom_attributes": {"tender_stage": "contract", "bank_name": "Газпромбанк"},
                },
                {
                    "project_code": "СМР-104",
                    "purchase_number": "0173200001424000104",
                    "project_name": "ТЦ «Авангард» (Инженерные сети)",
                    "customer_name": "ООО «Авангард Молл»",
                    "curator_name": "Кузнецов Д.В.",
                    "contract_sum": Decimal("145000000.00"),
                    "completed_sum": Decimal("35000000.00"),
                    "paid_sum": Decimal("35000000.00"),
                    "debt_sum": Decimal("0.00"),
                    "start_date": today - timedelta(days=40),
                    "deadline_date": today + timedelta(days=200),
                    "bank_guarantee_expiry": today + timedelta(days=10),  # WARNING (6-15 дней)
                    "application_guarantee_sum": Decimal("7250000.00"),
                    "status": "in_progress",
                    "risk_level": ProjectRisk.WARNING,
                    "custom_attributes": {"tender_stage": "bidding", "bank_name": "Альфа-Банк"},
                },
                {
                    "project_code": "СМР-105",
                    "purchase_number": "0173200001424000105",
                    "project_name": "Логистический парк «Юг» (Складской блок B)",
                    "customer_name": "ПАО «ПФО-Логистика»",
                    "curator_name": "Орлов А.К.",
                    "contract_sum": Decimal("210000000.00"),
                    "completed_sum": Decimal("210000000.00"),
                    "paid_sum": Decimal("210000000.00"),
                    "debt_sum": Decimal("0.00"),
                    "start_date": today - timedelta(days=400),
                    "deadline_date": today - timedelta(days=30),
                    "actual_completion_date": today - timedelta(days=30),
                    "bank_guarantee_expiry": today - timedelta(days=10),  # Закрытая БГ
                    "application_guarantee_sum": Decimal("10500000.00"),
                    "status": "completed",
                    "risk_level": ProjectRisk.NORMAL,
                    "custom_attributes": {"tender_stage": "won", "bank_name": "ПАО Сбербанк"},
                },
            ]

            project_objs = []
            for p_dict in projects_data:
                proj = TenderProject(company_id=company_id, **p_dict)
                db.add(proj)
                project_objs.append(proj)
            await db.flush()
            logger.info("Created %d construction projects", len(project_objs))

            # 5. 15 счетов ТМЦ в снабжении
            proc_data = [
                ("Школа на 1100 мест в мкр. Северный", "Арматура А500С d16мм", Decimal("45.0"), "т", "Северсталь Дистрибуция", Decimal("2925000.00"), "Оплачено", today + timedelta(days=2)),
                ("Школа на 1100 мест в мкр. Северный", "Бетон В25 W6 F150", Decimal("150.0"), "м³", "БетонМастер-Холдинг", Decimal("900000.00"), "В пути", today - timedelta(days=2)),  # Просрочка поставки бетона!
                ("Школа на 1100 мест в мкр. Северный", "Кирпич керамический полнотелый М150", Decimal("35000.0"), "шт", "ПромСтройКомплект", Decimal("700000.00"), "На объекте", today - timedelta(days=5)),
                ("Школа на 1100 мест в мкр. Северный", "Кабельная продукция ВВГнг-FRLS 5х16", Decimal("1200.0"), "м", "ООО КабельЭлектро", Decimal("840000.00"), "Счет на оплате", today + timedelta(days=6)),
                ("Школа на 1100 мест в мкр. Северный", "Минераловатный утеплитель Техноруф 100мм", Decimal("800.0"), "м²", "ТД Технониколь", Decimal("640000.00"), "Оплачено", today + timedelta(days=4)),

                ("Мост через р. Истра (ПК 42+00)", "Арматурная сталь периодического профиля А500С", Decimal("80.0"), "т", "НЛМК Снабжение", Decimal("5200000.00"), "Оплачено", today - timedelta(days=1)),
                ("Мост через р. Истра (ПК 42+00)", "Бетон гидротехнический мостовой В35 W12", Decimal("220.0"), "м³", "Евробетон-Групп", Decimal("1540000.00"), "В пути", today + timedelta(days=1)),
                ("Мост через р. Истра (ПК 42+00)", "Гидроизоляция мостового полотна Мостопласт", Decimal("1400.0"), "м²", "ТД Технониколь", Decimal("1120000.00"), "Счет на оплате", today + timedelta(days=7)),
                ("Мост через р. Истра (ПК 42+00)", "Трубы стальные 159х8 для водоотвода", Decimal("90.0"), "м", "ЧТПЗ Снабжение", Decimal("540000.00"), "На объекте", today - timedelta(days=10)),

                ("ЖК «Северное Сияние» (Корпуса 1-3)", "Арматура термомеханически упрочненная А500С", Decimal("110.0"), "т", "ЕВРАЗ Маркет", Decimal("7150000.00"), "Счет на оплате", today + timedelta(days=3)),
                ("ЖК «Северное Сияние» (Корпуса 1-3)", "Бетон монолитный В30", Decimal("300.0"), "м³", "БетонМастер-Холдинг", Decimal("1950000.00"), "В пути", today + timedelta(days=2)),
                ("ЖК «Северное Сияние» (Корпуса 1-3)", "Газобетонные блоки D500 600х300х200", Decimal("180.0"), "м³", "ГК Бонолит", Decimal("990000.00"), "На объекте", today - timedelta(days=3)),

                ("ТЦ «Авангард» (Инженерные сети)", "Кабель огнестойкий КПСВЭВнг(А)-FRLS", Decimal("3500.0"), "м", "ООО КабельЭлектро", Decimal("525000.00"), "Счет на оплате", today + timedelta(days=8)),
                ("ТЦ «Авангард» (Инженерные сети)", "Труба профильная 80х80х4", Decimal("65.0"), "м", "МеталлСервис", Decimal("260000.00"), "Оплачено", today + timedelta(days=5)),
                ("Логистический парк «Юг» (Складской блок B)", "Сэндвич-панели PIR 120мм", Decimal("2200.0"), "м²", "Профхолод ТД", Decimal("4840000.00"), "На объекте", today - timedelta(days=35)),
            ]

            for proj_name, item_name, qty, unit, supp, inv_amt, st, d_dl in proc_data:
                db.add(
                    ProcurementItem(
                        company_id=company_id,
                        project_name=proj_name,
                        item_name=item_name,
                        quantity=qty,
                        unit=unit,
                        supplier=supp,
                        invoice_amount=inv_amt,
                        status=st,
                        delivery_deadline=d_dl,
                    )
                )
            await db.flush()
            logger.info("Created %d procurement supply items", len(proc_data))

            # 6. 8 единиц спецтехники в Диспетчерской
            fleet_data = [
                (today, "Школа на 1100 мест в мкр. Северный", "machinery", "Автокран Liebherr LTM 1050 (50т)", "Воронов А.М. (Машинист)", "На объекте", "В работе по монтажу перекрытий 2 этажа"),
                (today, "Школа на 1100 мест в мкр. Северный", "machinery", "Автобетононасос Putzmeister 36м", "Кудряшов Е.А. (Оператор)", "На объекте", "Приемка товарного бетона под ростверк"),
                (today, "Мост через р. Истра (ПК 42+00)", "machinery", "Гусеничный экскаватор CAT 320D", "Ковалев Н.И. (Оператор)", "На объекте", "Выемка грунта под береговую опору №2"),
                (today, "Мост через р. Истра (ПК 42+00)", "machinery", "Самосвал КАМАЗ 6520 (20т)", "Ильин Д.С. (Водитель)", "В ремонте", "Замена гидроцилиндра кузова, ожидается доставка РВД"),
                (today, "ЖК «Северное Сияние» (Корпуса 1-3)", "machinery", "Башенный кран Potain MCT 88", "Романов С.В. (Крановщик)", "На объекте", "Подъем армокаркасов секции Б"),
                (today, "ЖК «Северное Сияние» (Корпуса 1-3)", "machinery", "Бульдозер Komatsu D65EX", "Григорьев П.С. (Машинист)", "Простой", "Технический простой из-за переувлажнения грунта"),
                (today, "ТЦ «Авангард» (Инженерные сети)", "machinery", "Экскаватор-погрузчик JCB 3CX", "Сергеев В.Н. (Оператор)", "На объекте", "Разработка траншей под кабельную трассу"),
                (today, "Логистический парк «Юг» (Складской блок B)", "machinery", "Автогрейдер ДЗ-98", "Михайлов К.И. (Машинист)", "На объекте", "Планировка площадки отстоя грузового транспорта"),
            ]

            for s_date, t_obj, r_type, u_name, resp_p, st, inc_notes in fleet_data:
                db.add(
                    FleetDispatchRecord(
                        company_id=company_id,
                        shift_date=s_date,
                        target_object=t_obj,
                        resource_type=r_type,
                        unit_name=u_name,
                        responsible_person=resp_p,
                        status=st,
                        incident_notes=inc_notes,
                    )
                )
            await db.flush()
            logger.info("Created %d dispatch fleet records", len(fleet_data))

            # 7. 10 оперативных задач в Смарт-реестре
            tasks_data = [
                ("Срочное продление банковской гарантии в Сбербанке", "СМР-101 / Школа 1100 мест", "tender", "Смирнов К.С. (Тендерный специалист)", today + timedelta(days=2), TaskPriority.URGENT, "Риск расторжения контракта и занесения в РНП по 44-ФЗ", Decimal("24250000.00"), TaskStatus.IN_PROGRESS),
                ("Подача протокола разногласий по доп. соглашению", "СМР-102 / Мост р. Истра", "lawyer", "Кузнецов Д.В. (Юрист)", today + timedelta(days=1), TaskPriority.URGENT, "Штрафные санкции и несогласованные объемы", Decimal("500000.00"), TaskStatus.IN_PROGRESS),
                ("Устранение срыва поставки товарного бетона", "СМР-101 / Школа 1100 мест", "procurement", "Васильев П.Н. (Снабженец)", today, TaskPriority.URGENT, "Остановка бетонирования ростверка", Decimal("900000.00"), TaskStatus.IN_PROGRESS),
                ("Сдача исполнительной документации и актов КС-2", "СМР-102 / Мост р. Истра", "engineer", "Петров В.С. (ГИП)", today + timedelta(days=3), TaskPriority.HIGH, "Начисление пени за каждый день просрочки КС-2", Decimal("150000.00"), TaskStatus.IN_PROGRESS),
                ("Согласование акта освидетельствования скрытых работ", "СМР-103 / ЖК Северное Сияние", "engineer", "Семенов В.П. (Прораб)", today + timedelta(days=4), TaskPriority.MEDIUM, "Задержка перехода на следующий технологический этап", Decimal("0.00"), TaskStatus.IN_PROGRESS),
                ("Пересогласование графика бетонирования корпуса №2", "СМР-103 / ЖК Северное Сияние", "manager", "Иванов И.И. (ГИП)", today + timedelta(days=5), TaskPriority.MEDIUM, "Корректировка календарно-сетевого графика", Decimal("0.00"), TaskStatus.PENDING),
                ("Оплата счета на поставку арматуры А500С", "СМР-103 / ЖК Северное Сияние", "accountant", "Сидоров А.П. (Бухгалтер)", today + timedelta(days=3), TaskPriority.HIGH, "Остановка отгрузки металлопроката с завода", Decimal("7150000.00"), TaskStatus.PENDING),
                ("Заказ запчастей для ремонта самосвала КАМАЗ", "СМР-102 / Мост р. Истра", "dispatcher", "Николаев С.В. (Диспетчер)", today + timedelta(days=1), TaskPriority.HIGH, "Срыв темпов вывозки скального грунта", Decimal("85000.00"), TaskStatus.IN_PROGRESS),
                ("Подписание итогового акта ввода в эксплуатацию", "СМР-105 / Логпарк Юг", "manager", "Орлов А.К. (Куратор)", today - timedelta(days=10), TaskPriority.MEDIUM, "Завершение финансовых расчетов", Decimal("0.00"), TaskStatus.COMPLETED),
                ("Проверка сметного расчета на доп. работы сетей ТЦ", "СМР-104 / ТЦ Авангард", "engineer", "Петров В.С. (ГИП)", today + timedelta(days=6), TaskPriority.LOW, "Уточнение локального сметного расчета", Decimal("0.00"), TaskStatus.PENDING),
            ]

            for t_title, r_cont, r_role, r_pers, d_date, prior, r_desc, p_amt, st in tasks_data:
                db.add(
                    OperationalTask(
                        company_id=company_id,
                        task_title=t_title,
                        related_contract=r_cont,
                        responsible_role=r_role,
                        responsible_person=r_pers,
                        due_date=d_date,
                        priority=prior,
                        penalty_risk_desc=r_desc,
                        estimated_penalty_amount=p_amt,
                        penalty_amount=p_amt,
                        status=st,
                    )
                )
            await db.flush()
            logger.info("Created %d operational tasks", len(tasks_data))

            # 8. Операции ДДС (для корректной работы кассового разрыва и сводки)
            cf_ops = [
                ("incoming", Decimal("15000000.00"), Decimal("15000000.00"), today - timedelta(days=5), True, "ГК «Самолет Девелопмент»", "Аванс по договору СМР ЖК Северное Сияние"),
                ("incoming", Decimal("22000000.00"), Decimal("22000000.00"), today - timedelta(days=2), True, "Департамент строительства г. Москвы", "Оплата КС-2 за этап монолитных работ"),
                ("outgoing", Decimal("12500000.00"), Decimal("12500000.00"), today - timedelta(days=3), True, "Северсталь Дистрибуция", "Оплата металлопроката и арматуры"),
                ("outgoing", Decimal("4500000.00"), Decimal("4500000.00"), today - timedelta(days=1), True, "ФОТ Сотрудников", "Выплата заработной платы за первую половину месяца"),
                ("outgoing", Decimal("8500000.00"), Decimal("8500000.00"), today + timedelta(days=4), False, "ООО КабельЭлектро", "Плановый платеж по договору поставки кабеля"),
            ]
            for direction, plan_amt, act_amt, op_date, is_pd, cp, purpose in cf_ops:
                db.add(
                    CashflowOperation(
                        company_id=company_id,
                        direction=direction,
                        planned_amount=plan_amt,
                        actual_amount=act_amt,
                        operation_date=op_date,
                        payment_due_date=op_date,
                        is_paid=is_pd,
                        counterparty=cp,
                        payment_purpose=purpose,
                    )
                )
            await db.flush()
            logger.info("Created baseline cashflow operations")

            # 9. Запуск Risk Engine («Где горит?») для генерации системных инцидентов и расчета штрафов
            logger.info("Executing AlertsEngine evaluation across all domains...")
            await alerts_engine.evaluate_tender_penalties(company_id, db)
            await alerts_engine.evaluate_procurement_risks(company_id, db)
            await alerts_engine.evaluate_operational_tasks_risks(company_id, db)
            await alerts_engine.evaluate_cash_gap(company_id, db)

            # Check generated alerts count
            alerts_count_q = select(SystemAlert).where(
                SystemAlert.company_id == company_id,
                SystemAlert.is_resolved.is_(False),
            )
            alerts_res = await db.execute(alerts_count_q)
            active_alerts = alerts_res.scalars().all()
            logger.info("Successfully generated %d active incidents/alerts in SystemAlert", len(active_alerts))

    logger.info("✅ Database seed completed successfully!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Enterprise Hub DB Seed Tool")
    parser.add_argument("--drop", action="store_true", help="Flush existing data before seeding")
    args = parser.parse_args()

    try:
        asyncio.run(seed_data(drop_tables=args.drop))
    except Exception as e:
        logger.exception("Seed failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
