import unittest
from contextlib import ExitStack
from unittest.mock import patch

from backend.base.custom_exceptions import InvalidKeyValue
from backend.base.definitions import ProxyType, StartType
from Kapowarr import InvalidCLIArgument, _main, _run_sub_process


class CLIValidation(unittest.TestCase):
    def test_server_failure_is_reported_after_service_cleanup(self):
        with ExitStack() as stack:
            for target in (
                'Kapowarr.set_start_method',
                'backend.base.logging.setup_logging',
                'backend.internals.db.set_db_location',
                'backend.internals.db.setup_db',
                'backend.internals.server.StartTypeHandlers.start_timer',
                'backend.internals.status.StatusHandlers',
                'backend.implementations.indexer_client_manager.IndexerClients.trigger_client_registration',
                'backend.implementations.query_builder_manager.QueryBuilders.trigger_builder_registration',
            ):
                stack.enter_context(patch(target))
            server = stack.enter_context(patch('backend.internals.server.Server'))
            server.return_value.run.side_effect = RuntimeError('Server failed')
            settings = stack.enter_context(patch('backend.internals.settings.Settings'))
            settings.return_value.get_settings.return_value.proxy_type = ProxyType.NONE
            downloads = stack.enter_context(patch('backend.features.download_queue.DownloadHandler'))
            tasks = stack.enter_context(patch('backend.features.tasks.TaskHandler'))
            clients = stack.enter_context(patch('backend.implementations.external_client_manager.ExternalClients'))
            with self.assertRaisesRegex(RuntimeError, 'Server failed'):
                _main(StartType.STARTUP)
            downloads.return_value.stop_handle.assert_called_once()
            tasks.return_value.stop_handle.assert_called_once()
            clients.disconnect_clients.assert_called_once()

    def test_frozen_server_restarts_itself_without_interpreter_arguments(self):
        for frozen in (False, True):
            with self.subTest(frozen=frozen), patch('Kapowarr.sys.frozen', frozen, create=True), \
                    patch('Kapowarr.argv', ['Kapowarr.py', '-d', '/tmp/data']), \
                    patch('Kapowarr.get_python_exe', return_value='/bin/server'), \
                    patch('Kapowarr.Popen') as spawn, \
                    patch('Kapowarr.register'), patch('Kapowarr.signal'):
                spawn.return_value.wait.return_value = 0
                self.assertEqual(_run_sub_process(StartType.RESTART), 0)
                expected = ['/bin/server']
                if not frozen:
                    from Kapowarr import __file__ as script
                    expected += ['-u', script]
                self.assertEqual(spawn.call_args.args[0], expected + ['-d', '/tmp/data'])
                self.assertEqual(spawn.call_args.kwargs['env']['KAPOWARR_RUN_MAIN'], '1')
                self.assertEqual(spawn.call_args.kwargs['env']['KAPOWARR_START_TYPE'], str(StartType.RESTART.value))

    def test_invalid_settings_identify_the_supplied_option(self):
        for argument, value, setting, option in (
            ('host', '', 'host', '-o/--Host'),
            ('port', 0, 'port', '-p/--Port'),
            ('url_base', 'invalid', 'url_base', '-u/--UrlBase'),
            ('td_folder', 'invalid', 'download_folder',
             '-t/--TempDownloadFolder')):
            with self.subTest(argument=argument), ExitStack() as stack:
                for target in (
                    'Kapowarr.set_start_method',
                    'backend.base.logging.setup_logging',
                    'backend.internals.db.set_db_location',
                    'backend.internals.db.setup_db',
                    'backend.internals.server.Server',
                    'backend.internals.server.StartTypeHandlers.start_timer'
                ):
                    stack.enter_context(patch(target))
                settings = stack.enter_context(
                    patch('backend.internals.settings.Settings'))
                settings.return_value.update.side_effect = InvalidKeyValue(
                                                                           setting,
                                                                           value)
                with self.assertRaisesRegex(InvalidCLIArgument, option):
                    _main(StartType.STARTUP, **{argument: value})
                settings.return_value.update.assert_called_once_with(
                    {setting: value})


if __name__ == '__main__':
    unittest.main()
