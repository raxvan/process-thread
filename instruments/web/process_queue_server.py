import http.server
import threading
import time
import json
# import BaseHTTPRequestHandler, HTTPServer


class RequestHandler(http.server.BaseHTTPRequestHandler):

	def __init__(self, qcontext, request, client_address, server):
		self.qcontext = qcontext
		http.server.BaseHTTPRequestHandler.__init__(self, request, client_address, server)

	def _begin_response_200(self):
		self.send_response(200)
		#self.send_header('Content-type', 'text/html')
		self.send_header('Content-type', 'application/json')
		self.end_headers()

	def do_GET(self):
		result = self.qcontext.get_request(self.path)

		self._begin_response_200()
		if(result != None):
			self.wfile.write(json.dumps(result).encode('utf-8'))

	def do_POST(self):
		content_length = int(self.headers['Content-Length'])
		post_data = self.rfile.read(content_length)

		result = self.qcontext.post_request(self.path, post_data.decode('utf-8'))

		self._begin_response_200()
		if(result != None):
			self.wfile.write(json.dumps(result).encode('utf-8'))


class ProcessQueueServer():
	def __init__(self, q, port):
		self.queue = q
		self.port = int(port)

		self.thread_handle = threading.Thread(target=lambda e: e.thread_run_loop(), args=(self,), daemon=True)
		self.thread_handle.start()

		self.server_handler = None
		self.server_ready = threading.Event()

	def shutdown(self):
		self.server_ready.wait()
		time.sleep(0.5)
		self.server_handler.shutdown()
		# https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.shutdown
		# ^ shutdown can deadlock

	def get_request(self, req_path):
		if req_path == "/i":
			return self.queue.query_items()
		elif req_path == "/s":
			return self.queue.query_status()
		elif req_path == "/q":
			self.shutdown()
			return None

		return None

	def post_request(self, req_path, data):
		return "hello world " + str(data)

	def thread_run_loop(self):
		server_address = ('', self.port)
		request_handler = lambda request, client_address, server: RequestHandler(self, request, client_address, server)
		
		self.server_handler = http.server.ThreadingHTTPServer(server_address, request_handler)
			
		try:
			self.server_ready.set()
			self.server_handler.serve_forever(poll_interval=1.0)
			self.server_ready.clear()
		except KeyboardInterrupt:
			pass

		self.server_handler.server_close()
		self.server_handler = None

		self.queue.stop()


