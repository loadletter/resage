import urllib2, json, logging, time, calendar, sys, signal
import psycopg2, psycopg2.pool
from collections import deque as Deque
from contextlib import contextmanager
from common import BOARDS, time_http2unix, time_unix2http
from dbconf import *

#BOARDS = {board : (bumplimit, refresh_interval, db_maxentries)}

CATALOG_URL = "http://a.4cdn.org/%s/catalog.json"
LOGLEVEL = logging.DEBUG
LOGFILE = ''
USERAGENT = "Mozilla/5.0 (sagebot)"
APPRUNNING = True

DB_EXEC_UPSERT = """WITH new_values (threadno, sagedlist, lastmod, board) AS (
  values 
     (%s, %s, %s, %s)

),
upsert AS
( 
    update sage s
        SET sagedlist = ARRAY(SELECT DISTINCT UNNEST(array_append(s.sagedlist, nv.sagedlist)) ORDER BY 1),
            lastmod = nv.lastmod
    FROM new_values nv
    WHERE s.threadno = nv.threadno AND s.board = nv.board
    RETURNING s.*
)
INSERT INTO sage (threadno, sagedlist, lastmod, board)
SELECT threadno, ARRAY[sagedlist], lastmod, board
FROM new_values
WHERE NOT EXISTS (SELECT 1 
                  FROM upsert up
                  WHERE up.threadno = new_values.threadno AND up.board = new_values.board)
"""
#UPDATE test SET sagedlist = ARRAY(SELECT DISTINCT UNNEST(array_append(sagedlist, 148)) ORDER BY 1) WHERE threadno = 8015616;
#adds a number to the postgre array, removing duplicates

def time_http2unix(http_time_string):
	time_tuple = time.strptime(http_time_string, '%a, %d %b %Y %H:%M:%S GMT')
	return calendar.timegm(time_tuple)

def Checkb4Download(url, lastmod=''):
	header = {'User-Agent': USERAGENT, }
	req = urllib2.Request(url, None, header)
	if lastmod != '':
		req.add_header('If-Modified-Since', lastmod)
	try:
		res = urllib2.urlopen(req)
		data = res.read()
		lastmodified = res.headers.get('Last-Modified')
		res.close()
	except (urllib2.HTTPError, urllib2.URLError), e:
		if e.code == 304 and lastmod != '':
			logging.debug("Not modified: %s",url)											
			return {'lastmodified' : lastmod, 'data' : ''}	#not modified
		else:
			logging.error("HTTP Error %i %s: %s", e.code, e.msg, url)
			return {'lastmodified' : lastmod, 'data' : '', 'error' : e.code}
	else:
		logging.debug("Downloaded: %s",url)
		return {'lastmodified' : lastmodified, 'data' : data}
	
def UpdateCatalog(catalog_lists, board, err_time_bonus):
	catalog_list = catalog_lists[board]
	if len(catalog_list) > 1:
		raw_data = Checkb4Download(CATALOG_URL % board, time_unix2http(catalog_list[0]['mod']))
	else:
		raw_data = Checkb4Download(CATALOG_URL % board)
	
	if raw_data['data'] == '':
		if 'error' in raw_data:
			logging.error("Couln't update catalog for /%s/", board)
		else:
			logging.debug("Catalog not modified for /%s/", board)
		return err_time_bonus
	
	try:
		catalog = json.loads(raw_data['data'])
	except (ValueError, TypeError):
		logging.error("JSON Error parsing %s", CATALOG_URL % board)
		return err_time_bonus * 2
		
	catalog_threads = []
	for i in range(0, 10): #10 pages
		thread_index = catalog[i][u'threads']
		assert catalog[i][u'page'] == i
		for single_thread in thread_index:
			catalog_threads.append(single_thread)
	
	catalog_list.appendleft({'d' : catalog_threads, 'mod' : time_http2unix(raw_data['lastmodified'])})
	while len(catalog_list) > 5: #older catalogs to keep in memory
		catalog_list.pop()
	
	logging.debug("Updated /%s/ catalog: %i threads (%i catalogs)", board, len(catalog_threads), len(catalog_list))
	return 0


def GetSagedPosts(catalog_lists, board):
	catalog_list = catalog_lists[board]
	current_catalog = catalog_list[0]['d']
	cat_last_modified = catalog_list[0]['mod']
	modtime_list = []
	for cat_index, t in enumerate(current_catalog):
		if t['replies'] > 0:
			last_mod = t['last_replies'][-1]['time']
		else:
			last_mod = t['time']
		modtime_list.append((cat_index, last_mod, t['replies']))
	
	#for xd in modtime_list: print repr(xd)
	
	modtime_list.sort(key=lambda x: x[1])
	
	#print "--------------"
	#for xd in modtime_list: print repr(xd)
	
	sagedlist = [] #list of (threadno, postno, last_modified)
	for lst_i in range(1, len(modtime_list)):
		curth = modtime_list[lst_i]
		preth = modtime_list[lst_i - 1]
		if curth[0] > preth[0] and curth[2] < BOARDS[board][0] and curth[1] != preth[1]:
			logging.debug("%s %i - %i %s" % (repr(curth), lst_i, lst_i - 1, repr(preth)))
			#TODO: code below is mostly useless
			if curth[2] > 0:
				for prev_reply in current_catalog[curth[0]]['last_replies']:
					if prev_reply['time'] > preth[1]:
						logging.debug("%i --> %i time %i" % (prev_reply['resto'], prev_reply['no'], prev_reply['time']))
						sagedlist.append((prev_reply['resto'], prev_reply['no'], curth[1], board))
	
	return sagedlist

#GetSagedPosts
#- 1)create a list of tuples like (index, last_mod, replies)
#  2)sort the list by last_mod
#  3)iterate over the list and chech that index is in the same order
#  4)if not in the same order and not over the bump limit and times aren't the same then check if previous posts in that thread are saged too
#-TODO: this works only if the last post is saged, find a way to compare all of those posts, maybe use the older catalogs in memory


def sig_handler(signum=None, frame=None):
	logging.warning("Signal handler called with signal %i, shutting down", signum)
	APPRUNNING = False
	time.sleep(3)
	logging.warning("Stopping")
	sys.exit(0)

@contextmanager
def getcursor(conn_pool, query_text):
	con = conn_pool.getconn()
	try:
		yield con.cursor()
	except:
		logging.error("DATABASE ERROR EXECUTING %s!", query_text)
		con.rollback()
	finally:
		con.commit()
		conn_pool.putconn(con)

def main():
	try:
		conn = psycopg2.pool.SimpleConnectionPool(1, 2, dbname=DB_NAME, user=DB_USER, host=DB_HOST, password=DB_PASS)
	except:
		logging.error("UNABLE TO CONNECT TO DATABASE, TERMINATING!")
		sys.exit(1)
	
	with getcursor(conn, "CREATE TABLE") as initcurs:
		initcurs.execute("CREATE TABLE IF NOT EXISTS sage (threadno INTEGER PRIMARY KEY, sagedlist INTEGER[], lastmod INTEGER, board VARCHAR(5))")
	
	catalog_lists = {}
	for brd in BOARDS.iterkeys():
		catalog_lists[brd] = Deque()
	
	refresh_timer = {}
	for tmr in BOARDS.iterkeys():
		refresh_timer[tmr] = 0
		
	for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
		signal.signal(sig, sig_handler)
	
	logging.warning("Worker starting...")
	
	while APPRUNNING:
		time.sleep(2)
		for board in BOARDS.iterkeys():
			if refresh_timer[board] < BOARDS[board][1]:
				refresh_timer[board] += 2
				continue

			if not APPRUNNING:
				break
			
			newtime = UpdateCatalog(catalog_lists, board, -BOARDS[board][1])
			data = GetSagedPosts(catalog_lists, board)
			
			logging.debug("Data processed for /%s/", board)
			
			with getcursor(conn, "UPSERT") as cur:
				cur.executemany(DB_EXEC_UPSERT, data)
			
			with getcursor(conn, "DATABASE CLEANUP") as cur:
				cur.execute("DELETE FROM sage WHERE threadno IN (SELECT threadno FROM sage WHERE board = (%s) ORDER BY lastmod DESC OFFSET (%s))", (board, BOARDS[board][2]))
			
			logging.debug("Data inserted in database for /%s/", board)
			
			refresh_timer[board] = newtime
	
	conn.closeall()
	logging.warning("Stopped")


if __name__ == '__main__':
	if LOGFILE == '':
		logging.basicConfig(level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	else:
		logging.basicConfig(filename=LOGFILE, level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	main()
