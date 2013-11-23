import urllib2, json, logging, time, calendar, psycopg2, sys, signal
from collections import deque as Deque
from dbconf import *

BOARD = "a"
BUMPLIMIT = 500 #300 for jp
UPDATEINTERVAL = 5
DBMAXENTRIES = 3000

CATALOG_URL = "http://api.4chan.org/" + BOARD + "/catalog.json"
LOGLEVEL = logging.DEBUG
LOGFILE = ''
USERAGENT = "Mozilla/5.0 (sagebot)"
APPRUNNING = True

DB_EXEC_UPSERT = """WITH new_values (threadno, sagedlist, lastmod) AS (
  values 
     (%s, %s, %s)

),
upsert AS
( 
    update sage s
        SET sagedlist = ARRAY(SELECT DISTINCT UNNEST(array_append(s.sagedlist, nv.sagedlist)) ORDER BY 1),
            lastmod = nv.lastmod
    FROM new_values nv
    WHERE s.threadno = nv.threadno
    RETURNING s.*
)
INSERT INTO sage (threadno, sagedlist, lastmod)
SELECT threadno, ARRAY[sagedlist], lastmod
FROM new_values
WHERE NOT EXISTS (SELECT 1 
                  FROM upsert up
                  WHERE up.threadno = new_values.threadno)
"""
#UPDATE test SET sagedlist = ARRAY(SELECT DISTINCT UNNEST(array_append(sagedlist, 148)) ORDER BY 1) WHERE threadno = 8015616;
#adds a number to the postgre array, removing duplicates

def time_http2unix(http_time_string):
	time_tuple = time.strptime(http_time_string, '%a, %d %b %Y %H:%M:%S GMT')
	return calendar.timegm(time_tuple)
	
def time_unix2http(unix_time_int):
	time_tuple = time.gmtime(unix_time_int)
	return time.strftime('%a, %d %b %Y %H:%M:%S GMT', time_tuple)

def Checkb4Download(url,lastmod=''):
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
			logging.debug("CKDL - Not modified: %s",url)											
			return {'lastmodified' : lastmod, 'data' : ''}	#not modified
		elif e.code == 404:
			logging.error("CKDL - 404 Error: %s",url)
			return {'lastmodified' : lastmod, 'data' : '', 'error' : 404}
		else:
			logging.error("CKDL - %i %s: %s", e.code, e.msg, url)
			return {'lastmodified' : lastmod, 'data' : '', 'error' : e.code}
	else:
		logging.debug("CKDL - Downloaded: %s",url)
		return {'lastmodified' : lastmodified, 'data' : data}
	
def UpdateCatalog(catalog_list):
	while True:
		if len(catalog_list) > 1:
			raw_data = Checkb4Download(CATALOG_URL, time_unix2http(catalog_list[0]['mod']))
		else:
			raw_data = Checkb4Download(CATALOG_URL)
		
		if raw_data['data'] == '':
			if 'error' in raw_data:
				logging.error("Couln't update catalog")
			else:
				logging.debug("Catalog not modified")
			time.sleep(UPDATEINTERVAL * 2)
			continue
		
		catalog = json.loads(raw_data['data'])
		catalog_threads = []
		for i in range(0, 10): #10 pages
			thread_index = catalog[i][u'threads']
			assert catalog[i][u'page'] == i
			for single_thread in thread_index:
				catalog_threads.append(single_thread)
		
		catalog_list.appendleft({'d' : catalog_threads, 'mod' : time_http2unix(raw_data['lastmodified'])})
		while len(catalog_list) > 5: #older catalogs to keep in memory
			catalog_list.pop()
		
		logging.debug("Updated catalog: %i threads (%i catalogs)", len(catalog_threads), len(catalog_list))
		break


def postcount(x):
	count = 0
	for t in x['d']:
		count += t['replies']
	return count	

def AvgPostCount(catalog_list):
	if len(catalog_list) < 1:
		return 0
	count_list = map(postcount, catalog_list)
	count_sum = reduce(lambda x, y: x + y, count_list)
	return count_sum / len(count_list)

def GetSagedPosts(catalog_list, page=0):
	current_catalog = catalog_list[page]['d']
	cat_last_modified = catalog_list[page]['mod']
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
		if curth[0] > preth[0] and curth[2] < BUMPLIMIT and curth[1] != preth[1]:
			logging.debug("%s %i - %i %s" % (repr(curth), lst_i, lst_i - 1, repr(preth)))
			#TODO: code below is mostly useless
			if curth[2] > 0:
				for prev_reply in current_catalog[curth[0]]['last_replies']:
					if prev_reply['time'] > preth[1]:
						logging.debug("%i --> %i time %i" % (prev_reply['resto'], prev_reply['no'], prev_reply['time']))
						sagedlist.append((prev_reply['resto'], prev_reply['no'], curth[1]))
	
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

def main():
	try:
		conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, password=DB_PASS)
	except:
		logging.error("UNABLE TO CONNECT TO DATABASE, TERMINATING!")
		sys.exit(1)
	
	initcurs = conn.cursor()
	initcurs.execute("CREATE TABLE IF NOT EXISTS sage (threadno INTEGER PRIMARY KEY, sagedlist INTEGER[], lastmod INTEGER)")
	conn.commit()
	initcurs.close()
	
	catalog_list = Deque()
		
	for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
		signal.signal(sig, sig_handler)
	
	while APPRUNNING:
		time.sleep(UPDATEINTERVAL)
		UpdateCatalog(catalog_list)
		#print AvgPostCount(catalog_list)
		data = GetSagedPosts(catalog_list)
		cur = conn.cursor()
		try:
			cur.executemany(DB_EXEC_UPSERT, data)
		except:
			logging.error("ERROR EXECUTING UPSERT!")
			conn.rollback()
		else:
			conn.commit()

		try:
			cur.execute("DELETE FROM sage WHERE threadno IN (SELECT threadno FROM sage ORDER BY lastmod DESC OFFSET (%s))", (DBMAXENTRIES,))
		except:
			logging.error("ERROR EXECUTING DATABASE CLEANUP!")
			conn.rollback()
		else:
			conn.commit()
		cur.close()
	
	logging.info("Avg Postcount: %i" % AvgPostCount(catalog_list))
	conn.close()
	
	#on the other program SELECT array_to_json(sagedlist) FROM test WHERE threadno = 8015616;
	

if __name__ == '__main__':
	if LOGFILE == '':
		logging.basicConfig(level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	else:
		logging.basicConfig(filename=LOGFILE, level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	main()
