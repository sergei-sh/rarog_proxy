
WHAT IS THIS?
This is the simple caching proxy server. Yes I know there are heaps of them, but this one
is not to reinvent the wheel. Its aim just to show my developing abilities. This task 
involves a good complex of technologies.

PREREQUISITES
Tested on Linux 3.19 (Mint 17.3) 

1) You need to install:
    python3.4
    psycopg2
    postgresql 

2) For using database as a storage please create the user with with permission to create
databases. Provide username, password, host and port in proxy.ini. You will also need to 
set storage=DB.


RUNING
From the source dir:
Exmample:
    python proxy.py 0.0.0.0 8080 20
Format:
    PYTHON3.4 proxy.py IP_ADDR PORT PROCESS_NUMBER
    IP_ADDR address of the interface to listen on it;
    PORT port to listen;
    PROCESS_NUMBER the number of running processes; Since all operaion is I/O you want to have
a large number of them, say 20

FILES
    proxy.ini - application settings
    proxy.py - entry point
    

