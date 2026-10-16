import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root and backend are on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_PATH = os.path.join(REPO_ROOT, "app", "backend")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

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

    @patch("deploy.adquirir_lock_deploy")
    @patch("deploy.audit_and_checks_phase")
    @patch("deploy.deploy_vps_phase")
    @patch("deploy.deploy_git_phase")
    @patch("deploy.sync_database_phase")
    @patch("deploy.print_summary")
    def test_main_db_only(self, mock_summary, mock_sync, mock_git, mock_vps, mock_audit, mock_lock):
        deploy.main(["--db-only"])
        mock_lock.assert_called_once()
        mock_audit.assert_called_once()
        mock_sync.assert_called_once()
        mock_summary.assert_called_once_with(unittest.mock.ANY, db_only=True)
        mock_git.assert_not_called()
        mock_vps.assert_not_called()

    @patch("scripts.sync_db_turso.sync_database")
    def test_sync_database_failure_aborts_deploy(self, mock_sync_db):
        """Comprova que falha na sincronização do Turso aborta o deploy com SystemExit(1)."""
        mock_sync_db.return_value = False
        with self.assertRaises(SystemExit) as cm:
            deploy.sync_database_phase(skip_db=False, root_dir=REPO_ROOT)
        self.assertEqual(cm.exception.code, 1)

    def test_turso_pipeline_body_error_raises_runtime_error(self):
        """Comprova que resposta HTTP 200 contendo erro SQL no corpo do JSON levanta RuntimeError."""
        import scripts.sync_db_turso as turso_mod
        fake_payload = {
            "baton": "xyz",
            "results": [
                {"type": "ok", "response": {}},
                {"type": "error", "error": {"message": "UNIQUE constraint failed: questions.id"}}
            ]
        }
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps(fake_payload).encode("utf-8")
        fake_resp.__enter__.return_value = fake_resp

        with patch("urllib.request.urlopen", return_value=fake_resp):
            with self.assertRaises(RuntimeError) as cm:
                turso_mod.execute_turso_pipeline("http://fake-turso", "token", [{"type": "execute"}, {"type": "execute"}])
            self.assertIn("UNIQUE constraint failed", str(cm.exception))

    def test_turso_pipeline_incomplete_results_raises_runtime_error(self):
        """Comprova que resposta do Turso com contagem menor que as operações enviadas levanta RuntimeError."""
        import scripts.sync_db_turso as turso_mod
        # Enviamos 2 statements, mas recebemos apenas 1 resultado
        fake_payload = {
            "baton": "xyz",
            "results": [{"type": "ok", "response": {}}]
        }
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps(fake_payload).encode("utf-8")
        fake_resp.__enter__.return_value = fake_resp

        with patch("urllib.request.urlopen", return_value=fake_resp):
            with self.assertRaises(RuntimeError) as cm:
                turso_mod.execute_turso_pipeline("http://fake-turso", "token", [{"type": "execute"}, {"type": "execute"}])
            self.assertIn("Resposta incompleta do Turso Pipeline", str(cm.exception))

    @patch("subprocess.run")
    def test_audit_phase_rejections(self, mock_subproc):
        """Testa que parecer fail, JSON inválido, SHA vazio e arquivo ausente abortam com SystemExit(1)."""
        import tempfile
        sha_teste = "d" * 40

        class FakeResult:
            def __init__(self, code, out):
                self.returncode = code
                self.stdout = out
                self.stderr = ""

        # Simula git status limpo e git rev-parse retornando SHA válido
        def fake_run(cmd, *args, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "status" in cmd_str:
                return FakeResult(0, "")
            elif "rev-parse HEAD" in cmd_str:
                return FakeResult(0, sha_teste)
            elif "pytest" in cmd_str or "unittest" in cmd_str:
                return FakeResult(0, "OK")
            return FakeResult(0, "")

        mock_subproc.side_effect = fake_run

        with tempfile.TemporaryDirectory() as tmp_dir:
            audit_dir = os.path.join(tmp_dir, "data", "auditorias_codex")
            os.makedirs(audit_dir, exist_ok=True)
            audit_path = os.path.join(audit_dir, f"audit_{sha_teste}.json")

            # 1. Parecer contendo verdict: fail
            with open(audit_path, "w", encoding="utf-8") as f:
                json.dump({"candidate_sha": sha_teste, "verdict": "fail", "summary": "Bad", "findings": [], "limitations": [], "required_followups": []}, f)
            with self.assertRaises(SystemExit) as cm:
                deploy.audit_and_checks_phase(skip_audit=False, root_dir=tmp_dir)
            self.assertEqual(cm.exception.code, 1)

            # 2. Parecer contendo JSON corrompido
            with open(audit_path, "w", encoding="utf-8") as f:
                f.write("INVALID JSON CONTENT {{{")
            with self.assertRaises(SystemExit) as cm2:
                deploy.audit_and_checks_phase(skip_audit=False, root_dir=tmp_dir)
            self.assertEqual(cm2.exception.code, 1)

            # 3. Parecer ausente (arquivo deletado)
            os.remove(audit_path)
            with self.assertRaises(SystemExit) as cm3:
                deploy.audit_and_checks_phase(skip_audit=False, root_dir=tmp_dir)
            self.assertEqual(cm3.exception.code, 1)

            # 4. Parecer aprovado limpo -> deve passar sem SystemExit e retornar o SHA
            with open(audit_path, "w", encoding="utf-8") as f:
                json.dump({"candidate_sha": sha_teste, "verdict": "pass", "summary": "Approved", "findings": [], "limitations": [], "required_followups": []}, f)
            ret_sha = deploy.audit_and_checks_phase(skip_audit=False, root_dir=tmp_dir)
            self.assertEqual(ret_sha, sha_teste)

    def test_turso_pipeline_empty_result_item_raises_runtime_error(self):
        """Comprova que resposta do Turso com objeto vazio em results [{}] levanta RuntimeError."""
        import scripts.sync_db_turso as turso_mod
        fake_payload = {
            "baton": "xyz",
            "results": [{}]  # Contagem 1, mas objeto vazio
        }
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps(fake_payload).encode("utf-8")
        fake_resp.__enter__.return_value = fake_resp

        with patch("urllib.request.urlopen", return_value=fake_resp):
            with self.assertRaises(RuntimeError) as cm:
                turso_mod.execute_turso_pipeline("http://fake-turso", "token", [{"type": "execute"}])
            self.assertIn("está vazio ou não é um objeto válido", str(cm.exception))

    @patch("subprocess.run")
    def test_deploy_git_phase_divergent_head_aborts(self, mock_subproc):
        """Comprova que se o HEAD mudar concorrentemente após a auditoria, o push é abortado fatalmente."""
        candidate_sha = "a" * 40
        outro_sha = "b" * 40

        class FakeResult:
            def __init__(self, code, out):
                self.returncode = code
                self.stdout = out
                self.stderr = ""

        def fake_run(cmd, *args, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "status" in cmd_str:
                return FakeResult(0, "")
            elif "--abbrev-ref" in cmd_str:
                return FakeResult(0, "main")
            elif "rev-parse HEAD" in cmd_str:
                return FakeResult(0, outro_sha)
            return FakeResult(0, "")

        mock_subproc.side_effect = fake_run

        with self.assertRaises(SystemExit) as cm:
            deploy.deploy_git_phase(skip_git=False, candidate_sha=candidate_sha)
        self.assertEqual(cm.exception.code, 1)

    @patch("subprocess.run")
    def test_deploy_git_phase_non_main_branch_aborts(self, mock_subproc):
        """Comprova que se a branch atual não for main, o deploy é abortado."""
        candidate_sha = "a" * 40

        class FakeResult:
            def __init__(self, code, out):
                self.returncode = code
                self.stdout = out
                self.stderr = ""

        def fake_run(cmd, *args, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "status" in cmd_str:
                return FakeResult(0, "")
            elif "--abbrev-ref" in cmd_str:
                return FakeResult(0, "feature/xyz")
            return FakeResult(0, "")

        mock_subproc.side_effect = fake_run

        with self.assertRaises(SystemExit) as cm:
            deploy.deploy_git_phase(skip_git=False, candidate_sha=candidate_sha)
        self.assertEqual(cm.exception.code, 1)

    def test_adquirir_lock_deploy_concurrency_blocks(self):
        """Comprova exclusão mútua física: segundo lock no mesmo arquivo aborta o deploy."""
        import tempfile
        import fcntl
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = os.path.join(tmp_dir, "data", ".deploy.lock")
            os.makedirs(os.path.dirname(lock_path), exist_ok=True)
            primeiro_lock = open(lock_path, "a+")
            fcntl.flock(primeiro_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            with self.assertRaises(SystemExit) as cm:
                deploy.adquirir_lock_deploy(tmp_dir)
            self.assertEqual(cm.exception.code, 1)

            primeiro_lock.close()

    def test_validator_rejects_line_range_number(self):
        """Comprova que line_range: 123 (int ao invés de string/null) é rejeitado pelo validador."""
        sha_teste = "e" * 40
        parecer = {
            "candidate_sha": sha_teste,
            "verdict": "pass",
            "summary": "OK",
            "findings": [
                {
                    "severity": "low",
                    "file": "main.py",
                    "line_range": 123,  # Inválido: int
                    "description": "Notice",
                    "failure_scenario": None
                }
            ],
            "limitations": [],
            "required_followups": []
        }
        valido, motivo = deploy.avaliar_parecer_auditoria(parecer, sha_esperado=sha_teste)
        self.assertFalse(valido)
        self.assertIn("campo 'line_range' deve ser string ou null", motivo)


if __name__ == "__main__":
    unittest.main()

