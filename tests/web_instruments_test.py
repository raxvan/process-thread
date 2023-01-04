import sys
import os
import json
import time
import threading
import queue

_this_dir = os.path.dirname(__file__)
_impl_dir = os.path.abspath(os.path.join(_this_dir,"..","impl"))
if not _impl_dir in sys.path:
	sys.path.append(_impl_dir)
_impl_dir = os.path.abspath(os.path.join(_this_dir,"..","instruments","web"))
if not _impl_dir in sys.path:
	sys.path.append(_impl_dir)

import process_queue
import process_handler

import process_queue_server

class DebugStdoutHandler(process_handler.StdoutHandler):
	def __init__(self):
		process_handler.StdoutHandler.__init__(self)

	#called when item is ready for execution
	def init(self, data):
		import json
		sys.stdout.write("HANDLER::INIT>" + json.dumps(data) + "\n")
		return process_handler.StdoutHandler.init(self, data);

	#called when we have pid
	def start(self, pid):
		process_handler.StdoutHandler.start(self, pid)
		sys.stdout.write("HANDLER::PID>" + str(pid) + "\n")

	#called when process terminates.
	def close(self, process_data, completed):
		process_handler.StdoutHandler.close(self, process_data, completed)
		import json
		sys.stdout.write("HANDLER::COMPLETED(" + str(completed) + ")>" + json.dumps(process_data,indent=2) + "\n")

class CustomQueue(process_queue.ProcessQueue):
	def create_process_handler(self, _id, _itm):
		return DebugStdoutHandler()

q = CustomQueue("", os.environ.copy())
q.start()

debug_server = process_queue_server.ProcessQueueServer(q,("127.0.0.1",8080))

_itm = {
	"_print" : False,
	"env" : {
		"SLEEP_SECONDS" : "10"
	},
	"cmd" : ["{_SHELL_OPT_}", "{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/wait.{_SHELL_EXT_}"]
}
q.push_back(0, _itm)
q.push_back(1, _itm)

debug_server.run()
print("exiting...")
q.stop()

