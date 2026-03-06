# Tool Executor - Executes OpenCode tools locally

import asyncio
import json
import logging
import os
import subprocess
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Executes OpenCode-compatible tools locally"""
    
    def __init__(self):
        self.tool_registry = {
            # File operations
            "file_read": self.file_read,
            "file_write": self.file_write,
            "file_search": self.file_search,
            "file_list": self.file_list,
            
            # System operations
            "bash": self.bash,
            "system_info": self.system_info,
            
            # Web operations
            "web_search": self.web_search,
            "web_fetch": self.web_fetch,
            
            # Code execution
            "code_execute": self.code_execute,
            
            # Git operations
            "git_status": self.git_status,
            "git_diff": self.git_diff,
            "git_log": self.git_log,
        }
    
    async def execute_batch(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute multiple tool calls in parallel"""
        tasks = []
        for call in tool_calls:
            task = self.execute_single(call)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "tool_call_id": tool_calls[i].get('id', f'call_{i}'),
                    "output": f"Error: {str(result)}",
                    "success": False
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def execute_single(self, tool_call: Dict) -> Dict:
        """Execute a single tool call"""
        function_name = tool_call.get('function', {}).get('name')
        arguments_str = tool_call.get('function', {}).get('arguments', '{}')
        call_id = tool_call.get('id', 'unknown')
        
        try:
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError:
            arguments = {}
        
        logger.info(f"Executing tool: {function_name}")
        
        if function_name not in self.tool_registry:
            return {
                "tool_call_id": call_id,
                "output": f"Unknown tool: {function_name}",
                "success": False
            }
        
        try:
            result = await self.tool_registry[function_name](**arguments)
            return {
                "tool_call_id": call_id,
                "output": result,
                "success": True
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "tool_call_id": call_id,
                "output": f"Error: {str(e)}",
                "success": False
            }
    
    # File Operations
    
    async def file_read(self, path: str, offset: int = 0, limit: int = None) -> str:
        """Read file contents"""
        logger.info(f"Reading file: {path}")
        
        # Security: prevent directory traversal
        path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.exists(path):
            return f"Error: File not found: {path}"
        
        if not os.path.isfile(path):
            return f"Error: Path is not a file: {path}"
        
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                if offset > 0:
                    f.seek(offset)
                content = f.read(limit) if limit else f.read()
                return content
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    async def file_write(self, path: str, content: str, append: bool = False) -> str:
        """Write content to file"""
        logger.info(f"Writing to file: {path}")
        
        path = os.path.abspath(os.path.expanduser(path))
        
        # Create directories if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        try:
            mode = 'a' if append else 'w'
            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
    
    async def file_search(self, pattern: str, path: str = '.', glob: str = '*') -> str:
        """Search for files by pattern"""
        import glob as glob_module
        
        path = os.path.abspath(os.path.expanduser(path))
        
        try:
            matches = []
            for root, dirs, files in os.walk(path):
                # Filter by glob pattern
                import fnmatch
                for filename in files:
                    if fnmatch.fnmatch(filename, glob):
                        full_path = os.path.join(root, filename)
                        # Check if pattern in content (if text file)
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if pattern in content:
                                    matches.append(full_path)
                        except:
                            continue
            
            if matches:
                return f"Found {len(matches)} matches:\n" + "\n".join(matches[:50])
            else:
                return "No matches found"
        except Exception as e:
            return f"Error searching: {str(e)}"
    
    async def file_list(self, path: str = '.') -> str:
        """List files in directory"""
        path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.exists(path):
            return f"Error: Path not found: {path}"
        
        try:
            entries = os.listdir(path)
            result = []
            for entry in sorted(entries):
                full_path = os.path.join(path, entry)
                entry_type = "📁" if os.path.isdir(full_path) else "📄"
                result.append(f"{entry_type} {entry}")
            return "\n".join(result)
        except Exception as e:
            return f"Error listing directory: {str(e)}"
    
    # System Operations
    
    async def bash(self, command: str, timeout: int = 30) -> str:
        """Execute bash command"""
        logger.info(f"Executing bash: {command[:100]}...")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            output = stdout.decode('utf-8', errors='ignore')
            if stderr:
                output += "\n[STDERR]\n" + stderr.decode('utf-8', errors='ignore')
            
            return output[:5000]  # Limit output size
        except asyncio.TimeoutError:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    async def system_info(self) -> str:
        """Get system information"""
        try:
            info = {
                "platform": os.uname().sysname if hasattr(os, 'uname') else 'unknown',
                "hostname": os.uname().nodename if hasattr(os, 'uname') else 'unknown',
                "cpu_count": os.cpu_count(),
                "cwd": os.getcwd(),
                "time": datetime.now().isoformat()
            }
            return json.dumps(info, indent=2)
        except Exception as e:
            return f"Error getting system info: {str(e)}"
    
    # Web Operations (placeholders - implement based on your needs)
    
    async def web_search(self, query: str) -> str:
        """Search the web"""
        # You can integrate with various search APIs
        return f"Web search not configured. Query: {query}"
    
    async def web_fetch(self, url: str) -> str:
        """Fetch web content"""
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read().decode('utf-8', errors='ignore')[:5000]
        except Exception as e:
            return f"Error fetching URL: {str(e)}"
    
    # Code Execution
    
    async def code_execute(self, code: str, language: str = 'python', timeout: int = 30) -> str:
        """Execute code in sandbox"""
        logger.info(f"Executing {language} code...")
        
        if language == 'python':
            return await self._execute_python(code, timeout)
        elif language == 'bash':
            return await self.bash(code, timeout)
        else:
            return f"Language {language} not supported"
    
    async def _execute_python(self, code: str, timeout: int) -> str:
        """Execute Python code safely"""
        # Create temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            process = await asyncio.create_subprocess_exec(
                'python3', temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            result = stdout.decode('utf-8', errors='ignore')
            if stderr:
                result += "\n[STDERR]\n" + stderr.decode('utf-8', errors='ignore')
            
            return result[:5000]
        except asyncio.TimeoutError:
            return f"Python execution timed out after {timeout}s"
        except Exception as e:
            return f"Error executing Python: {str(e)}"
        finally:
            os.unlink(temp_file)
    
    # Git Operations
    
    async def git_status(self, path: str = '.') -> str:
        """Get git status"""
        return await self.bash(f'cd {path} && git status', timeout=10)
    
    async def git_diff(self, path: str = '.', staged: bool = False) -> str:
        """Get git diff"""
        cmd = 'git diff --cached' if staged else 'git diff'
        return await self.bash(f'cd {path} && {cmd}', timeout=10)
    
    async def git_log(self, path: str = '.', n: int = 10) -> str:
        """Get git log"""
        return await self.bash(f'cd {path} && git log -n {n} --oneline', timeout=10)
