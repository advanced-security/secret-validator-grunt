from secret_validator_grunt.loaders.templates import load_report_template
from pathlib import Path


def test_load_report_template(tmp_path):
	p = tmp_path / "t.md"
	p.write_text("hello", encoding="utf-8")
	assert load_report_template(p) == "hello"
