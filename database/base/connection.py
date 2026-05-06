import mysql.connector
from mysql.connector import errorcode, pooling
import logging
import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine

from .config import get_env_bool, get_external_path


class Database:
    _instance = None
    _pool = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'db_config'):
            return

        env_path = get_external_path(".env")
        load_dotenv(env_path)

        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
            'port': int(os.getenv('DB_PORT', 3306))
        }

        if not all([self.db_config['user'], self.db_config['password'], self.db_config['database']]):
            raise ValueError("Database configuration is missing in .env file.")

        self._ensure_database_exists()

        if Database._pool is None:
            try:
                Database._pool = pooling.MySQLConnectionPool(
                    pool_name="modernlam_pool",
                    pool_size=32,
                    pool_reset_session=True,
                    use_pure=True,
                    auth_plugin='mysql_native_password',
                    **self.db_config
                )
                logging.info("🚀 Connection Pool initialized successfully (Size: 3).")
            except Exception as e:
                logging.error(f"❌ Failed to initialize Connection Pool: {e}")
                raise

        try:
            db_url = (f"mysql+mysqlconnector://{self.db_config['user']}:{self.db_config['password']}"
                      f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
            self.engine = create_engine(
                db_url,
                connect_args={'use_pure': True, 'auth_plugin': 'mysql_native_password'},
                echo=False
            )
        except Exception as e:
            logging.error(f"Failed to create SQLAlchemy engine: {e}")

        self.schema_check_on_startup = get_env_bool(
            "DB_SCHEMA_CHECK_ON_STARTUP",
            default=False
        )
        is_local = self.db_config['host'] in ['127.0.0.1', 'localhost']
        if is_local and self.schema_check_on_startup:
            self._initialize_schema()
        else:
            logging.info(
                "Schema startup checks skipped. Set DB_SCHEMA_CHECK_ON_STARTUP=true "
                "in .env to run migrations."
            )

    def _ensure_database_exists(self):
        try:
            conn_config = self.db_config.copy()
            db_name = conn_config.pop('database')
            conn_config['use_pure'] = True
            conn_config['auth_plugin'] = 'mysql_native_password'

            with mysql.connector.connect(**conn_config) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS {db_name} "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
        except mysql.connector.Error as err:
            logging.error(f"❌ Could not verify/create database: {err}")
            raise

    @contextmanager
    def get_db_connection(self):
        conn = None
        try:
            conn = Database._pool.get_connection()
            yield conn
            conn.commit()
        except mysql.connector.Error as err:
            logging.error(f"Database error: {err}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_raw_connection(self):
        return Database._pool.get_connection()
