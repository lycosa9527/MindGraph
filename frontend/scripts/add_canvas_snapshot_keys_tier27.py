"""Insert canvas.toolbar.snapshot* keys missing vs zh reference.

Tier-27 picker locales get native strings in BUNDLE; all other locales get
English fallback so `npm run i18n:check-keys` matches zh keys.

Run from repo root: python frontend/scripts/add_canvas_snapshot_keys_tier27.py
PEP8, no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "locales" / "messages"

EN_FALLBACK: dict[str, str] = {
    "too_large": (
        "Snapshot is too large (max {max} KB). Reduce diagram content and try again."
    ),
    "rate": "Too many snapshot actions. Wait a moment and try again.",
    "not_found": "Diagram not found. Reload the page or open it from your library.",
    "conflict": "Could not save snapshot (conflict). Please try again.",
}

BUNDLE: dict[str, dict[str, str]] = {
    "es": {
        "too_large": "La instantánea es demasiado grande (máx. {max} KB). "
        "Reduzca el contenido del diagrama e inténtelo de nuevo.",
        "rate": "Demasiadas acciones de instantánea. Espere un momento e inténtelo de nuevo.",
        "not_found": "No se encontró el diagrama. Recargue la página o ábralo desde su biblioteca.",
        "conflict": "No se pudo guardar la instantánea (conflicto). Inténtelo de nuevo.",
    },
    "fr": {
        "too_large": "La capture est trop volumineuse (max {max} KB). "
        "Réduisez le contenu du diagramme et réessayez.",
        "rate": "Trop d’actions de capture. Attendez un instant et réessayez.",
        "not_found": "Diagramme introuvable. Rechargez la page ou ouvrez-le depuis votre bibliothèque.",
        "conflict": "Impossible d’enregistrer la capture (conflit). Réessayez.",
    },
    "de": {
        "too_large": "Der Schnappschuss ist zu groß (max. {max} KB). "
        "Reduzieren Sie den Diagramminhalt und versuchen Sie es erneut.",
        "rate": "Zu viele Schnappschuss-Aktionen. Warten Sie einen Moment und versuchen Sie es erneut.",
        "not_found": "Diagramm nicht gefunden. Laden Sie die Seite neu oder öffnen Sie es aus Ihrer Bibliothek.",
        "conflict": "Schnappschuss konnte nicht gespeichert werden (Konflikt). Bitte erneut versuchen.",
    },
    "it": {
        "too_large": "L’istantanea è troppo grande (max {max} KB). Riduci il contenuto del diagramma e riprova.",
        "rate": "Troppe azioni su istantanee. Attendi un momento e riprova.",
        "not_found": "Diagramma non trovato. Ricarica la pagina o aprilo dalla libreria.",
        "conflict": "Impossibile salvare l’istantanea (conflitto). Riprova.",
    },
    "nl": {
        "too_large": "De momentopname is te groot (max. {max} KB). "
        "Verminder de diagraminhoud en probeer het opnieuw.",
        "rate": "Te veel momentopname-acties. Wacht even en probeer het opnieuw.",
        "not_found": "Diagram niet gevonden. Vernieuw de pagina of open het vanuit je bibliotheek.",
        "conflict": "Momentopname opslaan mislukt (conflict). Probeer het opnieuw.",
    },
    "pt": {
        "too_large": "O instantâneo é grande demais (máx. {max} KB). "
        "Reduza o conteúdo do diagrama e tente novamente.",
        "rate": "Muitas ações de instantâneo. Aguarde um momento e tente novamente.",
        "not_found": "Diagrama não encontrado. Recarregue a página ou abra pela biblioteca.",
        "conflict": "Não foi possível guardar o instantâneo (conflito). Tente novamente.",
    },
    "pl": {
        "too_large": "Migawka jest za duża (maks. {max} KB). Zmniejsz zawartość diagramu i spróbuj ponownie.",
        "rate": "Zbyt wiele operacji migawki. Poczekaj chwilę i spróbuj ponownie.",
        "not_found": "Nie znaleziono diagramu. Odśwież stronę lub otwórz z biblioteki.",
        "conflict": "Nie można zapisać migawki (konflikt). Spróbuj ponownie.",
    },
    "tr": {
        "too_large": "Anlık görüntü çok büyük (en fazla {max} KB). "
        "Diyagram içeriğini azaltıp yeniden deneyin.",
        "rate": "Çok fazla anlık görüntü işlemi. Kısa süre bekleyip yeniden deneyin.",
        "not_found": "Diyagram bulunamadı. Sayfayı yenileyin veya kitaplıktan açın.",
        "conflict": "Anlık görüntü kaydedilemedi (çakışma). Yeniden deneyin.",
    },
    "ru": {
        "too_large": "Снимок слишком велик (макс. {max} KB). "
        "Упростите диаграмму и попробуйте снова.",
        "rate": "Слишком много операций со снимками. Подождите немного и повторите попытку.",
        "not_found": "Диаграмма не найдена. Перезагрузите страницу или откройте из библиотеки.",
        "conflict": "Не удалось сохранить снимок (конфликт). Попробуйте снова.",
    },
    "uk": {
        "too_large": "Знімок завеликий (макс. {max} KB). "
        "Спростіть вміст діаграми й спробуйте ще раз.",
        "rate": "Забагато дій зі знімками. Зачекайте трохи й повторіть спробу.",
        "not_found": "Діаграму не знайдено. Перезавантажте сторінку або відкрийте з бібліотеки.",
        "conflict": "Не вдалося зберегти знімок (конфлікт). Спробуйте ще раз.",
    },
    "vi": {
        "too_large": "Ảnh chụp quá lớn (tối đa {max} KB). Giảm nội dung sơ đồ rồi thử lại.",
        "rate": "Quá nhiều thao tác ảnh chụp. Đợi một lát rồi thử lại.",
        "not_found": "Không tìm thấy sơ đồ. Tải lại trang hoặc mở từ thư viện.",
        "conflict": "Không lưu được ảnh chụp (xung đột). Thử lại.",
    },
    "th": {
        "too_large": "สแนปชอตใหญ่เกินไป (สูงสุด {max} KB) "
        "ลดเนื้อหาไดอะแกรมแล้วลองอีกครั้ง",
        "rate": "การทำสแนปชอตถี่เกินไป รอสักครู่แล้วลองอีกครั้ง",
        "not_found": "ไม่พบไดอะแกรม โหลดหน้าใหม่หรือเปิดจากคลัง",
        "conflict": "บันทึกสแนปชอตไม่ได้ (ขัดแย้ง) ลองอีกครั้ง",
    },
    "ms": {
        "too_large": "Snapshot terlalu besar (maks {max} KB). "
        "Kurangkan kandungan diagram dan cuba lagi.",
        "rate": "Terlalu banyak tindakan snapshot. Tunggu sebentar dan cuba lagi.",
        "not_found": "Diagram tidak dijumpai. Muat semula halaman atau buka dari pustaka.",
        "conflict": "Tidak dapat menyimpan snapshot (konflik). Cuba lagi.",
    },
    "af": {
        "too_large": "Momentopname is te groot (maks {max} KB). "
        "Verminder die inhoud van die diagram en probeer weer.",
        "rate": "Te veel momentopname-aksies. Wag ’n oomblik en probeer weer.",
        "not_found": "Diagram nie gevind nie. Laai die bladsy weer of maak dit van jou biblioteek oop.",
        "conflict": "Kon nie momentopname stoor nie (konflik). Probeer weer.",
    },
    "sq": {
        "too_large": "Fotografia është shumë e madhe (maks. {max} KB). "
        "Zvogëloni përmbajtjen e diagramit dhe provoni përsëri.",
        "rate": "Shumë veprime fotografie. Prisni pak dhe provoni përsëri.",
        "not_found": "Diagrami nuk u gjet. Ringarkoni faqen ose hapeni nga biblioteka.",
        "conflict": "Nuk u ruajt fotografia (konflikt). Provoni përsëri.",
    },
    "tl": {
        "too_large": "Masyadong malaki ang snapshot (maks. {max} KB). "
        "Bawasan ang nilalaman ng diagram at subukan muli.",
        "rate": "Masyadong maraming snapshot. Maghintay sandali at subukan muli.",
        "not_found": "Hindi nahanap ang diagram. I-reload ang page o buksan mula sa library.",
        "conflict": "Hindi masave ang snapshot (conflict). Subukan muli.",
    },
    "uz": {
        "too_large": "Nusxa juda katta (maks. {max} KB). "
        "Diagramma mazmunini qisqartiring va qayta urinib ko‘ring.",
        "rate": "Juda ko‘p snapshot amallari. Biroz kuting va qayta urinib ko‘ring.",
        "not_found": "Diagramma topilmadi. Sahifani yangilang yoki kutubxonadan oching.",
        "conflict": "Snapshot saqlanmadi (ziddiyat). Qayta urinib ko‘ring.",
    },
    "ar": {
        "too_large": "لقطة الشاشة كبيرة جداً (الحد الأقصى {max} كيلوبايت). "
        "قلّل محتوى المخطط وحاول مرة أخرى.",
        "rate": "عمليات لقطة شاشة كثيرة جداً. انتظر قليلاً ثم حاول مرة أخرى.",
        "not_found": "المخطط غير موجود. أعد تحميل الصفحة أو افتحه من مكتبتك.",
        "conflict": "تعذّر حفظ لقطة الشاشة (تعارض). حاول مرة أخرى.",
    },
    "fa": {
        "too_large": "عکس لحظه‌ای خیلی بزرگ است (حداکثر {max} کیلوبایت). "
        "محتوای نمودار را کم کنید و دوباره تلاش کنید.",
        "rate": "عملیات عکس لحظه‌ای بیش از حد است. کمی صبر کنید و دوباره تلاش کنید.",
        "not_found": "نمودار پیدا نشد. صفحه را بارگذاری مجدد کنید یا از کتابخانه باز کنید.",
        "conflict": "ذخیره عکس لحظه‌ای ممکن نشد (تضاد). دوباره تلاش کنید.",
    },
    "hi": {
        "too_large": "स्नैपशॉट बहुत बड़ा है (अधिकतम {max} KB)। "
        "आरेख सामग्री कम करें और पुनः प्रयास करें।",
        "rate": "बहुत अधिक स्नैपशॉट क्रियाएँ। क्षण प्रतीक्षा करें और पुनः प्रयास करें।",
        "not_found": "आरेख नहीं मिला। पृष्ठ पुनः लोड करें या पुस्तकालय से खोलें।",
        "conflict": "स्नैपशॉट सहेजा नहीं जा सका (संघर्ष)। पुनः प्रयास करें।",
    },
    "id": {
        "too_large": "Snapshot terlalu besar (maks {max} KB). "
        "Kurangi isi diagram dan coba lagi.",
        "rate": "Terlalu banyak tindakan snapshot. Tunggu sebentar dan coba lagi.",
        "not_found": "Diagram tidak ditemukan. Muat ulang halaman atau buka dari perpustakaan.",
        "conflict": "Tidak dapat menyimpan snapshot (konflik). Coba lagi.",
    },
    "ja": {
        "too_large": "スナップショットが大きすぎます（最大 {max} KB）。"
        "ダイアグラムの内容を減らしてから再度お試しください。",
        "rate": "スナップショット操作が多すぎます。しばらく待ってから再度お試しください。",
        "not_found": "ダイアグラムが見つかりません。ページを再読み込みするかライブラリから開いてください。",
        "conflict": "スナップショットを保存できませんでした（競合）。再度お試しください。",
    },
    "ko": {
        "too_large": "스냅샷이 너무 큽니다(최대 {max} KB). "
        "다이어그램 내용을 줄인 뒤 다시 시도하세요.",
        "rate": "스냅샷 작업이 너무 많습니다. 잠시 후 다시 시도하세요.",
        "not_found": "다이어그램을 찾을 수 없습니다. 페이지를 새로고침하거나 라이브러리에서 여세요.",
        "conflict": "스냅샷을 저장할 수 없습니다(충돌). 다시 시도하세요.",
    },
}


def _escape(val: str) -> str:
    return val.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _insert_block(code: str, path: Path, bundle: dict[str, str]) -> bool:
    text = path.read_text(encoding="utf-8")
    if "snapshotTooLarge" in text:
        return False
    block = (
        f"  'canvas.toolbar.snapshotTooLarge':\n"
        f"    '{_escape(bundle['too_large'])}',\n"
        f"  'canvas.toolbar.snapshotRateLimited': '{_escape(bundle['rate'])}',\n"
        f"  'canvas.toolbar.snapshotDiagramNotFound':\n"
        f"    '{_escape(bundle['not_found'])}',\n"
        f"  'canvas.toolbar.snapshotConflict': '{_escape(bundle['conflict'])}',\n"
    )
    pattern = re.compile(
        r"^([ \t]*'canvas\.toolbar\.snapshotFailed':[^\n]+\n)",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        print(f"skip {code}: no snapshotFailed line")
        return False
    new_text = pattern.sub(lambda m: m.group(1) + block, text, count=1)
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    for child in sorted(ROOT.iterdir()):
        if not child.is_dir():
            continue
        code = child.name
        path = child / "canvas.ts"
        if not path.is_file():
            continue
        bundle = BUNDLE.get(code, EN_FALLBACK)
        if _insert_block(code, path, bundle):
            print(f"patched {code}")


if __name__ == "__main__":
    main()
