import logging

from .connection import Database as _DatabaseBase
from .schema_initializer import SchemaInitializerMixin
from .backup_manager import BackupManagerMixin
from .archive_view_manager import ArchiveViewManagerMixin


class Database(SchemaInitializerMixin, BackupManagerMixin, ArchiveViewManagerMixin, _DatabaseBase):
    """
    Main Database class.

    Assembled from focused mixins:
      - connection.py         → connection pool, get_db_connection, get_raw_connection
      - schema_initializer.py → _initialize_schema (CREATE TABLE, migrations, indexes)
      - backup_manager.py     → CSV / Excel backup & restore, export_and_purge_tables
      - archive_view_manager.py → activate/deactivate archive view mode
    """
    pass
