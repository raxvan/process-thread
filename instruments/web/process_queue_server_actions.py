import json

class GetActiveItems():
	def __init__(self, queue):
		self.queue = queue

	def run(self, handler):
		handler.send_response(200)
		handler.send_header('Content-type', 'application/json')
		handler.end_headers()
		self.wfile.write(json.dumps(self.queue.query_items()).encode('utf-8'))

class GetStatus():
	def __init__(self, queue):
		self.queue = queue

	def run(self, handler):
		handler.send_response(200)
		handler.send_header('Content-type', 'application/json')
		handler.end_headers()
		self.wfile.write(json.dumps(self.queue.query_status()).encode('utf-8'))


