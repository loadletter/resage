import urllib2, json, logging, time, calendar
from threading import Thread
from collections import deque as Deque

BOARD = "a"
CATALOG_URL = "http://api.4chan.org/" + BOARD + "/catalog.json"
LOGLEVEL = logging.DEBUG
LOGFILE = ''
USERAGENT = "Mozilla/5.0 (X11; Linux i686; rv:18.0) Gecko/20100101 Firefox/18.0"

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
			logging.info("CKDL - 404 Error: %s",url)
			return {'lastmodified' : lastmod, 'data' : '', 'error' : 404}
		else:
			logging.error("CKDL - %i %s: %s", e.code, e.msg, url)
			return {'lastmodified' : lastmod, 'data' : '', 'error' : e.code}
	else:
		logging.debug("CKDL - Downloaded: %s",url)
		return {'lastmodified' : lastmodified, 'data' : data}
	
def UpdateCatalog(catalog_list):
	for i in range(0, 3):
		if len(catalog_list) > 1:
			raw_data = Checkb4Download(CATALOG_URL, time_unix2http(catalog_list[0]['mod']))
		else:
			raw_data = Checkb4Download(CATALOG_URL)
		
		if raw_data['data'] == '':
			if 'error' in raw_data:
				logging.error("Couln't update catalog")
			else:
				logging.debug("Catalog not modified")
			time.sleep(20)
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

#def GetSagedPosts(catalog_list):
#	current_catalog = catalog_list[0]['d']
#	cat_last_modified = catalog_list[0]['mod']
#	catalog_positiion = 0
#	for t in current_catalog:
#		if t['replies'] > 0:
#			last_mod = t['last_replies'][-1]['time']
#		else:
#			last_mod = t['time']
#TODO: store the catalogs in an efficiant way for comparing threads and think of a way to compare everything
#- 1)create a list of tuples like (index, last_mod)
#  2)sort the list by last_mod
#  3)iterate over the list and chech that index is in the same order
#  4)if not in the same order (compare index in the tuple with current index or a simple >) check if previous posts in that thread are saged too

def main():
	catalog_list = Deque()
	
	for i in range(0, 10):
		UpdateCatalog(catalog_list)
		print AvgPostCount(catalog_list)
		time.sleep(5)
	
	
	#try:
		#while True:
			#CatalogThreadDaemon(op_list)
			#catalog_list = []
			#for thr in op_list:
				#catalog_list.append(thr['no'])
			
			#dlthreads = []
			#for n in range(0,4):
				#DlThread = Thread(target=DownloadThreadDaemon, args=(op_list, thread_dict, dead_list))
				#DlThread.daemon=True
				#DlThread.start()
				#dlthreads.append(DlThread)
			#for dlthread in dlthreads:
				#dlthread.join()

			##DownloadThreadDaemon(op_list, thread_dict, dead_list)
			#DBThreadDaemon(dead_list, thread_dict, op_list, catalog_list)
			#sleep(UPDATE_DELAY)

	#except (KeyboardInterrupt, SystemExit):
		#logging.warn("Received keyboard interrupt! , terminating threads.")

if __name__ == '__main__':
	if LOGFILE == '':
		logging.basicConfig(level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	else:
		logging.basicConfig(filename=LOGFILE, level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
	main()
