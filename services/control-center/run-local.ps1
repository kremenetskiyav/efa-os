[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$Port = 8091)

$ErrorActionPreference = 'Stop'
$pythonPath = (Get-Command python -ErrorAction Stop).Source
# W06 structured snapshots are local read-only inputs. No MCP token or n8n needed.
& $pythonPath -X utf8 (Join-Path $PSScriptRoot 'app.py') --host 127.0.0.1 --port $Port
