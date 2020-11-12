# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

# -----------------------------------------------------------------------------
#
class SSHRemoteTunnel:
    '''
    Run ssh to set up a tunnel to a remote host.
    If the connection fails or times out raise an error.
    Randomly chosen ports in the port range are tried until an available one
    is found.  If all are unavailable an exception is raised.
    '''
    def __init__(self, remote, key_path, remote_port_range, local_port, log = None,
                 connection_timeout = 5, exit_check_interval = 1.0, closed_callback = None):
        host = remote.split('@')[1] if '@' in remote else remote
        self.host = host
        self.local_port = local_port
        self._log = log
        self._closed_callback = closed_callback

        p, remote_port = self._create_tunnel(remote, remote_port_range, local_port, key_path, connection_timeout)
        self._popen = p
        self.remote_port = remote_port

        # Assure at exit that the process is terminated.
        import atexit
        atexit.register(self.close)

        # Periodically check if ssh has exited.
        if exit_check_interval is None:
            t = None
        else:
            t = _periodic_callback(exit_check_interval, self._check_for_process_exit)
        self._exit_check_timer = t

    # -----------------------------------------------------------------------------
    #
    def _create_tunnel(self, remote, remote_port_range, local_port, key_path, connection_timeout):
        '''
        Run ssh trying remote ports until an available one is found.
        '''

        # Try ports in random order.
        port_min, port_max = remote_port_range
        from numpy import arange, int32, random
        ports = arange(port_min, port_max+1, dtype=int32)
        random.shuffle(ports)
        
        from chimerax.core.errors import UserError
        for remote_port in ports:
            self._log.status('Checking if port %d available on proxy server %s'
                             % (remote_port, self.host))
            p = self._run_ssh(remote, remote_port, local_port, key_path, connection_timeout)
            if p is None:
                raise UserError('meeting: failed creating tunnel to proxy')
            exit_message = self._tunnel_created(p, connection_timeout)
            if exit_message is None:
                self._log.status('Created tunnel to proxy %s' % self.host)
                return p, remote_port
            if 'timed out' in exit_message:
                self._log.warning(exit_message)
                raise UserError('meeting: Connection to proxy server %s timed out' % remote)
            elif 'Connection closed' in exit_message:
                self._log.warning(exit_message)
                raise UserError('meeting: Connection to proxy server %s closed' % remote +
                                ', possibly an authentication problem.')
            elif 'failed for listen port' in exit_message:
                continue

        self._log.warning(exit_message)
        raise UserError('meeting: No remote ports (%d - %d) available for ssh tunnel to proxy %s'
                        % (remote_port_range[0], remote_port_range[1], remote))

    # -----------------------------------------------------------------------------
    #
    def _run_ssh(self, remote, remote_port, local_port, key_path, connection_timeout):
        '''Returns subprocess.Popen object.  Does not wait for ssh to connect.'''

        import sys
        if sys.platform == 'win32':
            ssh_exe = 'C:\\Windows\\System32\\OpenSSH\\ssh.exe'
            # Prevent console window from showing.
            from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW
            startupinfo = STARTUPINFO()
            startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        else:
            ssh_exe = 'ssh'
            startupinfo = None

        command = [
            ssh_exe,
            '-N',					# Do not execute remote command
            '-i', key_path,				# Private key for authentication
            # '-f',  # Test: Fork and exit when tunnel created, leaves no way to kill process
            '-o', 'ExitOnForwardFailure=yes',		# If remote port in use already exit instead of warn
            '-o', 'ConnectTimeout=%d' % connection_timeout, # Fail faster than 75 second TCP timeout if can't connect
            '-o', 'StrictHostKeyChecking=no',		# Don't ask about host authenticity on first connection
            '-R', '%d:localhost:%d' % (remote_port,local_port),	# Remote port forwarding
            remote,	# Remote machine
        ]

        from subprocess import Popen, PIPE
        try:
            p = Popen(command, stdout=PIPE, stderr=PIPE, startupinfo=startupinfo)
        except Exception as e:
            msg = ('meeting: failed creating tunnel to proxy "%s"\n%s'
                   % (str(command), str(e)))
            self._log.warning(msg)
            p = None

        return p

    # -----------------------------------------------------------------------------
    #
    def _tunnel_created(self, p, connection_timeout):
        '''
        If ssh process p (subprocess.Popen instance) does not terminate
        before the connection time out interval then assume the tunnel has
        been created.  On failure return the ssh error message.
        '''
        check_interval = 0.5	# seconds
        steps = int((connection_timeout + 1) / check_interval)
        from time import sleep
        for step in range(steps):
            exit_code = p.poll()
            if exit_code is None:
                sleep(check_interval)
            else:
                return self._ssh_exit_message(p)
        return None
    
    # -----------------------------------------------------------------------------
    #
    def close(self):
        ect = self._exit_check_timer
        if ect is not None:
            ect.stop()
            self._exit_check_timer = None

        p = self._popen
        if p and p.poll() is None:
            p.terminate()
        self._popen = None

    # -----------------------------------------------------------------------------
    #
    def _check_for_process_exit(self):
        p = self._popen
        exit_code = p.poll()
        if exit_code is None:
            return	# Still running

        if exit_code == 0:
            self._log.info('meeting: ssh tunnel closed.')
        else:
            msg = self._ssh_exit_message(p)
            self._log.warning(msg)

        self._exit_check_timer.stop()

        ccb = self._closed_callback
        if ccb:
            ccb()

    # -----------------------------------------------------------------------------
    #
    def _ssh_exit_message(self, p):
        command = ' '.join(p.args)
        msg = 'meeting: ssh tunnel setup failed %s, exit code %d' % (command, p.returncode)
        out = p.stdout.read().decode('utf-8')
        err = p.stderr.read().decode('utf-8')
        if out:
            msg += '\nssh stdout:\n%s' % out
        if err:
            msg += '\nssh stderr:\n%s' % err
        return msg

# -----------------------------------------------------------------------------
#
def _periodic_callback(interval, callback, *args, **kw):
    from PyQt5.QtCore import QTimer
    t = QTimer()
    def cb(callback=callback, args=args, kw=kw):
        callback(*args, **kw)
    t.timeout.connect(cb)
    t.setSingleShot(False)
    t.start(int(1000*interval))
    return t
