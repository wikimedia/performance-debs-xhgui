#!/usr/bin/python3
#
# This script can be used to convert a MongoDB dump in JSON format to
# a file which can be piped to the MariaDB commandline.  This was
# successfully used at the Wikimedia Foundation, but your mileage may
# vary so proceed with caution.

from dateutil.parser import isoparse
import json
import sys

def convert_mongo(value):
	if not isinstance(value, dict):
		return value
	if len(value) == 1:
		type = list(value.keys())[0]
		if type == '$numberLong':
			return int(value[type])
		elif type == '$oid':
			return str(value[type])
		elif type == '$date':
			value = value[type]
			if not isinstance(value, str):
				return value
			else:
				return isoparse(value).timestamp()
	for k, v in value.items():
		value[k] = convert_mongo(v)
	return value

def convert_rows(input):
	for line in input:
		old = json.loads(line)
		new = dict()
		new['id'] = old['_id']['$oid']
		profile = convert_mongo(old['profile'])
		if not isinstance(profile, dict) or len(profile) == 0:
			continue
		new['profile'] = json.dumps(profile)
		new['url'] = old['meta']['url']
		env = convert_mongo(old['meta']['env'])
		new['ENV'] = json.dumps(env)
		server = convert_mongo(old['meta']['SERVER'])
		if 'HOSTNAME' in env:
			server['HOSTNAME'] = env['HOSTNAME']
		new['SERVER'] = json.dumps(server)
		new['GET'] = json.dumps(convert_mongo(old['meta']['get']))
		new['simple_url'] = old['meta']['simple_url']
		new['request_ts_micro'] = convert_mongo(old['meta']['request_ts']) / 1000.0
		new['request_ts'] = int(new['request_ts_micro'])
		new['request_date'] = old['meta']['request_date']
		for field in ('ct', 'wt', 'cpu', 'mu', 'pmu'):
			if 'main()' in profile and field in profile['main()']:
				new['main_'+field] = profile['main()'][field]
			else:
				new['main_'+field] = 0
		yield new

def quote(s):
	q = {
		'\x00': '\\0',
		"'": "\\'",
		'"': '\\"',
		'\b': '\\b',
		'\n': '\\n',
		'\r': '\\r',
		'\t': '\\t',
		'\x1a': '\\Z',
		'\\': '\\\\',
	}
	if isinstance(s, str):
		return "'" + ''.join([q[c] if c in q else c for c in s]) + "'"
	else:
		s = str(s)
	return s

def make_statement(row):
	columns = row.keys()
	return 'INSERT IGNORE INTO xhgui (%s) VALUES (%s);\n' % (
		', '.join(columns),
		', '.join([quote(row[col]) for col in columns]),
	)


def main(input, output):
	output.write('DELETE FROM xhgui WHERE request_ts = 2147483647;\n')
	for row in convert_rows(input):
		output.write(make_statement(row))

if __name__ == "__main__":
	main(sys.stdin, sys.stdout)
