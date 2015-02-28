#!/usr/bin/python
# ======================================================================
# A Python 2.x implementation of a CGI based BioFetch server.
# ======================================================================
# TODO:
# - Read configuration from file(s) [JSON?]
# - Handlers for specific data sources
# - Support for indexing sources [BioPython?]
# - Support for extensions to the BioFetch spec.
# - Response format and content-type checking
# - Command-line support (check for CGI variables)
# - Library/module support
# ======================================================================
# Module imports
import cgi, re, sys, traceback, urllib2
import cgitb
cgitb.enable()
from string import Template
from biofetch import BioFetch

# Get parameters from GET or POST request.
form = cgi.FieldStorage()

def printBiofetchForm():
    '''Output BioFetch web form.'''
    print 'Content-Type: text/html\n'
    print '''
<html>
<head>
<title>BioFetch</title>
</head>
<body>
<h1 align="center">BioFetch</h1>
<hr />
<form action="biofetch.cgi" method="GET">
<ul>
  <li>Database: 
    <select name="db">
      <option>embl</option>
      <option>genbank</option>
      <option>pdb</option>
      <option>swall</option>
    </select>
  </li>
  <li>Data format:
    <select name="format">
      <option>embl</option>
      <option>fasta</option>
      <option>genbank</option>
      <option>pdb</option>
      <option>swissprot</option>
    </select>
  </li>
  <li>Result style:
    <select name="style">
      <option>html</option>
      <option>raw</option>
    </select>
  </li>
  <li>Identifiers:
    <input type="text" name="id" />
  </li>
</ul>
<input type="submit" />
</form>
<hr />
</body>
</html>
'''

def formParametersDebugHtmlOutput():
    '''
    Output a HTML page for debugging the parameters.
    '''
    print 'Content-Type: text/html\n'
    debugParams = Template('''<html>
<head>
<title>BioFetch</title>
</head>
<body>
<h1 align="center">BioFetch</h1>
<hr />
<p>db: ${db}</p>
<p>format: ${format}</p>
<p>style: ${style}</p>
<p>id: ${id}</p>
<hr />
</body>
</html>
''')
    print debugParams.safe_substitute(form)

# No parameters so just return the form.
if len(form.keys()) == 0:
    printBiofetchForm()
elif 'id' in form and len(form['id'].value) > 0:
    # Got identifiers so fetch entries.
    try:
	biofetch = BioFetch()
        (resp, respStream) = biofetch.fetchDataStream(form['id'].value, form['db'].value, form['format'].value, form['style'].value)
        contentType = resp.info().getheader('Content-Type')
        print 'Content-Type: {0}\n'.format(contentType)
        for chunk in iter(lambda: respStream.read(biofetch.settings['chunkSize']), ''):
            print chunk
        respStream.close()
        resp.close()
    except IOError, e:
        print 'Content-Type: text/plain\n'
        print 'ERROR:', '{0} {1} {2}\n'.format(e.errno, e.strerror, e.filename)
	traceback.print_exc(file=sys.stdout)
    #formParametersDebugHtmlOutput() # DEBUG
# TODO: Handle meta-data resource requests.
# No idea what was intended, so return form.
else:
    printBiofetchForm()
