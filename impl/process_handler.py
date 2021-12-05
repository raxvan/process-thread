

class EmptyProcessHandler(object):
	def __init__(self):
		pass

	def info(self):
		return type(self).__name__

	def start(self, pid):
		pass

	def close(self, process_data):
		pass

	def stderr_lines_count(self):
		return 0

	def put_status_line(self, msg_str):
		pass

	#careful with this 2 functions, the callee is not from the realm of the living. 
	def stderr_buffer(self, msg_buffer):
		pass
	def stdout_buffer(self, msg_buffer):
		pass



class StdoutHandler(EmptyProcessHandler):
	def __init__(self):
		self.stderr_count = 0;

	def stderr_lines_count(self):
		return self.stderr_count

	def put_status_line(self, msg_str):
		print("#" + msg_str.rstrip().replace("\n","\n#"))

	def stderr_buffer(self, msg_buffer):
		self.stderr_count += 1
		print("*" + msg_buffer.decode("utf-8").rstrip().replace("\n","\n*"))

	def stdout_buffer(self, msg_buffer):
		print(">" + msg_buffer.decode("utf-8").rstrip().replace("\n","\n>"))