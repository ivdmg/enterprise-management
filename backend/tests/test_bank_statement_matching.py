from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.procurement import ProcurementItem
from app.services.template_parser import standard_template_parser


@pytest.mark.asyncio
@pytest.mark.parametrize(("encoding", "match_count"), [("utf-8-sig", 1), ("cp1251", 2)])
async def test_statement_only_updates_an_unambiguous_pending_invoice(encoding, match_count):
    statement = """1CClientBankExchange
СекцияДокумент=Платежное поручение
Номер=42
Дата=05.11.2026
Сумма=125.50
Получатель=Поставщик
НазначениеПлатежа=Оплата по счету за материалы
КонецДокумента
КонецФайла
"""
    invoices = [ProcurementItem(status="Счет_На_Оплате") for _ in range(match_count)]
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = invoices
    db.execute = AsyncMock(return_value=result)

    imported = await standard_template_parser.parse_and_persist(
        statement.encode(encoding), "statement.txt", "tenant", "file", db
    )

    assert imported == ("1c_bank_statement", 1)
    expected_status = "Оплачено" if match_count == 1 else "Счет_На_Оплате"
    assert all(invoice.status == expected_status for invoice in invoices)
    operation = db.add.call_args.args[0]
    assert operation.actual_amount == Decimal("125.50")
    assert operation.counterparty == "Поставщик"
