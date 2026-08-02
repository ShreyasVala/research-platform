from unittest.mock import Mock

from tools import storage


def test_safe_filename_rejects_paths():
    assert storage.safe_filename("paper.pdf") == "paper.pdf"
    assert storage.safe_filename("../paper.pdf") is None
    assert storage.safe_filename("folder/paper.pdf") is None


def test_local_upload_round_trip_and_listing(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(storage.settings, "uploads_dir", str(tmp_path))

    saved = storage.save_upload_bytes("notes.txt", b"research notes")
    content, error = storage.read_upload_bytes("notes.txt")
    files = storage.list_uploads()

    assert saved["storage"] == "local"
    assert content == b"research notes"
    assert error is None
    assert files[0]["name"] == "notes.txt"


def test_local_report_is_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(storage.settings, "reports_dir", str(tmp_path))

    location = storage.save_report_text("job123", "Test query", "Final report")

    report = tmp_path / "report_job123.txt"
    assert location == str(report.resolve())
    assert report.read_text(encoding="utf-8") == "Query: Test query\n\nFinal report"


def test_s3_upload_read_list_and_report(monkeypatch):
    client = Mock()
    client.get_object.return_value = {"Body": Mock(read=Mock(return_value=b"cloud file"))}
    client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "research-platform/uploads/cloud.txt",
                "Size": 1024,
            }
        ]
    }

    monkeypatch.setattr(storage.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage.settings, "s3_bucket", "test-bucket")
    monkeypatch.setattr(storage.settings, "s3_prefix", "research-platform")
    monkeypatch.setattr(storage, "_s3_client", lambda: client)

    saved = storage.save_upload_bytes("cloud.txt", b"cloud file")
    content, error = storage.read_upload_bytes("cloud.txt")
    files = storage.list_uploads()
    report_location = storage.save_report_text("job123", "Query", "Report")

    assert saved["location"] == "s3://test-bucket/research-platform/uploads/cloud.txt"
    assert content == b"cloud file"
    assert error is None
    assert files == [{"name": "cloud.txt", "size_kb": 1.0, "type": ".txt"}]
    assert report_location == "s3://test-bucket/research-platform/reports/report_job123.txt"
    assert client.put_object.call_count == 2
