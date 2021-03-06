"""
External search command for querying the JIRA SOAP API 

Usage:
  | jirasoap search "text search" | ... <other splunk commands here> ... # text search
  | jirasoap jqlsearch "JQL query" | ... <other splunk commands here> ... # JQL search*
  | jirasoap issues <filter_id> | ... <other splunk commands here> ... # filter search
  | jirasoap filters | ... <other splunk commands here> ... # list all filters (to get ids for issues command)

* The jqlsearch doesn't handle '=' very well - splunk parses these as options.
Instead of saying "project = foo AND status = Open" say "project in (foo) AND status in (Open)".
Or use the SearchRequest XML command instead

Author: Fred de Boer
Author: Jeffrey Isenberg
Author: Russell Uman
"""

import splunk.Intersplunk as isp
import splunk.mining.dcutils as dcu

import jiracommon
import logging
import sys
import time

from suds.client import Client

try:
    messages = {}
    logging.getLogger('suds').setLevel(logging.INFO)
    
    logger = dcu.getLogger()
    
    local_conf = jiracommon.getLocalConf()
    
    hostname = local_conf.get('jira', 'hostname')
    port = local_conf.get('jira', 'port')
    proto = local_conf.get('jira', 'porotocol')
    baseURL = local_conf.get('jira', 'baseURL')
    username = local_conf.get('jira', 'username')
    password = local_conf.get('jira', 'password')
    
    url = "%s://%s:%s/%s/rpc/soap/jirasoapservice-v2?wsdl" % (proto, hostname, port, baseURL)
    logger.info(url)
    client = Client(url)
    auth = client.service.login(username, password)
    
    keywords, options = isp.getKeywordsAndOptions()
    
    logger.info('keywords: ' + str(keywords))
    logger.info('options: ' + str(options))
    
    if keywords[0] == 'filters':
        filters =  client.service.getFavouriteFilters(auth)

        keys = (('author', None), ('id', None), ('name', None))
        
        results = []
        for jfilter in filters:
            row = jiracommon.flatten(jfilter, keys)
            logger.info(time.time())
            row['_time'] = int(time.time())
            row['_raw'] = row
            results.append(row)
        isp.outputResults(results)
        sys.exit(0)

    if keywords[0] == 'issues':
        issues = client.service.getIssuesFromFilter(auth, keywords[1])
    # TODO this 1000 issue max isn't working as expected - if there are more than 1000 results, no results are returned
    elif keywords[0] == 'search':
        issues = (client.service.getIssuesFromTextSearch(auth, keywords[1], 1000) )
    elif keywords[0] == 'jqlsearch':
        issues = (client.service.getIssuesFromJqlSearch(auth, keywords[1], 1000) )
    
    statuses = jiracommon.api_to_dict(client.service.getStatuses(auth))
    resolutions = jiracommon.api_to_dict(client.service.getResolutions(auth))
    priorities = jiracommon.api_to_dict(client.service.getPriorities(auth))
    
    resolutions[None] = 'UNRESOLVED'
    
    results = []

    # TODO get keys from configuration
    keys = (('assignee', None),
          ('description', None),
          ('key', None),
          ('summary', None),
          ('reporter', None),
          ('fixVersions', None),
          ('status', statuses),
          ('resolution', resolutions),
          ('priority', priorities),
          ('project', None),
          ('type', None),
          ('created', None),
          ('duedate', None),
          ('updated', None))
    
    
    customFields = {"customfield_10730" : "Cost", "customfield_10630" : "Product" }

    for issue in issues:
        row = jiracommon.flatten(issue, keys)
        # Handle custom fields
        for f in issue['customFieldValues']:
            if f['customfieldId'] in customFields:
                row[customFields[f['customfieldId']]] = f['values']
                
        row['_time'] = int(time.mktime(time.strptime(row['updated'], '%Y-%m-%d %H:%M:%S')))
        row['host'] = hostname
        row['index'] = 'jira'
        row['source'] = keywords[1]
        row['sourcetype'] = 'jira_soap'
        row['_raw'] = row

        results.append(row)

    isp.outputResults(results)

except Exception, e:
    logger.exception(str(e))
    isp.generateErrorResults(str(e))