import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import deploy


class TestDeployScript(unittest.TestCase):
    def test_parse_args_defaults(self):
        args = deploy.parse_args([])
        self.assertIsNone(args.message)
        self.assertFalse(args.vps)
        self.assertEqual(args.host, deploy.HOST_DEFAULT)
        self.assertEqual(args.user, deploy.USER_DEFAULT)
        self.assertIsNone(args.key)
        self.assertFalse(args.skip_git)
        self.assertFalse(args.skip_remote)
        self.assertFalse(args.skip_db)
        self.assertFalse(args.db_only)

    def test_parse_args_custom(self):
        args = deploy.parse_args(["My commit message", "--vps", "--host", "192.168.1.1", "--skip-db"])
        self.assertEqual(args.message, "My commit message")
        self.assertTrue(args.vps)
        self.assertEqual(args.host, "192.168.1.1")
        self.assertTrue(args.skip_db)

    @patch("deploy.resolve_ssh_key")
    @patch("deploy.run_command")
    def test_deploy_vps_phase_enabled(self, mock_run, mock_resolve_key):
        mock_resolve_key.return_value = "/path/to/key"
        enabled = deploy.deploy_vps_phase(
            vps=True,
            skip_remote=False,
            user="ubuntu",
            host="1.2.3.4",
            key="/path/to/key",
        )
        self.assertTrue(enabled)
        mock_run.assert_called_once()
        ssh_args = mock_run.call_args[0][0]
        self.assertIn("ssh", ssh_args)
        self.assertIn("ubuntu@1.2.3.4", ssh_args)

    def test_deploy_vps_phase_disabled(self):
        enabled = deploy.deploy_vps_phase(
            vps=False,
            skip_remote=False,
            user="ubuntu",
            host="1.2.3.4",
            key=None,
        )
        self.assertFalse(enabled)

    @patch("deploy.deploy_vps_phase")
    @patch("deploy.deploy_git_phase")
    @patch("deploy.sync_database_phase")
    @patch("deploy.print_summary")
    def test_main_db_only(self, mock_summary, mock_sync, mock_git, mock_vps):
        deploy.main(["--db-only"])
        mock_sync.assert_called_once()
        mock_summary.assert_called_once_with(unittest.mock.ANY, db_only=True)
        mock_git.assert_not_called()
        mock_vps.assert_not_called()


if __name__ == "__main__":
    unittest.main()
