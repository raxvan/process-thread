import http.server
import process_queue_server_actions

class RequestHandler(http.server.BaseHTTPRequestHandler):

	def do_GET(self):
		self.server.execute_get_request(self)

	#def do_POST(self):
	#	content_length = int(self.headers['Content-Length'])
	#	post_data = self.rfile.read(content_length)
	#	result = self.server.execute_post_request(self.path, post_data.decode('utf-8'))
	#	self._begin_response_200()
	#	if(result != None):
	#		self.wfile.write(json.dumps(result).encode('utf-8'))


class QuitException(Exception):
	pass

class ProcessQueueServer(http.server.HTTPServer):
	def __init__(self, q, address):
		self.running = 0
		http.server.HTTPServer.__init__(self,address, RequestHandler)

		self.get_active_items = process_queue_server_actions.GetActiveItems(q)
		self.get_status = process_queue_server_actions.GetStatus(q)

	def service_actions(self):
		if self.running == 1:
			self.running = 1
			raise QuitException()

	def execute_get_request(self, handler):
		if handler.path == "/q":
			self.running = 1
		elif handler.path == "/i":
			self.get_active_items.run(handler)
		elif handler.path == "/s":
			self.get_status.run(handler)
		else:
			handler.send_error(404, "Invalid.")

	#def execute_post_request(self, req_path, data):
	#	return "echo: " + str(data)

	def run(self):
		try:
			self.serve_forever()
		except KeyboardInterrupt:
			self.server_close()
		except SystemExit:
			self.server_close()
		except QuitException:
			self.server_close()
