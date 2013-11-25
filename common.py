import time, calendar


BOARDS = {"a" : (500, 10, 3000), "jp" : (300, 15, 3000)}
#{board : (bumplimit, refresh_interval, db_maxentries)}


def time_http2unix(http_time_string):
	time_tuple = time.strptime(http_time_string, '%a, %d %b %Y %H:%M:%S GMT')
	return calendar.timegm(time_tuple)

def time_unix2http(unix_time_int):
	time_tuple = time.gmtime(unix_time_int)
	return time.strftime('%a, %d %b %Y %H:%M:%S GMT', time_tuple)
