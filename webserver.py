#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
import SimpleHTTPServer, SocketServer, socket, cgi, urlparse
import sys, logging, signal, psycopg2
from dbconf import *

LOGFILE = ''
LOGLEVEL = logging.DEBUG

class webDispatcher(SimpleHTTPServer.SimpleHTTPRequestHandler):

	def req_hello(self):
		self.send_response(200)
		self.send_header("Content-Type", "text/plain")
		self.end_headers()       
		self.wfile.write("Hello World!")
		self.wfile.close()
		
	def req_s(self, b, t):
		board = b[0]
		thread = t[0]
		
		self.send_response(200)
		self.send_header("Content-Type","application/json")
		self.end_headers()       
		self.wfile.write('Hello. Go to <a href="/form">the form<a>.')

			
	def do_GET(self):
		params = cgi.parse_qs(urlparse.urlparse(self.path).query)
		action = urlparse.urlparse(self.path).path[1:]
		if action=="": action="hello"
		methodname = "req_"+action
		try:
			getattr(self, methodname)(**params)
		except AttributeError:
			self.send_response(404)
			self.end_headers()
			self.wfile.close()
		except TypeError:  # URL not called with the proper parameters
			self.send_response(400)
			self.end_headers()
			self.wfile.close()

		
def sig_handler(signum=None, frame=None):
	logging.warning("Signal handler called with signal %i, shutting down", signum)
	logging.warning("Stopping")
	sys.exit(0)
    
def main():
	if len(sys.argv) != 2:
		logging.error("Wrong arguments %s", repr(sys.argv))
		sys.exit(1)
	
	for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
		signal.signal(sig, sig_handler)
	port = int(sys.argv[1])
	hostname = socket.gethostbyaddr(socket.gethostname())[0]
	httpd = SocketServer.ThreadingTCPServer(('', port), webDispatcher)
	logging.warning(u"Server listening at http://%s:%s" % (hostname, port))
	httpd.allow_reuse_address = True
	httpd.serve_forever()


if __name__ == '__main__':
	if LOGFILE == '':
		logging.basicConfig(level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	else:
		logging.basicConfig(filename=LOGFILE, level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	main()
