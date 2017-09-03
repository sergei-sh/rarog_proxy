""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Storage indirection level
"""


from proxy.config import Config
from proxy.const import Const 

"""
returns - Storage object of certain type depending on config setting
"""
def get_storage():
    storage_type = Config.value(Const.STORAGE_SECTION, "storage")
    if "DB" == storage_type:
        from proxy.db_storage import DBStorage
        return DBStorage()
    elif "FS" == storage_type:
        from proxy.fs_storage import FSStorage
        return FSStorage()
    else:
        sys.exit('Need either DB or FS storage type in proxy.ini')
