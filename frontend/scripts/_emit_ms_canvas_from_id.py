"""Emit ms/canvas.ts from id/canvas.ts with conservative Malay wording fixes."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID_PATH = ROOT / "src/locales/messages/id/canvas.ts"
NL_PATH = ROOT / "src/locales/messages/nl/canvas.ts"
OUT_PATH = ROOT / "src/locales/messages/ms/canvas.ts"


def decode_ts_string(raw_inner: str) -> str:
    out: list[str] = []
    idx = 0
    while idx < len(raw_inner):
        if raw_inner[idx] == "\\" and idx + 1 < len(raw_inner):
            nxt = raw_inner[idx + 1]
            if nxt == "'":
                out.append("'")
                idx += 2
            elif nxt == "\\":
                out.append("\\")
                idx += 2
            else:
                out.append(raw_inner[idx])
                idx += 1
        else:
            out.append(raw_inner[idx])
            idx += 1
    return "".join(out)


def parse_values_ordered(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    values: list[str] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        rest = match.group(2).strip()
        if rest == "":
            idx += 1
            val_line = lines[idx].strip()
            if val_line.endswith(","):
                val_line = val_line[:-1].strip()
            assert val_line.startswith("'") and val_line.endswith("'")
            values.append(decode_ts_string(val_line[1:-1]))
            idx += 1
        else:
            raw = rest
            if raw.endswith(","):
                raw = raw[:-1].strip()
            assert raw.startswith("'") and raw.endswith("'")
            values.append(decode_ts_string(raw[1:-1]))
            idx += 1
    return values


def nl_key_multiline_rows(text: str) -> list[tuple[str, bool]]:
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    rows: list[tuple[str, bool]] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^(\s*)'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        key, rest = match.group(2), match.group(3).strip()
        if rest == "":
            rows.append((key, True))
            idx += 2
        else:
            rows.append((key, False))
            idx += 1
    return rows


def encode_ts_single_quoted(value: str) -> str:
    parts: list[str] = []
    for char in value:
        if char == "\\":
            parts.append("\\\\")
        elif char == "'":
            parts.append("\\'")
        else:
            parts.append(char)
    return "".join(parts)


def indonesian_to_malay(value: str) -> str:
    """Longest-first phrase replacements; export verbs handled before bare 'ekspor'."""
    out = value
    phrases: list[tuple[str, str]] = [
        ("Subbagian baru", "Subbahagian baharu"),
        ("subbagian", "subbahagian"),
        ("Subbagian", "Subbahagian"),
        ("Subpaso", "Sublangkah"),
        ("subpaso", "sublangkah"),
        ("Anda yakin?", "Pastikah anda?"),
        ("termasuk diagram dan palet simpul", "termasuk diagram dan palet nod"),
        ("palet simpul", "palet nod"),
        ("Tidak dapat mengatur ulang", "Tidak boleh set semula"),
        ("mengatur ulang", "set semula"),
        ("Atur ulang", "Set semula"),
        ("Kembalikan ke default", "Kembali kepada lalai"),
        ("coba lagi", "cuba lagi"),
        ("Coba lagi", "Cuba lagi"),
        ("berhasil", "berjaya"),
        ("Berhasil", "Berjaya"),
        ("Tidak dapat", "Tidak boleh"),
        ("Menghapus", "Memadam"),
        ("menghapus", "memadam"),
        ("Hapus", "Padam"),
        ("Sisipkan", "Sisip"),
        ("sisipkan", "sisip"),
        ("simpul", "nod"),
        ("Simpul", "Nod"),
        ("Menghasilkan…", "Menjana…"),
        ("Menghasilkan", "Menjana"),
        ("menghasilkan", "menjana"),
        ("Hasilkan AI", "Jana AI"),
        ("hasil AI", "penjanaan AI"),
        ("memakai hasil AI", "menggunakan penjanaan AI"),
        ("saat kolaborasi", "semasa kerjasama"),
        ("kolaborasi", "kerjasama"),
        ("Kolaborasi", "Kerjasama"),
        ("presentasi", "persembahan"),
        ("Presentasi", "Persembahan"),
        ("di kanvas", "pada lembaran kerja"),
        ("Di kanvas", "Pada lembaran kerja"),
        ("kanvas", "lembaran kerja"),
        ("Kanvas", "Lembaran kerja"),
        ("layar penuh", "skrin penuh"),
        ("Layar penuh", "Skrin penuh"),
        ("Matematika", "Matematik"),
        ("matematika", "matematik"),
        ("Geometri", "Geometri"),
        ("geometri", "geometri"),
        ("Trigonometri", "Trigonometri"),
        ("Aljabar", "Algebra"),
        ("aljabar", "algebra"),
        ("Trapesium", "Trapezium"),
        ("Cuplikan", "Cetan"),
        ("cuplikan", "cetan"),
        ("Berkolaborasi", "Bekerjasama"),
        ("berkolaborasi", "bekerjasama"),
        ("Bergabung", "Sertai"),
        ("bergabung", "sertai"),
        ("Impor", "Import"),
        ("impor", "import"),
        ("Ekspor", "Eksport"),
        ("ekspor", "eksport"),
        ("Unduh", "Muat turun"),
        ("unggah", "muat naik"),
        ("Pengguna", "Pengguna"),
        ("Anda", "Anda"),
        ("Anda yakin", "Pastikah anda"),
        ("di hapus", "dipadam"),
        ("dihapus", "dipadam"),
        ("Dihapus", "Dipadam"),
        ("ditambahkan", "ditambah"),
        ("Ditambahkan", "Ditambah"),
        ("diterapkan", "digunakan"),
        ("Diterapkan", "Digunakan"),
        ("Garis tepi", "Sempadan"),
        ("Lebar", "Ketebalan"),
        ("Ratakan", "Jajar"),
        ("ratakan", "jajar"),
        ("Memuat", "Memuatkan"),
        ("memuat", "memuatkan"),
        ("Komunitas", "Komuniti"),
        ("komunitas", "komuniti"),
        ("Desain pengajaran", "Reka bentuk pengajaran"),
        ("Bagikan", "Kongsi"),
        ("bagikan", "kongsi"),
        ("Berkolaborasi sekolah", "Kerjasama sekolah"),
        ("kolaborasi sekolah", "kerjasama sekolah"),
        ("kolaborasi bersama", "kerjasama dikongsi"),
        ("Kolaborasi bersama", "Kerjasama dikongsi"),
        ("kode undangan", "kod jemputan"),
        ("Kode undangan", "Kod jemputan"),
        ("kode presentasi", "kod persembahan"),
        ("Kode presentasi", "Kod persembahan"),
        ("jaringan", "rangkaian"),
        ("Jaringan", "Rangkaian"),
        ("gagal bergabung", "gagal menyertai"),
        ("Gagal bergabung", "Gagal menyertai"),
        ("Bergabung ke presentasi", "Gagal menyertai persembahan"),
        ("Bergabung:", "Menyertai:"),
        ("Presentasi bergabung", "Persembahan disertai"),
        ("memuat sesi", "memuatkan sesi"),
        ("Tidak ada sesi", "Tiada sesi"),
        ("tidak ada sesi", "tiada sesi"),
        ("rekan kerja", "rakan sekerja"),
        ("Rekan kerja", "Rakan sekerja"),
        ("memulai", "memulakan"),
        ("Memulai", "Memulakan"),
        ("Halo", "Helo"),
        ("halo", "helo"),
        ("asisten AI", "pembantu AI"),
        ("Asisten AI", "Pembantu AI"),
        ("pemikiran visual", "fikiran visual"),
        ("Pemikiran visual", "Fikiran visual"),
        ("online", "dalam talian"),
        ("validasi", "pengesahan"),
        ("Validasi", "Pengesahan"),
        ("hasil", "keputusan"),
        ("Tidak ada hasil", "Tiada keputusan"),
        ("tidak ada hasil", "tiada keputusan"),
        ("Tidak ada data", "Tiada data"),
        ("tidak ada data", "tiada data"),
        ("Barisan", "Jujukan"),
        ("barisan", "jujukan"),
        ("Senyawa", "Sebatian"),
        ("senyawa", "sebatian"),
        ("laboratorium", "makmal"),
        ("Laboratorium", "Makmal"),
        ("Reaksi klasik", "Tindak balas klasik"),
        ("reaksi klasik", "tindak balas klasik"),
        ("Karat", "Kakisan"),
        ("karat", "kakisan"),
        ("uji air kapur", "uji air kapur"),
        ("Nitrat amonium", "Nitrat ammonium"),
        ("Pemutih", "Pemutih"),
        ("Cuka", "Cuka"),
        ("Kapur tulis", "Kapur"),
        ("Gipsum", "Gipsum"),
        ("Benzena", "Benzena"),
        ("Urea", "Urea"),
        ("Fotosintesis", "Fotosintesis"),
        ("Respirasi", "Respirasi"),
        ("Sintesis", "Sintesis"),
        ("Yunani", "Greek"),
        ("perbedaan", "perbezaan"),
        ("Perbedaan", "Perbezaan"),
        ("kesamaan", "persamaan"),
        ("Kesamaan", "Persamaan"),
        ("penyebab", "punca"),
        ("Penyebab", "Punca"),
        ("akibat", "kesan"),
        ("Akibat", "Kesan"),
        ("Diagram", "Diagram"),
        ("diagram", "diagram"),
        ("Pemilik", "Pemilik"),
        ("pemilik", "pemilik"),
        ("yang dapat", "yang boleh"),
        ("Yang dapat", "Yang boleh"),
        ("dapat memakai", "boleh menggunakan"),
        ("sedang dikembangkan", "dalam pembangunan"),
        ("Sedang dikembangkan", "Dalam pembangunan"),
        ("dikembangkan", "dibina"),
        ("Mode peta", "Mod peta"),
        ("mode peta", "mod peta"),
        ("diperluas", "zum masuk"),
        ("diperkecil", "zum keluar"),
        ("Perluas", "Zum masuk"),
        ("Perkecil", "Zum keluar"),
        ("otomatis", "automatik"),
        ("Otomatis", "Automatik"),
        ("Ruang penuh", "Ruang penuh"),
        ("autoguardado", "simpan automatik"),
        ("penyimpanan otomatis", "simpan automatik"),
        ("Belum disimpan", "Belum disimpan"),
        ("belum disimpan", "belum disimpan"),
        ("baru saja disimpan", "baru sahaja disimpan"),
        ("Baru saja disimpan", "Baru sahaja disimpan"),
        ("detik yang lalu", "saat yang lalu"),
        ("menit yang lalu", "minit yang lalu"),
        ("Masuk untuk menyimpan", "Log masuk untuk menyimpan"),
        ("masuk untuk menyimpan", "log masuk untuk menyimpan"),
        ("Ekspor gambar", "Eksport imej"),
        ("ekspor gambar", "eksport imej"),
        ("Sesuaikan layar", "Sesuaikan skrin"),
        ("sesuaikan layar", "sesuaikan skrin"),
        ("Pilih tipe", "Pilih jenis"),
        ("pilih tipe", "pilih jenis"),
        ("hapus diagram", "padam diagram"),
        ("Hapus diagram", "Padam diagram"),
        ("Mengklasifikasikan", "Klasifikasi"),
        ("mengklasifikasikan", "klasifikasi"),
        ("Ide", "Idea"),
        (" ide ", " idea "),
        ("ide ", "idea "),
        (" ide", " idea"),
        ("otak ide", "ribut idea"),
        ("Mata pelajaran", "Subjek"),
        ("mata pelajaran", "subjek"),
        ("Pusat topik", "Topik pusat"),
        ("pusat topik", "topik pusat"),
        ("Batalkan", "Batal"),
        ("batalkan", "batal"),
        ("Batal", "Batal"),
        ("deskripsikan", "huraikan"),
        ("Deskripsikan", "Huraikan"),
        ("Membandingkan", "Membanding"),
        ("membandingkan", "membanding"),
        ("kontras", "bezakan"),
        ("Kontras", "Bezakan"),
        ("di bawah", "di bawah"),
        ("Kisi", "Grid"),
        ("Selamat datang", "Helo"),
        ("saya adalah", "saya ialah"),
        ("Saya adalah", "Saya ialah"),
        ("klik untuk", "klik untuk"),
        ("Klik untuk", "Klik untuk"),
        ("Tekan", "Tekan"),
        ("tekan", "tekan"),
        ("Masukkan", "Masukkan"),
        ("masukkan", "masukkan"),
        ("Pilih", "Pilih"),
        ("pilih", "pilih"),
        ("Buat", "Buat"),
        ("buat", "buat"),
        ("Simpan", "Simpan"),
        ("simpan", "simpan"),
        ("Gagal", "Gagal"),
        ("gagal", "gagal"),
        ("file MG", "fail MG"),
        ("File MG", "Fail MG"),
        ("file diagram", "fail diagram"),
        ("File diagram", "Fail diagram"),
        ("Tidak valid", "Tidak sah"),
        ("tidak valid", "tidak sah"),
        ("dari MindGraph", "daripada MindGraph"),
        ("Dari MindGraph", "Daripada MindGraph"),
        ("terlebih dahulu", "terlebih dahulu"),
        ("Terlebih dahulu", "Terlebih dahulu"),
        ("Sesuaikan ke kanvas", "Sesuaikan lembaran kerja"),
        ("sesuaikan ke kanvas", "sesuaikan lembaran kerja"),
        ("alat presentasi", "alat persembahan"),
        ("Alat presentasi", "Alat persembahan"),
        ("sembunyikan", "sembunyi"),
        ("Sembunyikan", "Sembunyi"),
        ("tampilkan", "tunjukkan"),
        ("Tampilkan", "Tunjukkan"),
        ("Mano", "Tangan"),
        ("tangan", "tangan"),
        ("Ctrl+klik", "Ctrl+klik"),
        ("Ctrl+Klik", "Ctrl+klik"),
        ("Pulihkan", "Pulihkan"),
        ("pulihkan", "pulihkan"),
        ("diganti", "diganti"),
        ("Diganti", "Diganti"),
        ("Perubahan saat ini", "Perubahan semasa"),
        ("perubahan saat ini", "perubahan semasa"),
        ("sebelum memulihkan", "sebelum memulihkan"),
        ("Kembali", "Kembali"),
        ("kembali", "kembali"),
        ("Keluar", "Keluar"),
        ("keluar", "keluar"),
        ("Mulai", "Mula"),
        ("mulai", "mula"),
        ("Jeda", "Jeda"),
        ("Menit", "Minit"),
        ("menit", "minit"),
        ("Atur", "Tetapkan"),
        ("atur", "tetapkan"),
        ("virtual", "maya"),
        ("Virtual", "Maya"),
        ("keyboard", "papan kekunci"),
        ("Keyboard", "Papan kekunci"),
        ("tutup keyboard", "tutup papan kekunci"),
        ("Tutup keyboard", "Tutup papan kekunci"),
        ("tekan dua kali", "klik dwi"),
        ("Tekan dua kali", "Klik dwi"),
        ("Lebih banyak aplikasi", "Lebih banyak aplikasi"),
        ("aplikasi lainnya", "aplikasi lain"),
        ("Aplikasi lainnya", "Aplikasi lain"),
        ("Air terjun", "Air terjun"),
        ("lembar belajar", "helaian pembelajaran"),
        ("Lembar belajar", "Helaian pembelajaran"),
        ("mode peta konsep", "mod peta konsep"),
        ("Mode peta konsep", "Mod peta konsep"),
        ("standar untuk saat ini", "standard buat masa ini"),
        ("Standar untuk saat ini", "Standard buat masa ini"),
        ("segera hadir", "tidak lama lagi"),
        ("Segera hadir", "Tidak lama lagi"),
        ("acak untuk belajar", "rawak untuk belajar"),
        ("belajar dan ulang", "belajar dan ulangkaji"),
        ("batch nod", "kumpulan nod"),
        ("Batch nod", "Kumpulan nod"),
        ("tersinkronisasi", "disegerakkan"),
        ("Tersinkronisasi", "Disegerakkan"),
        ("bahasa antarmuka", "bahasa antara muka"),
        ("Bahasa antarmuka", "Bahasa antara muka"),
        ("nama file", "nama fail"),
        ("Nama file", "Nama fail"),
        ("kelola ruang galeri", "urus ruang galeri"),
        ("Kelola ruang galeri", "Urus ruang galeri"),
        ("Ekspor sebagai", "Eksport sebagai"),
        ("ekspor sebagai", "eksport sebagai"),
        ("template default", "templat lalai"),
        ("Template default", "Templat lalai"),
        ("bagikan ke komunitas", "kongsi ke komuniti"),
        ("Bagikan ke komunitas", "Kongsi ke komuniti"),
        ("desain mengajar", "reka bentuk pengajaran"),
        ("Desain mengajar", "Reka bentuk pengajaran"),
        ("kolaborasi sekolah", "kerjasama sekolah"),
        ("Kolaborasi sekolah", "Kerjasama sekolah"),
        ("kolaborasi bersama", "kerjasama dikongsi"),
        ("Kolaborasi bersama", "Kerjasama dikongsi"),
        ("kerja sama", "kerjasama"),
        ("Kerja sama", "Kerjasama"),
        ("gaya disalin", "gaya disalin"),
        ("salin format", "salin format"),
        ("Salin format", "Salin format"),
        ("dibatalkan", "dibatalkan"),
        ("Dibatalkan", "Dibatalkan"),
        ("sumber nod", "nod sumber"),
        ("Sumber nod", "Nod sumber"),
        ("target nod", "nod sasaran"),
        ("Target nod", "Nod sasaran"),
        ("laser", "laser"),
        ("Laser", "Laser"),
        ("spotlight", "spotlight"),
        ("Spotlight", "Spotlight"),
        ("pena", "pen"),
        ("Pena", "Pen"),
        ("penghapus sorot", "padam sorot"),
        ("Penghapus sorot", "Padam sorot"),
        ("keluar presentasi", "keluar persembahan"),
        ("Keluar presentasi", "Keluar persembahan"),
        ("warna sorot", "warna sorot"),
        ("Warna sorot", "Warna sorot"),
        ("penghitung waktu", "pemasa"),
        ("Penghitung waktu", "Pemasa"),
        ("jawaban", "jawapan"),
        ("Jawaban", "Jawapan"),
        ("hubungan analogi", "hubungan analogi"),
        ("Hubungan analogi", "Hubungan analogi"),
        ("berhubungan dengan", "berkait dengan"),
        ("Berhubungan dengan", "Berkait dengan"),
        ("akar konsep", "konsep utama"),
        ("Akar konsep", "Konsep utama"),
        ("pertanyaan fokus", "soalan fokus"),
        ("Pertanyaan fokus", "Soalan fokus"),
        ("alternatif akan muncul", "alternatif akan muncul"),
        ("Alternatif akan muncul", "Alternatif akan muncul"),
        ("dimensi lain", "dimensi lain"),
        ("pol analogi", "corak analogi"),
        ("dimensi klasifikasi", "dimensi klasifikasi"),
        ("klasifikasi menurut", "klasifikasi mengikut"),
        ("Klasifikasi menurut", "Klasifikasi mengikut"),
        ("dekomposisi menurut", "penguraian mengikut"),
        ("Dekomposisi menurut", "Penguraian mengikut"),
        ("tambahkan ke grup ini", "tambah ke kumpulan ini"),
        ("Tambahkan ke grup ini", "Tambah ke kumpulan ini"),
        ("fitur tambah simpul", "ciri tambah nod"),
        ("Fitur tambah simpul", "Ciri tambah nod"),
        ("buat diagram dulu", "buat diagram dahulu"),
        ("Buat diagram dulu", "Buat diagram dahulu"),
        ("pilih simpul", "pilih nod"),
        ("Pilih simpul", "Pilih nod"),
        ("konsep baru", "konsep baharu"),
        ("Konsep baru", "Konsep baharu"),
        ("ide baru", "idea baharu"),
        ("Ide baru", "Idea baharu"),
        ("langkah baru", "langkah baharu"),
        ("Langkah baru", "Langkah baharu"),
        ("bagian baru", "bahagian baharu"),
        ("Bagian baru", "Bahagian baharu"),
        ("elemen baru", "unsur baharu"),
        ("Elemen baru", "Unsur baharu"),
        ("konteks baru", "konteks baharu"),
        ("Konteks baru", "Konteks baharu"),
        ("anak baru", "anak baharu"),
        ("Anak baru", "Anak baharu"),
        ("kategori baru", "kategori baharu"),
        ("Kategori baru", "Kategori baharu"),
        ("kanan baru", "kanan baharu"),
        ("kiri baru", "kiri baharu"),
        ("cabang baru", "cabang baharu"),
        ("Cabang baru", "Cabang baharu"),
        ("atribut baru", "atribut baharu"),
        ("Atribut baru", "Atribut baharu"),
        ("asosiasi baru", "asosiasi baharu"),
        ("Asosiasi baru", "Asosiasi baharu"),
        ("sub-elemen", "sub-item"),
        ("Sub-elemen", "Sub-item"),
        ("perbedaan kiri", "perbezaan kiri"),
        ("perbedaan kanan", "perbezaan kanan"),
        ("Perbedaan kiri", "Perbezaan kiri"),
        ("Perbedaan kanan", "Perbezaan kanan"),
        ("kesamaan baru", "persamaan baharu"),
        ("Kesamaan baru", "Persamaan baharu"),
        ("tersimpan pada", "disimpan pada"),
        ("Tersimpan pada", "Disimpan pada"),
        ("introduksi teks", "masukkan teks"),
        ("Introduksi teks", "Masukkan teks"),
        ("masukkan teks", "masukkan teks"),
        ("Masukkan teks", "Masukkan teks"),
        ("masukkan hubungan", "masukkan hubungan"),
        ("Masukkan hubungan", "Masukkan hubungan"),
        ("tekan 1–5", "tekan 1–5"),
        ("Tekan 1–5", "Tekan 1–5"),
        ("peristiwa utama", "peristiwa utama"),
        ("Peristiwa utama", "Peristiwa utama"),
        ("tema pusat", "tema pusat"),
        ("Tema pusat", "Tema pusat"),
        ("Mapa ", "Peta "),
        ("mapa ", "peta "),
        ("Seluruh & bagian", "Keseluruhan & bahagian"),
        ("Menggambarkan atribut", "Huraikan atribut"),
        ("Curah pendapat", "Ribut idea"),
        ("Hubungan konsep", "Hubungan konsep"),
        ("Membandingkan & kontras", "Banding & bezakan"),
        ("Urutan & langkah", "Urutan & langkah"),
        ("Menyusun ide", "Susun idea"),
        ("Penyebab & akibat", "Punca & kesan"),
        ("Mengelompokkan", "Klasifikasi & kumpul"),
        ("Buat di kanvas", "Cipta pada lembaran"),
        ("Jelaskan diagram", "Huraikan diagram"),
        ("atau pilih templat", "atau pilih templat"),
        ("Klasifikasi", "Klasifikasi"),
        ("Peristiwa", "Peristiwa"),
        ("Proses", "Proses"),
        ("Tema", "Tema"),
        ("Subjek", "Subjek"),
        ("Hubungan analogi", "Hubungan analogi"),
        ("Topik pusat", "Topik pusat"),
        ("Format kode", "Format kod"),
        ("tidak valid", "tidak sah"),
        ("lengkap", "lengkap"),
        ("Gagal bergabung ke presentasi", "Gagal menyertai persembahan"),
        ("Gagal bergabung", "Gagal menyertai"),
        ("Bergabung presentasi:", "Menyertai persembahan:"),
        ("Bergabung:", "Menyertai:"),
        ("Kesalahan jaringan, gagal bergabung", "Ralat rangkaian, gagal menyertai"),
        ("Masukkan kode undangan (xxx-xxx) untuk bergabung ke sesi mereka.",
         "Masukkan kod jemputan (xxx-xxx) untuk menyertai sesi mereka."),
        ("Pemilik diagram", "pemilik diagram"),
        ("diagram milik", "diagram milik"),
        ("generasi AI", "penjanaan AI"),
        ("Generasi AI", "Penjanaan AI"),
        ("gambar seperti stabilo", "lukis seperti penyerlah"),
        ("Gambar seperti stabilo", "Lukis seperti penyerlah"),
        ("dihapus saat", "dipadam apabila"),
        ("dihapus ketika", "dipadam apabila"),
        ("editor matematika", "editor matematik"),
        ("Editor matematika", "Editor matematik"),
        ("matematika sebaris", "matematik sebaris"),
        ("Matematika sebaris", "Matematik sebaris"),
        ("rumus kimia", "rumus kimia"),
        ("Rumus kimia", "Rumus kimia"),
        ("ion · garam · asam", "ion · garam · asid"),
        ("Ion · garam · asam", "Ion · garam · asid"),
        ("asam · organik", "asid · organik"),
        ("Asam · organik", "Asid · organik"),
    ]
    for src, tgt in sorted(phrases, key=lambda x: -len(x[0])):
        if src:
            out = out.replace(src, tgt)
    out = re.sub(r"\bmengekspor\b", "mengeksport", out)
    out = re.sub(r"\bMengekspor\b", "Mengeksport", out)
    out = re.sub(r"\bdiekspor\b", "dieksport", out)
    out = re.sub(r"\bEkspor\b", "Eksport", out)
    out = re.sub(r"\bekspor\b", "eksport", out)
    out = re.sub(r"mengeksportt+", "mengeksport", out)
    out = re.sub(r"dieksportt+", "dieksport", out)
    out = re.sub(r"Eksportt+", "Eksport", out)
    out = out.replace("tidak dikenal", "tidak diketahui")
    out = out.replace("Tidak dikenal", "Tidak diketahui")
    out = out.replace("tidak dapat dibatal", "tidak boleh dibatalkan")
    out = out.replace("Semua konten saat ini akan hilang", "Semua kandungan semasa akan hilang")
    out = out.replace("tambahkan ke", "tambah ke")
    out = out.replace("Tambahkan ke", "Tambah ke")
    return out


def main() -> None:
    nl_text = NL_PATH.read_text(encoding="utf-8")
    rows = nl_key_multiline_rows(nl_text)
    id_vals = parse_values_ordered(ID_PATH)
    if len(rows) != len(id_vals):
        raise SystemExit(f"keys {len(rows)} id {len(id_vals)}")
    ms_vals = [indonesian_to_malay(v) for v in id_vals]
    out_lines = [
        "/**",
        " * ms UI — canvas",
        " */",
        "",
        "export default {",
    ]
    for (key, multiline), val in zip(rows, ms_vals, strict=True):
        esc = encode_ts_single_quoted(val)
        if multiline:
            out_lines.append(f"  '{key}':")
            out_lines.append(f"    '{esc}',")
        else:
            out_lines.append(f"  '{key}': '{esc}',")
    out_lines.append("}")
    out_lines.append("")
    OUT_PATH.write_text("\n".join(out_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
