"""Guard against silent drift between the ``scan`` CLI options and ConfigLoader.

``ConfigLoader.merge_with_args`` only applies config-file / profile keys that are
listed in ``ConfigLoader.CONFIG_MAPPING`` and only overrides a CLI value when it
equals the Typer default recorded in ``ConfigLoader._TYPER_DEFAULTS``.  Both
tables are hand-maintained; every ``scan`` option added without updating them is
silently ignored in config files and profiles (this happened for ~20 keys,
including ``fail_on_severity`` and ``deduplicate`` used by built-in profiles).

These tests introspect the real Typer signature so the tables cannot drift again.
"""

from __future__ import annotations

import argparse
import inspect

import pytest

from core.cli import scan
from core.config_loader import ConfigLoader
from core.profiles import PROFILES, get_profile

# Options that intentionally have no config-file equivalent.
_NOT_CONFIGURABLE = {
    "path",  # required positional argument
    "path_opt",  # deprecated alias of the positional argument
    "config",  # the config file itself
    "profile",  # selects a profile; not a profile value
}


def _scan_option_defaults() -> dict[str, object]:
    """Return {option_name: typer_default} for every ``scan`` parameter."""
    defaults: dict[str, object] = {}
    for name, param in inspect.signature(scan).parameters.items():
        info = param.default
        # typer.Option(...) / typer.Argument(...) objects carry the value in .default
        defaults[name] = getattr(info, "default", info)
    return defaults


def _configurable_options() -> dict[str, object]:
    return {
        name: default
        for name, default in _scan_option_defaults().items()
        if name not in _NOT_CONFIGURABLE
    }


class TestConfigMappingSync:
    def test_every_scan_option_is_in_config_mapping(self):
        missing = sorted(
            set(_configurable_options()) - set(ConfigLoader.CONFIG_MAPPING.values())
        )
        assert not missing, (
            "scan options without a ConfigLoader.CONFIG_MAPPING entry "
            f"(config files / profiles silently ignore them): {missing}"
        )

    def test_every_scan_option_has_a_typer_default_shadow(self):
        # Without a recorded default, merge_with_args cannot tell "user passed
        # the default" from "user passed nothing", so config can never override.
        options = _configurable_options()
        missing = sorted(set(options) - set(ConfigLoader._TYPER_DEFAULTS))
        # openai_api_key is special-cased: the CLI resolves it from the
        # environment before merging, so a None default is deliberately absent.
        missing = [m for m in missing if m != "openai_api_key"]
        assert not missing, f"scan options without a _TYPER_DEFAULTS entry: {missing}"

    def test_typer_default_shadow_matches_real_defaults(self):
        options = _scan_option_defaults()
        mismatched = {
            name: (ConfigLoader._TYPER_DEFAULTS[name], options[name])
            for name in ConfigLoader._TYPER_DEFAULTS
            if name in options and ConfigLoader._TYPER_DEFAULTS[name] != options[name]
        }
        assert not mismatched, (
            "_TYPER_DEFAULTS disagrees with cli.scan defaults "
            f"(shadow, real): {mismatched}"
        )

    def test_config_mapping_has_no_unknown_targets(self):
        unknown = sorted(
            set(ConfigLoader.CONFIG_MAPPING.values()) - set(_scan_option_defaults())
        )
        assert not unknown, (
            f"CONFIG_MAPPING targets that are not scan options: {unknown}"
        )


class TestProfilesSync:
    @pytest.mark.parametrize("name", sorted(PROFILES))
    def test_profile_keys_are_mapped(self, name):
        unmapped = sorted(set(get_profile(name)) - set(ConfigLoader.CONFIG_MAPPING))
        assert not unmapped, f"profile '{name}' sets keys that are dropped: {unmapped}"

    @pytest.mark.parametrize("name", sorted(PROFILES))
    def test_profile_values_survive_merge_onto_default_args(self, name):
        """Applying a profile onto untouched CLI defaults must yield the profile."""
        args = argparse.Namespace(**{k: v for k, v in _scan_option_defaults().items()})
        # The CLI normalises ``exclude`` to a list before merging.
        args.exclude = list(args.exclude)
        merged = ConfigLoader.merge_with_args(get_profile(name), args)
        for key, expected in get_profile(name).items():
            assert getattr(merged, key) == expected, (
                f"profile '{name}': key '{key}' expected {expected!r}, "
                f"got {getattr(merged, key)!r}"
            )

    def test_ci_profile_sets_fail_on_severity(self):
        """Regression: profile 'ci' used to lose fail_on_severity entirely."""
        args = argparse.Namespace(regex=False, fail_on_severity=None, mode="balanced")
        merged = ConfigLoader.merge_with_args(get_profile("ci"), args)
        assert merged.fail_on_severity == "HIGH"
        assert merged.mode == "fast"

    def test_explicit_cli_value_beats_profile(self):
        args = argparse.Namespace(deduplicate=False, min_severity="LOW")
        merged = ConfigLoader.merge_with_args(get_profile("medical"), args)
        assert merged.deduplicate is True  # default -> profile applies
        assert merged.min_severity == "LOW"  # explicit -> profile does not override
