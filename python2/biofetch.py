#!/usr/bin/python
# ======================================================================
# A Python 2.x implementation of a BioFetch server.
# ======================================================================
# Module imports
import cgi
import cgitb
cgitb.enable()

# Get parameters from GET or POST request.
form = cgi.FieldStorage()

# BioFetch web form.
print 'Content-Type: text/html\n'
print '''
<html>
<head>
<title>BioFetch</title>
</head>
<body>
<h1 align="center">BioFetch</h1>
<hr />
<form action="biofetch.py" method="GET">
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
