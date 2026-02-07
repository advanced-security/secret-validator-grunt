from secret_validator_grunt.utils.parsing import (
    extract_json,
    strip_code_fences,
)


def test_strip_code_fences():
	text = """```json
{"a":1}
```"""
	assert strip_code_fences(text) == '{"a":1}'


def test_extract_json():
	text = """Here:
```json
{"a":1}
```"""
	assert extract_json(text) == {"a": 1}
