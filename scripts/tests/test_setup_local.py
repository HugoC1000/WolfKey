"""Regression tests for setup; no database or project .env is touched."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from dotenv import dotenv_values
import psycopg2

SCRIPT = Path(__file__).resolve().parents[1] / 'setup_local.py'
spec = importlib.util.spec_from_file_location('setup_local', SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy(SCRIPT.parent.parent / '.env.example', self.root / '.env.example')
        self.environ = patch.dict(os.environ, {}, clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_fresh_credentials_roundtrip_and_secure_mode(self):
        password = "pa\\ss #tag 'double\" unicode-🐺"
        answers = ['custom_db', 'custom_user', password, 'db.example.invalid', '6543']
        with patch.object(setup, 'ask', side_effect=answers):
            setup.prepare_environment(self.root)
        parsed = dotenv_values(self.root / '.env')
        self.assertEqual(parsed['DB_PASSWORD'], password)
        self.assertEqual(parsed['DB_HOST'], 'db.example.invalid')
        self.assertEqual(parsed['DB_PORT'], '6543')
        self.assertEqual(len(parsed['SECRET_KEY']), 50)
        Fernet(parsed['FERNET_KEY'].encode())
        self.assertEqual((self.root / '.env').stat().st_mode & 0o777, 0o600)
        text = (self.root / '.env').read_text()
        self.assertEqual(text.count('DB_NAME='), 1)

    def test_rerun_preserves_file_keys_and_uses_dotenv_parser(self):
        key = Fernet.generate_key().decode()
        content = f"DB_NAME=old\nDB_NAME='correct'\nSECRET_KEY={'x'*50}\nFERNET_KEY={key}\n"
        (self.root / '.env').write_text(content)
        with patch.object(setup, 'ask', side_effect=AssertionError('unexpected prompt')):
            setup.prepare_environment(self.root, no_input=True)
            setup.prepare_environment(self.root, no_input=True)
        self.assertEqual((self.root / '.env').read_text(), content)
        self.assertEqual(os.environ['DB_NAME'], 'correct')

    def test_exported_settings_override_existing_env(self):
        os.environ['DB_NAME'] = 'exported'
        os.environ['SECRET_KEY'] = 'x'*50
        os.environ['FERNET_KEY'] = Fernet.generate_key().decode()
        (self.root / '.env').write_text('DB_NAME=file_value\n')
        setup.prepare_environment(self.root, no_input=True)
        self.assertEqual(os.environ['DB_NAME'], 'exported')

    def test_unattended_creation_uses_exported_credentials(self):
        os.environ.update(DB_NAME='automated', DB_USER='role', DB_PASSWORD='secret #with\\slashes')
        setup.prepare_environment(self.root, no_input=True)
        values = dotenv_values(self.root / '.env')
        self.assertEqual(values['DB_NAME'], 'automated')
        self.assertEqual(values['DB_PASSWORD'], os.environ['DB_PASSWORD'])

    def test_database_url_is_saved_and_no_db_prompts(self):
        url = 'postgresql://role:password@localhost:6543/actual?sslmode=disable'
        os.environ['DATABASE_URL'] = url
        with patch.object(setup, 'ask', side_effect=AssertionError('unexpected prompt')):
            setup.prepare_environment(self.root)
        self.assertEqual(dotenv_values(self.root / '.env')['DATABASE_URL'], url)

    def test_placeholder_keys_fail_without_modifying_existing_file(self):
        shutil.copy(self.root / '.env.example', self.root / '.env')
        original = (self.root / '.env').read_bytes()
        with self.assertRaisesRegex(setup.SetupError, 'SECRET_KEY'):
            setup.prepare_environment(self.root, no_input=True)
        self.assertEqual((self.root / '.env').read_bytes(), original)

    def test_invalid_fernet_key_fails(self):
        (self.root / '.env').write_text(f"SECRET_KEY={'x'*50}\nFERNET_KEY=invalid\n")
        with self.assertRaisesRegex(setup.SetupError, 'FERNET_KEY'):
            setup.prepare_environment(self.root, no_input=True)

    def test_interpolation_input_rejected_before_file_creation(self):
        os.environ['DB_PASSWORD'] = 'secret${NOT_A_VARIABLE}'
        with self.assertRaisesRegex(setup.SetupError, 'interpolation'):
            setup.prepare_environment(self.root, no_input=True)
        self.assertFalse((self.root / '.env').exists())

    def test_eof_is_actionable(self):
        with patch('builtins.input', side_effect=EOFError), self.assertRaisesRegex(setup.SetupError, '--no-input'):
            setup.ask('test')


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock(vendor='postgresql')
        self.params = dict(dbname='custom_db', user='role', password='secret', host='db.host', port='6543', sslmode='require')
        self.connection.get_connection_params.return_value = self.params.copy()

    def test_existing_database_uses_exact_django_connection_and_closes(self):
        target = MagicMock()
        with patch.object(setup.psycopg2, 'connect', return_value=target) as connect:
            setup.prepare_database(self.connection, no_input=True)
        connect.assert_called_once_with(**self.params, connect_timeout=5)
        target.close.assert_called_once()

    def test_missing_database_created_on_same_server_and_role(self):
        admin, target = MagicMock(), MagicMock()
        admin.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        with patch.object(setup.psycopg2, 'connect', side_effect=[psycopg2.OperationalError(), admin, target]) as connect:
            setup.prepare_database(self.connection, no_input=True)
        self.assertEqual(connect.call_args_list[1].kwargs, dict(self.params, dbname='postgres', connect_timeout=5))
        self.assertEqual(connect.call_args_list[2].kwargs, dict(self.params, connect_timeout=5))
        self.assertTrue(admin.autocommit)
        admin.close.assert_called_once()
        target.close.assert_called_once()

    def test_connection_failure_does_not_leak_credentials(self):
        with patch.object(setup.psycopg2, 'connect', side_effect=psycopg2.OperationalError('password=secret')):
            with self.assertRaises(setup.SetupError) as error:
                setup.prepare_database(self.connection, no_input=True)
        self.assertNotIn('password=secret', str(error.exception))

    def test_non_postgresql_rejected(self):
        self.connection.vendor = 'sqlite'
        with self.assertRaisesRegex(setup.SetupError, 'PostgreSQL'):
            setup.prepare_database(self.connection)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.original_path = setup.sys.path[:]
        self.addCleanup(lambda: setup.sys.path.__setitem__(slice(None), self.original_path))
        for target in ('prepare_environment', 'prepare_database'):
            mock = patch.object(setup, target)
            mock.start()
            self.addCleanup(mock.stop)
        for target, value in [('django.setup', None), ('django.db.connections', {'default': MagicMock()})]:
            mock = patch(target, value) if value is not None else patch(target)
            mock.start()
            self.addCleanup(mock.stop)
        self.environ = patch.dict(os.environ)
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.output = io.StringIO()
        redirect = contextlib.redirect_stdout(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_unattended_skips_superuser(self):
        with patch.object(setup.subprocess, 'run') as run, patch.object(setup, 'confirm') as confirm:
            setup.main(['--no-input'])
        confirm.assert_not_called()
        self.assertEqual([call.args[0][2:] for call in run.call_args_list], [['migrate', '--noinput'], ['check']])

    def test_skip_superuser_does_not_prompt(self):
        with patch.object(setup.subprocess, 'run') as run, patch.object(setup, 'confirm') as confirm:
            setup.main(['--skip-superuser'])
        confirm.assert_not_called()
        self.assertEqual(run.call_count, 2)

    def test_interactive_superuser_choice_runs_command(self):
        with patch.object(setup.subprocess, 'run') as run, patch.object(setup, 'confirm', return_value=True):
            setup.main([])
        self.assertEqual(run.call_args.args[0][2], 'createsuperuser')
        self.assertTrue(run.call_args.kwargs['check'])

    def test_migration_failure_stops_setup_without_success_message(self):
        failure = subprocess.CalledProcessError(1, [setup.sys.executable, 'manage.py', 'migrate'])
        with patch.object(setup.subprocess, 'run', side_effect=failure) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                setup.main(['--no-input'])
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('Setup finished', self.output.getvalue())


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='setup wrapper ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        shutil.copy(SCRIPT.with_suffix('.sh'), self.root / 'scripts/setup_local.sh')
        self.script = self.root / 'scripts/setup_local.sh'

    def test_help_does_not_install_or_create_files(self):
        result = subprocess.run(['/bin/bash', str(self.script), '--help'], cwd='/', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / '.venv').exists())

    def test_invalid_python_rejected_before_creating_venv(self):
        result = subprocess.run(['/bin/bash', str(self.script)], env=dict(os.environ, PYTHON='/bin/false', VENV_DIR=str(self.root / 'new-venv')), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.10', result.stderr)
        self.assertFalse((self.root / 'new-venv').exists())

    def test_existing_broken_venv_is_preserved(self):
        venv = self.root / '.venv'
        venv.mkdir()
        marker = venv / 'keep'; marker.write_text('preserve')
        result = subprocess.run(['/bin/bash', str(self.script)], env=dict(os.environ, VENV_DIR=str(venv)), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'preserve')

    def test_paths_with_spaces_and_outside_cwd(self):
        venv = self.root / 'custom venv/bin'; venv.mkdir(parents=True)
        python = venv / 'python'
        python.write_text('#!/bin/bash\nif [[ "$1" == "-c" ]]; then exit 0; fi\nprintf "%s\\n" "$PWD" >> calls\n')
        python.chmod(0o755)
        result = subprocess.run(['/bin/bash', str(self.script), '--no-input'], cwd='/', env=dict(os.environ, VENV_DIR=str(venv.parent)), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'calls').read_text().splitlines(), [str(self.root)]*5)


if __name__ == '__main__':
    unittest.main()
