#!/usr/bin/env python
# ======================================================================
# A Python 2.x implementation of a BioFetch library.
# ----------------------------------------------------------------------
# See:
# - GitHub repository: https://github.com/hpmcwill/biofetch_server/
# - OBDA BioFetch specification:
#   https://github.com/OBF/OBDA/tree/master/biofetch
#
# TODO:
# - Handlers for specific data sources
# - Support for indexing sources [BioPython?]
# - Response format and content-type checking
# - Library/module support
# ======================================================================
# Module imports
import json, platform, os, re, sys, urllib2
from abc import ABCMeta, abstractmethod
from bz2 import BZ2File
from gzip import GzipFile
from os.path import exists, isfile
from string import Template
from StringIO import StringIO

class BiofetchError(Exception):
    def __init__(self, errNo, message):
        self.errNo = errNo
        self.message = message

    def __str__(self):
        return 'Error {0}: {1}'.format(self.errNo, self.message)

class AbstractDataSource(object):
    '''
    Abstract definition for a DataSource for use by BioFetch. Classes 
    implementing DataSources must inherit from this abstract class and 
    implement the abstract methods.
    '''
    __metaclass__ = ABCMeta

    @abstractmethod
    def getDataStream():
        '''Get a data stream from the data source.'''
        pass

class UrlDataSource(AbstractDataSource):
    '''
    A URL based DataSource for accessing data sources via:
    - HTTP GET
    - FTP
    '''

    def __init__(self):
        pass

    def _getUserAgent(self):
        '''
        Generate a User-agent string for use in HTTP requests.
        '''
        urllib_agent = 'Python-urllib/%s' % urllib2.__version__
        user_agent = 'BioFetch/%s (%s; Python %s; %s) %s' % (
            BioFetch.CLIENT_VERSION,
            os.path.basename( __file__ ), 
            platform.python_version(),
            platform.system(),
            urllib_agent
        )
        return user_agent

    def getDataStream(self, url):
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

    #
    # Meta-data access methods.
    #

    def getMaxIds(self):
        '''
        Get the maximum number of identifers accepted for a single request.
        '''
        return self.settings['maxEntries']

    def getDatabaseNames(self):
        '''
        Get a list of the names of the available databases.

        Returns:
        A sorted list of database names.
        '''
        databaseNameList = self.databases.keys()
        if databaseNameList != None and len(databaseNameList) > 1:
            databaseNameList.sort()
        return databaseNameList

    def getDbFormatNames(self, dbName):
        '''
        Get a list of the available data format names for a specified database.
        
        Parameters:
        - dbName: the name of the database.

        Returns:
        A sorted list of data format names.
        '''
        # Check database exists in configuration.
        if not dbName in self.databases:
            raise BiofetchError(1, 'Unknown database [' + dbName + ']')
        databaseConfig = self.databases[dbName]
        # Get list of available formats, removing duplicates.
        formatNamesDict = {}
        for service in databaseConfig['serviceList']:
            for formatName in service['dataFormats'].keys():
                formatNamesDict[formatName] = 1
        # Sort the list of data format names.
        formatNamesList = formatNamesDict.keys()
        if formatNamesList != None and len(formatNamesList) > 1:
            formatNamesList.sort()
        return formatNamesList

    def getDbFormatStyleNames(self, dbName, formatName):
        '''
        Get a list of the available result style names for a specified data 
        format of a specifed database.

        Parameters:
        - dbName: the name of the database.
        - formatName: the name of the data format.
        '''
        # Check database exists in configuration.
        if not dbName in self.databases:
            raise BiofetchError(1, 'Unknown database [' + dbName + ']')
        databaseConfig = self.databases[dbName]
        # Get list of available styles, removing duplicates.
        dataFormatFound = False
        styleNamesDict = {}
        for service in databaseConfig['serviceList']:
            if formatName in service['dataFormats']:
                dataFormatFound = True
                for styleName in service['dataFormats'][formatName]['resultStyles'].keys():
                    styleNamesDict[styleName] = 1
        if dataFormatFound == False:
            raise BiofetchError(3, 'Format [{0}] not known for database [{1}])'.format(formatName, dbName))
        # Sort the list of result style names.
        styleNamesList = styleNamesDict.keys()
        if styleNamesList != None and len(styleNamesList) > 1:
            styleNamesList.sort()
        return styleNamesList

    #
    # Data retrival methods.
    #

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

    def fetchDataToStream(self, fh, idStr, dbName, dataFormat, resultStyle):
        '''
        Fetch data to a stream/file.

        Parameters:
        - fh: stream/file handle opened for write.
        - idStr:
        - dbName:
        - dataFormat:
        - resultStyle:

        Returns:
        ?

        Throws:
        - BiofetchError
        '''
        (resp, respStream) = self.fetchDataStream(idStr, dbName, dataFormat, resultStyle)
        contentType = resp.info().getheader('Content-Type')
        # TODO: check for CGI web context.
        print 'Content-Type: {0}\n'.format(contentType)
        for chunk in iter(lambda: respStream.read(self.settings['chunkSize']), ''):
            # TODO: check first chunk for expected format.
            print chunk
        respStream.close()
        resp.close()

    def fetchDataStream(self, idStr, dbName, dataFormat, resultStyle):
        '''
        Fetch data.

        Parameters:
        - idStr: list of entry identifiers as a delimited string.
        - dbName: database name
        - dataFormat: data format name
        - resultStyle: result style name

        Returns: a response object and a file-like object which is used 
        to access the contents of the response.

        Throws:
        - BiofetchError: if requested combination of dbName, dataFormat or 
        resultStyle not found in biofetch configuration.
        '''
        # Handle default values for parameters.
        dbName, dataFormat, resultStyle = self._handleDefaultFetchValues(dbName, dataFormat, resultStyle)
        # Look for data sources matching request.
        serviceDataSources = self._getDataSourcesForFetch(dbName, dataFormat, resultStyle)
        # Loop over matching services trying each to get data.
        for service in serviceDataSources:
            serviceStr = self._resolveServiceTemplate(service, idStr, dbName, dataFormat, resultStyle)
            try:
                # TODO: Load requested DataSource class.
                if service['primaryAccess']['accessType'] == 'url':
                    dataSource = UrlDataSource()
                return dataSource.getDataStream(serviceStr)
            except IOError, e:
                # Record exception and move on to next service.
                pass
        # Failed to find working data source.
        # TODO: Re-throw least severe exception.
        raise e

    def _getDataSourcesForFetch(self, dbName, dataFormat, resultStyle):
        '''
        Get a list of data sources matching a combination of database 
        name, data format name and result style name.

        Parameters:
        - dbName: database name
        - dataFormat: data format name
        - resultStyle: result style name

        Returns:
        A list of data source service configurations which detail how to obatin 
        the requested data format and result style from the required database.

        Throws:
        - BiofetchError if no configurations matching the requested 
        combination of data format and result style are found.
        '''
        databaseConfig = self.databases[dbName]
        serviceDataSources = []
        dataFormatFound = False
        resultStyleFound = False
        for service in databaseConfig['serviceList']:
            if dataFormat in service['dataFormats']:
                dataFormatFound = True
                if resultStyle in service['dataFormats'][dataFormat]['resultStyles']:
                    resultStyleFound = True
                    serviceDataSources.append(service)
        # Check that data format and result style were found.
        if dataFormatFound == False:
            raise BiofetchError(3, 'Format [{0}] not known for database [{1}].'.format(dataFormat, dbName))
        if resultStyleFound == False:
            raise BiofetchError(2, 'Unknown style [{0}]'.format(resultStyle))
        return serviceDataSources

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

    def _handleDefaultFetchValues(self, dbName, dataFormat, resultStyle):
        '''
        Handle mapping of undefined or 'default' fetch parameters to 
        the actual values as defained in the configuration.
        '''
        # Handle default database name.
        if dbName == None or dbName == '' or dbName == 'default':
            dbName = self.settings['defaultDatabase']
        # Find matching service data sources.
        if not dbName in self.databases:
            raise BiofetchError(1, 'Unknown database [' + dbName + ']')
        databaseConfig = self.databases[dbName]
        # Handle default data format name.
        if dataFormat == None or dataFormat == '' or dataFormat == 'default':
            dataFormat = databaseConfig['defaultDataFormat']
        # Handle default result style name.
        if resultStyle == None or resultStyle == '' or resultStyle == 'default':
            resultStyle = databaseConfig['defaultResultStyles'][dataFormat]
        return (dbName, dataFormat, resultStyle)

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

    def _resolveServiceTemplate(self, service, idStr, dbName, dataFormat, resultStyle):
        '''
        Populate a service template to fetch the requested data.
        '''
        # Split list into individual identifiers.
        idList = re.split(r'[ +,]+', idStr)
        if len(idList) > self.settings['maxEntries']:
            raise BiofetchError(5, 'Too many IDs [{0}]. Max [{1}] allowed.'.format(len(idList), self.settings['maxEntries']))
        # Process the identifier list.
        if 'idCharacterCase' in service['primaryAccess']:
            if service['primaryAccess']['idCharacterCase'] == 'upper':
                idStr = idStr.upper()
            elif service['primaryAccess']['idCharacterCase'] == 'lower':
                idStr = idStr.lower()
        if 'idSeparator' in service['primaryAccess']:
            idStr = re.sub(r'[ +,]+', service['primaryAccess']['idSeparator'], idStr)
        expandedStr = self._expandTemplateString(
            service['primaryAccess']['urlTemplate'], 
            idStr,
            dbName,
            service['dataFormats'][dataFormat]['value'],
            service['dataFormats'][dataFormat]['resultStyles'][resultStyle]
            )
        return expandedStr

