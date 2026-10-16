import subprocess
import sys
import time
start = time.process_time()
while time.process_time() - start < .15:
    pass
subprocess.run([sys.executable, sys.argv[1]], check=True)
