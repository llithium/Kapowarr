import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, render_template


class ElementIds(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for key, value in attrs if key == 'id')


class UiTemplates(unittest.TestCase):
    def test_library_actions_have_unique_targets_including_empty_state(self):
        frontend = Path(__file__).resolve().parents[2] / 'frontend'
        app = Flask(__name__, template_folder=str(frontend / 'templates'))
        with app.test_request_context('/'):
            parser = ElementIds()
            parser.feed(render_template('volumes.html', url_base=''))
        counts = Counter(parser.ids)
        self.assertEqual({name: count for name, count in counts.items() if count > 1}, {})
        for action in ('updateall-button', 'searchall-button', 'massedit-button'):
            self.assertEqual(counts[action], 1)

    def test_api_key_has_an_associated_label(self):
        from bs4 import BeautifulSoup

        frontend = Path(__file__).resolve().parents[2] / 'frontend'
        app = Flask(__name__, template_folder=str(frontend / 'templates'))
        with app.test_request_context('/settings/general'):
            page = BeautifulSoup(render_template('settings_general.html', url_base=''), 'html.parser')
        field = page.select_one('#api-input')
        label = page.find('label', attrs={'for': field['id']})
        self.assertIsNotNone(label)
        self.assertEqual(label.get_text(strip=True), 'API key')

    def test_loading_dialogs_are_named_and_focusable_without_controls(self):
        from bs4 import BeautifulSoup

        frontend = Path(__file__).resolve().parents[2] / 'frontend'
        app = Flask(__name__, template_folder=str(frontend / 'templates'))
        with app.test_request_context('/volumes/3'):
            page = BeautifulSoup(render_template('view_volume.html', url_base=''), 'html.parser')
        dialogs = page.select('.window .loading-window')
        self.assertTrue(dialogs)
        for dialog in dialogs:
            self.assertEqual(dialog.get('role'), 'dialog')
            self.assertEqual(dialog.get('tabindex'), '-1')
            self.assertTrue(dialog.get('aria-label'))
