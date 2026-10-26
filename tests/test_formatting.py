import importlib

import pytest

from formatting import colorize, get_status, parse_range


@pytest.mark.parametrize(
    ("value", "reference", "expected"),
    [
        ("15.1", "4.0-15.0", "high"),
        ("3.9", "4.0-15.0", "low"),
        ("10.0", "4.0-15.0", None),
    ],
)
def test_get_status_numeric_values(value, reference, expected):
    assert get_status(value, reference, "") == expected


@pytest.mark.parametrize("value", ["4.0", "15.0"])
def test_get_status_boundaries_are_in_range(value):
    assert get_status(value, "4.0-15.0", "") is None


def test_parse_range_accepts_spaces_en_dash_and_comma_decimals():
    assert parse_range(" 4,0 – 15,0 ") == (4.0, 15.0)


@pytest.mark.parametrize(
    ("value", "reference", "flag", "expected"),
    [
        ("3", "4-15", "H", "high"),
        ("3", "4-15", "HH", "high"),
        ("16", "4-15", "L", "low"),
        ("16", "4-15", "LL", "low"),
        ("10", "4-15", "N", "normal"),
        ("10", "4-15", "normal", "normal"),
    ],
)
def test_device_flag_takes_priority(value, reference, flag, expected):
    assert get_status(value, reference, flag) == expected


def test_get_status_uses_numeric_comparison_with_comma_decimal():
    assert get_status("15,1", "4,0-15,0", "") == "high"


@pytest.mark.parametrize(
    ("value", "reference", "expected"),
    [
        ("9.5 10^9/L", "4.0-10.2 10^9/L", None),
        ("10,3 10^9/L", "4,0-10,2 10^9/L", "high"),
        ("3.9 10^9/L", "4.0-10.2", "low"),
        ("9.5", "4.0-10.2 10^9/L", None),
    ],
)
def test_status_parses_numeric_values_with_units(value, reference, expected):
    assert get_status(value, reference, "") == expected


def test_qualitative_value_without_flag_has_no_status():
    assert get_status("Positive", "4-15", "") is None


@pytest.mark.parametrize("reference", ["unknown", ">38 = Negative", ""])
def test_garbled_or_unrecognized_range_has_no_status(reference):
    assert parse_range(reference) == (None, None)
    assert get_status("100", reference, "") is None


def test_colorize_wraps_only_high_or_low_value():
    assert colorize("18.2", "high") == (
        '<span style="color:#d32f2f;font-weight:bold">'
        "18.2</span>"
    )
    assert colorize("3.1", "low") == (
        '<span style="color:#1976d2;font-weight:bold">'
        "3.1</span>"
    )
    assert colorize("12", None) == "12"


@pytest.fixture
def hl7_module(monkeypatch):
    monkeypatch.setenv("VETMANAGER_URL", "https://vetmanager.invalid")
    monkeypatch.setenv("API_KEY", "test-key")
    return importlib.import_module("hl7")


def test_hl7_result_fields_are_passed_to_stubbed_sender(
    hl7_module,
    monkeypatch
):
    sent = {}

    def stub_send_results_direct_to_medical_card(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(
        hl7_module,
        "send_results_direct_to_medical_card",
        stub_send_results_direct_to_medical_card
    )

    message = (
        "PV1|||||123\r"
        "OBX|1|NM|WBC||18.2|10^9/L|4.0-15.0|H"
    )
    assert hl7_module.process_hl7_message(
        message,
        {"name": "Test Analyzer", "lab_code": "CBC"}
    )

    assert sent["results_pack"] == [
        {
            "name": "Лейкоциты (WBC)",
            "value": "18.2",
            "unit": "10^9/L",
            "reference": "4.0-15.0",
            "flag": "H",
        }
    ]


@pytest.mark.parametrize(
    ("observation", "sub_id", "expected_name"),
    [
        ("WBC^White blood cells^LN", "", "Лейкоциты (WBC)"),
        ("NEW_CODE^English test name^L", "", "English test name"),
        ("NEW_CODE^^L", "Legacy test name", "Legacy test name"),
        ("NEW_CODE^^L", "", "NEW_CODE"),
    ],
)
def test_hl7_result_name_uses_translation_then_reported_name(
    hl7_module,
    observation,
    sub_id,
    expected_name,
):
    result = hl7_module.extract_hl7_results(
        [f"OBX|1|NM|{observation}|{sub_id}|18.2|10^9/L|4.0-15.0|H"]
    )

    assert result[0]["name"] == expected_name


def test_biochemistry_codes_keep_russian_names_and_flags(hl7_module):
    result = hl7_module.extract_hl7_results([
        "OBX|1|NM|GGT||<=5|U/L|<=10|L",
        "OBX|2|NM|GLU||157|mg/dL|81-155|H",
        "OBX|3|NM|Na+||130|mmol/L|140-164|L",
    ])

    assert result[0]["name"] == "Гамма-глутамилтранспептидаза / GGT (GGT)"
    assert result[0]["flag"] == "L"
    assert result[1]["name"] == "Глюкоза (GLU)"
    assert result[1]["flag"] == "H"
    assert result[2]["name"] == "Натрий / Na+ (Na+)"
    assert result[2]["flag"] == "L"


def test_noahcali_unframed_hl7_is_processed_and_sent(
    hl7_module,
    monkeypatch,
):
    import device_handlers
    from config import DEVICES_CONFIG

    message = (
        "MSH|^~\\&|locmedt|Noahcali_100|||20261026102615||ORU^R01||P|2.3.1\r\n"
        "PID||123|1||Sample||456|M\r\n"
        "OBR||||NC0000000001|||20261024095024\r\n"
        "OBX||ST|ALB|ALB|3.6|g/dL|2.2-4.4| |||F|||||||\r\n"
        "OBX||ST|TP|TP|8.9|g/dL|5.3-8.6|H|||F|||||||\r\n"
        "OBX||ST|GGT|GGT|<=5|U/L|<=10| |||F|||||||\r\n"
    )
    sent = {}

    def stub_send_results_direct_to_medical_card(**kwargs):
        sent.update(kwargs)
        return True

    class UnframedHL7Socket:
        def __init__(self):
            self.chunks = [message.encode("utf-8"), b""]

        def recv(self, _):
            return self.chunks.pop(0)

        def sendall(self, _):
            pass

        def close(self):
            pass

    monkeypatch.setattr(
        hl7_module,
        "send_results_direct_to_medical_card",
        stub_send_results_direct_to_medical_card,
    )

    device_handlers.handle_device_data(
        UnframedHL7Socket(),
        DEVICES_CONFIG[5006],
    )

    assert sent["card_id"] == "123"
    assert sent["device_name"] == "Lockmedt Biochemistry Analyzer"
    assert sent["lab_code"] == "Биохимический анализ крови"
    assert sent["results_pack"] == [
        {
            "name": "Альбумин (ALB)",
            "value": "3.6",
            "unit": "g/dL",
            "reference": "2.2-4.4",
            "flag": "",
        },
        {
            "name": "Общий белок (TP)",
            "value": "8.9",
            "unit": "g/dL",
            "reference": "5.3-8.6",
            "flag": "H",
        },
        {
            "name": "Гамма-глутамилтранспептидаза / GGT (GGT)",
            "value": "<=5",
            "unit": "U/L",
            "reference": "<=10",
            "flag": "",
        },
    ]


@pytest.mark.parametrize(
    ("device_name", "reported_name", "expected_name"),
    [
        (
            device_name,
            reported_name,
            expected_name,
        )
        for device_name in ("Ozelle EHVT-75", "Ozelle Vet BHA-5000")
        for reported_name, expected_name in (
            ("Complete Blood Count", "Общий анализ крови"),
            ("Fecal Occult Blood Test", "Анализ кала на скрытую кровь"),
            ("Some new analysis", "Some new analysis"),
        )
    ] + [
        (device_name, "", "МФВА")
        for device_name in ("Ozelle EHVT-75", "Ozelle Vet BHA-5000")
    ],
)
def test_ozelle_analysis_title_uses_reported_name_and_fallback(
    hl7_module,
    monkeypatch,
    device_name,
    reported_name,
    expected_name,
):
    sent = {}

    def stub_send_results_direct_to_medical_card(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(
        hl7_module,
        "send_results_direct_to_medical_card",
        stub_send_results_direct_to_medical_card
    )

    obr_name = (
        "OBR|1|||"
        if not reported_name
        else f"OBR|1|||BHA^{reported_name}"
    )
    message = (
        f"PV1|||||123\r"
        f"{obr_name}\r"
        "OBX|1|NM|WBC||18.2|10^9/L|4.0-15.0|H"
    )
    assert hl7_module.process_hl7_message(
        message,
        {"name": device_name, "lab_code": "МФВА"}
    )

    assert sent["lab_code"] == expected_name


@pytest.mark.parametrize(
    ("value", "reference", "flag", "expected"),
    [
        (
            "18.2",
            "4.0-15.0",
            "",
            '<span style="color:#d32f2f;font-weight:bold">'
            "18.2</span>"
        ),
        (
            "3.1",
            "5.5-8.5",
            "",
            '<span style="color:#1976d2;font-weight:bold">'
            "3.1</span>"
        ),
        (
            "10,3 10^9/L",
            "4,0-10,2 10^9/L",
            "",
            '<span style="color:#d32f2f;font-weight:bold">'
            "10,3 10^9/L</span>"
        ),
        ("12", "8-15", "", "12"),
    ],
)
def test_result_value_formatting_always_uses_html(
    value,
    reference,
    flag,
    expected,
    monkeypatch
):
    monkeypatch.setenv("VETMANAGER_URL", "https://vetmanager.invalid")
    monkeypatch.setenv("API_KEY", "test-key")
    import vetmanager

    from formatting import get_status

    status = get_status(value, reference, flag)
    actual = vetmanager._format_result_value(value, status)
    assert actual == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("high", '<tr style="color:#d32f2f;font-weight:bold">'),
        ("low", '<tr style="color:#1976d2;font-weight:bold">'),
        ("normal", '<tr style="color:#000000;font-weight:bold">'),
        (None, "<tr>"),
    ],
)
def test_result_row_uses_status_color(status, expected, monkeypatch):
    monkeypatch.setenv("VETMANAGER_URL", "https://vetmanager.invalid")
    monkeypatch.setenv("API_KEY", "test-key")
    import vetmanager

    assert vetmanager._format_result_row_start(status) == expected
