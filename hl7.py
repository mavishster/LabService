import re

from config import BHA_ANALYSIS_NAMES, test_names_ru
from vetmanager import send_results_direct_to_medical_card

def extract_hl7_results(lines):
    """
    Извлекает результаты из OBX-сегментов HL7.

    Логика названия показателя:
    1. Сначала используется OBX-3 через test_names_ru.
    2. Если для OBX-3 нет русского названия,
       используется OBX-4.
    """

    results_pack = []

    obx_lines = [
        line.strip()
        for line in lines
        if line.strip().startswith("OBX|")
    ]

    for obx in obx_lines:

        parts = obx.split("|")

        if len(parts) < 8:
            continue

        # OBX-3 — код показателя
        t_name_code = (
            parts[3]
            .split("^")[0]
            .strip()
        )

        # Сначала ищем русское название по коду
        t_name = test_names_ru.get(
            t_name_code
        )

        # Если кода нет в словаре — берем OBX-4
        if not t_name:
            t_name = (
                parts[4].strip()
                if len(parts) > 4
                else ""
            )

        # OBX-5 — результат
        r_val = parts[5].strip()

        # OBX-6 — единица
        unit = (
            parts[6].strip()
            if len(parts) > 6
            else ""
        )

        # OBX-7 — референс
        ref = (
            parts[7].strip()
            if len(parts) > 7
            else ""
        )

        # OBX-8 — флаг
        flag = (
            parts[8].strip()
            if len(parts) > 8
            else ""
        )

        # Игнорируем большие технические данные
        if (
            "Histo" in t_name
            or "Base64" in r_val
        ):
            continue

        results_pack.append({
            "name": t_name,
            "value": r_val,
            "unit": unit,
            "reference": ref,
            "flag": flag
        })

    return results_pack

def extract_card_id_from_hl7(lines):
    """
    Извлекает номер медицинской карты из HL7.

    Приоритет:
    1. PV1-6 — существующий формат.
    2. PID-3 — используется, в частности, Getein 1160.

    Возвращает строку с ID или "0".
    """

    card_id = "0"

    # Сначала ищем существующий формат PV1-6.
    for line in lines:

        line = line.strip()

        if not line.startswith("PV1|"):
            continue

        parts = line.split("|")

        if len(parts) < 6:
            continue

        raw_id = parts[5].strip()

        card_id = (
            raw_id
            .split("^")[0]
            .strip()
        )

        if card_id:
            return card_id

    # Если PV1 нет или номер карты в PV1 не найден,
    # ищем PID-3.
    for line in lines:

        line = line.strip()

        if not line.startswith("PID|"):
            continue

        parts = line.split("|")

        if len(parts) < 3:
            continue

        raw_id = parts[2].strip()

        card_id = (
            raw_id
            .split("^")[0]
            .strip()
        )

        if card_id:
            return card_id

    return card_id

def process_hl7_message(
    raw_text,
    device_info
):
    """
    Полностью разбирает HL7 сообщение
    и отправляет результаты в VetManager.

    Возвращает:
        True  - результаты успешно отправлены
        False - отправка не выполнена
    """

    print(
        f"\n--- ПОЛУЧЕН ПОЛНЫЙ ТЕКСТ АНАЛИЗА "
        f"({len(raw_text)} симв.) ---"
    )

    # ============================================================
    # HEARTBEAT
    # ============================================================

    if "HEARTBEAT" in raw_text:

        print(
            "💓 [BHA-5000] "
            "Получен HEARTBEAT — игнорируем."
        )

        return False

    # ============================================================
    # HL7 SEGMENTS
    # ============================================================

    print(
        "\n🔍 ===== HL7 СЕГМЕНТЫ ====="
    )

    clean_text = (
        raw_text
        .replace("\x0b", "")
        .replace("\x1c", "")
        .replace("\x03", "")
    )

    for segment in re.split(
        r"[\r\n]+",
        clean_text
    ):

        segment = segment.strip()

        if segment:
            print(segment)

    print(
        "🔍 ========================\n"
    )

    # ============================================================
    # LINES
    # ============================================================

    lines = (
        clean_text
        .replace("\r", "\n")
        .split("\n")
    )

    lines = [
        line.strip()
        for line in lines
        if line.strip()
    ]

    # ============================================================
    # MEDICAL CARD
    # ============================================================

    card_id = extract_card_id_from_hl7(
        lines
    )

    print(
        f"   [Парсер] "
        f"Извлечен номер медицинской карты "
        f"пациента: '{card_id}'"
    )

    if (
        card_id == "0"
        or not card_id.isdigit()
    ):

        print(
            f"   ⚠️ Отмена отправки: "
            f"Не удалось определить валидный "
            f"ID медкарты "
            f"(получено: '{card_id}')"
        )

        return False

    # ============================================================
    # OBX
    # ============================================================

    results_pack = extract_hl7_results(
        lines
    )

    print(
        f"   [Парсер] "
        f"Найдено лабораторных результатов: "
        f"{len(results_pack)}"
    )

    if not results_pack:

        print(
            "   ⚠️ [Парсер] "
            "OBX-сегменты не содержат "
            "пригодных результатов."
        )

        return False

    # ============================================================
    # VETMANAGER
    # ============================================================

    if device_info.get("name") in {
        "Ozelle Vet BHA-5000",
        "Ozelle EHVT-75",
    }:
        analysis_name = (
            extract_analysis_name_from_obr(raw_text)
            or device_info.get("lab_code")
            or ""
        )
        analysis_name = BHA_ANALYSIS_NAMES.get(
            analysis_name,
            analysis_name
        )
    else:
        analysis_name = device_info["lab_code"]

    print(
        f"\n📤 [Ветменеджер] "
        f"Отправляем {len(results_pack)} "
        f"результатов в карту №{card_id}"
    )

    print(
         f"\n[Исследование] {analysis_name}"
    )

    success = send_results_direct_to_medical_card(
        card_id=card_id,
        device_name=device_info["name"],
        lab_code=analysis_name,
        results_pack=results_pack
    )

    if success:

        print(
            f"✅ [Ветменеджер] "
            f"Результаты успешно отправлены "
            f"в карту №{card_id}"
        )

    else:

        print(
            f"❌ [Ветменеджер] "
            f"Результаты НЕ отправлены "
            f"в карту №{card_id}"
        )

    return success

def extract_analysis_name_from_obr(raw_text):
    for line in raw_text.splitlines():

        if line.startswith("OBR|"):

            fields = line.split("|")

            if len(fields) > 4:

                analysis = fields[4].split("^")

                if len(analysis) > 1:
                    return analysis[1].strip()

                return analysis[0].strip()

    return ""
