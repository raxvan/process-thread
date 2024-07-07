

import os
import sys
import queue
import asyncio
import threading

################################################################################################

class StreamingProtocol(asyncio.SubprocessProtocol):
	def __init__(self, stdhandlers):
		asyncio.SubprocessProtocol.__init__(self)
		
		self.onStdout, self.onStderr = stdhandlers

	def pipe_data_received(self, fd, data):
		if fd == 1:
			self.onStdout(data)
		elif fd == 2:
			self.onStderr(data)

################################################################################################

class ProcessState():
	def __init__(self, command, workdir, environment, stdhandlers):
		self.command = command
		self.workdir = workdir
		self.environment = environment

		self.stdhandlers = stdhandlers

		self.processStarted = threading.Event()
		self.processReturned = threading.Event()
		
		self.pid = None
		self.returnCode = None
		self.error = None

	def waitForId(self):
		self.processStarted.wait()
		return self.pid

	def waitForExit(self):
		self.processReturned.wait()
		return self.returnCode, self.error


	async def _asyncio_subprocess_exec(self, loop):
			
		transport, protocol = await loop.subprocess_exec(
			lambda: StreamingProtocol(self.stdhandlers),
			*self.command,
			cwd=self.workdir,
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
			env=self.environment
		)

		pid = transport.get_pid()

		#_handler.start(pid)
		self.pid = pid
		self.processStarted.set()

		rc = await transport._wait() #maybe replace with something else

		self.returnCode = rc

		transport.close()

	def failedWithException(self, err):
		self.error = err
		self.processStarted.set()
		self.processReturned.set()

	def kill(self):
		self.processStarted.wait()
		if self.pid == None:
			return

		return _kill_process_with_pid(self.pid)

################################################################################################

class ProcessThread():
	def __init__(self):

		self.thread = None
		self.stop = None
		self.states = None

		self.onStdout = None
		self.onStderr = None
		self.onProcessStart = None
		self.onProcessEnd = None
		self.onProcessError = None

	def start(self, cmd, cwd, env):
		state = ProcessState(cmd, cwd, env, (self.onStdout, self.onStderr))

		if self.thread == None:
			self.stop = threading.Event()
			self.states = queue.Queue()

			self.thread = threading.Thread(target=lambda : self._process_thread(), daemon=True)
			self.thread.start()

		self.states.put(state)

		return state

	def join(self):
		if self.thread == None:
			return

		self.stop.set()
		self.thread.join()

		self.thread = None
		self.stop = None
		self.states = None

	def _run_state(self, loop, state):
		try:

			# https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-subprocess-proto
			# https://stackoverflow.com/questions/24435987/how-to-stream-stdout-stderr-from-a-child-process-using-asyncio-and-obtain-its-e/24435988#24435988
			
			if self.onProcessStart != None:
				self.onProcessStart(state)

			loop.run_until_complete(
				state._asyncio_subprocess_exec(loop)
			)

			if self.onProcessEnd != None:
				self.onProcessEnd(state)

			state.processReturned.set()

		except:
			import traceback
			exc_type, exc_value, exc_traceback = sys.exc_info()

			error_message = f"ERROR:{str(exc_type)}\nINFO:{str(exc_value)}\nCALLSTACK:\n"
			el = traceback.format_exception(exc_type, exc_value, exc_traceback)
			index = 0
			for e in el:
				stri = str(index).rjust(8)
				error_message += f"{stri} : {e}\n"
				index += 1

			state.failedWithException(error_message)

			if self.onProcessError != None:
				self.onProcessError(state)


	def _process_thread(self):
		loop = None
		if sys.platform.startswith('win'):
			loop = asyncio.ProactorEventLoop()
			#see https://stackoverflow.com/questions/44633458/why-am-i-getting-notimplementederror-with-async-and-await-on-windows
		else:
			loop = asyncio.new_event_loop()

		while not self.stop.is_set():
			try:
				state = self.states.get(timeout = 1)
				if state == None:
					break
				self._run_state(loop, state)
			except queue.Empty:
				pass


		loop.close()

################################################################################################
################################################################################################

def _kill_process_with_pid(_pid):
	errors = None

	#process might be still running, go for the kill and wait for result
	try:
		errors = _kill_with_pid(_pid)
	except:
		#kill failed for unknown reason, try something else
		_, exc_value, _ = sys.exc_info()
		errors = [str(exc_value)]
		pass

	if errors == None:
		#killed worked
		return True
	return False

def _kill_with_pid(pid):
	errors = []
	try:
		import psutil
		ks = _kill_process_psutil(psutil,pid)
		if ks == None:
			return None
		errors.append(ks)
	except ImportError:
		errors.append("Missing psutil; To install run `pip3 install psutil`.")

	#try something else
	ks = None
	if sys.platform.startswith('win'):
		ks = _kill_process_windows(pid)
	elif sys.platform.startswith('darwin'):
		ks = _kill_process_unix(pid)
	else:
		ks = _kill_process_linux(pid)
	if ks == None:
		return None

	errors.append(ks)
	return errors

def _kill_process_psutil(psutil, pid):
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

def _kill_process_windows(pid):
	#option 1:
	import subprocess
	subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)])
	return "using taskkill"

	#option 2
	# http://mackeblog.blogspot.com/2012/05/killing-subprocesses-on-windows-in.html

	#import process_kill_windows
	#process_kill_windows.killsubprocesses(pid);

	#return "No windows fallback for killing process " + str(pid);

def _kill_process_unix(pid):
	#option 1:
	#os.killpg()

	#option 2:
	#kill -9 -PID

	return _kill_process_pgrep_sigterm(pid)

def _kill_process_linux(pid):
	#option 1:
	#kill -9 PID
	
	return _kill_process_pgrep_sigterm(pid)


def _kill_process_pgrep_sigterm(pid):
	try:
		p = subprocess.Popen(['pgrep', '-P', str(pid)], stdout=subprocess.PIPE)
		child_pids = p.communicate()[0]
		child_pid_list = child_pids.split()
		
		for child_pid in child_pid_list:
			os.kill(int(child_pid), signal.SIGTERM)
		
		os.kill(pid, signal.SIGTERM)
		return None
	except OSError as error:
		return f"Error: {error}"