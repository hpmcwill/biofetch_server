#!/usr/bin/python
# ======================================================================
# A Python 2.x implementation of a CGI based BioFetch server.
# ----------------------------------------------------------------------
# See:
# - GitHub repository: https://github.com/hpmcwill/biofetch_server/
# - OBDA BioFetch specification:
#   https://github.com/OBF/OBDA/tree/master/biofetch
# ======================================================================
# Module imports
import cgi, re, sys, traceback, urllib2
import cgitb
cgitb.enable()
from string import Template
from biofetch import BioFetch, BiofetchError

# Get parameters from GET or POST request.
form = cgi.FieldStorage()
# Initialise biofetch object.
biofetch = BioFetch()

def printBiofetchForm():
    '''Output BioFetch web form.'''
    print 'Content-Type: text/html\n'
    htmlFile = open('etc/biofetch_form.html', 'r')
    formHtml = htmlFile.read()
    # TODO: insert databases, formats and styles from the BioFetch config.
    print formHtml

try:
    # No parameters so just return the form.
    if len(form.keys()) == 0:
        printBiofetchForm()
    # biofetch.rb style meta-data requests.
    elif 'info' in form:
        print 'Content-Type: text/plain\n'
        try:
            if form['info'].value == 'maxids':
                print biofetch.getMaxIds()
            elif form['info'].value == 'dbs':
                dbNameList = biofetch.getDatabaseNames()
                for dbName in dbNameList:
                    print dbName
            elif form['info'].value == 'formats':
                formatNameList = biofetch.getDbFormatNames(form['db'].value)
                for formatName in formatNameList:
                    print formatName
            elif form['info'].value == 'styles':
                styleNameList = biofetch.getDbFormatStyleNames(form['db'].value, form['format'].value)
                for styleName in styleNameList:
                    print styleName
            else:
                print 'Error 6: Unknown information.'
        except BiofetchError, e:
            print e
    elif 'id' in form and len(form['id'].value) > 0:
        # Handle default values.
        dbName = 'default'
        if 'db' in form and len(form['db'].value) > 0:
            dbName = form['db'].value
        dataFormat = 'default'
        if 'format' in form and len(form['format'].value) > 0:
            dataFormat = form['format'].value
        resultStyle = 'default'
        if 'style' in form and len(form['style'].value) > 0:
            resultStyle = form['style'].value
        # Got identifiers so fetch entries to STDOUT.
        biofetch.fetchDataToStream(sys.stdout, 
                                   form['id'].value, 
                                   dbName, 
                                   dataFormat, 
                                   resultStyle)
    # No idea what was intended, so return form.
    else:
        printBiofetchForm()
except BiofetchError, e:
    print 'Content-Type: text/plain\n'
    print e
except IOError, e:
    print 'Content-Type: text/plain\n'
    print 'ERROR:', '{0} {1} {2}\n'.format(e.errno, e.strerror, e.filename)
    traceback.print_exc(file=sys.stdout)
