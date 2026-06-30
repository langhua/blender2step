"""
Tests for step_exporter.core.i18n — verify translation completeness and format correctness.
Usage: blender --background --python ci_test_runner.py  (runs via CI)
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from step_exporter.core.i18n import _STRINGS, _build_translations, _t


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


class TestBuildTranslations:
    """Test _build_translations() — the dict transformer for Blender's i18n API."""

    def test_returns_dict_with_language_keys(self):
        result = _build_translations()
        assert "zh_CN" in result
        assert "zh" in result
        assert isinstance(result["zh_CN"], dict)
        assert isinstance(result["zh"], dict)

    def test_every_key_has_translation(self):
        result = _build_translations()
        for en_str, loc in _STRINGS.items():
            expected_zh = loc.get("zh_CN", en_str)
            # Blender uses ('*', en_str) and ('Operator', en_str) as context keys
            assert result["zh_CN"][('*', en_str)] == expected_zh
            assert result["zh_CN"][('Operator', en_str)] == expected_zh

    def test_translation_count_matches(self):
        result = _build_translations()
        # Each string generates 2 entries (* and Operator contexts)
        expected_count = len(_STRINGS) * 2
        assert len(result["zh_CN"]) == expected_count

    def test_no_empty_context_keys(self):
        result = _build_translations()
        for ctx_key, val in result["zh_CN"].items():
            assert isinstance(ctx_key, tuple)
            assert len(ctx_key) == 2
            assert ctx_key[0] in ("*", "Operator")
            assert isinstance(ctx_key[1], str)
            assert len(val) > 0, f"Empty translation for {ctx_key}"


class TestTranslationLookup:
    """Test _t() — the core translation lookup function."""

    def test_en_returns_key_unchanged(self, monkeypatch):
        """English: _t('Hello') → 'Hello'"""
        monkeypatch.setattr("step_exporter.core.i18n._get_language", lambda: "en")
        assert _t("Hello") == "Hello"
        assert _t("STEP Exporter") == "STEP Exporter"

    def test_zh_returns_translation(self, monkeypatch):
        """Chinese: _t('STEP Exporter') → 'STEP 导出器'"""
        monkeypatch.setattr("step_exporter.core.i18n._get_language", lambda: "zh_CN")
        assert _t("STEP Exporter") == "STEP 导出器"

    def test_unknown_key_returns_key_itself(self, monkeypatch):
        """Unknown key falls back to the key string itself."""
        monkeypatch.setattr("step_exporter.core.i18n._get_language", lambda: "zh_CN")
        assert _t("NoSuchKey12345") == "NoSuchKey12345"

    def test_format_kwargs(self, monkeypatch):
        """Format placeholders like {version} are substituted."""
        monkeypatch.setattr("step_exporter.core.i18n._get_language", lambda: "zh_CN")
        # "✓ Module v{version} loaded" → "✓ 模块 v{version} 已加载"
        result = _t("✓ Module v{version} loaded", version="4.1.1")
        assert "4.1.1" in result
        assert result.startswith("✓")

    def test_missing_kwargs_does_not_crash(self, monkeypatch):
        """Missing format args should not raise exception (defensive)."""
        monkeypatch.setattr("step_exporter.core.i18n._get_language", lambda: "zh_CN")
        result = _t("Cylinder created: {name}")  # no name= provided
        assert isinstance(result, str)  # should not crash
