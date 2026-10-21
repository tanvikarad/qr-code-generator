import logging
from pathlib import Path
from unittest.mock import patch

import main


def test_setup_logging_configures_stdout():
    with patch("main.logging.basicConfig") as basic_config:
        main.setup_logging()

    basic_config.assert_called_once()
    handlers = basic_config.call_args.kwargs["handlers"]
    assert len(handlers) == 1
    assert handlers[0].stream is main.sys.stdout


def test_create_directory_creates_nested_path(tmp_path):
    path = tmp_path / "nested" / "qr_codes"

    main.create_directory(path)

    assert path.is_dir()


def test_create_directory_logs_and_exits_on_os_error(tmp_path, caplog):
    path = tmp_path / "not-a-directory"
    path.write_text("file")

    with caplog.at_level(logging.ERROR), patch.object(
        Path, "mkdir", side_effect=OSError("permission denied")
    ):
        try:
            main.create_directory(path / "qr_codes")
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError("create_directory should exit on an OS error")

    assert "Failed to create directory" in caplog.text


def test_is_valid_url_accepts_valid_url():
    with patch("main.validators.url", return_value=True):
        assert main.is_valid_url("https://example.com") is True


def test_is_valid_url_logs_invalid_url(caplog):
    with patch("main.validators.url", return_value=False), caplog.at_level(
        logging.ERROR
    ):
        assert main.is_valid_url("not a url") is False

    assert "Invalid URL provided: not a url" in caplog.text


def test_generate_qr_code_writes_png(tmp_path):
    output_path = tmp_path / "qr.png"

    assert main.generate_qr_code("https://example.com", output_path) is True
    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_generate_qr_code_skips_invalid_url(tmp_path):
    output_path = tmp_path / "qr.png"

    with patch("main.validators.url", return_value=False):
        assert main.generate_qr_code("not a url", output_path) is False

    assert not output_path.exists()


def test_generate_qr_code_logs_save_error(tmp_path, caplog):
    output_path = tmp_path / "missing" / "qr.png"

    with caplog.at_level(logging.ERROR):
        assert main.generate_qr_code("https://example.com", output_path) is False

    assert "An error occurred while generating or saving the QR code" in caplog.text


def test_generate_qr_code_handles_data_overflow(tmp_path, caplog):
    with patch("main.qrcode.QRCode.make", side_effect=main.DataOverflowError):
        with caplog.at_level(logging.ERROR):
            assert main.generate_qr_code(
                "https://example.com", tmp_path / "qr.png"
            ) is False

    assert "An error occurred while generating or saving the QR code" in caplog.text


def test_main_returns_success_and_uses_configured_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "QR_DIRECTORY", "custom_qr_codes")
    monkeypatch.setattr(main.sys, "argv", ["main.py", "--url", "https://example.com"])

    assert main.main() == 0
    output_files = list((tmp_path / "custom_qr_codes").glob("QRCode_*.png"))
    assert len(output_files) == 1
    assert output_files[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_main_returns_failure_for_invalid_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main.sys, "argv", ["main.py", "--url", "not a url"])

    assert main.main() == 1
    assert not list((tmp_path / main.QR_DIRECTORY).glob("QRCode_*.png"))
