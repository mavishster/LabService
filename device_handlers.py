import re
from datetime import datetime

from config import pcr_names_ru, translate
from hl7 import process_hl7_message
from vetmanager import send_results_direct_to_medical_card

def handle_getein_7000_data(
    client_socket,
    device_info
):
    """
    Отдельный обработчик Getein GN 7000.

    BHA-5000 сюда никогда не попадает.
    """

    print(
        f"\n⚡ [GETEIN 7000] "
        f"Сетевой контакт! "
        f"[{device_info['name']}] подключился..."
    )

    buffer = b""
    ack_sent = False

    try:

        while True:

            data = client_socket.recv(4096)

            if not data:

                print(
                    f"🔴 [{datetime.now():%H:%M:%S}] "
                    f"[GETEIN 7000] "
                    f"Аппарат закрыл соединение"
                )

                break

            buffer += data

            print(
                f"📥 [{datetime.now():%H:%M:%S}] "
                f"[GETEIN 7000] "
                f"Получено данных: "
                f"{len(data)} байт"
            )

            # ====================================================
            # RAW DEBUG
            # ====================================================

            if len(data) <= 50:

                print(
                    "   🔎 [GETEIN 7000] "
                    f"RAW: {repr(data)}"
                )

            # ====================================================
            # ACK
            # ====================================================

            if not ack_sent:

                try:

                    client_socket.sendall(
                        b"\x06"
                    )

                    ack_sent = True

                    print(
                        "📤 [GETEIN 7000] "
                        "ACK (06) отправлен"
                    )

                except Exception as e:

                    print(
                        f"⚠️ [GETEIN 7000] "
                        f"Ошибка ACK: {e}"
                    )

            # ====================================================
            # TEXT
            # ====================================================

            raw_text = buffer.decode(
                "utf-8",
                errors="ignore"
            )

            # ====================================================
            # ИЩЕМ НАЧАЛО ПАКЕТА GN 7000
            # ====================================================

            start_pos = -1

            # Ищем строку, которая начинается с названия панели
            # и содержит структуру:
            #
            # PANEL_NAME|номер|пациент|...|номер_карты|...
            #
            # Название панели заранее не знаем.

            for match in re.finditer(
                r"([A-Za-z0-9_/]+)\|(\d+)\|[^|]*\|(\d+)\|(\d+)\|",
                raw_text
            ):

                candidate = match.group(0)

                # Проверяем, что дальше в пакете действительно
                # присутствует результат вида:
                #
                # TEST^45^0^0^...
                #
                rest = raw_text[match.start():]

                if re.search(
                    r"\|[A-Za-z0-9_]+?\^[0-9]+(?:\.[0-9]+)?\^",
                    rest
                ):

                    start_pos = match.start()
                    break


            if start_pos == -1:

                print(
                    "   ⏳ [GETEIN 7000] "
                    "Полезная часть пакета "
                    "пока не найдена."
                )

                continue


            payload = raw_text[start_pos:]

            # ====================================================
            # Очищаем управляющие символы
            # ====================================================

            payload = (
                payload
                .replace("\x00", "")
                .replace("\x02", "")
                .replace("\x03", "")
                .replace("\x04", "")
                .replace("\x05", "")
                .replace("\x06", "")
                .replace("\x15", "")
                .strip()
            )

            print(
                f"\n--- [GETEIN 7000] "
                f"ПОЛУЧЕН ПАКЕТ: {len(payload)} символов ---"
            )

            print(payload)

            # ====================================================
            # FIELDS
            # ====================================================

            fields = [
                field.strip()
                for field in payload.split("|")
            ]

            print(
                f"   Полей в пакете: {len(fields)}"
            )

            # ====================================================
            # Проверка количества полей
            # ====================================================

            if len(fields) < 5:

                print(
                    "❌ [GETEIN 7000] "
                    "Недостаточно полей в пакете."
                )

                print(
                    "\n===== RAW GETEIN PAYLOAD ====="
                )

                print(payload)

                print(
                    "===============================\n"
                )

                break

            # ====================================================
            # Формат:
            #
            # [0] FCoV/FPV/TF/GL
            # [1] 3
            # [2] Bayfong
            # [3] 12
            # [4] 3968
            # [5] M
            # [6] 26001
            # [7] 0
            # [8] 2026-09-22 18:31:38
            # [9] 3
            # [10] FCoV^45^0^0^...
            # [11] FPV^45^0^0^...
            # [12] TF^45^0^0^...
            # [13] GL^45^0^0^...
            # ====================================================

            card_id = fields[4].strip()

            patient_name = (
                fields[2].strip()
                if len(fields) > 2
                else ""
            )

            analysis_date = (
                fields[8].strip()
                if len(fields) > 8
                else ""
            )

            print(
                f"\n   👤 Пациент: "
                f"{patient_name}"
            )

            print(
                f"   🕐 Дата анализа: "
                f"{analysis_date}"
            )

            print(
                f"   💳 Номер медицинской карты: "
                f"'{card_id}'"
            )

            # ====================================================
            # CARD ID
            # ====================================================

            if (
                not card_id.isdigit()
                or card_id == "0"
            ):

                print(
                    f"❌ [GETEIN 7000] "
                    f"Некорректный номер карты: "
                    f"'{card_id}'"
                )

                break

           # ====================================================
            # РЕЗУЛЬТАТЫ PCR
            # ====================================================

            results_pack = []

            for field in fields:

                field = field.strip()

                if "^" not in field:
                    continue

                parts = field.split(
                    "^",
                    4
                )

                if len(parts) < 2:
                    continue

                test_code = parts[0].strip()

                if not test_code:
                    continue

                ct_value = parts[1].strip()

                # =================================================
                # CT
                # =================================================

                try:

                    ct = float(ct_value)

                except ValueError:

                    print(
                        f"⚠️ [GETEIN 7000] "
                        f"Не удалось определить CT "
                        f"для {test_code}: "
                        f"'{ct_value}'"
                    )

                    continue

                # =================================================
                # РЕЗУЛЬТАТ
                #
                # По отчету прибора:
                #
                # CT > 38  -> Negative
                # CT <= 38 -> Positive
                # =================================================

                if ct > 38:

                    result = "Negative"

                else:

                    result = "Positive"

                name = translate(
                    test_code,
                    pcr_names_ru
                )

                print(
                    f"\n   🧪 [GETEIN 7000] "
                    f"{name}"
                )

                print(
                    f"      CT: {ct:.1f}"
                )

                print(
                    f"      Результат: {result}"
                )

                results_pack.append({
                    "name": name,
                    "value": result,
                    "unit": f"CT {ct:.1f}",
                    "reference": ">38 = Negative",
                    "flag": ""
                })
            # ====================================================
            # RESULTS
            # ====================================================

            if not results_pack:

                print(
                    "⚠️ [GETEIN 7000] "
                    "Результаты PCR "
                    "в пакете не найдены."
                )

                print(
                    "\n===== RAW GETEIN PAYLOAD ====="
                )

                print(payload)

                print(
                    "===============================\n"
                )

                break

            # ====================================================
            # SEND
            # ====================================================

            print(
                f"\n📤 [GETEIN 7000] "
                f"Отправляем результаты "
                f"в карту №{card_id}"
            )

            success = (
                send_results_direct_to_medical_card(
                    card_id=card_id,
                    device_name=device_info["name"],
                    lab_code=device_info["lab_code"],
                    results_pack=results_pack
                )
            )

            if success:

                print(
                    f"✅ [GETEIN 7000] "
                    f"Результаты отправлены "
                    f"в карту №{card_id}"
                )

            else:

                print(
                    f"❌ [GETEIN 7000] "
                    f"Результаты НЕ отправлены "
                    f"в карту №{card_id}"
                )

            buffer = b""
            # ====================================================
            # FINAL ACK
            # ====================================================

            try:

                client_socket.sendall(
                    b"\x06"
                )

                print(
                    "📤 [GETEIN 7000] "
                    "Финальный ACK (06) отправлен"
                )

            except Exception as e:

                print(
                    f"⚠️ [GETEIN 7000] "
                    f"Ошибка финального ACK: {e}"
                )

            break

    except Exception as e:

        print(
            f"💥 [GETEIN 7000] "
            f"Ошибка сессии: {e}"
        )

    finally:

        try:
            client_socket.close()

        except Exception:
            pass

        print(
            f"🔌 [GETEIN 7000] "
            f"Сессия завершена.\n"
            + "=" * 50
        )

def handle_device_data(
    client_socket,
    device_info
):
    """
    Общий вход для всех приборов.

    Getein GN 7000 отправляется
    в специальный обработчик.

    Остальные приборы используют
    HL7-логику.

    Для HL7 устройств поддерживается
    обработка нескольких сообщений
    через одно TCP-соединение.
    """

    # ============================================================
    # GETEIN GN 7000
    # ============================================================

    if device_info.get("lab_code") == "ПЦР":

        return handle_getein_7000_data(
            client_socket,
            device_info
        )

    # ============================================================
    # ВСЕ ОСТАЛЬНЫЕ ПРИБОРЫ
    #
    # В том числе:
    # Ozelle Vet BHA-5000
    # ============================================================

    print(
        f"\n⚡ Сетевой контакт! "
        f"[{device_info['name']}] подключился..."
    )

    buffer = b""

    try:

        while True:

            data = client_socket.recv(4096)

            if not data:

                print(
                    f"🔴 [{datetime.now():%H:%M:%S}] "
                    f"Аппарат закрыл соединение"
                )

                break

            buffer += data

            print(
                f"📥 [{datetime.now():%H:%M:%S}] "
                f"Получены данные от аппарата: "
                f"{len(data)} байт"
            )

            # ====================================================
            # DEBUG короткого пакета
            # ====================================================

            if len(data) <= 50:

                print(
                    f"   🔎 Содержимое пакета: "
                    f"{repr(data)}"
                )

            # ====================================================
            # ACK
            #
            # Отправляем ACK на полученные данные.
            # ====================================================

            if (
                b"\x05" in data
                or len(buffer) < 10
            ):

                try:

                    client_socket.sendall(
                        b"\x06"
                    )

                    print(
                        f"📤 [{datetime.now():%H:%M:%S}] "
                        f"Сервер отправил ACK (06)"
                    )

                except Exception as e:

                    print(
                        f"⚠️ Ошибка отправки ACK: {e}"
                    )

            # ====================================================
            # ОБРАБАТЫВАЕМ ВСЕ ПОЛНЫЕ HL7 СООБЩЕНИЯ,
            # КОТОРЫЕ УЖЕ ЕСТЬ В BUFFER
            #
            # HL7/MLLP:
            #
            #   0x0b ... 0x1c 0x0d
            #
            # 0x0b = начало сообщения
            # 0x1c = конец сообщения
            # 0x0d = CR
            # ====================================================

            while b"\x1c" in buffer:

                # =================================================
                # Находим конец первого HL7 сообщения
                # =================================================

                end_pos = buffer.find(
                    b"\x1c"
                )

                message_bytes = (
                    buffer[:end_pos + 1]
                )

                # =================================================
                # Удаляем обработанное сообщение из buffer.
                #
                # Остаток может содержать:
                #
                # - следующее HL7 сообщение
                # - часть следующего сообщения
                # =================================================

                buffer = buffer[
                    end_pos + 1:
                ]

                # =================================================
                # Если после 0x1c сразу идет CR,
                # удаляем его.
                # =================================================

                if buffer.startswith(
                    b"\r"
                ):

                    buffer = buffer[1:]

                # =================================================
                # DECODE
                # =================================================

                raw_text = message_bytes.decode(
                    "utf-8",
                    errors="ignore"
                )

                # =================================================
                # PROCESS HL7
                # =================================================

                print(
                    "\n"
                    + "=" * 80
                )

                print(
                    f"📨 [HL7] "
                    f"Получено отдельное сообщение "
                    f"({len(message_bytes)} байт)"
                )

                print(
                    "=" * 80
                )

                success = process_hl7_message(
                    raw_text,
                    device_info
                )

                if success:

                    print(
                        "✅ [HL7] "
                        "Сообщение успешно обработано."
                    )

                else:

                    print(
                        "⚠️ [HL7] "
                        "Сообщение обработано, "
                        "но результаты не были отправлены."
                    )

                # =================================================
                # Финальный ACK
                #
                # Отправляем ACK после обработки каждого
                # отдельного HL7 сообщения.
                # =================================================

                try:

                    client_socket.sendall(
                        b"\x06"
                    )

                    print(
                        f"📤 [{datetime.now():%H:%M:%S}] "
                        f"Финальный ACK (06) "
                        f"отправлен после обработки HL7"
                    )

                except Exception as e:

                    print(
                        f"⚠️ Ошибка финального ACK: {e}"
                    )

                print(
                    "=" * 80
                )

            # ====================================================
            # Если 0x1c пока нет, сообщение ещё не полное.
            # Ждём следующий TCP пакет.
            # ====================================================

            if b"\x1c" not in buffer:

                if b"OBX|" in buffer:

                    print(
                        "   ⏳ [HL7] "
                        "OBX найден, но полное сообщение "
                        "ещё не получено. Ждём продолжение."
                    )

                else:

                    print(
                        "   ⏳ [HL7] "
                        "Полное сообщение ещё не получено. "
                        "Ждём продолжение."
                    )

    except Exception as e:

        print(
            f"   ❌ [Ошибка сессии]: {e}"
        )

    finally:

        try:

            client_socket.close()

        except Exception:
            pass

        print(
            f"🔌 Сессия с "
            f"[{device_info['name']}] завершена.\n"
            + "=" * 50
        )
