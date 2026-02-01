@echo off
echo Starting MCP Server (port 8002)...
cd /d "%~dp0backend"
"%~dp0mcp_venv\Scripts\python.exe" mcp_server.py
pause
