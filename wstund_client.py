# -*- coding: utf-8 -*-
import sys
import select
import config as g
from time import sleep
from subprocess import check_call
from lockfile import LockTimeout
from daemon.runner import DaemonRunner, DaemonRunnerStopFailureError
from threading import Thread
from pytun import TunTapDevice, IFF_TUN, IFF_NO_PI
from ws4py.client.threadedclient import WebSocketClient
from ws4py.exc import HandshakeError


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
        g.logger.debug('YMK in wstundClientApp __init__')
        self.pidfile_path = g.config.get('wstund', 'pidpath')
        self.pidfile_timeout = int(g.config.get('wstund', 'pidtimeout'))
        self.reconnect_interval = int(g.config.get('client', 'reconnect.interval'))
        # ## wstundClient
        self.ws_tun_client = wstundClient()

    def __del__(self):
        g.logger.debug('YMK in wstundClientApp __del__')
        self.ws_tun_client.stop()

    def run(self):
        while True:
            try:
                self.ws_tun_client.start()
            except HandshakeError as e:
                self.ws_tun_client.stop()
                g.logger.info('wstund client wait {0} seconds to reconnect'.format(self.reconnect_interval))
                sleep(self.reconnect_interval)


class webSocketTunClient(WebSocketClient):
    def __init__(self, url, tun, protocols=None, extensions=None, heartbeat_freq=None,
                 ssl_options=None, headers=None):
        WebSocketClient.__init__(self, url, protocols, extensions, heartbeat_freq,
                                 ssl_options, headers=headers)
        self.tun = tun

    def opened(self):
        g.logger.info("wstund connected")
        if g.config.get('client', 'script.up') is not None:
            # g.logger.debug(g.config.get('client', 'script.up'))
            check_call(g.config.get('client', 'script.up'), shell=True)

    def closed(self, code, reason):
        g.logger.info(("wstund closed", code, reason))
        if g.config.get('client', 'script.down') is not None:
            check_call(g.config.get('client', 'script.down'), shell=True)

    def received_message(self, m):
        if m is not None:
            g.logger.debug("incoming len(m) {0}".format(len(m)))
            try:
                self.tun.write(m.data)
            except RuntimeError as e:
                pass


class wstundClient():
    def __init__(self):
        # g.logger.debug('YMK in wstundClient __init__')
        self.tun = None
        self.ws = None
        self.thread = None
        self.running = False

    def outgoing(self):
        # while True:
        #     g.logger.debug('YMK in wstundClient outgoing')
        #     sleep(1)
        self.thread_closing = False
        self.count = 0
        poller = select.epoll()
        poller.register(self.tun, select.EPOLLIN)
        while True:
            # sleep(0.50)
            if self.thread_closing is True:
                break
            events = poller.poll(2)
            for fd, flag in events:
                if fd is self.tun.fileno():
                    buf = self.tun.read(self.tun.mtu)
                    # print("data len(buf) {1} [{0}]".format(hexlify(buf), len(buf)))
                    g.logger.debug("outgoing len(buf) {0}".format(len(buf)))
                    self.count += 1
                    self.ws.send(buf, True)

    def start(self):
        self.running = True
        # ## tuntap
        if self.tun is None:
            self.tun = TunTapDevice(flags=IFF_TUN | IFF_NO_PI)
        g.logger.debug(self.tun.name)
        self.tun.addr = g.config.get('client', 'ip')
        # self.tun.dstaddr = '10.10.0.1'
        self.tun.netmask = g.config.get('client', 'netmask')
        self.tun.mtu = int(g.config.get('client', 'mtu'))
        self.tun.up()

        # ## websocket
        # ws = PingClient('ws://{0}:{1}/ws'.format(args.host, args.port), protocols=['http-only', 'chat'])
        self.url = 'ws://{0}:{1}/ws'.format(g.config.get('client', 'host'), g.config.get('client', 'port'))
        self.ws = webSocketTunClient(self.url, self.tun, protocols=['http-only', 'chat'], heartbeat_freq=2.0)
        try:
            self.ws.daemon = True
            self.ws.connect()
        except:
            return

        # ## thread
        if self.thread is None:
            self.thread = Thread(target=self.outgoing)
            self.thread.daemon = True
            self.thread.start()

        # ## run forever
        self.run()

    def stop(self):
        if self.running is False:
            return
        self.thread_closing = True
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        if self.ws is not None and not self.ws.terminated:
            self.ws.close()
            self.ws.closed(1000, "client receive signal.SIGTERM)")
            self.ws = None
        if self.tun is not None:
            self.tun.down()
        self.running = False

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
    daemon_runner = DaemonRunner(wstundClientApp())
    try:
        daemon_runner.do_action()
    except (DaemonRunnerStopFailureError, LockTimeout) as e:
        g.logger.error(e)
        sys.exit(e)

# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
