import copy

import threading
import queue

class SingleTaskListener():
	def __init__(self):
		self.ev = threading.Event()

	def wait(self):
		self.ev.wait()

	def notify(self, _id, _data):
		self.ev.set()

class MultipleTaskListener():
	def __init__(self, count):
		self.count = 0
		self.expected = count
		self.ev = threading.Event()

	def wait(self):
		self.ev.wait()

	def notify(self, _id, _data):
		self.count += 1
		if self.count == self.expected:
			self.ev.set()

class TaskFuture():
	def __init__(self):
		self.data = None
	
	def notify(self, _id, _data):
		if(_data != None):
			self.data = copy.deepcopy(_data)

class ThreadedWorkQueue(object):
	def __init__(self):
		self.queue = queue.Queue()

		self.thread_handle = None
		self.work_lock = threading.Lock()
		self.tasks = {}
		self.payload = {}

		self.context_id = None
		self.context_copy = None

		self.listeners = None

	def start(self):
		self.work_lock.acquire()
		self.thread_handle = threading.Thread(target=lambda e: e.thread_run_loop(), args=(self,), daemon=True)
		self.thread_handle.start()
		self.work_lock.release()

	def _task_removed(self, _id, _data, _payload):
		pass

	def _try_remove_task(self, _id):
		data = self.tasks.get(_id,None)
		if data != None:
			_p = self.payload[_id]

			del self.tasks[_id]
			del self.payload[_id]

			self._task_removed(_id, data, _p)

	def stop(self):
		self.work_lock.acquire()

		if self.thread_handle == None:
			self.work_lock.release()
			return

		#flush queue
		try:
			while True:
				_id = self.queue.get_nowait()
				self._try_remove_task(_id)
				
		except queue.Empty:
			pass
		self.work_lock.release()

		#push empty task and wait for shutdown
		self.queue.put(None)
		self.thread_handle.join()
		self.thread_handle = None

	#discard a queued item, item must not be started, if it's started then discard will fail
	def remove(self, _id):
		self.work_lock.acquire()
		if _id != self.context_id:
			self._try_remove_task(_id)
		self.work_lock.release()

	#add item to queue
	def add(self, _id, _item_dict, _payload):
		self.work_lock.acquire()
		if _id in self.tasks:
			self.work_lock.release()
			return False
		
		self.tasks[_id] = _item_dict
		self.payload[_id] = _payload
		self.work_lock.release()

		self.queue.put(_id)
		return True

	def query_items(self):
		self.work_lock.acquire()
		result = copy.deepcopy(self.tasks)
		if self.context_copy != None:
			result[self.context_id] = copy.deepcopy(self.context_copy)
		self.work_lock.release()

		return result

	def query_status(self):
		
		status = None
		tasks = None
		active = None

		self.work_lock.acquire()

		if (self.thread_handle != None):
			status = "active"
		else:
			status = "inactive"

		tasks = copy.deepcopy(self.tasks)

		if self.context_copy != None:
			active = copy.deepcopy(self.context_copy)

		self.work_lock.release()

		return {
			"status" : status,
			"queue" : tasks,
			"active" : active
		}

	def is_active(self):
		self.work_lock.acquire()
		if self.thread_handle == None:
			self.work_lock.release()
			return False
		
		result = len(self.tasks)
		self.work_lock.release()
		if result > 0:
			return True

		return False

	def wait(self):
		self.work_lock.acquire()
		sz = len(self.tasks)
		if sz > 0:
			ev = threading.Event()
			func = lambda: ev.set()
			if self.listeners == None:
				self.listeners = [func]
			else:
				self.listeners.append(func)

			self.work_lock.release()
			ev.wait()
			return;
			
		self.work_lock.release()

	def prepare_task(self, _id, _itm):
		return copy.deepcopy(_itm), self.payload.get(_id, None)

	def execute_active_task(self, _id, _payload):
		pass

	def task_finished(self, _id, _task_copy, _payload):
		del self.tasks[_id]
		del self.payload[_id]

		if len(self.tasks) == 0 and self.listeners != None:
			l = self.listeners
			self.listeners = None
			for func in l:
				func()

	def acquire_active_context(self):
		self.work_lock.acquire()
		return self.context_copy

	def release_active_context(self, _ctx):
		self.work_lock.release()

	def thread_run_loop(self):
		
		while True:
			_id = self.queue.get()
			if _id == None:
				break

			self.work_lock.acquire()
			_item = self.tasks.get(_id,None)

			if _item != None:
				_work_item_copy, _exec_payload = self.prepare_task(_id, _item)
				self.context_id = _id
				self.context_copy = _work_item_copy
				self.work_lock.release()
				
				self.execute_active_task(_id, _exec_payload)
				
				self.work_lock.acquire()
				self.context_id = None
				self.context_copy = None
				
				self.task_finished(_id, _work_item_copy, _exec_payload)
				
			#else: item could be removed before it was processed

			self.work_lock.release()