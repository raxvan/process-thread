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

import process_queue
import process_handler

def create_env():
	return {
		"PATH" : str(os.environ['PATH'])
	}

def print_dict(d):
	if d == None:
		return print("None")
	print(json.dumps(d, sort_keys=True, indent=4))

class CustomHandler(process_handler.StdoutHandler):
	def __init__(self, print_result):
		process_handler.StdoutHandler.__init__(self)
		self.print_result = print_result

	def close(self, process_data, completed):
		if self.print_result:
			print("Competed: " + str(completed))
			print_dict(process_data)

		process_handler.StdoutHandler.close(self, process_data, completed)

class CustomQueue(process_queue.ProcessQueue):
	def __init__(self, workdir, env):
		process_queue.ProcessQueue.__init__(self, workdir, env)

	def create_process_handler(self, _id, _itm):
		return CustomHandler(_itm.get("_print", True))

#########################################################################################

class CustomHandler2(process_handler.StdoutHandler):
	def __init__(self, q):
		process_handler.StdoutHandler.__init__(self)
		self.queue = q

	def put_status_line(self, msg_str):
		print("#" + msg_str.rstrip().replace("\n","\n#"))

	def stderr_buffer(self, msg_buffer):
		#print(msg_buffer.decode("utf-8"), end='')
		self.queue.put(msg_buffer)

	def stdout_buffer(self, msg_buffer):
		#print(msg_buffer.decode("utf-8"), end='')
		self.queue.put(msg_buffer)

	def close(self, process_data, completed):
		print("Competed: " + str(completed))
		print_dict(process_data)
		self.queue.put(None)

class CustomQueue2(process_queue.ProcessQueue):
	def __init__(self, workdir, env):
		process_queue.ProcessQueue.__init__(self, workdir, env)
		self.stream_queue = queue.Queue()

	def create_process_handler(self, _id, _itm):
		return CustomHandler2(self.stream_queue)

#########################################################################################

def test_start_stop():
	q = CustomQueue("", {})
	assert(q.is_active() == False)
	q.start()
	assert(q.is_active() == False)
	print_dict(q.create_env(-1,{}))
	q.stop()
	assert(q.is_active() == False)
	q.push_back(123, {
		"_print" : True,
	})
	q.remove(123)
	for i in range(3):
		q.start()
		_itm = {
			"_print" : False,
			"cmd" : ["{_SHELL_OPT_}","{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/hello_world.{_SHELL_EXT_}"]
		}
		q.push_back(0, _itm)
		assert(q.is_active() == True)
		q.wait()
		q.stop()

def test_missing_command():
	q = process_queue.ProcessQueue(_this_dir, {})
	
	_itm = {
		"_print" : False,
		"env" : {
			"TEST_ENV_STR" : "asdf",
		}
	}

	h = q.push_back(1, _itm)

	q.start()

	data = h.wait()

	q.stop()

	print_dict(data)

def test_invalid_command():
	q = CustomQueue(_this_dir, {})
	
	_itm = {
		"cmd" : ["ljkbihyerbjkhj"]
	}

	h = q.push_back(0, _itm)

	q.start()

	h = q.wait()

	q.stop()

def test_valid_command():
	q = CustomQueue(_this_dir, os.environ.copy())
	q.start()	
	_itm = {
		"_print" : False,
		"cmd" : ["{_SHELL_OPT_}","{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/hello_world.{_SHELL_EXT_}"]
	}

	q.push_back(0, _itm)

	q.wait()
	q.stop()

def test_command_with_error():
	q = CustomQueue(_this_dir, {})

	q.start()	
	_itm = {
		"cmd" : ["{_SHELL_OPT_}", "{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/exit_code.{_SHELL_EXT_}"]
	}

	q.push_back(0, _itm)

	q.wait()
	q.stop()

def test_command_with_stderr():
	q = CustomQueue(_this_dir, {})
	q.start()	
	_itm = {
		"cmd" : ["{_SHELL_OPT_}", "{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/stderr.{_SHELL_EXT_}","hello","world"]
	}

	q.push_back(0, _itm)

	q.wait()
	q.stop()

def test_wait_pid():
	q = CustomQueue(_this_dir, os.environ.copy())
	q.start()
	_itm = {
		"_print" : False,
		"env" : {
			"SLEEP_SECONDS" : "2"
		},
		"cmd" : ["{_SHELL_OPT_}", "{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/wait.{_SHELL_EXT_}"]
	}

	h0 = q.push_back(0, _itm)
	h1 = q.push_back(1, _itm)
	h2 = q.push_back(2, _itm)

	print_dict(q.query_items())
	q.remove(2)
	assert(q.is_active() == True)

	pid = h1.pid()
	print("[PID] " + str(pid))

	pid = h2.pid()
	assert(pid == None)

	q.stop()

def test_kill():
	q = CustomQueue(_this_dir, os.environ.copy())
	q.start()	
	_itm = {
		"_print" : True,
		"env" : {
			"SLEEP_SECONDS" : "10"
		},
		"cmd" : ["{_SHELL_OPT_}", "{_ROOT_WORKDIR_}/scripts_{_SHELL_EXT_}/wait.{_SHELL_EXT_}"]
	}
	h = q.push_back(0, _itm)
	time.sleep(1.0)
	q.remove_or_kill(0)

	h = q.push_back(1, _itm)

	q.push_back(2, _itm)

	q.stop()


def test_streaming(exe_path):
	q = CustomQueue2(None, os.environ.copy())
	q.start()	
	_itm = {
		"delay" : 2,
		"cmd" : [exe_path]
	}
	print("queue process...")
	h = q.push_back(0, _itm)
	print_dict(h.pid())
	
	while True:
		o = q.stream_queue.get()
		if o == None:
			break
		print(o.decode("utf-8"), end='')
		sys.stdout.flush()

	q.stop()

print("TEST START-STOP ----------------------------------------------------------------------------")
test_start_stop()
print("TEST MISSING COMMAND -----------------------------------------------------------------------")
test_missing_command()
print("TEST INVALID COMMAND -----------------------------------------------------------------------")
test_invalid_command()
print("TEST VALID COMMAND -------------------------------------------------------------------------")
test_valid_command()
print("TEST VALID COMMAND THAT FAILS --------------------------------------------------------------")
test_command_with_error()
print("TEST STDERR STREAM -------------------------------------------------------------------------")
test_command_with_stderr()
print("TEST WAIT FOR PID --------------------------------------------------------------------------")
test_wait_pid()
print("TEST KILL ----------------------------------------------------------------------------------")
test_kill()


print("STREAMING TEST -----------------------------------------------------------------------------")
posix_exe = os.path.join(_this_dir, "executable", "pqtest")
win_exe = os.path.join(_this_dir, "executable", "Release", "pqtest.exe")
if os.path.exists(posix_exe) and not sys.platform.startswith('win'):
	test_streaming(os.path.abspath(posix_exe))
elif os.path.exists(win_exe) and sys.platform.startswith('win'):
	test_streaming(os.path.abspath(win_exe))
else:
	print("Missing executable...")
