""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: String conversions
"""


def to_str(data):
    if isinstance(data, bytes):
        return data.decode("utf-8")
    else:
        return data

def to_bytes(data):
    if isinstance(data, str):
        return data.encode("utf-8")
    else:
        return data


