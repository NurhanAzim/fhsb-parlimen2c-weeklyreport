from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bot_state import Session
from draft_store import DraftSummary, GeneratedFileRecord


FIELDS: list[tuple[str, str, str]] = [
    ("date_start", "Tarikh mula", "Format: DD/MM/YYYY. Contoh: 26/12/2026"),
    ("date_end", "Tarikh akhir", "Format: DD/MM/YYYY. Contoh: 31/12/2026"),
    ("location", "Lokasi", "Contoh: ARAS 2 BLOK UTAMA"),
]
EDITABLE_FIELDS: list[tuple[str, str, str]] = FIELDS
FIELD_LABELS = {key: label for key, label, _ in EDITABLE_FIELDS}
FIELD_GUIDANCE = {key: guidance for key, _, guidance in EDITABLE_FIELDS}
YES_LABEL = "Ya"
NO_LABEL = "Tidak"

BOT_COMMANDS = [
    {"command": "start", "description": "Mula laporan mingguan baharu"},
    {"command": "reports", "description": "Senarai laporan aktif"},
    {"command": "archived", "description": "Senarai laporan arkib"},
    {"command": "done", "description": "Selesai untuk langkah semasa"},
    {"command": "cancel", "description": "Padam laporan semasa"},
    {"command": "help", "description": "Tunjuk panduan ringkas"},
]

REVIEW_CALLBACK_PREFIX = "review"
DRAFT_CALLBACK_PREFIX = "draft"
ARCHIVED_CALLBACK_PREFIX = "archived"


def _drafts_text(drafts: list[DraftSummary]) -> str:
    lines = ["Laporan mingguan aktif:"]
    for draft in drafts:
        location = draft.project_name or "(belum diisi)"
        month_year = draft.project_sub_name or "-"
        date_range = draft.date or "-"
        lines.append(f"R-{draft.draft_id} | {location} | {month_year} | {date_range}")
    lines.append("")
    lines.append("Tekan butang Buka atau guna /edit <nombor laporan>.")
    return "\n".join(lines)


def _archived_reports_text(reports: list[DraftSummary]) -> str:
    lines = ["Laporan mingguan arkib:"]
    for report in reports:
        location = report.project_name or "(belum diisi)"
        month_year = report.project_sub_name or "-"
        date_range = report.date or "-"
        lines.append(f"R-{report.draft_id} | {location} | {month_year} | {date_range}")
    lines.append("")
    lines.append("Tekan butang Buka untuk lihat dan pulihkan laporan arkib.")
    return "\n".join(lines)


def _field_prompt(index: int) -> str:
    key, label, guidance = FIELDS[index]
    return f"{index + 1}/{len(FIELDS)}. Masukkan {label} ({key}).\n{guidance}"


def _review_text(session: Session) -> str:
    draft_label = _draft_label_for_session(session)
    status_line = "Status: Diarkibkan" if session.report_status == "archived" else "Status: Aktif"
    month_year = _derived_month_year(session.data.get("date_start", ""))
    detail_rows = [
        ("Tarikh mula", session.data.get("date_start", "-")),
        ("Tarikh akhir", session.data.get("date_end", "-")),
        ("Bulan dan tahun", month_year or "-"),
        ("Lokasi", session.data.get("location", "-")),
    ]
    label_width = max(len(label) for label, _value in detail_rows)
    header_lines = [
        f"Semakan {draft_label}",
        status_line,
        "",
        "Butiran laporan",
        "-" * (label_width + 24),
        *[f"{label.ljust(label_width)} : {value}" for label, value in detail_rows],
        "-" * (label_width + 24),
        "",
        "Senarai kerja",
    ]
    if session.issues:
        work_lines = [
            "\n".join(
                [
                    f"[{index}] {issue.description}",
                    f"Catatan : {issue.images_description or '-'}",
                    f"Gambar  : {len(issue.image_paths)}",
                ]
            )
            for index, issue in enumerate(session.issues, start=1)
        ]
    else:
        work_lines = ["Tiada kerja."]
    return "\n".join(header_lines + work_lines + ["", "Gunakan butang di bawah untuk semak, ubah, atau jana laporan."])


def _review_keyboard(session: Session) -> dict:
    if session.report_status == "archived":
        return {
            "inline_keyboard": [
                [
                    _button("Lihat PDF", f"{REVIEW_CALLBACK_PREFIX}:show_revisions"),
                    _button("Pulih", f"{REVIEW_CALLBACK_PREFIX}:restore"),
                ],
                [_button("Padam Laporan", f"{REVIEW_CALLBACK_PREFIX}:delete_report")],
                [_button("Muat Semula", f"{REVIEW_CALLBACK_PREFIX}:show")],
            ]
        }

    rows = [
        [
            _button("Jana Laporan", f"{REVIEW_CALLBACK_PREFIX}:generate"),
            _button("Tambah Kerja", f"{REVIEW_CALLBACK_PREFIX}:add_issue"),
        ],
        [_button("Edit Butiran", f"{REVIEW_CALLBACK_PREFIX}:menu_fields")],
    ]
    if session.issues:
        rows.append(
            [
                _button("Edit Kerja", f"{REVIEW_CALLBACK_PREFIX}:menu_edit_issues"),
                _button("Padam Kerja", f"{REVIEW_CALLBACK_PREFIX}:menu_delete_issues"),
            ]
        )
    rows.append(
        [
            _button("Lihat PDF", f"{REVIEW_CALLBACK_PREFIX}:show_revisions"),
            _button("Arkib", f"{REVIEW_CALLBACK_PREFIX}:archive"),
        ]
    )
    rows.append([_button("Padam Laporan", f"{REVIEW_CALLBACK_PREFIX}:delete_report")])
    rows.append([_button("Muat Semula", f"{REVIEW_CALLBACK_PREFIX}:show")])
    return {"inline_keyboard": rows}


def _field_selection_keyboard() -> dict:
    rows = [
        [_button(f"{index}. {label}", f"{REVIEW_CALLBACK_PREFIX}:field:{key}")]
        for index, (key, label, _) in enumerate(EDITABLE_FIELDS, start=1)
    ]
    rows.append([_button("Kembali", f"{REVIEW_CALLBACK_PREFIX}:back")])
    return {"inline_keyboard": rows}


def _yes_no_reply_keyboard() -> dict:
    return {
        "keyboard": [[{"text": YES_LABEL}, {"text": NO_LABEL}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def _remove_reply_keyboard() -> dict:
    return {"remove_keyboard": True}


def _issue_selection_keyboard(session: Session, mode: str) -> dict:
    action = "edit_issue" if mode == "edit" else "delete_issue"
    rows = []
    for index, issue in enumerate(session.issues, start=1):
        preview = issue.description.strip() or "(tanpa butiran)"
        preview = preview[:36] + "..." if len(preview) > 36 else preview
        rows.append([_button(f"{index}. {preview}", f"{REVIEW_CALLBACK_PREFIX}:{action}:{index - 1}")])
    rows.append([_button("Kembali", f"{REVIEW_CALLBACK_PREFIX}:back")])
    return {"inline_keyboard": rows}


def _issue_edit_options_keyboard(issue_index: int) -> dict:
    return {
        "inline_keyboard": [
            [_button("Butiran Kerja", f"{REVIEW_CALLBACK_PREFIX}:edit_issue_description:{issue_index}")],
            [_button("Catatan", f"{REVIEW_CALLBACK_PREFIX}:edit_issue_images_description:{issue_index}")],
            [_button("Tambah Gambar", f"{REVIEW_CALLBACK_PREFIX}:edit_issue_add_image:{issue_index}")],
            [_button("Padam Gambar", f"{REVIEW_CALLBACK_PREFIX}:menu_remove_issue_image:{issue_index}")],
            [_button("Kembali", f"{REVIEW_CALLBACK_PREFIX}:menu_edit_issues")],
        ]
    }


def _issue_image_selection_keyboard(issue_index: int, image_paths: list[str]) -> dict:
    rows = [
        [_button(f"{position}. {Path(path).name}", f"{REVIEW_CALLBACK_PREFIX}:remove_issue_image:{issue_index}:{position - 1}")]
        for position, path in enumerate(image_paths, start=1)
    ]
    rows.append([_button("Kembali", f"{REVIEW_CALLBACK_PREFIX}:edit_issue:{issue_index}")])
    return {"inline_keyboard": rows}


def _drafts_keyboard(drafts: list[DraftSummary]) -> dict:
    rows = [[_button(f"Buka R-{draft.draft_id}", f"{DRAFT_CALLBACK_PREFIX}:edit:{draft.draft_id}")] for draft in drafts]
    rows.append([_button("Muat Semula", f"{DRAFT_CALLBACK_PREFIX}:list")])
    return {"inline_keyboard": rows}


def _archived_reports_keyboard(reports: list[DraftSummary]) -> dict:
    rows = [[_button(f"Buka R-{report.draft_id}", f"{ARCHIVED_CALLBACK_PREFIX}:edit:{report.draft_id}")] for report in reports]
    rows.append([_button("Muat Semula", f"{ARCHIVED_CALLBACK_PREFIX}:list")])
    return {"inline_keyboard": rows}


def _back_to_review_keyboard() -> dict:
    return {"inline_keyboard": [[_button("Kembali ke Semakan", f"{REVIEW_CALLBACK_PREFIX}:back")]]}


def _delete_report_confirmation_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [_button("Ya, Padam Laporan", f"{REVIEW_CALLBACK_PREFIX}:confirm_delete_report")],
            [_button("Batal", f"{REVIEW_CALLBACK_PREFIX}:cancel_delete_report")],
        ]
    }


def _delete_issue_confirmation_keyboard(issue_index: int) -> dict:
    return {
        "inline_keyboard": [
            [_button("Ya, Padam Kerja Ini", f"{REVIEW_CALLBACK_PREFIX}:confirm_delete_issue:{issue_index}")],
            [_button("Batal", f"{REVIEW_CALLBACK_PREFIX}:cancel_delete_issue")],
        ]
    }


def _button(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


def _url_button(text: str, url: str) -> dict:
    return {"text": text, "url": url}


def _draft_label_for_session(session: Session) -> str:
    ref = f"R-{session.draft_id}" if session.draft_id is not None else "laporan"
    return f"laporan {ref}"


def _format_timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone()
    return local_dt.strftime("%d/%m/%Y %H:%M")


def _revision_keyboard(revisions: list[GeneratedFileRecord]) -> dict:
    rows = []
    for revision in revisions:
        if revision.status == "available":
            rows.append([_url_button(f"Revision {revision.revision_number}", revision.share_url)])
        else:
            rows.append(
                [
                    _button(
                        f"Revision {revision.revision_number} (luput)",
                        f"{REVIEW_CALLBACK_PREFIX}:expired_revision:{revision.revision_number}",
                    )
                ]
            )
    rows.append([_button("Kembali", f"{REVIEW_CALLBACK_PREFIX}:back")])
    return {"inline_keyboard": rows}


def _revision_status_label(status: str) -> str:
    return {
        "available": "Tersedia",
        "expired": "Luput",
    }.get(status, status)


def _expired_revision_prefix(revision_number: int) -> str:
    return (
        f"Revision {revision_number} telah luput dan fail PDF itu sudah dipadam.\n"
        "Pilih revision lain yang masih tersedia, atau tekan Kembali untuk jana PDF baharu.\n\n"
    )


def _parse_callback_data(data: str) -> tuple[str, str | int | None]:
    parts = data.split(":")
    if len(parts) < 2:
        return "unknown", None

    prefix, action = parts[0], parts[1]
    if prefix == REVIEW_CALLBACK_PREFIX:
        if action in {
            "generate",
            "back",
            "show",
            "add_issue",
            "menu_fields",
            "menu_edit_issues",
            "menu_delete_issues",
            "show_revisions",
            "archive",
            "restore",
            "delete_report",
            "confirm_delete_report",
            "cancel_delete_report",
            "cancel_delete_issue",
        }:
            return action, None
        if action == "expired_revision" and len(parts) >= 3 and parts[2].isdigit():
            return "expired_revision", int(parts[2])
        if action == "field" and len(parts) >= 3:
            return "select_field", parts[2]
        if action == "edit_issue" and len(parts) >= 3 and parts[2].isdigit():
            return "select_edit_issue", int(parts[2])
        if action == "edit_issue_description" and len(parts) >= 3 and parts[2].isdigit():
            return "edit_issue_description", int(parts[2])
        if action == "edit_issue_images_description" and len(parts) >= 3 and parts[2].isdigit():
            return "edit_issue_images_description", int(parts[2])
        if action == "edit_issue_add_image" and len(parts) >= 3 and parts[2].isdigit():
            return "edit_issue_add_image", int(parts[2])
        if action == "delete_issue" and len(parts) >= 3 and parts[2].isdigit():
            return "select_delete_issue", int(parts[2])
        if action == "confirm_delete_issue" and len(parts) >= 3 and parts[2].isdigit():
            return "confirm_delete_issue", int(parts[2])
        if action == "menu_remove_issue_image" and len(parts) >= 3 and parts[2].isdigit():
            return "menu_remove_issue_image", int(parts[2])
        if action == "remove_issue_image" and len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
            return "remove_issue_image", (int(parts[2]), int(parts[3]))
        return "unknown", None

    if prefix == DRAFT_CALLBACK_PREFIX:
        if action == "list":
            return "draft_list", None
        if action == "edit" and len(parts) >= 3 and parts[2].isdigit():
            return "draft_edit", int(parts[2])

    if prefix == ARCHIVED_CALLBACK_PREFIX:
        if action == "list":
            return "archived_list", None
        if action == "edit" and len(parts) >= 3 and parts[2].isdigit():
            return "archived_edit", int(parts[2])

    return "unknown", None


def _help_text(
    max_images_per_issue_default: int,
    max_issues_per_report_default: int,
    max_total_images_per_report_default: int,
    max_image_file_size_mb_default: int,
    retention_days: int,
    archived_report_retention_days: int,
) -> str:
    return (
        "Arahan bot:\n"
        "/start - mula laporan mingguan baharu\n"
        "/reports - senarai laporan aktif\n"
        "/archived - senarai laporan arkib\n"
        "/done - siap untuk langkah semasa\n"
        "/cancel - padam laporan semasa\n\n"
        "Format penting:\n"
        "- Tarikh mula dan akhir: DD/MM/YYYY\n"
        "- Bulan dan tahun dijana automatik daripada tarikh mula\n"
        "- Lokasi: teks bebas\n"
        "- Butiran kerja akan dijana sebagai HURUF BESAR\n"
        "- Catatan akan dijana dengan huruf pertama besar\n\n"
        "Aliran kerja:\n"
        "- Selepas butiran laporan, bot akan minta butiran kerja pertama\n"
        "- Selepas itu bot akan minta catatan kerja; balas /skip jika kosong\n"
        "- Kemudian hantar satu atau lebih gambar dan balas /done\n\n"
        "Had lalai:\n"
        f"- Max gambar per kerja: {max_images_per_issue_default}\n"
        f"- Max kerja per laporan: {max_issues_per_report_default}\n"
        f"- Max jumlah gambar per laporan: {max_total_images_per_report_default}\n"
        f"- Max saiz gambar: {max_image_file_size_mb_default} MB\n"
        f"- Revision PDF disimpan sekitar {retention_days} hari sebelum luput\n"
        f"- Laporan arkib kekal boleh dipulihkan sekitar {archived_report_retention_days} hari\n\n"
        "Semakan akhir menggunakan butang. Setiap jana PDF akan mencipta revision baharu."
    )


def _derived_month_year(date_start: str) -> str:
    if not date_start:
        return ""
    month_map = {
        "01": "JANUARI",
        "02": "FEBRUARI",
        "03": "MAC",
        "04": "APRIL",
        "05": "MEI",
        "06": "JUN",
        "07": "JULAI",
        "08": "OGOS",
        "09": "SEPTEMBER",
        "10": "OKTOBER",
        "11": "NOVEMBER",
        "12": "DISEMBER",
    }
    parts = date_start.strip().split("/")
    if len(parts) != 3:
        return ""
    month = month_map.get(parts[1])
    if not month:
        return ""
    return f"{month} {parts[2]}"
