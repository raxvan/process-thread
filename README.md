# process-queue

Portable asynchronous process creation queue with streamed output (stdout,stderr). For each queue, processes are started in order, one at a time (first one need to exit for the next one to start).

### Dependencies:

- python3
- `psutil` for killing processes (imported only if a process needs to be killed)

### Tested on:

- windows 10
- x86 ubuntu server
- arm ubuntu server
- arm raspbian os
- x86 ubuntu docker container

## Basic Usage:

See `tests` folder for more examples on how to create custom handlers other "advanced" functionality

```
q = ProcessQueue(root_dir, base_environment_vars_dict)
q.start()

process = {
	"cmd" : ["powershell" script.cmd]
}
q.push_back(id, process)
q.wait_for_empty()
q.stop()
```

where:
- `id` is a number or string that uniquely identifies the instance of the process
- `root_dir` can be None, is the root directory for all processes that are going to be executed
- `base_environment_vars_dict` is the base environment dict for executables. Can be `os.environ.copy()` for simple use-cases.

### Details:

Each entry requires a dictionary (process data) with the following keys:

- `cmd`: list, the command that's going to be executed
- `cwd`: string or list, the working directory of the process
- `env`: dict, additional environment variables to be added to the process

Note that `cmd` and `cwd` can have syntax like `{ENV_VAR}` that will be replaced (python format) before launching the executable (see "final" data member below)

Additional data can be added and will be passed on to the handler when processes finishes. After a process completes the dictionary can look something like this:

```
{
    "cmd": ...,
    "cwd": ...,
    "env": ...,
    	#^ input

    "error": "Error message",
    	#^ a simplified error message when the process failed to run, or crashed
    "exit": 1234,
    	#^ executable exit code
    "stderr": 0,
    	#^ number of lines in stderr stream

    "final": {
        "cmd": ...,
        "cwd": ...,
        "env": { ... }
         #^ final command, working directory and environment that was used to spawn the process
         #note that you can use {_ENV_VAR_} to expand from `env` in cmd or cwd
    },
    "pid": 123,
    #^ process id if the process actually started
    "state": -1,
    #^ current state of the execution
    #0: process is queued
    #1: process is running
    #2: process completed without error
    #-1: some error was encountered and 
    

    "time-end": 1638626792.890096,
    "time-queue": 1638626792.8670387,
    "time-start": 1638626792.8680394
    #^ timepoint in seconds (when it was queued, when the process started, and when it ended)
}
```

Some of the data from above 


### Important functions:

- `ProcessQueue.push_back(self, id, data)` add process to queue
- `ProcessQueue.wait_for_pid(self, id, _sleep_interval_fsec = 0.25)` will wait until the process actually started, will return pid
- `ProcessQueue.remove_or_kill(self, id, _sleep_interval_fsec = 0.25)` remove process from queue, or kill if the process started. Returns process data
- `ProcessQueue.remove(self, id)` removes a process from queue if it's not started
- `ProcessQueue.query_items(self)` returns a dictionary (key is id, value is process data) of the active state of the queue
- `ProcessQueue.wait_for_task_finished(self, id)` wait for a certain process to be completed, returns process data
- `ProcessQueue.wait_for_empty(self)` wait for queue to be empty
- `ProcessQueue.create_process_handler(self, id, process, env_dict)` overritable function when you want to create a custom handler (see process_handler.py and tests)
- `ProcessQueue.start/stop(self)` start and stop the queue thread. `stop` flushes the queue and waits for the active process to complete

### Environment variables

The environment for each process is added in order, first ProcessQueue env (added in the constructor), process data env (added with process data) and other calculated env vars:

- `_ID_` the process id passed to `push_back`
- `_WORKDIR_` the current working directory when the process starts
- `_HANDLER_` class name of the handler
- `_PROCESS_ROOT_DIR_` process queue root directory (passed to ProcessQueue constructor)
- `_SHELL_` proffered shell, on windows this is `powershell`, on everything else is `/bin/bash`
- `_SHELL_EXT_` on windows this is `cmd`, on everything else it's `sh`
- `_SHELL_OPT_` empty on windows, `_SHELL_EXT_` on anything else


## TODO and improvements:

Considering to improve `_SHELL_` and `_SHELL_EXT_` support.



