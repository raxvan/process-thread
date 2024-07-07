
import os
import sys
import time
import json

_thisdir = os.path.dirname(__file__)
sys.path.append(os.path.join(_thisdir,"..","process-thread"))

import process_thread

def stdout(m):
	print(m.decode("utf-8"), end="")

def stderr(m):
	print(m.decode("utf-8"), end="")

h = process_thread.ProcessThread()

h.onStdout = stdout
h.onStderr = stderr

p = h.start(
	cmd = ["pwd"],
	cwd = ".",
	env = {}
)

rc, error = p.waitForExit()

if error != None:
	print(error)
else:
	print(f"DONE:{rc}")

h.join()

