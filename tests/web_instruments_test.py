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

q = process_queue.ProcessQueue("", os.environ.copy())

qs = process_queue_server.ProcessQueueServer(q,8080)

q.start()
_itm = {
	"_print" : False,
	"env" : {
		"SLEEP_SECONDS" : "50"
	},
	"cmd" : ["{_SHELL_OPT_}", "{_PROCESS_ROOT_DIR_}/scripts_{_SHELL_EXT_}/wait.{_SHELL_EXT_}"]
}

h = q.push_back(0, _itm)
q.push_back(1, _itm)

h.wait()

q.stop()