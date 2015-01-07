wstund
======

install
-------
* pip2
  .. code:: sh

    $ sudo pip2 install python-pytun

    # wstund
    # client
    $ sudo pip2 install python-pytun ws4py ConfigParser python-daemon
    # compile all pyc
    $ python2 -m compileall .

    # server
    $ sudo pip install python-pytun ws4py cherrypy ConfigParser python-daemon
    # compile all pyc
    $ python2 -m compileall .

run
---
* server
  .. code:: sh

    # run
    $ python2 wstund.py start
    # or use -c to select config file
    $ python2 wstund.py start -c ./wstund.conf

    # /etc/wstund.conf
    [wstund]
    debug=false
    role=server

    [server]
    host=0.0.0.0
    port=80
    ip=10.10.0.1

* client
  .. code:: sh
    # run
    $ python2 wstund.py start
    # or use -c to select config file
    $ python2 wstund.py start -c ./wstund.conf

    # /etc/wstund.conf
    [wstund]
    debug=false
    role=client

    [client]
    host=wstund.domain.com
    port=80
    ip=10.10.0.2

.. vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
