from app.services.path_utils import safe_filename


def test_safe_filename_replaces_windows_illegal_characters():
    assert safe_filename('住建部<公告>:"/\\|?*.pdf') == "住建部_公告________.pdf"


def test_safe_filename_handles_reserved_windows_names():
    assert safe_filename("CON.txt") == "CON_.txt"


def test_safe_filename_limits_utf8_bytes():
    name = safe_filename("资质" * 200 + ".pdf", max_bytes=60)

    assert len(name.encode("utf-8")) <= 60
    assert name.endswith(".pdf")
