# Weekly Report Automation

Telegram bot untuk menjana `template-weekly-report.odt` dan menukar hasilnya ke PDF.

Struktur dikekalkan hampir sama dengan `initial-doc-automation`:

- long-polling Telegram bot
- draft/session dalam SQLite
- semakan akhir dengan butang inline
- setiap jana menghasilkan revision PDF baharu
- upload revision ke Nextcloud dan pulangkan share URL
- arkib dan pemulihan laporan

Perbezaan utama:

- template baharu ialah `template-weekly-report.odt`
- medan input tetap ialah `date_start`, `date_end`, dan `location`
- `month_year` dijana automatik daripada `date_start`
- setiap kerja menjadi satu halaman
- `work_detail` dijana sebagai huruf besar
- `work_note` dijana dengan huruf pertama besar
- gambar diskalakan supaya muat dalam kotak gambar
- jika jumlah halaman minimum `1`, bot guna susun atur halaman kedua sahaja
- jika jumlah halaman minimum `2`, bot kekalkan dua halaman template
- jika jumlah halaman `3` atau lebih, halaman pertama digunakan semula untuk semua halaman tengah dan halaman kedua kekal sebagai halaman terakhir

## Setup

1. Pastikan Python 3.13+ tersedia.
2. Pasang dependencies:

```bash
python3 -m pip install -r requirements.txt
```

3. Sediakan `.env`:

- `TELEGRAM_BOT_TOKEN`
- `NEXTCLOUD_BASE_URL`
- `NEXTCLOUD_USERNAME`
- `NEXTCLOUD_APP_PASSWORD`
- Optional: `NEXTCLOUD_UPLOAD_DIR`
- Optional: `DATA_DIR`
- Optional: `RUNTIME_DIR`
- Optional: `DATABASE_PATH`
- Optional: `DRAFTS_DIR`
- Optional: `BACKUP_DIR`
- Optional: `RETENTION_PERIOD_DAYS`
- Optional: `ARCHIVED_REPORT_RETENTION_DAYS`
- Optional: `AUTO_ARCHIVE_ACTIVE_REPORT_DAYS`
- Optional: `MAX_IMAGES_PER_ISSUE`
- Optional: `MAX_ISSUES_PER_REPORT`
- Optional: `MAX_TOTAL_IMAGES_PER_REPORT`
- Optional: `MAX_IMAGE_FILE_SIZE_MB`

4. Jalankan bot:

```bash
python3 telegram_bot.py
```

## Telegram flow

1. Hantar `/start`
2. Isi:
   - `date_start`: `DD/MM/YYYY`
   - `date_end`: `DD/MM/YYYY`
   - `location`: teks lokasi
3. Hantar satu butiran kerja
4. Hantar catatan kerja, atau `/skip`
5. Hantar satu atau lebih gambar
6. Balas `/done`
7. Pilih `Ya` atau `Tidak` untuk tambah kerja lain
8. Di skrin semakan:
   - `Jana Laporan`
   - `Tambah Kerja`
   - `Edit Butiran`
   - `Edit Kerja`
   - `Padam Kerja`
   - `Lihat PDF`
   - `Arkib`
   - `Padam Laporan`

## Docker

```bash
docker compose up -d --build
```

Staging:

```bash
docker compose -f docker-compose.staging.yml up -d --build
```

## Backup

```bash
./scripts/backup_db.sh
```

## Local tests

```bash
python3 -m unittest tests/test_report_generator.py tests/test_telegram_bot.py tests/test_draft_store.py
```

## CLI render example

Payload JSON:

```json
{
  "date_start": "26/12/2026",
  "date_end": "31/12/2026",
  "location": "ARAS 2 BLOK UTAMA",
  "issues": [
    {
      "description": "PEMASANGAN KABEL TRUNKING",
      "images_description": "Catatan mingguan",
      "image_paths": ["./sample.png"]
    }
  ]
}
```

Render:

```bash
python3 report_generator.py payload.json --output output/weekly-report.odt
```
