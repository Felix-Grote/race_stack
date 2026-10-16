"""Report nonsecret execution facts and enforce required container isolation."""
import json
import os
import pathlib
import platform
import socket

status = pathlib.Path('/proc/self/status').read_text().splitlines()
security = dict(line.split(':', 1) for line in status if ':' in line)
assert os.getuid() != 0
assert int(security['CapEff'].strip(), 16) == 0
assert security['NoNewPrivs'].strip() == '1'
assert socket.if_nameindex() == [(1, 'lo')]
for path in ('/', '/src'):
    assert os.statvfs(path).f_flag & os.ST_RDONLY
print(json.dumps({
    'python': platform.python_version(), 'platform': platform.platform(),
    'uid': os.getuid(), 'interfaces': socket.if_nameindex(),
    'cap_eff': security['CapEff'].strip(), 'no_new_privs': security['NoNewPrivs'].strip(),
    'root_and_source_readonly': True, 'ros_distro': os.environ['ROS_DISTRO'],
}, indent=2))
