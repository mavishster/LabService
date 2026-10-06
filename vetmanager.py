import html
import requests
from datetime import datetime

from config import API_KEY, COLOR_MODE, VETMANAGER_URL
from formatting import colorize, get_status


def _format_result_value(value, reference, flag):
    escaped_value = html.escape(str(value))
    status = get_status(value, reference, flag)

    if COLOR_MODE == "html":
        return colorize(escaped_value, status)

    if status == "high":
        return f"{escaped_value} ↑"
    if status == "low":
        return f"{escaped_value} ↓"
    return escaped_value


def send_results_direct_to_medical_card(card_id, device_name, lab_code, results_pack):
    """
    Отправляет результаты анализа напрямую в медицинскую карту VetManager
    и подробно логирует GET/PUT ответы для диагностики.
    """

    sent_at = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    if not card_id:
        print("❌ [Ветменеджер] Не указан номер медицинской карты")
        return False

    card_id = str(card_id).strip()

    if not card_id.isdigit():
        print(f"❌ [Ветменеджер] Некорректный номер карты: '{card_id}'")
        return False

    if not results_pack:
        print("❌ [Ветменеджер] results_pack пустой — отправлять нечего")
        return False

    headers = {
        "X-REST-API-KEY": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    card_url = f"{VETMANAGER_URL}/rest/api/medicalCards/{card_id}"

    print(
        f"\n🔎 [Ветменеджер] Карта №{card_id}"
    )

    # ---------------------------------------------------------
    # 1. GET медицинской карты
    # ---------------------------------------------------------

    try:
        response = requests.get(
            card_url,
            headers=headers,
            timeout=30
        )
    except requests.RequestException as e:
        print(f"❌ [Ветменеджер] Ошибка GET: {e}")
        return False

    print(
        f"📥 [Ветменеджер] GET: HTTP {response.status_code}"
    )

    if response.status_code != 200:
        print(
            f"❌ [Ветменеджер] Не удалось получить карту №{card_id}. "
            f"HTTP {response.status_code}"
        )
        return False

    try:
        card_data = response.json()
    except ValueError:
        print("❌ [Ветменеджер] GET вернул не JSON")
        return False


    # ---------------------------------------------------------
    # 2. Извлекаем медицинскую карту
    # ---------------------------------------------------------

    medical_cards = card_data.get("data", {}).get("medicalCards")

    if not medical_cards:
        print("❌ [Ветменеджер] В ответе нет data.medicalCards")
        return False

    if isinstance(medical_cards, list):
        if not medical_cards:
            print("❌ [Ветменеджер] medicalCards пустой")
            return False

        medical_card = medical_cards[0]

    elif isinstance(medical_cards, dict):
        medical_card = medical_cards

    else:
        print(
            f"❌ [Ветменеджер] Неизвестный формат medicalCards: "
            f"{type(medical_cards)}"
        )
        return False

    # ---------------------------------------------------------
    # 3. Получаем обязательные поля
    # ---------------------------------------------------------

    patient_id = medical_card.get("patient_id")
    doctor_id = medical_card.get("doctor_id")
    clinic_id = medical_card.get("clinic_id")

    current_description = medical_card.get("description") or ""

    print()
    print(f"👤 patient_id: {patient_id}")
    print(f"👨‍⚕️ doctor_id: {doctor_id}")
    print(f"🏥 clinic_id: {clinic_id}")
    #print(f"📝 Текущий description: {repr(current_description)}")

    if not patient_id:
        print("❌ [Ветменеджер] Не найден patient_id")
        return False

    if not doctor_id:
        print("❌ [Ветменеджер] Не найден doctor_id")
        return False

    if not clinic_id:
        print("❌ [Ветменеджер] Не найден clinic_id")
        return False

    # ---------------------------------------------------------
    # 4. Формируем HTML результатов
    # ---------------------------------------------------------

    html_table = []



    html_table.append(
    	f"<p><strong>{html.escape(str(device_name))}</strong> "
   	f"— {html.escape(str(lab_code))}</p>"
    )

    html_table.append(
   	 f"<p><strong>Дата и время отправки:</strong> "
   	 f"{html.escape(sent_at)}</p>"
    )

    html_table.append(
   	 "<table border='1' cellpadding='5' cellspacing='0'>"
    )

    if device_name == "Getein GN 7000 (PCR)":

        html_table.append(
            "<tr>"
            "<th>Показатель</th>"
            "<th>Результат</th>"
            "<th>Единица</th>"
            "<th>Референс</th>"
            "</tr>"
        )

    else:   

        html_table.append(
            "<tr>"
            "<th>Показатель</th>"
            "<th>Результат</th>"
            "<th>Единица</th>"
            "<th>Референс</th>"
            "<th>Флаг</th>"
            "</tr>"
        )

    for item in results_pack:
        if isinstance(item, dict):
            name = item.get("name", item.get("code", ""))
            value = item.get("value", "")
            unit = item.get("unit", "")
            reference = item.get("reference", "")
            flag = item.get("flag", "")

        else:
            name = str(item)
            value = ""
            unit = ""
            reference = ""
            flag = ""

        formatted_value = _format_result_value(
            value,
            reference,
            flag
        )

        if device_name == "Getein GN 7000 (PCR)":

            html_table.append(
                "<tr>"
                f"<td>{html.escape(str(name))}</td>"
                f"<td>{formatted_value}</td>"
                f"<td>{html.escape(str(unit))}</td>"
                f"<td>{html.escape(str(reference))}</td>"
                "</tr>"
            )

        else:

            html_table.append(
                "<tr>"
                f"<td>{html.escape(str(name))}</td>"
                f"<td>{formatted_value}</td>"
                f"<td>{html.escape(str(unit))}</td>"
                f"<td>{html.escape(str(reference))}</td>"
                f"<td>{html.escape(str(flag))}</td>"
                "</tr>"
            )

    html_table.append("</table>")

    html_table = "".join(html_table)

    print(
        f"🧪 [Ветменеджер] "
        f"Подготовлено результатов: {len(results_pack)}"
    )

    # ---------------------------------------------------------
    # 5. Формируем JSON для PUT
    # ---------------------------------------------------------

    new_description = (
        current_description
        + "<br>"
        + html_table
    )

    payload = {
        "patient_id": int(patient_id),
        "doctor_id": int(doctor_id),
        "clinic_id": int(clinic_id),
        "description": new_description
    }

    print(
        f"📤 [Ветменеджер] PUT карты №{card_id}"
    )
    # ---------------------------------------------------------
    # 6. PUT медицинской карты
    # ---------------------------------------------------------

    print(f"📤 [Ветменеджер] PUT {card_url}")

    try:
        put_response = requests.put(
            card_url,
            headers=headers,
            json=payload,
            timeout=30
        )
    except requests.RequestException as e:
        print(f"❌ [Ветменеджер] Ошибка PUT: {e}")
        return False

    # ---------------------------------------------------------
    # 7. ПОЛНЫЙ ответ VetManager
    # ---------------------------------------------------------

    print(
        f"📥 [Ветменеджер] PUT: "
        f"HTTP {put_response.status_code}"
    )

    if put_response.status_code not in (200, 201):
        print(
            f"❌ [Ветменеджер] PUT ОТКЛОНЁН. "
            f"HTTP {put_response.status_code}"
        )
        return False

    # ---------------------------------------------------------
    # 8. Пробуем разобрать ответ PUT как JSON
    # ---------------------------------------------------------


    # ---------------------------------------------------------
    # 9. Повторно читаем медицинскую карту
    #
    # Это самый важный диагностический шаг.
    # Мы проверяем, сохранился ли новый description.
    # ---------------------------------------------------------

    print(
        "🔄 [Ветменеджер] Проверяем сохранение..."
    )

    try:
        verify_response = requests.get(
            card_url,
            headers=headers,
            timeout=30
        )
    except requests.RequestException as e:
        print(
            f"⚠️ [Ветменеджер] Не удалось выполнить повторный GET: {e}"
        )

        print(
            f"⚠️ PUT вернул HTTP {put_response.status_code}, "
            f"но проверить сохранение не удалось."
        )

        return True

    print(
        f"📥 [Ветменеджер] VERIFY GET: "
        f"HTTP {verify_response.status_code}"
    )

    if verify_response.status_code != 200:
        print(
            "⚠️ [Ветменеджер] Повторный GET карты завершился "
            f"HTTP {verify_response.status_code}"
        )
        return True

    try:
        verify_json = verify_response.json()

        verify_cards = (
            verify_json
            .get("data", {})
            .get("medicalCards")
        )

        if isinstance(verify_cards, list):
            verify_card = verify_cards[0] if verify_cards else {}
        elif isinstance(verify_cards, dict):
            verify_card = verify_cards
        else:
            verify_card = {}

        verify_description = verify_card.get("description") or ""

        if html_table in verify_description:

            print(
                "✅ [Ветменеджер] "
                "Данные сохранены и проверены."
            )

        else:

            print(
                "⚠️ [Ветменеджер] "
                "PUT успешен, но данные не найдены "
                "при проверке."
            )

        # -----------------------------------------------------
        # Проверяем, появился ли именно наш HTML
        # -----------------------------------------------------

        if html_table in verify_description:
            print()
            print(
                "✅ [Ветменеджер] ПРОВЕРКА УСПЕШНА: "
                "новые данные действительно сохранились в description."
            )
        else:
            print()
            print(
                "⚠️ [Ветменеджер] PUT вернул успешный HTTP-код, "
                "но отправленный HTML НЕ НАЙДЕН в description после повторного GET."
            )

            print()
            print("🔴 Это очень важно:")
            print(
                "VetManager ответил на PUT успешно, "
                "но данные не появились в medicalCard.description."
            )

    except ValueError:
        print(
            "⚠️ [Ветменеджер] Повторный GET вернул не JSON"
        )

    print()
    print("=" * 80)
    print(
        f"🏁 [Ветменеджер] Обработка карты №{card_id} завершена"
    )
    print("=" * 80)

    return True
