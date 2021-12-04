

class ProcessHandler(object):
	def __init__(self):
		pass

	def info(self):
		return type(self).__name__

	def close(self, process_data):
		pass

	def stderr_lines_count(self):
		return 0

	def put_status_line(self, msg_str):
		pass

	def stderr_linebuffer(self, msg_buffer):
		pass
	def stdout_linebuffer(self, msg_buffer):
		pass



class StdoutHandler(ProcessHandler):
	def __init__(self):
		self.stderr_count = 0;

	def stderr_lines_count(self):
		return self.stderr_count

	def put_status_line(self, msg_str):
		print("#" + msg_str.rstrip().replace("\n","\n#"))

	def stderr_linebuffer(self, msg_buffer):
		self.stderr_count += 1
		print("*" + msg_buffer.decode("utf-8").rstrip().replace("\n","\n*"))

	def stdout_linebuffer(self, msg_buffer):
		print(">" + msg_buffer.decode("utf-8").rstrip().replace("\n","\n>"))