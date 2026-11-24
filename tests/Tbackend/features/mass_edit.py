import unittest
from unittest.mock import patch

from backend.base.custom_exceptions import InvalidKeyValue, KeyNotFound
from backend.base.definitions import SpecialVersion
from backend.features.mass_edit import run_mass_editor_action


class MassEditSpecialVersionTests(unittest.TestCase):
    def run_action(self, **kwargs):
        with patch('backend.features.mass_edit.Volume') as volume:
            run_mass_editor_action('special_version', [3, 4], **kwargs)
        return volume

    def test_sets_and_locks_edition_for_every_volume(self):
        volume = self.run_action(special_version='tpb')
        self.assertEqual([c.args for c in volume.call_args_list], [(3,), (4,)])
        volume.return_value.update.assert_called_with({
            'special_version_locked': True,
            'special_version': SpecialVersion.TPB
        })

    def test_standard_edition_is_stored_as_normal(self):
        volume = self.run_action(special_version='')
        volume.return_value.update.assert_called_with({
            'special_version_locked': True,
            'special_version': SpecialVersion.NORMAL
        })

    def test_auto_unlocks_detection(self):
        volume = self.run_action(special_version='auto')
        volume.return_value.update.assert_called_with(
            {'special_version_locked': False}
        )

    def test_rejects_missing_unknown_and_internal_values(self):
        with self.assertRaises(KeyNotFound):
            self.run_action()
        for value in ('paperback', 'cover', 'metadata'):
            with self.assertRaises(InvalidKeyValue):
                self.run_action(special_version=value)
