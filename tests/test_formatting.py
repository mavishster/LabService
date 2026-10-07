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

    actual = vetmanager._format_result_value(value, reference, flag)
    assert actual == expected
