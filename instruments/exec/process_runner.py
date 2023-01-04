
import os
import sys
import argparse
import json

_this_dir = os.path.dirname(__file__)
_impl_dir = os.path.abspath(os.path.join(_this_dir,"..","..","impl"))
if not _impl_dir in sys.path:
	sys.path.append(_impl_dir)

import process_queue
import process_handler

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
	def __init__(self, workdir, env, _debug):
		self.debug = _debug
		process_queue.ProcessQueue.__init__(self, workdir, env)


	def create_process_handler(self, _id, _itm):
		if self.debug:
			return DebugStdoutHandler()
		else:
			return process_handler.StdoutHandler()

def main(args):
	jobs = args.ifile['jobs']

	workdir = ""
	env = os.environ.copy()

	q = CustomQueue(workdir, env, args.debug)
	q.start()

	index = 0
	for j in jobs:
		q.push_back(index, j)
		index = index + 1

	try:
		q.wait()
	except KeyboardInterrupt:
		pass

	q.stop()


def is_valid_file(parser, arg):
	if not os.path.exists(arg):
		parser.error("The file %s does not exist!" % arg)
	else:
		f = open(arg, 'r')
		if f == None:
			parser.error("Could not open file %s!" % arg)
			return None

		try:
			return json.load(f)
		except json.JSONDecodeError:
			parser.error("Invalid json %s!" % arg)
			return None


if __name__ == "__main__":
	user_arguments = sys.argv[1:]

	parser = argparse.ArgumentParser()
	parser.add_argument('--debug', dest='debug', action='store_true')
	parser.add_argument("ifile", help="Input Json file", metavar="FILE", type=lambda x: is_valid_file(parser, x))

	args = parser.parse_args(user_arguments)
	main(args)
