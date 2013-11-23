#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
import SimpleHTTPServer, SocketServer, socket, cgi, urlparse
import sys, logging, signal, psycopg2, time
from dbconf import *
from worker import BOARD

LOGFILE = ''
LOGLEVEL = logging.DEBUG

try:
	DBCONN = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, password=DB_PASS)
except:
	logging.error("UNABLE TO CONNECT TO DATABASE, TERMINATING!")
	sys.exit(1)

def time_unix2http(unix_time_int):
	time_tuple = time.gmtime(unix_time_int)
	return time.strftime('%a, %d %b %Y %H:%M:%S GMT', time_tuple)


class webDispatcher(SimpleHTTPServer.SimpleHTTPRequestHandler):
	#server_version = "TornadoServer/2.3"
	
	def req_hello(self):
		self.send_response(200)
		self.send_header("Content-Type", "text/plain")
		self.end_headers()       
		self.wfile.write("Hello World!")
		self.wfile.close()
		
	def req_s(self, b, t):
		try:
			board = str(b[0])
			thread = int(t[0])
		except (IndexError, ValueError):
			self.send_response(400)
			self.end_headers()
			self.wfile.close()
			return
		
		if board != BOARD:
			self.send_response(404)
			self.end_headers()
			self.wfile.close()
			return
		
		cur = DBCONN.cursor()
		try:
			cur.execute('SELECT array_to_json(sagedlist), lastmod FROM sage WHERE threadno = (%s) LIMIT 1', (thread, ))
		except:
			logging.error("ERROR WHILE RUNNING QUERY")
			DBCONN.rollback()
			self.send_response(505)
			self.end_headers()
			self.wfile.close()
			return
	
		data = cur.fetchone()
		DBCONN.commit()
		
		if not data:
			self.send_response(404)
			self.end_headers()
			self.wfile.close()
			return
		
		lastmod = time_unix2http(data[1])
		if 'If-Modified-Since' in self.headers and self.headers['If-Modified-Since'] == lastmod:
			self.send_response(304)
			self.end_headers()
			self.wfile.close()
			return
			
		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Last-Modified", lastmod)
		self.end_headers()       
		self.wfile.write(data[0])
		self.wfile.close()

	def do_HEAD(self):
		self.send_response(501)
		self.end_headers()
		self.wfile.close()
			
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
