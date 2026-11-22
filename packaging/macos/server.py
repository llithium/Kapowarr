"""Entry point for the bundled server and its spawned worker processes."""

import multiprocessing
import os
import runpy
import sys

def _use_bundled_ca_certificates() -> None:
    """The bundled OpenSSL looks for root certificates inside the Python
    installation the app was built with, which usually doesn't exist on the
    machine running the app. Point it at the bundled certifi CA file instead,
    unless the user configured one themselves."""
    try:
        import certifi
    except ImportError:
        return
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())


if __name__ == '__main__':
    _use_bundled_ca_certificates()

    # Workers must enter multiprocessing before importing the application.
    multiprocessing.freeze_support()

    if sys.argv[1:] == ['--check-bundle']:
        from backend.base.files import folder_path
        from backend.implementations.external_client_manager import \
            ExternalClients
        from backend.implementations.query_builder_manager import QueryBuilders

        ExternalClients.trigger_client_registration()
        QueryBuilders.trigger_builder_registration()
        assert ExternalClients.clients and QueryBuilders.builders
        assert os.path.isfile(folder_path('frontend', 'templates', 'volumes.html'))
        with multiprocessing.get_context('spawn').Pool(1) as pool:
            assert pool.map(abs, [-1, -2]) == [1, 2]
        print('Bundled resources, client registration, and spawned workers passed.')
    else:
        if os.environ.get('KAPOWARR_RUN_MAIN') != '1' and os.getpgrp() != os.getpid():
            # The native launcher can stop the entire process group if graceful
            # shutdown fails, including any outstanding conversion workers.
            os.setsid()
        runpy.run_module('Kapowarr', run_name='__main__')
