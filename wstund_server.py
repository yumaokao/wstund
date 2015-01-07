# -*- coding: utf-8 -*-
import config as g
import os
import random
import select
import logging
import cherrypy
from time import sleep
from daemon import runner
from threading import Thread
from pytun import TunTapDevice, IFF_TUN, IFF_NO_PI
from ws4py import configure_logger
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket
from ws4py.messaging import TextMessage


class TunWebSocketHandler(WebSocket):
    tun = None
    thread = None
    thread_counter = 0
    thread_closing = False

    def background_send(self):
        count = 0
        poller = select.epoll()
        poller.register(self.tun, select.EPOLLIN)
        while True:
            # time.sleep(1)
            # cherrypy.log("YMK in B background_send epoll fileno {0}".format(self.tun.fileno()))
            events = poller.poll(2)
            # cherrypy.log("YMK in A background_send epoll events {0}".format(events))
            for fd, flag in events:
                if fd is self.tun.fileno():
                    buf = self.tun.read(self.tun.mtu)
                    cherrypy.log("data len(buf) {0}".format(len(buf)))
                    count += 1
                    cherrypy.engine.publish('websocket-broadcast', buf, True)
                    # self.send(buf, True)
                    # self.send("YMK in background_send {0}".format(count))

            # ## timeout then check thread_closing
            # cherrypy.log("YMK in background_send timeout thread_closing {0} count {1}".format(self.thread_closing, count))
            if self.thread_closing is True:
                cherrypy.log("YMK in background_send thread_closing")
                break

    def opened(self):
        cherrypy.log("YMK in TunWebSocketHandler opened")

        if TunWebSocketHandler.tun is None:
            cherrypy.log("YMK in TunWebSocketHandler new tun")
            tun = TunTapDevice(flags=IFF_TUN | IFF_NO_PI)
            tun.addr = g.config.get('server', 'ip')
            # tun.dstaddr = '10.10.0.2'
            tun.netmask = g.config.get('server', 'netmask')
            tun.mtu = 1500
            tun.up()
            TunWebSocketHandler.tun = tun

        if TunWebSocketHandler.thread is None:
            cherrypy.log("YMK in TunWebSocketHandler new thread")
            TunWebSocketHandler.thread = Thread(target=self.background_send)
            TunWebSocketHandler.thread.daemon = True
            TunWebSocketHandler.thread.start()
        TunWebSocketHandler.thread_counter += 1

    def received_message(self, m):
        # cherrypy.log("YMK in received_message: bin {0} len {1} self {2}".format(m.is_binary, len(m), repr(self)))
        cherrypy.log("YMK in received_message: bin {0} len {1}".format(m.is_binary, len(m)))
        if m is not None:
            self.tun.write(m.data)

        # self.send(str(pongip), True)
        # cherrypy.engine.publish('websocket-broadcast', m)

    def closed(self, code, reason="A client left the room without a proper explanation."):
        cherrypy.engine.publish('websocket-broadcast', TextMessage(reason))
        cherrypy.log("YMK in TunWebSocketHandler closing thread")
        TunWebSocketHandler.thread_counter -= 1
        if TunWebSocketHandler.thread_counter is 0:
            TunWebSocketHandler.thread_closing = True
            TunWebSocketHandler.thread.join()
            cherrypy.log("YMK in TunWebSocketHandler closed thread")
            TunWebSocketHandler.thread = None
            TunWebSocketHandler.thread_closing = False


class Root(object):
    def __init__(self, host, port, ssl=False):
        self.host = host
        self.port = port
        self.scheme = 'wss' if ssl else 'ws'

    @cherrypy.expose
    def index(self):
        return """<html>
    <head>
      <script type='application/javascript' src='https://ajax.googleapis.com/ajax/libs/jquery/1.8.3/jquery.min.js'></script>
      <script type='application/javascript'>
        $(document).ready(function() {

          websocket = '%(scheme)s://%(host)s:%(port)s/ws';
          if (window.WebSocket) {
            ws = new WebSocket(websocket);
          }
          else if (window.MozWebSocket) {
            ws = MozWebSocket(websocket);
          }
          else {
            console.log('WebSocket Not Supported');
            return;
          }

          window.onbeforeunload = function(e) {
            $('#chat').val($('#chat').val() + 'Bye bye...\\n');
            ws.close(1000, '%(username)s left the room');

            if(!e) e = window.event;
            e.stopPropagation();
            e.preventDefault();
          };
          ws.onmessage = function (evt) {
             $('#chat').val($('#chat').val() + evt.data + '\\n');
          };
          ws.onopen = function() {
             ws.send("%(username)s entered the room");
          };
          ws.onclose = function(evt) {
             $('#chat').val($('#chat').val() + 'Connection closed by server: ' + evt.code + ' \"' + evt.reason + '\"\\n');
          };

          $('#send').click(function() {
             console.log($('#message').val());
             ws.send('%(username)s: ' + $('#message').val());
             $('#message').val("");
             return false;
          });
        });
      </script>
    </head>
    <body>
    <form action='#' id='chatform' method='get'>
      <textarea id='chat' cols='35' rows='10'></textarea>
      <br />
      <label for='message'>%(username)s: </label><input type='text' id='message' />
      <input id='send' type='submit' value='Send' />
      </form>
    </body>
    </html>
    """ % {'username': "User%d" % random.randint(0, 100), 'host': self.host, 'port': self.port, 'scheme': self.scheme}

    @cherrypy.expose
    def ws(self):
        cherrypy.log("Handler created: %s" % repr(cherrypy.request.ws_handler))


# ## for daemon.runner
class wstundServertApp():
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
        self.pidfile_path = '/run/wstund.pid'
        self.pidfile_timeout = 5
        self.host = g.config.get('server', 'host')
        self.port = int(g.config.get('server', 'port'))
        # self.ip = g.config.get('server', 'ip')
        # self.netmask = g.config.get('server', 'netmask')

    def run(self):
        g.logger.debug('YMK in wstundServertApp run')
        # ## fro cherrypy
        configure_logger(level=logging.DEBUG)
        cherrypy.config.update({'server.socket_host': self.host,
                                'server.socket_port': self.port,
                                'tools.staticdir.root': os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))})
        WebSocketPlugin(cherrypy.engine).subscribe()
        cherrypy.tools.websocket = WebSocketTool()

        cherrypy.quickstart(Root(self.host, self.port), '', config={
            '/ws': {
                'tools.websocket.on': True,
                'tools.websocket.handler_cls': TunWebSocketHandler
            }
        })


def main():
    if g.config.get('wstund', 'role') != 'server':
        g.logger.error('config role is not server')
        return

    # g.logger.debug('YMK in wstund_client main')

    daemon_runner = runner.DaemonRunner(wstundServertApp())
    daemon_runner.do_action()

# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
