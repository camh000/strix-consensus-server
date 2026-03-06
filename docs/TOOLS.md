# Supported Tools

Strix Consensus Server supports all OpenCode tools through the Tool Executor. This document lists available tools and their usage.

## File Operations

### file_read

Read contents of a file.

**Parameters**:
- `path` (string, required): File path
- `offset` (int, optional): Start reading from this byte offset
- `limit` (int, optional): Maximum bytes to read

**Example**:
```json
{
  "tool": "file_read",
  "arguments": {
    "path": "/home/user/project/main.py",
    "offset": 0,
    "limit": 1000
  }
}
```

### file_write

Write or append to a file.

**Parameters**:
- `path` (string, required): File path
- `content` (string, required): Content to write
- `append` (boolean, optional): Append instead of overwrite (default: false)

**Example**:
```json
{
  "tool": "file_write",
  "arguments": {
    "path": "/home/user/project/output.txt",
    "content": "Hello World",
    "append": false
  }
}
```

### file_search

Search for files containing a pattern.

**Parameters**:
- `pattern` (string, required): Text to search for
- `path` (string, optional): Directory to search (default: current)
- `glob` (string, optional): File pattern filter (default: *)

**Example**:
```json
{
  "tool": "file_search",
  "arguments": {
    "pattern": "TODO",
    "path": "/home/user/project",
    "glob": "*.py"
  }
}
```

### file_list

List files in a directory.

**Parameters**:
- `path` (string, optional): Directory path (default: current)

**Example**:
```json
{
  "tool": "file_list",
  "arguments": {
    "path": "/home/user/project"
  }
}
```

## System Operations

### bash

Execute bash commands.

**Parameters**:
- `command` (string, required): Command to execute
- `timeout` (int, optional): Timeout in seconds (default: 30)

**Example**:
```json
{
  "tool": "bash",
  "arguments": {
    "command": "ls -la /home/user/project",
    "timeout": 10
  }
}
```

**Security Note**: Commands run as current user without sudo access.

### system_info

Get system information.

**Parameters**: None

**Returns**: Platform, hostname, CPU count, working directory, time

**Example**:
```json
{
  "tool": "system_info",
  "arguments": {}
}
```

## Web Operations

### web_search

Search the web (requires configuration).

**Parameters**:
- `query` (string, required): Search query

**Example**:
```json
{
  "tool": "web_search",
  "arguments": {
    "query": "Python best practices 2024"
  }
}
```

**Note**: Requires search API configuration. Returns placeholder by default.

### web_fetch

Fetch content from a URL.

**Parameters**:
- `url` (string, required): URL to fetch

**Example**:
```json
{
  "tool": "web_fetch",
  "arguments": {
    "url": "https://api.example.com/docs"
  }
}
```

## Code Execution

### code_execute

Execute code in a sandbox.

**Parameters**:
- `code` (string, required): Code to execute
- `language` (string, optional): Language (python, bash, default: python)
- `timeout` (int, optional): Timeout in seconds (default: 30)

**Example**:
```json
{
  "tool": "code_execute",
  "arguments": {
    "code": "print('Hello from Python')",
    "language": "python",
    "timeout": 10
  }
}
```

**Supported Languages**:
- `python`: Python 3.x
- `bash`: Bash shell commands

**Security**: Code runs in isolated subprocess with timeout.

## Git Operations

### git_status

Get git status of a repository.

**Parameters**:
- `path` (string, optional): Repository path (default: current)

**Example**:
```json
{
  "tool": "git_status",
  "arguments": {
    "path": "/home/user/project"
  }
}
```

### git_diff

Get git diff.

**Parameters**:
- `path` (string, optional): Repository path (default: current)
- `staged` (boolean, optional): Show staged changes (default: false)

**Example**:
```json
{
  "tool": "git_diff",
  "arguments": {
    "path": "/home/user/project",
    "staged": false
  }
}
```

### git_log

Get recent git commits.

**Parameters**:
- `path` (string, optional): Repository path (default: current)
- `n` (int, optional): Number of commits (default: 10)

**Example**:
```json
{
  "tool": "git_log",
  "arguments": {
    "path": "/home/user/project",
    "n": 5
  }
}
```

## Tool Execution Flow

1. **Client Request**: OpenCode sends chat request with tools
2. **Orchestrator**: Receives request and forwards to worker(s)
3. **Worker Response**: Model returns response with `tool_calls`
4. **Tool Detection**: Orchestrator detects tool_calls in response
5. **Execution**: ToolExecutor.execute_batch() runs all tools
6. **Result Collection**: Tool outputs collected
7. **Re-query**: Messages updated with tool results
8. **Final Response**: Worker generates final response
9. **Return**: Complete response sent to client

## Adding Custom Tools

To add a custom tool:

1. Edit `orchestrator/tool_executor.py`
2. Add method to `ToolExecutor` class:

```python
async def my_custom_tool(self, param1: str, param2: int = 10) -> str:
    """Description of what this tool does"""
    # Implementation
    return f"Result: {param1}, {param2}"
```

3. Register in `__init__`:

```python
self.tool_registry = {
    # ... existing tools ...
    "my_custom_tool": self.my_custom_tool,
}
```

4. Restart orchestrator

## Tool Calling Format

When OpenCode uses tools, it sends:

```json
{
  "tool_calls": [
    {
      "id": "call_123",
      "type": "function",
      "function": {
        "name": "file_read",
        "arguments": "{\"path\": \"/path/to/file\"}"
      }
    }
  ]
}
```

Tools are executed and results appended to conversation:

```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "{tool output here}"
}
```

## Best Practices

1. **Use Absolute Paths**: Avoid relative paths when possible
2. **Handle Timeouts**: Set appropriate timeouts for long operations
3. **Check Outputs**: Always verify tool outputs before proceeding
4. **Limit Output Size**: Large outputs are truncated at 5000 chars
5. **Error Handling**: Tools return error messages in output field

## Limitations

- **No Network from Sandbox**: Code execution cannot access network
- **No Sudo**: Bash commands run as current user without elevation
- **Timeout**: All tools have timeout limits
- **Output Size**: Limited to 5000 characters
- **File Access**: Restricted to user-accessible files
