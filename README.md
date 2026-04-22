# mini-splunk-agent

A lightweight log-forwarding agent for [Mini-Splunk](https://github.com/kakuPandeyy). It tails `.log` files in watched directories and ships batches to the Mini-Splunk backend over HTTP.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- A running Mini-Splunk backend

## Installation

Install the `splunk-agent` command globally using `uv`:

```bash
uv tool install git+https://github.com/kakuPandeyy/mini-Splunk-agent.git
```

Or run it once without a permanent install:

```bash
uvx --from git+https://github.com/kakuPandeyy/mini-Splunk-agent.git splunk-agent
```

## Configuration

Create a `.env` file in your working directory with the variables below. All values are optional — defaults are shown.

```env
BACKEND_URL=http://localhost:8000
AGENT_USERNAME=
AGENT_PASSWORD=
WATCH_PATH=
APP_TYPE=python
BATCH_SIZE=50
FLUSH_INTERVAL=5.0
MAX_RETRIES=3
DEAD_LETTER_FILE=agent_dead_letter.jsonl
LOG_LEVEL=INFO
```

| Variable | Default | Description |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Mini-Splunk backend URL |
| `AGENT_USERNAME` | _(empty)_ | Agent login username |
| `AGENT_PASSWORD` | _(empty)_ | Agent login password |
| `WATCH_PATH` | _(empty)_ | Directory to watch (optional, can be set interactively) |
| `APP_TYPE` | `python` | Log source type: `python`, `node`, or `windows` |
| `BATCH_SIZE` | `50` | Lines buffered before a flush is triggered |
| `FLUSH_INTERVAL` | `5.0` | Seconds between timed flushes |
| `MAX_RETRIES` | `3` | Retry attempts before dead-lettering a failed batch |
| `DEAD_LETTER_FILE` | `agent_dead_letter.jsonl` | File where failed batches are saved |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Usage

### Interactive mode

Run the agent without arguments — it will prompt for credentials, a watch path, and app type:

```bash
splunk-agent
```

```
Mini-Splunk Agent — Login
Username: agent
Password:

--- Agent Init ---
Watch path (Tab to complete): /var/log/myapp
App type (use arrow keys):
  > python
    node
    windows
```

### Non-interactive mode

Pass one or more directories via `--watch` to skip the init prompt (credentials are still requested):

```bash
splunk-agent --watch /var/log/myapp /var/log/other
```

### Interactive CLI commands

Once the agent is running, a simple REPL lets you manage watched directories at runtime:

```
Commands:
  add <path>   Start watching a directory for .log files
  rm  <path>   Stop watching a directory
  list         Show all active watch paths
  help         Show this message
  quit         Exit the agent
```

Example session:

```
agent> list
  /var/log/myapp
agent> add /var/log/another
added '/var/log/another'
agent> rm /var/log/myapp
removed '/var/log/myapp'
agent> quit
```

## How it works

1. On startup the agent authenticates with the backend and obtains a JWT.
2. It starts a filesystem watcher (`watchdog`) on each configured directory — recursively monitoring all `.log` files.
3. New lines appended to any `.log` file are buffered and forwarded to the backend in batches.
4. Batches are flushed when the buffer reaches `BATCH_SIZE` lines **or** `FLUSH_INTERVAL` seconds elapse, whichever comes first.
5. Failed deliveries are retried up to `MAX_RETRIES` times; batches that still fail are written to `DEAD_LETTER_FILE`.
6. Watch paths are persisted in `agent_sources.json` and automatically restored on the next run.

## Upgrading

```bash
uv tool upgrade mini-splunk-agent
```

## Uninstalling

```bash
uv tool uninstall mini-splunk-agent
```
