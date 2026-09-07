import unittest
from contextlib import ExitStack
from unittest.mock import patch

from backend.base.custom_exceptions import InvalidKeyValue
from backend.base.definitions import StartType
from Kapowarr import InvalidCLIArgument, _main


class CLIValidation(unittest.TestCase):
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
