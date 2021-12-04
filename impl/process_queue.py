import os
import sys
import re
import time
import copy

import asyncio

import process_handler
import thread_worker_queue

async def _read_stdout_stream(stream, _handler):
	while True:
		line = await stream.readline()
		if line:
			_handler.stdout_linebuffer(line)
		else:
			break

async def _read_stderr_stream(stream, _handler):
	while True:
		line = await stream.readline()
		if line:
			_handler.stderr_linebuffer(line)
		else:
			break

def _expand_vars(value, env):
	v = value.format(**env)
	if v == "":
		return None
	return v

class ProcessQueue(thread_worker_queue.ThreadedWorkQueue):
	def __init__(self, workdir, env):
		thread_worker_queue.ThreadedWorkQueue.__init__(self)

		self.workdir = os.path.abspath(os.path.expandvars(workdir))

		if self.workdir != None:
			if self.workdir.endswith("\\\\"):
				self.workdir = self.workdir[:-2]
			if self.workdir.endswith("/") or self.workdir.endswith("\\"):
				self.workdir = self.workdir[:-1]

		else:
			self.workdir = ""
		
		self.env = env
		self.loop = None

		self.env['_PROCESS_ROOT_DIR_'] = self.workdir

		if sys.platform.startswith('win'):
			self.env['_SHELL_EXT_'] = "cmd"
			self.env['_SHELL_'] = "powershell"
			self.env['_SHELL_OPT_'] = ""
		else:
			#maybe detect the active shell?
			self.env['_SHELL_EXT_'] = "sh"
			self.env['_SHELL_'] = "/bin/bash"

			self.env['_SHELL_OPT_'] = self.env['_SHELL_']

	def format_working_directory(self, path_str_or_list, env):
		if path_str_or_list == None:
			return self.workdir

		if isinstance(path_str_or_list, str):
			path_str_or_list = os.path.join(self.workdir, _expand_vars(path_str_or_list, env))

		elif isinstance(path_str_or_list, list):
			l = [_expand_vars(p, env) for p in path_str_or_list]
			path_str_or_list = os.path.join(self.workdir,*[i for i in l if i])

		_abs_path = os.path.abspath(path_str_or_list)

		if not self.workdir in _abs_path:
			return None

		if not os.path.exists(_abs_path):
			os.makedirs(_abs_path)
		elif os.path.isfile(_abs_path):
			return None

		return _abs_path

	def format_command(self, cmd_str_or_list, env):
		if isinstance(cmd_str_or_list, list):
			l = [_expand_vars(c, env) for c in cmd_str_or_list]
			return [i for i in l if i]
		else:
			return None

	def create_env(self, task_id, task_env):
		_env = {}
		_env.update(self.env)
		if task_env != None:
			_env.update(task_env)

		return _env

	def create_process_handler(self, _id, _itm, _env):
		return process_handler.StdoutHandler()

	def get_task_timepoint(self):
		return time.time()

	def push_back(self, _id, _item):
		_item['state'] = 0
		_item['time-queue'] = self.get_task_timepoint()
		
		self.push_back_nocopy(_id, _item)

	def prepare_task(self, _id, _item):
		_item_copy = copy.deepcopy(_item)
		_item_copy['state'] = 1
		_item_copy['time-start'] = self.get_task_timepoint()
		
		return _item_copy

	#wait until process with _id has started and has a pid
	def wait_for_pid(self, _id, _sleep_interval_fsec = 0.25):
		pid = None
		self.work_lock.acquire()
		if _id in self.active_items:
			f = thread_worker_queue.TaskFuture()
			self.add_listener_locked(_id, f) #in case the process stoppes immediatly

			
			while _id in self.active_items:
				if self.active_work_id == _id:
					pid = self.active_work_item.get("pid",None)
					if pid != None:
						break;

				self.work_lock.release()
				time.sleep(_sleep_interval_fsec)
				self.work_lock.acquire()

			if pid == None and f.data != None:
				pid = f.data.get('pid',None)

		self.work_lock.release()
		return pid

	#returns the task data
	def remove_or_kill(self, _id, _sleep_interval_fsec =  0.25):
		data = None
		self.work_lock.acquire()
		if _id in self.active_items:
			f = thread_worker_queue.SingleTaskListener()
			self.add_listener_locked(_id, f) #in case the process stoppes immediatly

			pid = None
			while _id in self.active_items:
				if self.active_work_id == _id:
					#process has started, wait for pid
					pid = self.active_work_item.get("pid",None)
					if pid != None:
						break;
				else:
					#process is not started yet
					del self.active_items[_id]
					l = self.on_complete_listeners.get(_id,None)
					if l != None:
						del self.on_complete_listeners[_id]
						for func in l:
							_func(_id, None)
					break

				self.work_lock.release()
				time.sleep(_sleep_interval_fsec)
				self.work_lock.acquire()

			if f.data != None:
				#process stopped in the meantime, just get the data and return
				data = f.data
				
			elif pid != None:
				#process might be still running, go for the kill and wait for result
				try:
					self.kill_process_with_pid(pid)
				except:
					#kill failed for some reason
					pass

				self.work_lock.release()
				f.wait()
				self.work_lock.acquire()
				data = f.data
				data['killed'] = True

		self.work_lock.release()
		return data

	def kill_process_with_pid(self, pid):
		import psutil
		p = None
		try:
			p = psutil.Process(pid)
		except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
			return

		try:
			for child in p.children(recursive=True):
				child.kill()
		except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
				logs.log_warn('Failed to kill process child.')
			
		p.kill()

	def _construct(self, _id):
		_cmd = self.active_work_item.get('cmd',None)
		_cwd = self.active_work_item.get('cwd',None)
		_env = self.active_work_item.get('env',None)

		_env = self.create_env(_id, _env)
		if _env == None:
			self.active_work_item['error'] = "Invalid environment: " + str(_env)
			return None

		_handler = self.create_process_handler(_id, self.active_work_item, _env)
		if _handler == None:
			self.active_work_item['error'] = "Failed to create process handler."
			return None

		_cwd = self.format_working_directory(_cwd, _env)
		if _cwd == None:
			self.active_work_item['error'] = "Invalid working directory: " + str(_cwd)
			return None

		_cmd = self.format_command(_cmd, _env)
		if _cmd == None:
			self.active_work_item['error'] = "Invalid command: " + str(_cmd)
			return None

		_env["_ID_"] = str(_id)
		_env["_WORKDIR_"] = str(_cwd)
		_env["_HANDLER_"] = _handler.info()

		return (_handler, _cwd, _cmd, _env)

	def execute_active_task(self, _id):

		self.work_lock.acquire()
		_exc = self._construct(_id)
		self.work_lock.release()

		if _exc == None:
			return

		_handler, _cwd, _cmd, _env = _exc

		try:
			return_code = self._thread_execute_command_and_wait(
				_cmd,
				_cwd,
				_env,
				_handler
			)

			stderr_lines = _handler.stderr_lines_count()
			_handler.put_status_line("stderr:{} lines".format(stderr_lines))
			_handler.put_status_line("exit-code:{}".format(int(return_code)))

			self.work_lock.acquire()
			self.active_work_item['exit'] = return_code
			self.active_work_item['stderr'] = stderr_lines
			self.active_work_item['state'] = 2

			if return_code != 0:
				self.active_work_item['state'] = -1
				self.active_work_item['error'] = "Invalid exit code {}".format(return_code)
			elif stderr_lines != 0:
				self.active_work_item['warning'] = "Error stream output {} lines.".format(stderr_lines)

		except:
			import traceback
			exc_type, exc_value, exc_traceback = sys.exc_info()

			_handler.put_status_line("INTERNAL ERROR:" + str(exc_type) + " INFO:" + str(exc_value))
			el = traceback.format_exception(exc_type, exc_value, exc_traceback)
			for e in el:
				_handler.put_status_line("\t" + e)

			self.work_lock.acquire()
			self.active_work_item['state'] = -1
			self.active_work_item['error'] = str(exc_value)

		self.active_work_item['time-end'] = self.get_task_timepoint()
		self.active_work_item["final"] = {
			"cmd" : " ".join(_cmd),
			"cwd" : _cwd,
			"env" : _env
		}
		_handler.close(self.active_work_item)
		self.work_lock.release()

	def thread_run_loop(self):
		self.loop = None

		if sys.platform.startswith('win'):
			self.loop = asyncio.ProactorEventLoop()
			#see https://stackoverflow.com/questions/44633458/why-am-i-getting-notimplementederror-with-async-and-await-on-windows
		else:
			self.loop = asyncio.new_event_loop()

		#asyncio.set_event_loop(self.loop) #it seems we don't need this

		thread_worker_queue.ThreadedWorkQueue.thread_run_loop(self)

	async def _thread_stream_subprocess(self, _handler, _cmd, _cwd, _env):
		# kwargs of create_subprocess_exec: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
		process = await asyncio.create_subprocess_exec(
			*_cmd,
			cwd=_cwd,
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
			loop=self.loop,
			env=_env
		)

		_handler.put_status_line("pid={}".format(process.pid))

		self.work_lock.acquire()
		self.active_work_item['pid'] = process.pid
		self.work_lock.release()

		await asyncio.wait([
			_read_stdout_stream(process.stdout, _handler),
			_read_stderr_stream(process.stderr, _handler)
		])
		return await process.wait()

	def _thread_execute_command_and_wait(self, _cmd, _cwd, _env, _handler):

		# https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-subprocess-proto
		# https://stackoverflow.com/questions/24435987/how-to-stream-stdout-stderr-from-a-child-process-using-asyncio-and-obtain-its-e/24435988#24435988
		_handler.put_status_line("command={}".format(" ".join(_cmd)))
		_handler.put_status_line("workdir={}".format(_cwd))

		start_time = time.time()
		rc = self.loop.run_until_complete(
			ProcessQueue._thread_stream_subprocess(
				self,
				_handler,
				_cmd,
				_cwd,
				_env
			)
		)
		end_time = time.time()

		_handler.put_status_line("time:{} seconds".format(end_time - start_time))

		return rc


