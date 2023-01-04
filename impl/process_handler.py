
import sys
import threading

class EmptyProcessHandler(object):
	def __init__(self):
		self._pid = None
		self._data = None

		self._pid_ready = threading.Event()
		self._data_ready = threading.Event()

	def info(self):
		return type(self).__name__

	#called when item is ready for execution
	def init(self, data):
		return True

	#called when we have pid
	def start(self, pid):
		self._pid = pid
		self._pid_ready.set()

	#called when process terminates.
	def close(self, process_data, completed):
		if self._pid == None:
			self._pid_ready.set()

		self._data = process_data
		if self._pid != None:
			self._data['pid'] = self._pid
		self._data_ready.set()

	def stderr_lines_count(self):
		return 0
	def put_status_line(self, msg_str):
		pass

	def pid(self):
		self._pid_ready.wait()
		return self._pid

	def wait(self):
		self._data_ready.wait()
		return self._data

	#careful with this 2 functions, the callee is not from the realm of the living. 
	def stderr_buffer(self, msg_buffer):
		pass
	def stdout_buffer(self, msg_buffer):
		pass



class StdoutHandler(EmptyProcessHandler):
	def __init__(self):
		EmptyProcessHandler.__init__(self)
		self.stderr_count = 0;

	def stderr_lines_count(self):
		return self.stderr_count

	def put_status_line(self, msg_str):
		sys.stdout.write("#" + msg_str.rstrip().replace("\n","\n#") + "\n")

	def stderr_buffer(self, msg_buffer):
		self.stderr_count += 1
		m = msg_buffer.decode("utf-8").rstrip()
		if m:
			sys.stdout.write("*" + m.rstrip().replace("\n","\n*") + "\n")

	def stdout_buffer(self, msg_buffer):
		m = msg_buffer.decode("utf-8").rstrip()
		if m:
			sys.stdout.write(">" + m.replace("\n","\n>") + "\n")

