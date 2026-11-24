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
        for action in ('updateall-button', 'searchall-button', 'inspector', 'publisher-list'):
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
        with app.test_request_context('/add'):
            page = BeautifulSoup(render_template('add_volume.html', url_base=''), 'html.parser')
        dialogs = page.select('.window .loading-window')
        self.assertTrue(dialogs)
        for dialog in dialogs:
            self.assertEqual(dialog.get('role'), 'dialog')
            self.assertEqual(dialog.get('tabindex'), '-1')
            self.assertTrue(dialog.get('aria-label'))


    def test_series_page_edits_in_the_panel_not_in_windows(self):
        from bs4 import BeautifulSoup

        frontend = Path(__file__).resolve().parents[2] / 'frontend'
        app = Flask(__name__, template_folder=str(frontend / 'templates'))
        with app.test_request_context('/volumes/3'):
            page = BeautifulSoup(render_template('view_volume.html', url_base=''), 'html.parser')
        # Only the downloads-only "Find links" dialog is left.
        self.assertEqual([w['id'] for w in page.select('.window > section')], ['manual-search-window'])
        panel = page.select_one('#sp-panel')
        for control in ('specialoverride-input', 'root-folder-input', 'volumefolder-input',
                        'match-list', 'rename-button', 'submit-delete'):
            self.assertIsNotNone(panel.select_one(f'#{control}'), control)
        ids = [el['id'] for el in page.select('[id]')]
        self.assertEqual(len(ids), len(set(ids)))


class OrganizerModeTemplates(unittest.TestCase):
    def render(self, template, path, **context):
        from bs4 import BeautifulSoup

        frontend = Path(__file__).resolve().parents[2] / 'frontend'
        app = Flask(__name__, template_folder=str(frontend / 'templates'))
        with app.test_request_context(path):
            return BeautifulSoup(render_template(template, url_base='', **context), 'html.parser')

    def test_organizer_mode_marks_page_and_swaps_primary_action(self):
        page = self.render('volumes.html', '/', organizer_mode=True)
        self.assertIn('organizer-mode', page.html.get('class', []))
        self.assertIsNotNone(page.select_one('a[href="/library-import"].primary-action'))
        self.assertIsNone(page.select_one('option[value="monitored"]'))

        page = self.render('volumes.html', '/', organizer_mode=False)
        self.assertNotIn('organizer-mode', page.html.get('class', []) or [])
        self.assertIsNotNone(page.select_one('option[value="monitored"]'))

    def test_organizer_mode_drops_download_settings_tabs(self):
        page = self.render('settings_general.html', '/settings/general', organizer_mode=True)
        tabs = {a['href'] for a in page.select('.tab-container a, nav a') if a.get('href', '').startswith('/settings/')}
        self.assertNotIn('/settings/download', tabs)
        self.assertNotIn('/settings/downloadclients', tabs)
        self.assertIsNotNone(page.select_one('#organizer-mode-input'))
