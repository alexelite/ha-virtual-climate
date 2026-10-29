import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / 'dev/deploy.py'
spec = importlib.util.spec_from_file_location('deploy', HELPER)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / 'custom_components/virtual_climate'
        self.target.mkdir(parents=True)
        (self.target / 'manifest.json').write_text(json.dumps({'domain': 'virtual_climate', 'version': '0.1.0'}))
        (self.target / '__init__.py').write_text('VERSION = "old"\n')
        (self.root / '.storage').mkdir()
        self.storage = self.root / '.storage/core.config_entries'
        self.storage.write_text(json.dumps({'data': {'entries': [
            {'domain': 'virtual_climate', 'entry_id': 'entry', 'options': {'sensor_floor': 'old'}},
            {'domain': 'unrelated', 'data': {'password': 'must-not-be-exported'}},
        ]}}))
        self.storage_before = self.storage.read_bytes()
        self.transaction = deploy.Deployment(self.root, 'test-run')

    def stage(self):
        self.transaction.prepare()
        deploy.copy_component(self.target, self.transaction.stage)
        (self.transaction.stage / 'manifest.json').write_text(json.dumps({'domain': 'virtual_climate', 'version': '0.1.1b1'}))
        (self.transaction.stage / '__init__.py').write_text('VERSION = "new"\n')
        deploy.write_json(self.transaction.folder / 'payload.json', deploy.payload_manifest(self.transaction.stage))

    def verify(self):
        with patch.object(self.transaction, 'verify_runtime_imports'):
            self.transaction.verify_stage()

    def test_snapshot_is_scoped_and_never_writes_storage(self):
        self.transaction.prepare()
        snapshot = json.loads((self.transaction.folder / 'config-entries.json').read_text())
        self.assertEqual(len(snapshot['entries']), 1)
        self.assertNotIn('must-not-be-exported', json.dumps(snapshot))
        self.assertEqual(self.storage.read_bytes(), self.storage_before)
        self.assertEqual((self.transaction.folder.stat().st_mode & 0o777), 0o700)

    def test_hash_mismatch_leaves_live_code_intact(self):
        self.stage()
        (self.transaction.stage / '__init__.py').write_text('tampered = True\n')
        with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
            self.transaction.verify_stage()
        self.assertIn('old', (self.target / '__init__.py').read_text())

    def test_stage_syntax_error_blocks_activation(self):
        self.stage()
        (self.transaction.stage / '__init__.py').write_text('def invalid(\n')
        deploy.write_json(self.transaction.folder / 'payload.json', deploy.payload_manifest(self.transaction.stage))
        with self.assertRaises(SyntaxError):
            self.transaction.verify_stage()
        self.assertIn('old', (self.target / '__init__.py').read_text())

    def test_unverified_stage_cannot_be_activated(self):
        self.stage()
        with self.assertRaisesRegex(RuntimeError, 'Stage must pass'):
            self.transaction.activate()

    def test_live_code_changed_during_staging_is_preserved(self):
        self.stage()
        self.verify()
        (self.target / '__init__.py').write_text('updated_elsewhere = True\n')
        with self.assertRaisesRegex(RuntimeError, 'Installed code changed'):
            self.transaction.activate()
        self.assertIn('updated_elsewhere', (self.target / '__init__.py').read_text())

    def test_failed_config_check_restores_original_without_restart(self):
        self.stage()
        self.verify()
        with patch.object(self.transaction, 'check_config', side_effect=RuntimeError('invalid')), patch.object(self.transaction, 'restart_and_wait') as restart:
            with self.assertRaisesRegex(RuntimeError, 'invalid'):
                self.transaction.activate()
            restart.assert_not_called()
        self.assertIn('old', (self.target / '__init__.py').read_text())
        self.assertEqual(self.transaction.state()['status'], 'rolled_back')
        self.assertEqual(self.storage.read_bytes(), self.storage_before)
        self.assertFalse(self.transaction.lock.exists())

    def test_failed_restart_restores_and_restarts_previous_code(self):
        self.stage()
        self.verify()
        with patch.object(self.transaction, 'check_config'), patch.object(self.transaction, 'restart_and_wait', side_effect=[RuntimeError('not ready'), None]) as restart:
            with self.assertRaisesRegex(RuntimeError, 'not ready'):
                self.transaction.activate()
            self.assertEqual(restart.call_count, 2)
        self.assertIn('old', (self.target / '__init__.py').read_text())

    def test_no_restart_install_keeps_backup_and_reports_pending(self):
        self.stage()
        self.verify()
        with patch.object(self.transaction, 'check_config'), patch.object(self.transaction, 'restart_and_wait') as restart:
            result = self.transaction.activate(restart=False)
            restart.assert_not_called()
        self.assertEqual(result['status'], 'pending_restart')
        self.assertIn('new', (self.target / '__init__.py').read_text())
        self.assertIn('old', (self.transaction.folder / 'component/__init__.py').read_text())

    def test_explicit_rollback_prepares_previous_code_and_saves_current(self):
        self.stage()
        self.verify()
        with patch.object(self.transaction, 'check_config'):
            self.transaction.activate(restart=False)
        restore = deploy.Deployment(self.root, 'rollback-run')
        restore.prepare(from_backup='test-run')
        self.assertIn('old', (restore.stage / '__init__.py').read_text())
        self.assertIn('new', (restore.folder / 'component/__init__.py').read_text())

    def test_second_deployment_cannot_steal_lock(self):
        self.transaction.prepare()
        other = deploy.Deployment(self.root, 'other-run')
        with self.assertRaisesRegex(RuntimeError, 'Another deployment'):
            other.prepare()
        other.release()
        self.assertEqual(self.transaction.lock.read_text().strip(), 'test-run')

    def test_backup_id_cannot_escape_backup_directory(self):
        with self.assertRaises(ValueError):
            deploy.Deployment(self.root, '../outside')

    def test_packaging_excludes_bytecode(self):
        (self.target / '__pycache__').mkdir()
        (self.target / '__pycache__/cached.pyc').write_bytes(b'compiled')
        self.assertFalse(any('__pycache__' in name for name in deploy.payload_manifest(self.target)['files']))

    def test_restart_timeout_still_checks_actual_new_api(self):
        def command(command):
            if command[:3] == ['ha', 'core', 'restart']:
                raise subprocess.TimeoutExpired(command, 180)
            if command[:3] == ['ha', 'core', 'info']:
                return subprocess.CompletedProcess(command, 0, '{"data":{"port":8123,"ssl":false}}', '')
            if command[:2] == ['docker', 'inspect']:
                content = '{"Status":"running","StartedAt":"new"}' if 'json' in command[3] else 'old'
                return subprocess.CompletedProcess(command, 0, content, '')
            return subprocess.CompletedProcess(command, 0, '', '')
        self.transaction.prepare()
        with patch.object(deploy, 'run', side_effect=command):
            self.transaction.restart_and_wait()
