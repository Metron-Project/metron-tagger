import tempfile
from unittest import TestCase, main

from metrontagger.taggerlib.settings import MetronTaggerSettings


class TestSettings(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_settings(self):
        user = "test"
        dummy = "dummy_value"
        # Save a test config file
        config = MetronTaggerSettings(config_dir=self.tmp_dir.name)
        config.metron_user = user
        config.metron_pass = dummy
        config.save()

        # Now load that file and verify the contents
        new_config = MetronTaggerSettings(config_dir=self.tmp_dir.name)
        self.assertEqual(new_config.metron_user, user)
        self.assertEqual(new_config.metron_pass, dummy)


if __name__ == "__main__":
    main()
