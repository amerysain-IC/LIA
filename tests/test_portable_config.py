import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bridge_service as service

class PortableConfigTests(unittest.TestCase):
    def test_status_host_is_read_from_selected_config(self):
        with tempfile.TemporaryDirectory(dir=service.RUNTIME) as directory:
            env=Path(directory)/'bridge.env'
            env.write_text('VB_REMOTE_HOST=example-vm\nVB_GUI_HOST=example-gui\n',encoding='utf-8')
            with patch.object(service,'ENV',env):self.assertEqual(service.configured_host(),'example-gui')

    def test_library_path_uses_remote_home(self):
        with patch.object(service,'skill',return_value='"/home/example-user"') as call:
            self.assertEqual(service.remote_library_path('CircuitImageTests'),'/home/example-user/.virtuoso-bridge/CircuitImageTests')
            call.assert_called_once_with('getShellEnvVar("HOME")')
        with self.assertRaises(ValueError):service.remote_library_path('../other')
