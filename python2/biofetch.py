#!/usr/bin/env python
# ======================================================================
# A Python 2.x implementation of a BioFetch library.
# ======================================================================
# TODO:
# - Handlers for specific data sources
# - Support for indexing sources [BioPython?]
# - Support for extensions to the BioFetch spec.
# - Response format and content-type checking
# - Command-line support (check for CGI variables)
# - Library/module support
# ======================================================================
# Module imports
import json, platform, os, re, sys, urllib2
from bz2 import BZ2File
from gzip import GzipFile
from StringIO import StringIO
from string import Template
from os.path import exists, isfile

class BioFetch(object):
    '''
    BioFetch based data access library.
    '''
    CLIENT_VERSION = '0'  # Version number for User-agent.

    def __init__(self, configDir=None):
        '''
        Parameters:
        * configDir: optional directory containing a set of BioFetch configuration
        files.
        '''
        if configDir != None:
            self.readConfig(configDir)
        else:
            self.readConfig('etc')

    def fetchData(self, idStr, dbName, dataFormat, resultStyle):
        '''
        Fetch data.

        Returns: the data returned by the back-end service.
        '''
        # Fetch the data stream from the URL.
        (resp, respStream) = self.fetchDataStream(idStr, dbName, dataFormat, resultStyle)
        # Read into a string.
        result = respStream.read()
        # Close the streams.
        respStream.close()
        resp.close()
        return result

    def fetchDataStream(self, idStr, dbName, dataFormat, resultStyle):
        '''
        Fetch data.

        Returns: a HTTP response object and a file handle like object which is used 
        to access the contents of the response.
        '''
        # TODO: Generate service URL.
        url = self._getServiceUrl(idStr, dbName, dataFormat, resultStyle)
        # Fetch the data from the URL.
        return self._httpGetRequest(url)

    def readConfig(self, directory):
        '''
        Read a set of files describing a BioFetch configuration from a directory.
        '''
        if directory != None and os.path.exists(directory):
            settingsFile = directory + '/' + 'settings.json'
            if os.path.isfile(settingsFile):
                self.settings = self._readJSONFile(settingsFile)
                if self.settings['databaseConfig']:
                    if self.settings['databaseConfig'].startswith('/'):
                        databasesFile = self.settings['databaseConfig']
                    else:
                        databasesFile = directory + '/' + self.settings['databaseConfig']
                    if os.path.isfile(databasesFile):
                        self.databases = self._readJSONFile(databasesFile)

    def _readJSONFile(self, filename):
        '''Read data from a JSON format data file.'''
        json_file = open(filename, 'r')
        json_data = json.load(json_file)
        json_file.close()
        return json_data

    def _getUserAgent(self):
        '''Generate an appropriate User-agent string.'''
        urllib_agent = 'Python-urllib/%s' % urllib2.__version__
        user_agent = 'BioFetch/%s (%s; Python %s; %s) %s' % (
            BioFetch.CLIENT_VERSION,
            os.path.basename( __file__ ), 
            platform.python_version(),
            platform.system(),
            urllib_agent
        )
        return user_agent

    def _httpGetRequest(self, url):
        '''
        Fetch a resource specified by a URL using HTTP GET.
        Adds support for HTTP compression.

        Parameters:
        * url: URL of the resource to GET.

        Returns: a HTTP response and a file handle like object for 
        accessing the resource contents.
        '''
        try:
            user_agent = self._getUserAgent()
            http_headers = {
                'User-Agent' : user_agent,
                'Accept-Encoding' : 'gzip, bzip2'
            }
            req = urllib2.Request(url, None, http_headers)
            resp = urllib2.urlopen(req)
            responseStream = self._httpResponseStream(resp)
        except urllib2.HTTPError, ex:
            raise IOError(-1, 'HTTP error', url)
        except urllib2.URLError, e:
            raise IOError(-1, 'URL error', url)
        return (resp, responseStream)

    def _httpResponseStream(self, response):
        '''
        Get a file handle (stream) from a HTTP request response.
        Provides handling bzip2 and gzip compressed HTTP responses.

        Returns: a file handle (stream) like object supporting read()
        and close(). Depending on the nature of the resonse this may be
        a 
        '''
        # TODO: investigate options for fully stream based decompression, see:
        # https://rationalpie.wordpress.com/2010/06/02/python-streaming-gzip-decompression/
        encoding = response.info().getheader('Content-Encoding')
        retStream = None
        # Uncompressed response.
        if encoding == None or encoding == 'identity':
            retStream = response
        # BZIP2 compressed
        elif encoding == 'bzip2':
            retStream = BZ2File(
                fileobj=StringIO(response.read()),
                mode="r"
            )
        # TODO: Add support for 'deflate'
        # GZIP compressed
        elif encoding == 'gzip':
            retStream = GzipFile(
                fileobj=StringIO(response.read()),
                mode="r"
            )
        else:
            raise IOError(0, 'Unsupported Content-Encoding: %s' % (encoding))
        return retStream

    def _expandTemplateString(self, templateStr, idListStr, dbName, dataFormat, resultStyle):
        '''
        Expand a URL or other template string by subsituting the following tokens:
        * ${db}: database name
        * ${format}: data format name
        * ${style}: result style name
        * ${id}: formatted list of entry identifiers
        * ${maxEntries}: maximum number of entries to fetch.
        '''
        paramDict = {
            'db':dbName,
            'id':idListStr,
            'format':dataFormat,
            'style':resultStyle,
            'maxEntries': self.settings['maxEntries']
            }
        template = Template(templateStr)
        expandedStr = template.safe_substitute(paramDict)
        return expandedStr

    def _getServiceUrl(self, idListStr, dbName, dataFormat, resultStyle):
        '''
        Generate a GET URL for a service which will fetch the requested data.
        '''
        databaseConfig = self.databases[dbName]
        # Use the first service that provides the selected format and style.
        for service in databaseConfig['serviceList']:
            if(service['primaryAccess']['accessType'] == 'url' and
               dataFormat in service['dataFormats'] and 
               resultStyle in service['dataFormats'][dataFormat]['resultStyles']):
                break
        if service:
            # Process the identifier list.
            if 'idCharacterCase' in service['primaryAccess']:
                if service['primaryAccess']['idCharacterCase'] == 'upper':
                    idListStr = idListStr.upper()
                elif service['primaryAccess']['idCharacterCase'] == 'lower':
                    idListStr = idListStr.lower()
            if 'idSeparator' in service['primaryAccess']:
                idListStr = re.sub(r'[ +,]+', service['primaryAccess']['idSeparator'], idListStr)
        url = self._expandTemplateString(
            service['primaryAccess']["urlTemplate"], 
            idListStr,
            dbName,
            service['dataFormats'][dataFormat]['value'],
            service['dataFormats'][dataFormat]['resultStyles'][resultStyle]
            )
        return url
