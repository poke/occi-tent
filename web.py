#!/usr/bin/env python3
'''
OCCI tent web interface server.
'''

from http.server import HTTPServer, BaseHTTPRequestHandler
import argparse, glob, os, shutil
import threading, sys
import webbrowser

from inc.tent import Tent

class TentRequestHandler ( BaseHTTPRequestHandler ):
	server_version = 'TentWeb/1.0'
	tent = None
	homelink = '<a id="homelink" href="/">Home</a>'
	
	def GET_main ( self, *path ):
		body = [ '<h1>Tent web interface</h1>' ]
		
		body.append( '<h2>Global actions</h2>' )
		body.append( '<ul>' )
		body.append( '  <li><a href="/modules">Test module overview</a></li>' )
		body.append( '  <li><a href="/suites">Test suites</a></li>' )
		body.append( '  <li><a href="/shutdown">Shutdown web interface</a></li>' )
		body.append( '</ul>' )
		
		body.append( '<h2>Test suites</h2>' )
		body.append( '<ul>' )
		for suite in self.tent.suites:
			body.append( '  <li><a href="/suite/{0}">{0}</a> (<a href="/log/{0}">logs</a>, <a href="/run/{0}">run</a>)</li>'.format( suite ) )
		body.append( '</ul>' )
		
		self.sendHtmlResponse( body )
	
	def GET_shutdown ( self, *path ):
		body = '<h1>Tent web interface</h1>\n<p>Shutting down…</p>'
		self.sendHtmlResponse( body )
		
		print( 'Shutdown requested, shutting down...' )
		threading.Thread( name='TentShutdownThread', target=self.server.shutdown ).start()
	
	def GET_suite ( self, suite, *path ):
		body = [ self.homelink, '<h1>Test cases of suite: ' + suite + '</h1>' ]
		
		try:
			f = open( 'suites/' + suite + '.yaml' )
		except IOError:
			body.append( '<p>Invalid suite name.</p>' )
		else:
			body.append( '<ol>' )
			for testCase in self.tent.loadTestCases( f ):
				body.append( '  <li>' + testCase.title + '</li>' )
			body.append( '</ol>' )
		self.sendHtmlResponse( body )
	
	def GET_run ( self, suite, *path ):
		body = [ self.homelink, '<h1>Running suite: ' + suite + '</h1>' ]
		
		try:
			suiteFile = open( 'suites/' + suite + '.yaml' )
		except IOError:
			body.append( '<p>Invalid suite name.</p>' )
		else:
			logFileName = '{}.log'.format( suiteFile.name )
			
			def run ( tent ):
				from datetime import datetime
				with open( logFileName, 'a+' ) as logFile:
					print( '=' * 50 + ' {0} =='.format( datetime.utcnow().isoformat( ' ' ) ), file=logFile )
					tent.runSuite( suiteFile, logFile, suppressPrint=True )
					print( file=logFile )
			
			threading.Thread( name='SuiteRunner', target=run, args=( self.tent, ) ).start()
			
			body.append( '<h2>Logs</h2>' )
			body.append( '<p>Live logs are not yet available. Please refer to the static logs after the suite executed.</p>' )
			body.append( '<p><a href="/log/{0}">Show static logs.</a></p>'.format( suite ) )
		self.sendHtmlResponse( body )
	
	def GET_log ( self, suite, *path ):
		body = [ self.homelink, '<h1>Log of suite: ' + suite + '</h1>' ]
		
		try:
			f = open( 'suites/' + suite + '.yaml.log' )
		except IOError:
			body.append( '<p>No logs found or invalid suite name.</p>' )
		else:
			logTime = None
			logLines = []
			for line in f.readlines():
				if line.startswith( '==========' ):
					logLines = []
					logTime = line.strip( '\n= ' )
				else:
					logLines.append( line.strip( '\n' ) )
			f.close()
			
			body.append( '<p>Last execution of suite <strong>{}</strong>: {}'.format( suite, logTime ) + '</p>' )
			body.append( '<pre>\n' + '\n'.join( logLines ) + '</pre>' )
		self.sendHtmlResponse( body )
	
	def GET_modules ( self, *path ):
		body = [ self.homelink, '<h1>Test module index</h1>' ]
		
		for module in self.tent.modules:
			body.append( '<h2>' + module['name'] + '</h2>' )
			
			if module['doc']:
				body.append( '<p>' + module['doc'] + '</p>' )
			
			for function in module['functions']:
				body.append( '<h3>' + function['name'] + '</h3>' )
				
				if function['doc']:
					body.append( '<p>' + function['doc'] + '</p>' )
				
				body.append( '<h4>Parameters</h4>' )
				body.append( '<dl>' )
				for param in function['params']:
					body.append( '  <dt>' + param['name'] + '</dt>' )
					
					if param['annotation']:
						body.append( '  <dd>' + param['annotation'] + '</dd>' )
					else:
						body.append( '  <dd><em>Undocumented</em></dd>' )
					
					if param['default']:
						body.append( '  <dd><em>Default value:</em> <code>' + repr( param['default'] ) + '</code></dd>' )
				body.append( '</dl>' )
		self.sendHtmlResponse( body )
	
	def sendStylesheet ( self ):
		self.send_response( 200 )
		self.send_header( 'Content-Type', 'text/css; charset=utf-8' )
		self.send_header( 'Content-Length', str( os.stat( 'web_styles.css' ).st_size ) )
		self.end_headers()
		
		with open( 'web_styles.css', 'br' ) as f:
			shutil.copyfileobj( f, self.wfile )
	
	# internal handlers & utility functions
	def do_GET ( self ):
		path = self.path.split( '?', 1 )[0].split( '#', 1 )[0]
		
		if path == '/':
			self.send_response( 301 )
			self.send_header( 'Location', '/main' )
			self.end_headers()
			return
		elif path == '/style.css':
			self.sendStylesheet()
			return
		
		action, *remainder = path[1:].split( '/' )
		action = 'GET_' + action.lower()
		
		if hasattr( self, action ):
			getattr( self, action )( *remainder )
		else:
			print( 'Unknown handler:', action )
			self.send_error( 404, 'File not found' )
	
	def sendHtmlResponse ( self, htmlBody, title = 'Tent web interface' ):
		body  = b'<!DOCTYPE html>\n<html>\n<head>\n  <meta charset="utf-8" />\n  <title>'
		body += title.encode()
		body += b'</title>\n  <link rel="stylesheet" href="/style.css" type="text/css" />\n</head>\n\n<body>\n'
		
		if isinstance( htmlBody, list ):
			body += b'\n'.join( map( lambda l: b'  ' + ( l.encode() if isinstance( l, str ) else l ), htmlBody ) )
		elif isinstance( htmlBody, str ):
			body += '\n'.join( map( lambda l: '  ' + l, htmlBody.split( '\n' ) ) ).encode()
		else:
			body += b'\n'.join( map( lambda l: b'  ' + l, htmlBody.split( b'\n' ) ) )
		
		body += b'\n</body>\n</html>'
		self.send_response( 200 )
		self.send_header( 'Content-Type', 'text/html; charset=utf-8' )
		self.send_header( 'Content-Length', str( len( body ) ) )
		self.end_headers()
		self.wfile.write( body )


if __name__ == '__main__':
	parser = argparse.ArgumentParser( description='OCCI tent web interface', epilog=None )
	parser.add_argument( '--config', '-c', default='config.yaml', type=open, help='configuration file (default: %(default)s)', metavar='FILE' )
	parser.add_argument( '--port', '-p', default=8080, type=int, help='port on which the webserver should listen (default: %(default)s)' )
	
	try:
		args = parser.parse_args()
	except IOError as e:
		parser.error( str( e ) )
	
	TentRequestHandler.tent = Tent( args.config )
	httpd = HTTPServer( ( '', args.port ), TentRequestHandler )
	try:
		print( 'Serving on {0}:{1}...'.format( *httpd.socket.getsockname() ) )
		webbrowser.open( 'http://localhost:{0}'.format( args.port ) )
		httpd.serve_forever()
	except KeyboardInterrupt:
		print( '\nKeyboard interrupt received, shutting down.' )
		httpd.server_close()
		sys.exit( 0 )