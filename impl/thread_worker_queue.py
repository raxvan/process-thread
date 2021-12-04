import copy

import threading
import queue

class SingleTaskListener():
	def __init__(self):
		self.data = None
		self.ev = threading.Event()

	def wait(self):
		self.ev.wait()

	def notify(self, _id, _data):
		if(_data != None):
			self.data = copy.deepcopy(_data)
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

		self.work_lock = threading.Lock()
		self.active_items = {}
		self.active_work_id = None
		self.active_work_item = None

		self.on_complete_listeners = {}
				
	def start(self):
		self.thread_handle = threading.Thread(target=lambda e: e.thread_run_loop(), args=(self,), daemon=True)
		self.thread_handle.start()

	def stop(self):
		if self.thread_handle == None:
			return

		#flush queue
		self.work_lock.acquire()
		try:
			while True:
				_id = self.queue.get_nowait()
				del self.active_items[_id]
				l = self.on_complete_listeners.get(_id,None)
				if l != None:
					del self.on_complete_listeners[_id]
					for func in l:
						_func(_id, None)
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
		if _id != self.active_work_id:
			_item = self.active_items.get(_id,None)
			if _item != None:
				del self.active_items[_id]
		self.work_lock.release()

	#add item to queue
	def push_back_nocopy(self, _id, _item_dict):
		self.work_lock.acquire()
		if _id in self.active_items:
			self.work_lock.release()
			return False	
		self.active_items[_id] = _item_dict
		self.work_lock.release()

		self.queue.put(_id)
		return True

	def query_items(self):
		self.work_lock.acquire()
		result = copy.deepcopy(self.active_items)
		if self.active_work_item != None:
			result[self.active_work_id] = copy.deepcopy(self.active_work_item)
		self.work_lock.release()

		return result

	def prepare_task_data(self, _id, _itm):
		return None

	def execute_active_task(self, _id):
		pass

	def add_listener_locked(self, _id, e):
		ln = lambda _id, _itm: e.notify(_id, _itm)
		self.on_complete_listeners.setdefault(_id,[]).append(ln)
		
	def wait_for_task_finished(self, _id):
		self.work_lock.acquire()
		if _id in self.active_items:
			e = SingleTaskListener()
			self.add_listener_locked(_id, e)
			self.work_lock.release()
			e.wait()
			return e.data

		self.work_lock.release()
		return None

	def wait_for_empty(self):
		self.work_lock.acquire()
		sz = len(self.active_items)
		if sz > 0:
			#keep waiting
			e = MultipleTaskListener(sz)
			for k, v in self.active_items.items():
				self.add_listener_locked(k, e)

			self.work_lock.release()
			e.wait()
			return
			
		self.work_lock.release()

	def prepare_task(self, _id, _itm):
		return copy.deepcopy(_itm)

	def task_finished(self, _id, _itm_copy):
		#notify listeners
		l = self.on_complete_listeners.get(_id,None)
		if l != None:
			del self.on_complete_listeners[_id]
			for func in l:
				func(_id, _itm_copy)


	def thread_run_loop(self):
		
		while True:
			_id = self.queue.get()
			if _id == None:
				break

			self.work_lock.acquire()
			_item = self.active_items.get(_id,None)

			if _item != None:
				_work_item_copy = self.prepare_task(_id, _item)
				self.active_work_id = _id
				self.active_work_item = _work_item_copy
				self.work_lock.release()
				
				self.execute_active_task(_id)
				
				self.work_lock.acquire()
				self.active_work_id = None
				self.active_work_item = None
				
				if _id in self.active_items:
					#item with _id could be deleted by a stop()
					del self.active_items[_id]

				self.task_finished(_id, _work_item_copy)
				
			#else: item could be removed before it was processed

			self.work_lock.release()