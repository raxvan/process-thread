
# AsyncProcessStream

Efficient management and streaming of subprocesses in Python with asynchronous capabilities.

## Features

- Asynchronous execution of subprocesses.
- Streaming of `stdout` and `stderr` output in real-time.
- Ability to wait for process start and completion.
- Thread-based management for handling multiple processes concurrently.

## Requirements

- Python 3.6+
- `asyncio`
- `psutil` (for process management)

## Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/raxvan/process-thread.git
cd https://github.com/raxvan/process-thread.git
pip install .
```

## Quickstart

Here's a simple way to use `AsyncProcessStream` to run a subprocess:

```python
from your_module import ProcessThread

# Callbacks for process events
def stdout_handler(data):
    print("STDOUT:", data.decode())

def stderr_handler(data):
    print("STDERR:", data.decode())

def process_started(state):
    print(f"Process {state.pid} started.")

# Initialize and start the process
process_thread = ProcessThread()
process_thread.onStdout = stdout_handler
process_thread.onStderr = stderr_handler
process_thread.onProcessStart = process_started

# Command to run, working directory, and environment variables
cmd = ['python', 'script.py']
cwd = '/path/to/directory'
env = {'MY_VAR': 'value'}

process_state = process_thread.start(cmd, cwd, env)

# Wait for the process to complete
exit_code, error = process_state.waitForExit()
print(f"Process exited with code {exit_text}.")

process_thread.join()
```

## API Reference

### `ProcessThread`

- `start(cmd, cwd, env)`: Starts a new process with the specified command, working directory, and environment.
- `join()`: Waits for all started processes to complete.

### `ProcessState`

- `waitForId()`: Waits for the process to start and returns its PID.
- `waitForExit()`: Waits for the process to complete and returns its exit code and error, if any.

## Contribution

Contributions are welcome! Please fork the repository and open a pull request with your improvements.

## License