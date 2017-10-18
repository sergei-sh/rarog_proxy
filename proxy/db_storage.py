""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Database storage for cached data
"""


from logging import WARNING
from psycopg2 import connect, Binary, DatabaseError, ProgrammingError, IntegrityError, OperationalError
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import time

from proxy import encoding
from proxy.logger import proc_error, log
from proxy.config import Config
from proxy.const import Const

def _connect(db_name):
        return connect("host=%s port=%s dbname=%s user=%s password=%s" % 
            (Config.value(Const.STORAGE_SECTION, "host"),
             Config.value(Const.STORAGE_SECTION, "port"),
             db_name,
             Config.value(Const.STORAGE_SECTION, "user"),
             Config.value(Const.STORAGE_SECTION, "password")))

class DBStorage:
    TIME_FORMAT = "%H:%M:%S %b %d %Y"
    DB_NAME = "proxy_cache"

    def __init__(self):
        self._conn = _connect(DBStorage.DB_NAME)

    def __del__(self):
        if hasattr(self, '_conn'):
            self._conn.close()

    @staticmethod
    def check_init_db():
        """Checks if can connect to proxy_cache and creates the DB and the files table"""
        try:
            conn = _connect(DBStorage.DB_NAME)
        except OperationalError as errv:
            log("Cannot connect to the database. Trying to create the database\n ", WARNING) 
            DBStorage._init_db()
        finally:
            if 'conn' in locals(): 
                conn.close()

    def _init_db():
        conn = DBStorage._connect("postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        query = "CREATE DATABASE " + DBStorage.DB_NAME # no quotes for this command
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()

        conn = DBStorage._connect(DBStorage.DB_NAME)
        cur = conn.cursor()
        try:
            cur.execute("CREATE TABLE files (url TEXT PRIMARY KEY, timestamp TEXT, content BYTEA) ; ")
        except DatabaseError as errv:
            proc_error("DB create table failed: %s" % str(errv))

        conn.commit()
        cur.close()
        conn.close()
        log("Initialized new database\n ", WARNING) 

    def save(self, key_path, data):
        cur = self._conn.cursor()
        try:
            timestamp = time.strftime(DBStorage.TIME_FORMAT)
            spath = encoding.to_str(key_path)
            cur.execute("INSERT INTO files (url, timestamp, content) VALUES (%s, %s, %s);",
               (spath, timestamp, Binary(data)))
            return True
        except IntegrityError as errv: #key already exists
            pass 
        except DatabaseError as errv:
            proc_error("DB write failed: %s" % str(errv))
            return False
        finally:
            self._conn.commit()
            cur.close()

    def _fetch_col(self, column, key_path):
        cur = self._conn.cursor()
        try:
            str_path = encoding.to_str(key_path)
            #insert col name without quotes
            query = "SELECT %s FROM files WHERE url = " % (column,)
            query += "%s ;"
            #insert url value with quotes 
            cur.execute(query, (str_path,))
            vals = cur.fetchone()
            if None == vals:
                return None
            return vals[0]
        except DatabaseError as errv:
            proc_error("DB read failed: %s" % str(errv))
        finally:
            cur.close()
        return None

    def fetch(self, key_path):
        return self._fetch_col("content", key_path)

    def haskey_time(self, key_path): 
        time_str = self._fetch_col("timestamp", key_path)
        return (True, time.mktime(time.strptime(time_str, DBStorage.TIME_FORMAT))) if time_str else (False, None)


    def erase(self, key_path):
        cur = self._conn.cursor()
        try:
            str_path = encoding.to_str(key_path)
            cur.execute("DELETE FROM files WHERE url = %s ;", (str_path,))
            self._conn.commit()
        except DatabaseError as errv:
            proc_error("DB delete failed: %s" % str(errv))
        finally:
            cur.close()
        


