import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from services.tax_engine.importer import (
    ImportContractError,
    extract_realization_workbook,
    preview_monthly_report,
    preview_monthly_workbook,
)


def write_fixture(path, order_level=False):
    workbook=Workbook(); sheet=workbook.active; sheet.title="Отчет о реализации"
    sheet["C4"]="Реализация товаров за период с 01.07.2026 по 31.07.2026"
    sheet["A13"]="№ п/п"; sheet["F13"]="Реализовано"
    returned_column="O" if order_level else "J"
    sheet[f"{returned_column}13"]="Возвращено клиентом"
    if order_level:
        sheet["V13"]="Отправление"; sheet["V14"]="Номер"; sheet["W14"]="Дата"
        columns={"gross":"F","loyalty":"G","qty":"I","returns":"O","reversal":"P","return_qty":"R"}
    else:
        columns={"gross":"F","loyalty":"G","qty":"H","returns":"J","reversal":"K","return_qty":"L"}
    labels={"gross":"Реализовано на сумму, руб.","loyalty":"Выплаты по механикам лояльности партнёров, руб.",
            "qty":"Кол-во","returns":"Возвращено на сумму, руб.",
            "reversal":"Выплаты по механикам лояльности партнёров, руб.","return_qty":"Кол-во"}
    for field,column in columns.items(): sheet[f"{column}14"]=labels[field]
    for row,values in ((16,(100,2,1,10,1,1)),(17,(50,3,2,0,0,0))):
        sheet[f"A{row}"]=row-15; sheet[f"C{row}"]="УФ 001Б"; sheet[f"D{row}"]=4601821825
        for field,value in zip(("gross","loyalty","qty","returns","reversal","return_qty"),values):
            sheet[f"{columns[field]}{row}"]=value
        if order_level:
            sheet[f"V{row}"]=f"posting-{row}"; sheet[f"W{row}"]=datetime(2026,7,row)
    workbook.save(path); workbook.close()


class ImporterTests(unittest.TestCase):
    def test_official_file_required_and_july_reconciles(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"official.xlsx"; source.write_bytes(b"test-only-official-fixture")
            preview=preview_monthly_report({"source_period":"2026-07","gross_realised":"138224.71","returns":"356.77","partner_loyalty_payments":"1803.32","partner_loyalty_reversals":"3.57"},source)
            self.assertEqual(str(preview["accounting_income"]),"139667.69")
            self.assertEqual(len({row.event_id for row in preview["events"]}),4)
            self.assertFalse(preview["persist"])

    def test_missing_source_stops_preview(self):
        with self.assertRaises(ImportContractError):
            preview_monthly_report({"source_period":"2026-07","gross_realised":1,"returns":0,"partner_loyalty_payments":0,"partner_loyalty_reversals":0},"missing.xlsx")

    def test_excel_files_are_not_tracked(self):
        ignore=Path(".gitignore").read_text(encoding="utf-8")
        self.assertTrue("*.xlsx" in ignore or ".xlsx" in ignore)

    def test_real_monthly_schema_is_discovered_and_previewed(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"monthly.xlsx"; write_fixture(source)
            extracted=extract_realization_workbook(source)
            self.assertEqual(extracted["report_kind"],"MONTHLY")
            self.assertEqual(extracted["data_rows_count"],2)
            self.assertEqual(extracted["totals"]["gross_realised"],150)
            self.assertEqual(preview_monthly_workbook(source)["accounting_income"],144)

    def test_extended_order_schema_is_reconciliation_only(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"orders.xlsx"; write_fixture(source,order_level=True)
            extracted=extract_realization_workbook(source)
            self.assertEqual(extracted["report_kind"],"ORDER_LEVEL")
            self.assertEqual(extracted["totals"]["realised_quantity"],3)
            self.assertEqual(extracted["source_event_date_min"],datetime(2026,7,16))
            with self.assertRaises(ImportContractError): preview_monthly_workbook(source)

    def test_modified_workbook_has_different_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            first=Path(directory)/"first.xlsx"; second=Path(directory)/"second.xlsx"
            write_fixture(first); write_fixture(second)
            workbook=__import__("openpyxl").load_workbook(second); workbook.active["F16"]=101; workbook.save(second); workbook.close()
            self.assertNotEqual(extract_realization_workbook(first)["source_checksum"],extract_realization_workbook(second)["source_checksum"])
