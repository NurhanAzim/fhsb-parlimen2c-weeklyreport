from __future__ import annotations

import base64
import struct
import tempfile
import unittest
import zlib
from binascii import crc32
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from report_generator import Issue, ODT_NS, ReportData, render_report


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jX3sAAAAASUVORK5CYII="
)


class ReportGeneratorTest(unittest.TestCase):
    def test_single_work_uses_second_page_only_and_replaces_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "work.png"
            image_path.write_bytes(PNG_1X1)
            output = root / "weekly.odt"

            report = ReportData(
                date_start="26/12/2026",
                date_end="31/12/2026",
                location="ARAS 2 BLOK UTAMA",
                issues=[
                    Issue(
                        description="pemasangan kabel trunking",
                        images_description="catatan mingguan",
                        image_paths=[image_path],
                    )
                ],
            )

            render_report("template-weekly-report.odt", output, report)
            styles_text, content_text, content_root = _read_odt_xml(output)
            rows = content_root.findall(".//table:table/table:table-row", ODT_NS)

            self.assertEqual(len(rows), 1)
            self.assertIn("26/12/2026", styles_text)
            self.assertIn("31/12/2026", styles_text)
            self.assertIn("DISEMBER 2026", styles_text)
            self.assertIn("ARAS 2 BLOK UTAMA", content_text)
            self.assertIn("PEMASANGAN KABEL TRUNKING", content_text)
            self.assertIn("Catatan mingguan", content_text)
            self.assertIn("Disediakan Oleh", styles_text)
            self.assertNotIn("<work2_detail>", content_text)
            self.assertNotIn("<date_start>", styles_text)

    def test_three_works_expand_to_three_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "weekly-three.odt"

            report = ReportData(
                date_start="26/12/2026",
                date_end="31/12/2026",
                location="ARAS 5",
                issues=[
                    Issue(description="kerja pertama", images_description="nota pertama", image_paths=[]),
                    Issue(description="kerja kedua", images_description="nota kedua", image_paths=[]),
                    Issue(description="kerja ketiga", images_description="nota ketiga", image_paths=[]),
                ],
            )

            render_report("template-weekly-report.odt", output, report)
            _styles_text, content_text, content_root = _read_odt_xml(output)
            rows = content_root.findall(".//table:table/table:table-row", ODT_NS)
            soft_breaks = content_root.findall(".//table:table/text:soft-page-break", ODT_NS)

            self.assertEqual(len(rows), 3)
            self.assertEqual(len(soft_breaks), 2)
            self.assertIn("KERJA PERTAMA", content_text)
            self.assertIn("KERJA KEDUA", content_text)
            self.assertIn("KERJA KETIGA", content_text)

    def test_work_image_is_scaled_to_fit_box(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "wide.png"
            _write_png(image_path, width=2400, height=1200)
            output = root / "weekly-image.odt"

            report = ReportData(
                date_start="26/12/2026",
                date_end="31/12/2026",
                location="BILIK SERVER",
                issues=[Issue(description="susunan rak", images_description="", image_paths=[image_path])],
            )

            render_report("template-weekly-report.odt", output, report)
            _styles_text, _content_text, content_root = _read_odt_xml(output)
            frame = content_root.find(".//draw:frame", ODT_NS)

            self.assertIsNotNone(frame)
            assert frame is not None
            width_in = float(frame.attrib[f'{{{ODT_NS["svg"]}}}width'].removesuffix("in"))
            height_in = float(frame.attrib[f'{{{ODT_NS["svg"]}}}height'].removesuffix("in"))
            self.assertLessEqual(width_in, 3.4375)
            self.assertLessEqual(height_in, 4.75)

            with ZipFile(output) as archive:
                self.assertIn("Pictures/wide.png", archive.namelist())


def _read_odt_xml(path: Path) -> tuple[str, str, ET.Element]:
    with ZipFile(path) as archive:
        styles_text = archive.read("styles.xml").decode("utf-8")
        content_text = archive.read("content.xml").decode("utf-8")
    return styles_text, content_text, ET.fromstring(content_text)


def _write_png(path: Path, width: int, height: int) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", crc32(tag + data) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\xff\xff\xff" * width)
    image_data = zlib.compress(row * height)
    path.write_bytes(
        header
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", image_data)
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    unittest.main()
