import os
import sys
import re
import time
import copy

import asyncio

import process_handler
import thread_worker_queue

class StreamingProtocol(asyncio.SubprocessProtocol):
	def __init__(self, _handler):
		asyncio.SubprocessProtocol.__init__(self)
		self.handler = _handler

	def pipe_data_received(self, fd, data):
		if fd == 1:
			self.handler.stdout_buffer(data)
		elif fd == 2:
			self.handler.stderr_buffer(data)
		
def _expand_vars(value, env):
	v = value.format(**env)
	if v == "":
		return None
	return v

class ProcessQueue(thread_worker_queue.ThreadedWorkQueue):
	def __init__(self, workdir, env):
		thread_worker_queue.ThreadedWorkQueue.__init__(self)

		if workdir != None:
			self.workdir = os.path.abspath(os.path.expandvars(workdir))
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
		try:
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
		except:
			return None

	def format_command(self, cmd_str_or_list, env):
		try:
			if isinstance(cmd_str_or_list, list):
				l = [_expand_vars(c, env) for c in cmd_str_or_list]
				return [i for i in l if i]
			else:
				return None
		except:
			return None

	def create_env(self, task_id, task_env):
		try:
			_env = {}
			_env.update(self.env)
			if task_env != None:
				_env.update(task_env)

			return _env
		except:
			return None

	def create_process_handler(self, _id, _itm):
		return process_handler.StdoutHandler()

	def get_task_timepoint(self):
		return time.time()

	def push_back(self, _id, _item):
		_item['state'] = 0
		_item['time-queue'] = self.get_task_timepoint()

		_handler = self.create_process_handler(_id, _item)

		if self.add(_id, _item, _handler) == False:
			return None
		return _handler

	#returns the task data
	def remove_or_kill(self, _id):
		data = None
		self.work_lock.acquire()

		if not _id in self.tasks:
			self.work_lock.release()
			return None

		_handler = self.payload[_id]

		if _id != self.context_id:
			self._try_remove_task(_id)
			self.work_lock.release()
		else:
			self.work_lock.release()

			_pid = _handler.pid()

			if(self._kill_active_process(_pid) == False):
				#failed to kill the process, might as whell just exit quickly
				return None

		return _handler.wait()

	def _stop_active_task(self, _id):
		_handler = self.payload[_id]
		self.work_lock.release()
		_pid = _handler.pid()
		self._kill_active_process(_pid)
		self.work_lock.acquire()

	def _kill_active_process(self, _pid):
		ctx = self.acquire_active_context()
		
		ctx.setdefault('warnings',[]).append("Process scheduled for termination.")

		kill_warnings = None
	
		#process might be still running, go for the kill and wait for result
		try:
			kill_warnings = self.kill_process_with_pid(_pid)
		except:
			#kill failed for unknown reasonse
			_, exc_value, _ = sys.exc_info()
			kill_warnings = [str(exc_value)]
			pass

		if kill_warnings != None:
			ctx.setdefault('warnings',[]).extend(kill_warnings)

		self.release_active_context(ctx)
		
		if kill_warnings == None:
			return True
		return False

	def _kill_process_psutil(self, psutil, pid):
		try:
			#kill process tree, children first then parent
			p = psutil.Process(pid)
			for child in p.children(recursive=True):
				child.kill()
			p.kill()
			return None
		except psutil.AccessDenied as e:
			return str(e)
		except psutil.NoSuchProcess as e:
			return str(e)
		except psutil.ZombieProcess as e:
			return str(e)
		except psutil.TimeoutExpired as e:
			return str(e)
		except OSError as e:
			return str(e)
		except:
			return str(e)

	def _kill_process_windows(self, pid):
		#option 1:
		#subprocess.call(['taskkill', '/F', '/T', '/PID', str(p.pid)])

		#option 2
		# http://mackeblog.blogspot.com/2012/05/killing-subprocesses-on-windows-in.html

		return "No windows fallback for killing process " + str(pid);

	def _kill_process_unix(self,pid):
		#option 1:
		#os.killpg()

		#option 2:
		#kill -9 -PID
		
		return "No unix fallback for killing process " + str(pid);

	def _kill_process_linux(self,pid):
		#option 1:
		#kill -9 PID
		
		return "No linux fallback for killing process " + str(pid);
		
	def kill_process_with_pid(self, pid):
		errors = []
		try:
			import psutil
			ks = self._kill_process_psutil(psutil,pid)
			if ks == None:
				return None
			errors.append(ks)
		except ImportError:
			errors.append("Missing psutil; To install run `pip3 install psutil`.")

		#try something else
		ks = None
		if sys.platform.startswith('win'):
			ks = self._kill_process_windows(pid)
		elif sys.platform.startswith('darwin'):
			ks = self._kill_process_unix(pid)
		else:
			ks = self._kill_process_linux(pid)
		if ks == None:
			return None
		errors.append(ks)
		return errors

	def _construct(self, _id, _data, _handler):
		_cmd_base = _data.get('cmd',None)
		_cwd_base = _data.get('cwd',None)
		_env_base = _data.get('env',None)
		_delay_base = _data.get('delay',None)
		_delay = _delay_base
		try:
			if _delay != None:
				_delay = float(_delay)
		except:
			_data.setdefault('warnings',[]).append("Invalid parameter delay: " + str(_delay_base))

		_env = self.create_env(_id, _env_base)
		if _env == None:
			_data['error'] = "Invalid environment: " + str(_env_base)
			return None

		if _handler == None:
			_data['error'] = "Failed to create process handler."
			return None

		_cwd = self.format_working_directory(_cwd_base, _env)
		if _cwd == None:
			_data['error'] = "Invalid working directory: " + str(_cwd_base)
			return None

		_cmd = self.format_command(_cmd_base, _env)
		if _cmd == None:
			_data['error'] = "Invalid command: " + str(_cmd_base)
			return None

		_env["_ID_"] = str(_id)
		_env["_WORKDIR_"] = str(_cwd)
		_env["_HANDLER_"] = _handler.info()

		return (_cwd, _cmd, _env, _delay)

	def _task_removed(self, _id, _data, _payload):

		_data.setdefault('warnings',[]).append("Task aborted...")

		_payload.close(_data, False)

	def prepare_task(self, _id, _item):
		_icopy, _handler = thread_worker_queue.ThreadedWorkQueue.prepare_task(self, _id, _item)
		
		_icopy['state'] = 1
		_icopy['time-start'] = self.get_task_timepoint()

		_ctx = self._construct(_id, _icopy, _handler)
		if _ctx == None:
			return _icopy, (_handler, None)

		_cwd, _cmd, _env, _delay = _ctx

		try:
			if _handler.init(_icopy) == False:
				_icopy['error'] = "Failed to initalize handler."
				return _icopy, (_handler, None)
		except:
			_icopy['error'] = "Handler initalization failed."
			return _icopy, (_handler, None)

		return _icopy, (_handler, (_cwd, _cmd, _env, _delay))

	def execute_active_task(self, _id, _payload):

		_handler, params = _payload

		if params == None:
			return

		_cwd, _cmd, _env, _delay = params

		if _delay != None:
			time.sleep(_delay)

		_system_cwd = os.getcwd()
		if _cwd == "":
			_cwd = _system_cwd

		ctx = None
		try:
			_handler.put_status_line("command={}".format(" ".join(_cmd)))
			_handler.put_status_line("workdir={}".format(_cwd))

			return_code, duration = self._thread_execute_command_and_wait(
				_cmd,
				_cwd,
				_env,
				_handler
			)

			stderr_lines = _handler.stderr_lines_count()
			_handler.put_status_line("duration:{} seconds".format(duration))
			_handler.put_status_line("stderr:{} lines".format(stderr_lines))
			_handler.put_status_line("exit-code:{}".format(int(return_code)))

			ctx = self.acquire_active_context()

			ctx['time'] = duration #in seconds, how long the process was alive
			ctx['exit'] = return_code
			ctx['stderr'] = stderr_lines
			ctx['state'] = 2

			if return_code != 0:
				ctx['error'] = "Invalid exit code {}".format(return_code)
			if stderr_lines != 0:
				ctx.setdefault('warnings',[]).append("stderr output... [{}]".format(stderr_lines))

			self.release_active_context(ctx)

		except:
			import traceback
			exc_type, exc_value, exc_traceback = sys.exc_info()

			_handler.put_status_line("INTERNAL ERROR:" + str(exc_type) + " INFO:" + str(exc_value))
			el = traceback.format_exception(exc_type, exc_value, exc_traceback)
			for e in el:
				_handler.put_status_line("\t" + e)

			ctx = self.acquire_active_context()
			ctx['error'] = str(exc_value)
			self.release_active_context(ctx)

		os.chdir(_system_cwd)

	def task_finished(self, _id, _task_copy, _payload):
		_handler, params = _payload
		_task_copy['time-end'] = self.get_task_timepoint()
		
		if 'error' in _task_copy:
			_task_copy['state'] = -1

		if params != None:
			#_cwd, _cmd, _env, _delay = params
			_task_copy["params"] = params
		_handler.close(_task_copy, True)

		thread_worker_queue.ThreadedWorkQueue.task_finished(self, _id, _task_copy, _payload)

	def thread_run_loop(self):
		self.loop = None

		if sys.platform.startswith('win'):
			self.loop = asyncio.ProactorEventLoop()
			#see https://stackoverflow.com/questions/44633458/why-am-i-getting-notimplementederror-with-async-and-await-on-windows
		else:
			self.loop = asyncio.new_event_loop()

		#asyncio.set_event_loop(self.loop) #it seems we don't need this

		thread_worker_queue.ThreadedWorkQueue.thread_run_loop(self)

		self.loop.close();
		self.loop = None

	#async def _asyncio_create_subprocess_exec(self, _handler, _cmd, _cwd, _env):
	#	# kwargs of create_subprocess_exec: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
	#	process = await asyncio.create_subprocess_exec(
	#		*_cmd,
	#		cwd=_cwd,
	#		stdout=asyncio.subprocess.PIPE,
	#		stderr=asyncio.subprocess.PIPE,
	#		loop=self.loop,
	#		env=_env
	#	)
    #
	#	_handler.put_status_line("pid={}".format(process.pid))
    #
	#	pid = process.pid
    #
	#	_handler.start(pid)
    #
	#	await asyncio.wait([_read_stdout_stream(process.stdout, _handler)])
    #
	#	#await asyncio.wait([_read_stderr_stream(process.stderr, _handler)])
	#	return process.wait();

	async def _asyncio_subprocess_exec(self, _handler, _cmd, _cwd, _env):
		
		transport, protocol = await self.loop.subprocess_exec(
			lambda: StreamingProtocol(_handler),
			*_cmd,
			cwd=_cwd,
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
			env=_env
		)

		pid = transport.get_pid()

		_handler.start(pid)

		rc = await transport._wait() #maybe replace with something else

		transport.close()

		return rc

	def _thread_execute_command_and_wait(self, _cmd, _cwd, _env, _handler):

		# https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-subprocess-proto
		# https://stackoverflow.com/questions/24435987/how-to-stream-stdout-stderr-from-a-child-process-using-asyncio-and-obtain-its-e/24435988#24435988
		start_time = time.time()

		rc = self.loop.run_until_complete(
			ProcessQueue._asyncio_subprocess_exec(
				self,
				_handler,
				_cmd,
				_cwd,
				_env
			)
		)

		duration = time.time() - start_time
		
		return rc, duration


