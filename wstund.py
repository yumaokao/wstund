# -*- coding: utf-8 -*-
import os
import sys
import logging
import argparse
import ConfigParser
# from config import config, version, logger
import config as g

import wstund_client
import wstund_server


def load_default_config():
    # global config
    g.config = ConfigParser.RawConfigParser()
    g.config.add_section('wstund')
    g.config.add_section('client')
    g.config.add_section('server')
    g.config.set('wstund', 'role', 'server')
    g.config.set('wstund', 'debug', 'false')
    g.config.set('wstund', 'logfile', '/var/log/wstund.log')
    g.config.set('wstund', 'loglevel', 'INFO')
    g.config.set('wstund', 'tundev', '/dev/net/tun')
    g.config.set('client', 'host', 'wstund.your.domain')
    g.config.set('client', 'port', '80')
    g.config.set('client', 'ip', '10.10.0.4')
    g.config.set('client', 'netmask', '255.255.255.0')
    g.config.set('server', 'host', '0.0.0.0')
    g.config.set('server', 'port', '5000')
    g.config.set('server', 'ip', '10.10.0.1')
    g.config.set('server', 'netmask', '255.255.255.0')


def load_config(args=None):
    load_default_config()

    if args.config is not None:
        g.config.read(args.config)

    # ## YMK TODO: from config
    set_logging_level(logging.DEBUG)


def set_logging_level(plevel=0):
    # global logger
    g.logger = logging.getLogger('WSTUND')
    g.logger.setLevel(plevel)
    # g.logger.addHandler(logging.StreamHandler())
    if g.config.get('wstund', 'debug') == 'true':
        g.logger.addHandler(logging.StreamHandler())


def main():
    parser = argparse.ArgumentParser(description='websocket tunnel daemon')
    parser.add_argument('-c', '--config', nargs='?', default='/etc/wstund.conf',
                        help='specify config file')
    parser.add_argument('-v', '--version', action='version',
                        version='{0}'.format(g.version),
                        help='show version infomation')

    args = parser.parse_known_args()[0]
    load_config(args)

    g.logger.debug('YMK args.config [{0}]'.format(args.config))
    g.logger.debug('YMK config role [{0}]'.format(g.config.get('wstund', 'role')))
    if g.config.get('wstund', 'role') == 'client':
        g.logger.debug('YMK call client.main')
        wstund_client.main()
    else:
        g.logger.debug('YMK call server.main')
        wstund_server.main()


if __name__ == "__main__":
    # print("uid {0}".format(os.getuid()))
    if os.getuid() is not 0:
        os.execvp("sudo", ["sudo", "python2"] + sys.argv)
    main()

# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
