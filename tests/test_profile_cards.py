"""Offline regression checks for repository-owned profile SVGs."""
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

os.environ.setdefault("PROFILE_OWNER", "example")
os.environ.setdefault("GH_TOKEN", "offline-test")
from scripts import profile_cards as cards

LIGHT = ("#ffffff", "#24292f", "#57606a", "#d0d7de", "#0969da")
DARK = ("#0d1117", "#e6edf3", "#8b949e", "#30363d", "#58a6ff")
NS = {"s": "http://www.w3.org/2000/svg"}


class ProfileCardsTests(unittest.TestCase):
    def test_pagination_excludes_private(self):
        batch = [{"private": False, "id": i} for i in range(99)] + [{"private": True}]
        with patch.object(cards, "get", side_effect=[batch, [{"private": False, "id": 100}]]) as api:
            result = cards.repos()
        self.assertEqual(len(result), 100)
        self.assertEqual(api.call_count, 2)
        self.assertTrue(api.call_args_list[1].args[0].endswith("page=2"))

    def test_card_is_valid_accessible_svg_in_both_themes(self):
        for theme in (LIGHT, DARK):
            with self.subTest(theme=theme):
                root = ElementTree.fromstring(cards.stats_card({"followers": 7}, [
                    {"stargazers_count": 2, "forks_count": 1}
                ], theme))
                self.assertEqual(root.attrib["viewBox"], "0 0 420 204")
                self.assertEqual(root.attrib["role"], "img")
                self.assertEqual(root.find("s:title", NS).text, "GitHub Stats")
                self.assertEqual(root.find("s:rect", NS).attrib["fill"], theme[0])
                self.assertIn("7", "".join(root.itertext()))

    def test_language_percentages_other_and_escaping(self):
        values = Counter({"A&B": 50, "Python": 20, "C": 10, "Java": 8, "Shell": 7, "CSS": 3, "HTML": 2})
        root = ElementTree.fromstring(cards.languages_card(values, LIGHT))
        labels = " ".join(root.itertext())
        self.assertIn("A&B 50.0%", labels)
        self.assertIn("Other 5.0%", labels)
        self.assertNotIn("CSS 3.0%", labels)
        widths = [float(r.attrib["width"]) for r in root.findall(".//s:rect", NS) if r.attrib.get("y") == "45"]
        self.assertAlmostEqual(sum(widths), 380, places=2)

    def test_empty_languages(self):
        root = ElementTree.fromstring(cards.languages_card(Counter(), DARK))
        self.assertIn("No language data available", "".join(root.itertext()))

    def test_generation_excludes_fork_languages_and_preserves_assets_on_api_failure(self):
        repositories = [
            {"full_name": "example/project", "private": False, "fork": False, "stargazers_count": 2, "forks_count": 0},
            {"full_name": "example/fork", "private": False, "fork": True, "stargazers_count": 0, "forks_count": 0},
        ]
        def api(path):
            if "/repos?" in path:
                return repositories
            if path.endswith("/languages"):
                self.assertEqual(path, "/repos/example/project/languages")
                return {"Python": 100}
            return {"followers": 7}
        with tempfile.TemporaryDirectory() as tmp:
            original = Path.cwd()
            try:
                os.chdir(tmp)
                with patch.object(cards, "get", side_effect=api):
                    cards.main()
                assets = Path("assets")
                before = {p.name: p.read_bytes() for p in assets.glob("*.svg")}
                self.assertEqual(len(before), 4)
                self.assertIn(b"Python 100.0%", before["top-languages-light.svg"])
                with patch.object(cards, "get", side_effect=OSError("API unavailable")):
                    with self.assertRaises(OSError):
                        cards.main()
                self.assertEqual(before, {p.name: p.read_bytes() for p in assets.glob("*.svg")})
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
