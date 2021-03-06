import cherrypy
import os, sys, logging, signal, time
import psycopg2, psycopg2.pool
from common import BOARDS, time_unix2http
from dbconf import *
from contextlib import contextmanager

try:
	DBCONN = psycopg2.pool.ThreadedConnectionPool(1, 8, dbname=DB_NAME, user=DB_USER, host=DB_HOST, password=DB_PASS)
except:
	cherrypy.log("UNABLE TO CONNECT TO DATABASE, TERMINATING!", context='DATABASE', severity=logging.ERROR, traceback=False)
	sys.exit(1)

try:
	from common import INDEX_MOTD
except ImportError:
	INDEX_MOTD = u"Hello World!"

@contextmanager
def getcursor():
	con = DBCONN.getconn()
	try:
		yield con.cursor()
	except:
		cherrypy.log("Error while running SELECT", context='DATABASE', severity=logging.ERROR, traceback=False)
		con.rollback()
	finally:
		con.commit()
		DBCONN.putconn(con)


class Api(object):
	@cherrypy.expose
	def default(self, board, thread):
		if not thread.isdigit():
			cherrypy.response.status = 400
			return ""
		
		if board not in BOARDS:
			cherrypy.response.status = 404
			return ""
		
		for i in range(0, 4):
			try:
				with getcursor() as cur:
					cur.execute('SELECT array_to_json(sagedlist), lastmod FROM sage WHERE threadno = (%s) AND board = (%s) LIMIT 1', (thread, board))
					data = cur.fetchone()
			except psycopg2.InterfaceError:
				if i == 3:
					cherrypy.response.status = 500
					return "Database connection error"
				if not 'data' in locals():
					continue
			break
		
		if not data:
			cherrypy.response.status = 404
			return ""
		
		lastmod = time_unix2http(data[1])
		if 'If-Modified-Since' in cherrypy.request.headers and cherrypy.request.headers['If-Modified-Since'] == lastmod:
			cherrypy.response.status = 304
			return
		
		cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		cherrypy.response.headers['Last-Modified'] = lastmod
		
		return str(data[0])


class Root(object):
	api = Api()
	@cherrypy.expose
	def index(self):
		cherrypy.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
		return INDEX_MOTD.encode('utf-8')
	
	
def main():
	conf_path = os.path.dirname(os.path.abspath(__file__))
	conf_path = os.path.join(conf_path, "webserver.conf")
	if os.path.isfile(conf_path):
		cherrypy.config.update(conf_path)
	else:
		cherrypy.log("Configuration file NOT Found: %s" % conf_path, context='CONFIG', severity=logging.WARNING, traceback=False)
	cherrypy.config.update({'server.socket_host' : '0.0.0.0', })
	cherrypy.config.update({'server.socket_port' : int(os.environ.get('PORT', '5000')), })
	cherrypy.quickstart(Root())

if __name__ == '__main__':
	main()
