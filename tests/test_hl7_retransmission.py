import importlib


def test_ozelle_message_identity_tracks_replay_and_new_measurement(monkeypatch):
    monkeypatch.setenv("VETMANAGER_URL", "https://vetmanager.invalid")
    monkeypatch.setenv("API_KEY", "test-key")
    hl7 = importlib.import_module("hl7")
    source_ids = []

    def send_results(**kwargs):
        source_ids.append(kwargs["source_message_id"])
        return True

    monkeypatch.setattr(hl7, "send_results_direct_to_medical_card", send_results)
    device = {"name": "Ozelle Vet BHA-5000", "lab_code": "CBC"}

    def message(timestamp, message_id):
        return (
            "MSH|^~\\&|OZELLE|LAB|||"
            f"{timestamp}||ORU^R01|{message_id}|P|2.3\r"
            "PV1|||||123\r"
            "OBR|1|||BHA^CBC\r"
            "OBX|1|NM|WBC||18.2|10^9/L|4.0-15.0|H"
        )

    replay = message("20261012121100", "record-1")
    assert hl7.process_hl7_message(replay, device)
    assert hl7.process_hl7_message(replay, device)
    assert hl7.process_hl7_message(
        message("20261012121800", "record-2"),
        device,
    )

    assert source_ids[0] == source_ids[1]
    assert source_ids[2] != source_ids[0]


def test_ozelle_retransmission_is_skipped_but_new_measurement_is_appended(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("VETMANAGER_URL", "https://vetmanager.invalid")
    monkeypatch.setenv("API_KEY", "test-key")
    vetmanager = importlib.import_module("vetmanager")
    monkeypatch.setattr(vetmanager, "TRANSFER_LOG_DIR", tmp_path)

    description = ""
    put_count = 0

    class Response:
        status_code = 200

        def json(self):
            return {
                "data": {
                    "medicalCards": {
                        "patient_id": 1,
                        "doctor_id": 2,
                        "clinic_id": 3,
                        "description": description,
                    }
                }
            }

    def get(*args, **kwargs):
        return Response()

    def put(*args, json, **kwargs):
        nonlocal description, put_count
        description = json["description"]
        put_count += 1
        return Response()

    monkeypatch.setattr(vetmanager.requests, "get", get)
    monkeypatch.setattr(vetmanager.requests, "put", put)

    send = vetmanager.send_results_direct_to_medical_card
    kwargs = {
        "card_id": "123",
        "device_name": "Ozelle Vet BHA-5000",
        "lab_code": "CBC",
        "results_pack": [{"name": "WBC", "value": "18.2"}],
    }

    assert send(**kwargs, source_message_id="replayed-record")
    assert send(**kwargs, source_message_id="replayed-record")
    assert put_count == 1

    # Same patient, panel, and result are retained as a new measurement when
    # its HL7/device record identifier differs.
    assert send(**kwargs, source_message_id="new-measurement")
    assert put_count == 2
    assert description.count("LabService HL7 source:") == 2
