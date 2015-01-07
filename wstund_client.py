# -*- coding: utf-8 -*-
import config as g
from time import sleep
from daemon import runner
from threading import Thread
from pytun import TunTapDevice, IFF_TUN, IFF_NO_PI
from ws4py.client.threadedclient import WebSocketClient


# ## for daemon.runner
class wstundClientApp():
    def __init__(self):
        # ## for daemon.runner
        if g.config.get('wstund', 'debug') == 'true':
            self.stdin_path = '/dev/tty'
            self.stdout_path = '/dev/tty'
            self.stderr_path = '/dev/tty'
        else:
            self.stdin_path = '/dev/null'
            self.stdout_path = '/dev/null'
            self.stderr_path = '/dev/null'
        # g.logger.debug('YMK in wstundClientApp __init__')
        self.pidfile_path = '/run/wstund.pid'
        self.pidfile_timeout = 5
        # ## wstundClient
        self.ws_tun_client = wstundClient()

    def run(self):
        self.ws_tun_client.start()


class webSocketTunClient(WebSocketClient):
    def __init__(self, url, tun, protocols=None, extensions=None, heartbeat_freq=None,
                 ssl_options=None, headers=None):
        WebSocketClient.__init__(self, url, protocols, extensions, heartbeat_freq,
                                 ssl_options, headers=headers)
        self.tun = tun

    def closed(self, code, reason):
        g.logger.debug(("Closed down", code, reason))

    def received_message(self, m):
        if m is not None:
            g.logger.debug("incoming len(m) {0}".format(len(m)))
            self.tun.write(m.data)


class wstundClient():
    def __init__(self):
        g.logger.debug('YMK in wstundClient __init__')
        self.tun = None
        self.ws = None
        self.thread = None

    def outgoing(self):
        # while True:
        #     g.logger.debug('YMK in wstundClient outgoing')
        #     sleep(1)
        self.count = 0
        while True:
            # time.sleep(1)
            buf = self.tun.read(self.tun.mtu)
            # print("data len(buf) {1} [{0}]".format(hexlify(buf), len(buf)))
            g.logger.debug("outgoing len(buf) {0}".format(len(buf)))
            self.count += 1
            self.ws.send(buf, True)

    def start(self):
        # ## tuntap
        if self.tun is None:
            self.tun = TunTapDevice(flags=IFF_TUN | IFF_NO_PI)
        g.logger.debug(self.tun.name)
        self.tun.addr = g.config.get('client', 'ip')
        # self.tun.dstaddr = '10.10.0.1'
        self.tun.netmask = g.config.get('client', 'netmask')
        self.tun.mtu = 1500
        self.tun.up()

        # ## websocket
        # ws = PingClient('ws://{0}:{1}/ws'.format(args.host, args.port), protocols=['http-only', 'chat'])
        self.url = 'ws://{0}:{1}/ws'.format(g.config.get('client', 'host'), g.config.get('client', 'port'))
        self.ws = webSocketTunClient(self.url, self.tun, protocols=['http-only', 'chat'])
        self.ws.connect()

        # ## thread
        if self.thread is None:
            self.thread = Thread(target=self.outgoing)
            self.thread.daemon = True

        # ## run forever
        self.thread.start()
        self.run()

    def run(self):
        self.ws.run_forever()
        # while True:
        #     g.logger.debug('YMK in wstundClient run')
        #    sleep(1)


def main():
    if g.config.get('wstund', 'role') != 'client':
        g.logger.error('config role is not client')
        return

    # g.logger.debug('YMK in wstund_client main')

    # client = wstundClient()
    daemon_runner = runner.DaemonRunner(wstundClientApp())
    daemon_runner.do_action()

# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
