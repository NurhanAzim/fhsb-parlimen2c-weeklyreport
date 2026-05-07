from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bot_state import Session
from report_generator import Issue, ReportData
from telegram_bot import (
    NO_LABEL,
    YES_LABEL,
    _build_output_paths,
    _drafts_keyboard,
    _drafts_text,
    _field_selection_keyboard,
    _issue_selection_keyboard,
    _parse_callback_data,
    _remove_reply_keyboard,
    _review_keyboard,
    _review_text,
    _yes_no_reply_keyboard,
)
from draft_store import DraftSummary


class TelegramBotReviewTest(unittest.TestCase):
    def test_parse_callback_data(self) -> None:
        self.assertEqual(_parse_callback_data("review:generate"), ("generate", None))
        self.assertEqual(_parse_callback_data("review:field:location"), ("select_field", "location"))
        self.assertEqual(_parse_callback_data("review:edit_issue:1"), ("select_edit_issue", 1))
        self.assertEqual(_parse_callback_data("review:remove_issue_image:1:0"), ("remove_issue_image", (1, 0)))
        self.assertEqual(_parse_callback_data("draft:edit:9"), ("draft_edit", 9))
        self.assertEqual(_parse_callback_data("archived:list"), ("archived_list", None))


    def test_review_text_contains_weekly_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = Session(chat_id=1, draft_id=7, workspace=Path(temp_dir))
            session.data.update(
                {
                    "date_start": "26/12/2026",
                    "date_end": "31/12/2026",
                    "location": "ARAS 2 BLOK UTAMA",
                }
            )
            session.issues = [
                Issue(description="KERJA PERTAMA", images_description="Catatan pertama", image_paths=[Path("a.jpg")]),
                Issue(description="KERJA KEDUA", image_paths=[]),
            ]

            text = _review_text(session)

            self.assertIn("Butiran laporan", text)
            self.assertIn("Tarikh mula     : 26/12/2026", text)
            self.assertIn("Tarikh akhir    : 31/12/2026", text)
            self.assertIn("Bulan dan tahun : DISEMBER 2026", text)
            self.assertIn("Lokasi          : ARAS 2 BLOK UTAMA", text)
            self.assertIn("[1] KERJA PERTAMA", text)
            self.assertIn("Catatan : Catatan pertama", text)
            self.assertIn("Gambar  : 1", text)
            self.assertIn("[2] KERJA KEDUA", text)
            self.assertIn("Gambar  : 0", text)

    def test_review_keyboard_matches_weekly_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = Session(chat_id=1, workspace=Path(temp_dir))
            session.issues = [Issue(description="KERJA PERTAMA", image_paths=[])]

            keyboard = _review_keyboard(session)
            labels = [button["text"] for row in keyboard["inline_keyboard"] for button in row]

            self.assertIn("Jana Laporan", labels)
            self.assertIn("Tambah Kerja", labels)
            self.assertIn("Edit Kerja", labels)
            self.assertIn("Padam Kerja", labels)

    def test_field_selection_keyboard_uses_weekly_fields(self) -> None:
        keyboard = _field_selection_keyboard()
        self.assertEqual(keyboard["inline_keyboard"][0][0]["text"], "1. Tarikh mula")
        self.assertEqual(keyboard["inline_keyboard"][1][0]["text"], "2. Tarikh akhir")
        self.assertEqual(keyboard["inline_keyboard"][2][0]["text"], "3. Lokasi")

    def test_yes_no_keyboard_and_remove_keyboard(self) -> None:
        keyboard = _yes_no_reply_keyboard()
        self.assertEqual(keyboard["keyboard"][0][0]["text"], YES_LABEL)
        self.assertEqual(keyboard["keyboard"][0][1]["text"], NO_LABEL)
        self.assertEqual(_remove_reply_keyboard(), {"remove_keyboard": True})

    def test_issue_selection_keyboard_uses_work_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = Session(chat_id=1, workspace=Path(temp_dir))
            session.issues = [
                Issue(description="KERJA PERTAMA", image_paths=[]),
                Issue(description="KERJA KEDUA", image_paths=[]),
            ]

            keyboard = _issue_selection_keyboard(session, "edit")
            self.assertEqual(keyboard["inline_keyboard"][0][0]["text"], "1. KERJA PERTAMA")
            self.assertEqual(keyboard["inline_keyboard"][1][0]["text"], "2. KERJA KEDUA")

    def test_drafts_keyboard_and_text(self) -> None:
        drafts = [
            DraftSummary(
                draft_id=3,
                chat_id=99,
                date="26/12/2026 - 31/12/2026",
                project_name="ARAS 2",
                project_sub_name="DISEMBER 2026",
                updated_at="2026-12-31T10:00:00+00:00",
                created_at="2026-12-26T09:00:00+00:00",
                current_revision=0,
            )
        ]
        text = _drafts_text(drafts)
        keyboard = _drafts_keyboard(drafts)
        self.assertIn("R-3 | ARAS 2 | DISEMBER 2026 | 26/12/2026 - 31/12/2026", text)
        self.assertEqual(keyboard["inline_keyboard"][0][0]["text"], "Buka R-3")

    def test_build_output_paths_use_weekly_naming(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = ReportData(
                date_start="26/12/2026",
                date_end="31/12/2026",
                location="ARAS 2 BLOK UTAMA",
                issues=[],
            )

            docx_path, pdf_path = _build_output_paths(Path(temp_dir), report)

            self.assertEqual(docx_path.name, "weekly-report-26-12-2026-31-12-2026-ARAS-2-BLOK-UTAMA-DISEMBER-2026.odt")
            self.assertEqual(pdf_path.suffix, ".pdf")


if __name__ == "__main__":
    unittest.main()
