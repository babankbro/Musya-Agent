"""Helper script to re-authenticate NotebookLM with a 60-second wait."""
import subprocess
import time
import sys

print("Starting NotebookLM login...")
print("Browser will open — please login to Google and wait for NotebookLM homepage.")
print("Will auto-confirm in 60 seconds...\n")

proc = subprocess.Popen(
    [sys.executable, "-m", "notebooklm", "login"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# Wait for user to login in browser
time.sleep(60)

# Send ENTER to confirm
proc.stdin.write("\n")
proc.stdin.flush()

try:
    out, _ = proc.communicate(timeout=30)
    print(out)
    print("\nLogin complete!")
except subprocess.TimeoutExpired:
    proc.kill()
    print("Timeout — check if login succeeded by running: notebooklm list")
