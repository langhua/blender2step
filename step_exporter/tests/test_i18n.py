"""
Tests for step_exporter.core.i18n — verify translation completeness and format correctness.
Usage: blender --background --python ci_test_runner.py  (runs via CI)
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from step_exporter.core.i18n import _STRINGS


class TestI18nCompleteness:
    """Every English key must have a zh_CN translation."""

    def test_all_keys_have_zh_cn(self):
        missing = [k for k, v in _STRINGS.items() if "zh_CN" not in v]
        assert not missing, f"Keys missing zh_CN: {missing}"

    def test_no_empty_translations(self):
        empty = [k for k, v in _STRINGS.items() if v.get("zh_CN", "").strip() == ""]
        assert not empty, f"Keys with empty zh_CN: {empty}"

    def test_no_duplicate_keys(self):
        # Dict keys are unique by definition, but verify nothing weird
        assert len(_STRINGS) > 0

    def test_no_duplicate_zh_cn_values(self):
        """Duplicate zh_CN translations might indicate copy-paste errors."""
        seen = {}
        dupes = []
        for k, v in _STRINGS.items():
            zh = v.get("zh_CN", "")
            if zh in seen:
                dupes.append((k, seen[zh]))
            else:
                seen[zh] = k
        # Ignore: some short strings naturally overlap (e.g. "None", "mm")
        # Only flag longer strings
        long_dupes = [(k1, k2) for k1, k2 in dupes if len(_STRINGS[k1]["zh_CN"]) > 5]
        assert not long_dupes, f"Duplicate long zh_CN values: {long_dupes}"


class TestI18nFormatStrings:
    """Format placeholders like {name} must match between en and zh_CN."""

    def test_format_placeholders_match(self):
        fmt_re = re.compile(r'\{(\w+)\}')
        mismatched = []
        for key, trans in _STRINGS.items():
            en_placeholders = set(fmt_re.findall(key))
            zh_placeholders = set(fmt_re.findall(trans.get("zh_CN", "")))
            if en_placeholders != zh_placeholders:
                mismatched.append((key, en_placeholders, zh_placeholders))
        assert not mismatched, f"Format placeholder mismatch: {mismatched}"

    def test_no_unbalanced_braces(self):
        """Ensure { and } are balanced in all translations."""
        bad = []
        for key, trans in _STRINGS.items():
            zh = trans.get("zh_CN", "")
            if zh.count("{") != zh.count("}"):
                bad.append(key)
        assert not bad, f"Unbalanced braces in zh_CN: {bad}"


class TestI18nCoverage:
    """Sanity checks on the translation table itself."""

    def test_minimum_coverage(self):
        """We should have at least some baseline number of strings."""
        assert len(_STRINGS) >= 50, f"Only {len(_STRINGS)} strings, expected >= 50"

    def test_all_keys_are_strings(self):
        for k in _STRINGS:
            assert isinstance(k, str), f"Non-string key: {k!r}"
