import json

import pytest


@pytest.mark.parametrize(
    ("success", "expected_outcome"),
    [(True, "успешно"), (False, "неудачно")],
)
def test_result_and_transfer_are_written_to_daily_log(
    monkeypatch,
    tmp_path,
    success,
    expected_outcome,
):
    monkeypatch.setenv("VETMANAGER_URL", "https://vetmanager.invalid")
    monkeypatch.setenv("API_KEY", "test-key")
    import vetmanager

    results = [{"name": "Лейкоциты", "value": "18.2"}]
    monkeypatch.setattr(vetmanager, "TRANSFER_LOG_DIR", tmp_path)
    monkeypatch.setattr(
        vetmanager,
        "_send_results_direct_to_medical_card",
        lambda *args: success,
    )

    assert vetmanager.send_results_direct_to_medical_card(
        "123",
        "Test Analyzer",
        "CBC",
        results,
    ) is success

    log_files = list(tmp_path.glob("vetmanager_*.log"))
    assert len(log_files) == 1

    entries = [
        json.loads(line)
        for line in log_files[0].read_text(encoding="utf-8").splitlines()
    ]
    assert [entry["event"] for entry in entries] == [
        "Получены результаты",
        "Результат передачи",
    ]
    assert entries[0]["results"] == results
    assert entries[1]["outcome"] == expected_outcome
