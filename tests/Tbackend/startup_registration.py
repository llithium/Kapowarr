import unittest
from tempfile import TemporaryDirectory

from flask import Flask

from backend.implementations.external_client_manager import ExternalClients
from backend.implementations.indexer_client_manager import IndexerClients
from backend.implementations.query_builder_manager import QueryBuilders
from backend.internals.db import (DBConnection, DBConnectionManager,
                                  close_db, set_db_location, setup_db)


class StartupRegistrationTest(unittest.TestCase):
    def test_fresh_database_resolves_seeded_indexer(self):
        app = Flask('startup-registration')
        app.teardown_appcontext(close_db)
        previous_db = DBConnection.default_file
        with TemporaryDirectory() as folder:
            set_db_location(folder)
            try:
                with app.app_context():
                    setup_db()
                    IndexerClients.trigger_client_registration()
                    QueryBuilders.trigger_builder_registration()
                    ExternalClients.trigger_client_registration()
                    clients = IndexerClients.get_all_clients()
                    self.assertTrue(any(c.client_type == 'GetComics' for c in clients))
                    self.assertTrue(QueryBuilders.builders)
                    self.assertTrue(ExternalClients.clients)
            finally:
                DBConnectionManager.close_connection_of_thread()
                DBConnection.default_file = previous_db
