from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPolicyTests(unittest.TestCase):
    def test_primary_license_is_polyform_shield(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("PolyForm Shield License 1.0.0", text)
        self.assertIn("https://polyformproject.org/licenses/shield/1.0.0", text)
        self.assertIn("Required Notice:", text)
        self.assertIn("Licensor Line of Business:", text)
        self.assertNotIn("MIT License", text)

    def test_readme_describes_source_available_model(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("source-available", text)
        self.assertIn("PolyForm Shield License 1.0.0", text)
        self.assertIn("COMMERCIAL_LICENSE.md", text)
        self.assertIn("CONTRIBUTOR_LICENSE_AGREEMENT.md", text)
        self.assertNotIn("source is MIT licensed", text)

    def test_commercial_license_path_is_documented(self):
        text = (ROOT / "COMMERCIAL_LICENSE.md").read_text(encoding="utf-8")
        self.assertIn("separate commercial license", text.lower())
        self.assertIn("competing", text.lower())
        self.assertIn("OEM", text)
        self.assertIn("white-label", text)

    def test_contributor_agreement_preserves_relicensing_rights(self):
        text = (ROOT / "CONTRIBUTOR_LICENSE_AGREEMENT.md").read_text(encoding="utf-8")
        self.assertIn("You retain ownership", text)
        self.assertIn("relicense your Contribution", text)
        self.assertIn("proprietary", text)
        self.assertIn("commercial", text)

    def test_pull_request_template_requires_cla_confirmation(self):
        text = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        self.assertIn("- [ ]", text)
        self.assertIn("CONTRIBUTOR_LICENSE_AGREEMENT.md", text)
        self.assertIn("cannot be merged until this box is checked", text)


if __name__ == "__main__":
    unittest.main()
