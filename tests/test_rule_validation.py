import unittest
import tempfile
from pathlib import Path
import sys

# Import validate_file from caelestia repo validator script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "caelestia" / "hypr" / "scripts"))
try:
    from validate_rules import validate_file
except ImportError:
    validate_file = None


class TestRuleValidation(unittest.TestCase):
    def setUp(self):
        if validate_file is None:
            self.skipTest("validate_rules module not available")

    def test_valid_rules_conf(self):
        rules_conf = Path(__file__).resolve().parent.parent.parent / "caelestia" / "hypr" / "hyprland" / "rules.conf"
        self.assertTrue(rules_conf.exists(), f"{rules_conf} does not exist")
        errors = validate_file(rules_conf)
        self.assertEqual(errors, [], f"Expected no validation errors in rules.conf, got: {errors}")

    def test_detect_legacy_match_prefix(self):
        content = "windowrule = float true, match:class yad\n"
        with tempfile.NamedTemporaryFile("w+", suffix=".conf", delete=False) as tf:
            tf.write(content)
            tf.flush()
            errors = validate_file(Path(tf.name))
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("Legacy/invalid match prefix used" in e for e in errors))

    def test_detect_boolean_float(self):
        content = "windowrulev2 = float true, class:^(yad)$\n"
        with tempfile.NamedTemporaryFile("w+", suffix=".conf", delete=False) as tf:
            tf.write(content)
            tf.flush()
            errors = validate_file(Path(tf.name))
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("'float' should not have boolean parameters" in e for e in errors))

    def test_detect_deprecated_keywords(self):
        content = (
            "windowrulev2 = no_blur, class:^(foo)$\n"
            "layerrule = blur true, launcher\n"
        )
        with tempfile.NamedTemporaryFile("w+", suffix=".conf", delete=False) as tf:
            tf.write(content)
            tf.flush()
            errors = validate_file(Path(tf.name))
            self.assertEqual(len(errors), 2)

    def test_valid_user_override(self):
        content = (
            "# Custom user override\n"
            "windowrulev2 = float, class:^(my-app)$\n"
            "windowrulev2 = center, class:^(my-app)$\n"
            "windowrulev2 = size 800 600, class:^(my-app)$\n"
        )
        with tempfile.NamedTemporaryFile("w+", suffix=".conf", delete=False) as tf:
            tf.write(content)
            tf.flush()
            errors = validate_file(Path(tf.name))
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
