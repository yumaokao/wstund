# -*- coding: utf-8 -*-
import config as g
import os
import sys
import random
import select
import logging
import cherrypy
from time import sleep
from lockfile import LockTimeout
from daemon.runner import DaemonRunner, DaemonRunnerStopFailureError
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
            tun.mtu = int(g.config.get('server', 'mtu'))
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
            if m.is_binary:
                self.tun.write(m.data)
            else:
                cherrypy.log("YMK in received_message: {0}".format(m))

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
      <script type='application/javascript' src='js/cbuffer.js'></script>
      <script type='application/javascript'>
        $(document).ready(function() {

          // websocket = '%(scheme)s://%(host)s:%(port)s/ws';
          websocket = '%(scheme)s://' + window.location.host + '/ws';
          console.log(window.location);
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

          var Packet = function (src, dst, size, time) {
            this.src = src;
            this.dst = dst;
            this.size = size;
            this.time = time;
          }
          var pcbuffs = CBuffer(10);

          window.onbeforeunload = function(e) {
            ws.close(1000, 'wstund monitor leave');

            if(!e) e = window.event;
            e.stopPropagation();
            e.preventDefault();
          };
          ws.onmessage = function (evt) {
             // console.log("ws.onmessage packet size " + evt.data.size);
             var reader = new FileReader();
             reader.onload = function(event) {
                arrayBufferNew = this.result;
                pdata  = new Uint8Array(this.result);
                // console.log("data length " + pdata.length);
                /* for (i = 0; i < pdata.length; i++) {
                    console.log("data[ " + i + "] " + pdata[i]);
                } */

                src_ip = pdata[12] + '.' + pdata[13] + '.' + pdata[14] + '.' + pdata[15];
                dst_ip = pdata[16] + '.' + pdata[17] + '.' + pdata[18] + '.' + pdata[19];
                // console.log("src " + src_ip + " dst " + dst_ip);
                pcbuffs.push(new Packet(src_ip, dst_ip, pdata.length, Date.now()));
                // console.log("pcbuffs last " + pcbuffs.last().time);

                $('#pcbs').empty();
                for (i = 0; i < pcbuffs.length; i++) {
                    var p = pcbuffs.get(i);
                    if (p == undefined)
                        break;
                    var d = new Date(p.time);
                    var appstr = "<tr><td>" + p.src + "</td><td>";
                    appstr += p.dst + "</td><td>" + p.size + "</td><td>";
                    appstr += d + "</td></tr>";
                    $('#pcbs').append(appstr);
                }
             }
             reader.readAsArrayBuffer(evt.data)
          };
          ws.onopen = function() {
             // ws.send("%(username)s entered the room");
             console.log("ws.onopen could send messages");
             $('#status').text("wstund status: CONNECTED");
          };
          ws.onclose = function(evt) {
             $('#status').text("wstund status: DISCONNECTED");
          };
        });
      </script>
    </head>
    <body>
    <h2>wstund monitor (%(scheme)s://%(host)s:%(port)s)</h2>
    <h3 id='status'>wstund status: </h3>
    <table>
    <thead><tr><th>src</th><th>dst</th><th>len</th><th>time</th></tr></thead>
    <tbody id='pcbs'>
    </tbody>
    </table>
    </body>
    </html>
    """ % {'username': "wstund", 'host': self.host, 'port': self.port, 'scheme': self.scheme}

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
        self.pidfile_path = g.config.get('wstund', 'pidpath')
        self.pidfile_timeout = int(g.config.get('wstund', 'pidtimeout'))
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
            },
            '/js': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'js'
            }
        })


def main():
    if g.config.get('wstund', 'role') != 'server':
        g.logger.error('config role is not server')
        return

    # g.logger.debug('YMK in wstund_client main')

    daemon_runner = DaemonRunner(wstundServertApp())
    try:
        daemon_runner.do_action()
    except (DaemonRunnerStopFailureError, LockTimeout) as e:
        g.logger.error(e)
        sys.exit(e)

# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
