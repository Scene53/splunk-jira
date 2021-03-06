"""
External search command for querying the JIRA SearchRequest XML endpoint

Usage:
  | jira "JQL query" | ... <other splunk commands here> ...

Author: Stephen Sorkin
Author: Russell Uman
"""

import base64
import datetime
import lxml.etree as et
import re
import sys
import time
import urllib
import urllib2

import jiracommon

import splunk.mining.dcutils as dcu
import splunk.Intersplunk as isp

try:
   messages = {}
   logger = dcu.getLogger()

   offset = 0
   count = 100

   splunk_conf = jiracommon.getSplunkConf()
   keys = splunk_conf.get('keys', '').split(',')
   time_keys = splunk_conf.get('time_keys', '').split(',')
   custom_keys = splunk_conf.get('custom_keys', '').split(',')

   local_conf = jiracommon.getLocalConf()

   hostname = local_conf.get('jira', 'hostname')
   username = local_conf.get('jira', 'username')
   password = local_conf.get('jira', 'password')

   if len(sys.argv) > 1:
      jql = sys.argv[1]
   else:
      jql = "project=%s" % stanza.get('default_project')

   while True:
      query = urllib.urlencode({'jqlQuery':jql, 'tempMax':count, 'pager/start':offset})
      url = "https://%s/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml?%s" % (hostname, query)
      request = urllib2.Request(url)
      logger.info(url)

      request.add_header('Authorization', "Basic %s" % base64.b64encode("%s:%s" % (username, password)))
      result = urllib2.urlopen(request)

      root = et.parse(result)

      results = []
      added_count = 0
      for elem in root.iter('item'):
         added_count = added_count + 1
         row = {}

         for k in keys:
            v = elem.xpath(k)
            if len(v) > 0:
               row[k] = ",".join([val.text for val in v])
         
         for k in time_keys:
            v = elem.xpath(k)
            if len(v) == 1:
               row[k] = v[0].get("seconds")

         for k in custom_keys:
            v = elem.xpath('customfields/customfield/customfieldvalues/customfieldvalue[../../customfieldname/text() = "%s"]' % k)
            if len(v) > 0:
               row[k] = ",".join([val.text for val in v])

            v = elem.xpath('customfields/customfield/customfieldvalues/label[../../customfieldname/text() = "%s"]' % k)
            if len(v) > 0:
               row[k] = ",".join([val.text for val in v])

         # Add a _time field by converting updated into a timestamp. This is helpful if you're piping results to collect.
         if 'updated' in keys:
            updated = re.sub(r' (\+|-)\d+$', '', elem.findtext('updated')) 
            timestamp = time.mktime(datetime.datetime.strptime(updated, "%a, %d %b %Y %H:%M:%S").timetuple())
            row['_time'] = timestamp

         row['host'] = hostname
         row['index'] = 'jira'
         row['source'] = 'jql'
         row['sourcetype'] = 'jira'
         row['_raw'] = row

         results.append(row)

      if added_count > 0:
         isp.outputResults(results)
         offset = offset + added_count

      if added_count < count:
         break

except Exception, e:
   logger.exception(str(e))
   isp.generateErrorResults(str(e))