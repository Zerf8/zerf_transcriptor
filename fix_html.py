import re

with open("manager_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove the bad block injected from line 676 onwards. I will use regex.
bad_block_start = content.find('<div id="process-log-container"')
bad_block_end_str = "let logInterval = null;\n"
bad_block_end = content.find(bad_block_end_str, bad_block_start) + len(bad_block_end_str)

if bad_block_start != -1 and bad_block_end != -1:
    content = content[:bad_block_start] + content[bad_block_end:]

# 2. Insert process-log-container before <div id="toast">
html_to_insert = """
    <div id="process-log-container" style="display:none; position: fixed; bottom: 2rem; left: 2rem; width: 500px; height: 350px; background: #0a0a0c; border: 1px solid var(--border); border-radius: 12px; z-index: 1000; flex-direction: column; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.8);">
        <div style="background: #151518; padding: 0.5rem 1rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-size: 0.9rem; font-weight: bold; color: var(--primary);">
            <span>Consola de Procesamiento (main.py)</span>
            <button onclick="document.getElementById('process-log-container').style.display='none'; clearInterval(logInterval); logInterval=null;" style="background: none; border: none; color: white; cursor: pointer;">✕</button>
        </div>
        <div id="process-log-content" style="padding: 1rem; flex-grow: 1; overflow-y: auto; font-family: monospace; font-size: 0.8rem; color: #22c55e; white-space: pre-wrap; word-wrap: break-word;">
            Iniciando conexión con el proceso...
        </div>
    </div>
"""
if "process-log-container" not in content:
    content = content.replace('<div id="toast">Cargando...</div>', html_to_insert + '\n    <div id="toast">Cargando...</div>')

# 3. Ensure let logInterval = null; is at the top of the script
if "let logInterval = null;" not in content:
    content = content.replace("const pageLimit = 25;", "const pageLimit = 25;\n        let logInterval = null;")

with open("manager_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)
