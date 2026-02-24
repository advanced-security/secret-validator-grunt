from secret_validator_grunt.utils.parsing import (
    extract_json,
    extract_section,
    extract_table_from_section,
    normalize_heading,
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


# ---------------------------------------------------------------------------
# normalize_heading — numeric prefix stripping
# ---------------------------------------------------------------------------


class TestNormalizeHeading:
	"""Test heading normalization with numeric prefixes."""

	def test_plain_heading(self):
		"""Plain heading normalizes to lowercase words."""
		assert normalize_heading("Verification Testing") == (
		    "verification testing")

	def test_numbered_heading(self):
		"""Numbered heading strips the prefix."""
		assert normalize_heading("4. Verification Testing") == (
		    "verification testing")

	def test_numbered_equals_plain(self):
		"""Numbered and plain versions normalize identically."""
		assert (normalize_heading("2. Locations") == normalize_heading(
		    "Locations"))

	def test_no_space_after_dot(self):
		"""Prefix like '3.Context' is still stripped."""
		assert normalize_heading("3.Context and Intent") == (
		    "context and intent")

	def test_multi_digit_prefix(self):
		"""Multi-digit prefix like '10. ' is stripped."""
		assert normalize_heading("10. Appendix") == "appendix"

	def test_no_prefix(self):
		"""Heading without numeric prefix is unchanged."""
		assert normalize_heading("Executive Summary") == ("executive summary")

	def test_only_number_dot(self):
		"""Heading that is just a number-dot normalizes to empty."""
		assert normalize_heading("7. ") == ""

	def test_non_numeric_dot(self):
		"""Heading like 'A. Something' is not stripped."""
		result = normalize_heading("A. Something")
		assert result == "a something"

	def test_all_numbered_sections_match_template(self):
		"""All numbered template headings match their plain
		counterparts used as extract_section targets."""
		pairs = [
		    ("1. Secret Alert Details", "Secret Alert Details"),
		    ("2. Locations", "Locations"),
		    ("3. Context and Intent", "Context and Intent"),
		    ("4. Verification Testing", "Verification Testing"),
		    ("5. Documentary Evidence", "Documentary Evidence"),
		    ("6. Evidence Analysis", "Evidence Analysis"),
		    ("7. Confidence Scoring", "Confidence Scoring"),
		    ("8. Risk Assessment", "Risk Assessment"),
		    ("9. Verdict", "Verdict"),
		]
		for numbered, plain in pairs:
			assert normalize_heading(numbered) == (normalize_heading(plain)), (
			    f"{numbered!r} != {plain!r}")


# ---------------------------------------------------------------------------
# extract_section — numbered heading support
# ---------------------------------------------------------------------------


class TestExtractSection:
	"""Test section extraction with numbered headings."""

	def test_unnumbered_heading(self):
		"""Extract section with plain heading."""
		md = "## Locations\n\nSome content\n"
		assert extract_section(md, "Locations") == ("Some content")

	def test_numbered_heading(self):
		"""Extract section with numbered heading."""
		md = "## 2. Locations\n\nSome content\n"
		assert extract_section(md, "Locations") == ("Some content")

	def test_table_from_numbered_section(self):
		"""Extract table from numbered section heading."""
		md = ("## 8. Risk Assessment\n\n"
		      "| Risk Factor | Assessment |\n"
		      "| ----------- | ---------- |\n"
		      "| Exploit     | High       |\n")
		table = extract_table_from_section(md, "Risk Assessment")
		assert table is not None
		assert len(table) == 1
		assert table[0]["Risk Factor"] == "Exploit"

	def test_missing_section_returns_none(self):
		"""Missing section returns None."""
		md = "## Executive Summary\n\nStuff\n"
		assert extract_section(md, "Locations") is None
