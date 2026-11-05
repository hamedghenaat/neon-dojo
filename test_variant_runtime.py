import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import variant_setup
from neon_dojo import PlayerSettings
from variant_game import Controller
from variant_scene import draw_scene


class SetupTests(unittest.TestCase):
    def test_ready_checks_minimum_distribution_version(self):
        with patch.object(variant_setup.importlib, 'import_module', return_value=object()), patch.object(variant_setup.metadata, 'version', return_value='9.5.0'):
            self.assertFalse(variant_setup._ready({'PIL': 'Pillow>=10'}))
        for version, expected in (('10.0.0', True), ('10.0.0rc1', False), ('11.2.0', True)):
            with self.subTest(version=version), patch.object(variant_setup.importlib, 'import_module', return_value=object()), patch.object(variant_setup.metadata, 'version', return_value=version):
                self.assertEqual(variant_setup._ready({'PIL': 'Pillow>=10'}), expected)

    def test_ready_runtime_is_silent_and_does_not_install(self):
        with patch.object(variant_setup, '_ready', return_value=True), patch.object(variant_setup, '_stream') as stream, patch.object(variant_setup.os, 'execv') as restart:
            variant_setup.ensure_runtime({'pygame': 'pygame-ce'})
        stream.assert_not_called()
        restart.assert_not_called()

    def test_existing_managed_environment_restarts_without_system_pip(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'env'
            python = env / ('Scripts/python.exe' if variant_setup.os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(variant_setup, 'ENV_DIR', env), patch.object(variant_setup, '_ready', return_value=False), patch.object(variant_setup, '_stream') as stream, patch.object(variant_setup.os, 'execv') as restart:
                variant_setup.ensure_runtime({'PIL': 'Pillow'})
            stream.assert_not_called()
            self.assertEqual(restart.call_args.args[0], str(python))

    def test_failed_install_does_not_restart_or_install_into_system(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'env'
            with patch.object(variant_setup, 'ENV_DIR', env), patch.object(variant_setup, '_ready', return_value=False), patch.object(variant_setup, '_stream', side_effect=[True, False]) as stream, patch.object(variant_setup.os, 'execv') as restart:
                with self.assertRaises(SystemExit):
                    variant_setup.ensure_runtime({'PIL': 'Pillow'})
            restart.assert_not_called()
            self.assertEqual(stream.call_args_list[0].args[0][1:3], ['-m','venv'])
            self.assertIn(str(env), stream.call_args_list[1].args[0][0])
            self.assertNotIn('--break-system-packages', stream.call_args_list[1].args[0])


class ControllerTests(unittest.TestCase):
    def setUp(self):
        with patch('variant_game.load_settings', return_value=PlayerSettings('custom','KNIGHT')):
            self.controller = Controller()
        self.addCleanup(self.controller.close)

    def test_name_edit_accepts_q_as_text_and_persists(self):
        controller = self.controller
        controller.game.state='settings'
        controller.game.settings_index=1
        controller.press('enter')
        controller.press('q')
        controller.text('Queen')
        with patch('variant_game.save_settings', return_value=True) as save:
            controller.press('enter')
        self.assertTrue(controller.running)
        self.assertEqual(controller.game.player.name,'Queen')
        self.assertIsNone(controller.text_prompt)
        save.assert_called_once()

    def test_combat_controls_only_mutate_fight_and_pause_stops_clock(self):
        controller=self.controller
        controller.press('z')
        self.assertEqual(controller.game.player.action,'idle')
        controller.press('enter')
        self.assertEqual(controller.game.state,'intro')
        controller.game.state='fight'
        controller.press('z')
        self.assertEqual(controller.game.player.action,'punch')
        controller.press('p')
        remaining=controller.game.round_time
        controller.update(1/30,{'left','x'})
        self.assertEqual(controller.game.state,'paused')
        self.assertEqual(controller.game.round_time,remaining)

    def test_client_cannot_advance_host_round(self):
        controller=self.controller
        controller.network=Mock(role='client')
        controller.game.state='round_over'
        controller.press('enter')
        self.assertEqual(controller.game.state,'round_over')

    def test_all_states_render_through_common_canvas(self):
        controller=self.controller
        for state in ('title','settings','hosting','searching','intro','fight','paused','finisher','round_over','wedding','match_over'):
            with self.subTest(state=state):
                controller.game.state=state
                controller.game.round_winner=1
                canvas=Mock()
                draw_scene(controller,canvas)
                canvas.clear.assert_called_once()
                canvas.sprite.assert_called()
        controller.text_prompt='CHARACTER NAME'
        controller.text_buffer='Knight'
        draw_scene(controller,Mock())


if __name__ == '__main__':
    unittest.main()
