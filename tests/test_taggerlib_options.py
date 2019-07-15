import tempfile
from unittest import TestCase, main

from metrontagger.taggerlib.options import make_parser


class TestOptions(TestCase):
    def setUp(self):
        self.parser = make_parser()
        self.path = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.path.cleanup()

    def test_creditial_options(self):
        parsed = self.parser.parse_args(
            [
                "--user",
                "test_user",
                "--password",
                "test_passwd",
                "--set-metron-user",
                self.path.name,
            ]
        )
        self.assertEqual(parsed.user, "test_user")
        self.assertEqual(parsed.password, "test_passwd")
        self.assertTrue(parsed.set_metron_user)
        self.assertEqual(parsed.path, [self.path.name])

    def test_online_option(self):
        parsed = self.parser.parse_args(["-o", self.path.name])
        self.assertTrue(parsed.online)
        self.assertEqual(parsed.path, [self.path.name])

    def test_id_option(self):
        parsed = self.parser.parse_args(["--id", "1", self.path.name])
        self.assertEqual(parsed.id, "1")
        self.assertEqual(parsed.path, [self.path.name])

    def test_delete_option(self):
        parsed = self.parser.parse_args(["-d", self.path.name])
        self.assertTrue(parsed.delete)
        self.assertEqual(parsed.path, [self.path.name])

    def test_missing_option(self):
        parsed = self.parser.parse_args(["--missing", self.path.name])
        self.assertTrue(parsed.missing)
        self.assertEqual(parsed.path, [self.path.name])

    def test_rename_option(self):
        parsed = self.parser.parse_args(["-r", self.path.name])
        self.assertTrue(parsed.rename)
        self.assertEqual(parsed.path, [self.path.name])

    def test_ignore_option(self):
        parsed = self.parser.parse_args(["--ignore-existing", self.path.name])
        self.assertTrue(parsed.ignore_existing)
        self.assertEqual(parsed.path, [self.path.name])


if __name__ == "__main__":
    main()
