"""Remote execution utilities for Enterprise Mode.

Handles SSH execution against RHEL servers. In the local POC environment,
this intercepts the commands and simply logs them to simulate the execution
of massive Ab Initio or Teradata batch jobs without actually needing a live
infrastructure connection.
"""

import os
from config.settings import ENTERPRISE_MODE
from utils.logger import get_logger

log = get_logger("remote_executor")


class RemoteExecutor:
    """Wrapper for executing shell commands on remote legacy/enterprise servers."""

    def __init__(self, host: str, user: str, mock_override: bool = True):
        self.host = host
        self.user = user
        self.mock = mock_override or not ENTERPRISE_MODE
        self.client = None

        if not self.mock:
            try:
                import paramiko
                self.client = paramiko.SSHClient()

                # Load system known-hosts for host key verification.
                # Reject unknown hosts to prevent MITM attacks.
                known_hosts = os.getenv("SSH_KNOWN_HOSTS", os.path.expanduser("~/.ssh/known_hosts"))
                if os.path.isfile(known_hosts):
                    self.client.load_host_keys(known_hosts)
                else:
                    log.warning(f"Known-hosts file not found at {known_hosts}")
                self.client.set_missing_host_key_policy(paramiko.RejectPolicy())

                log.info(f"Initialized SSH client for {user}@{host} (host key verification enabled)")
            except Exception as e:
                log.warning(f"Failed to initialize SSH client: {e}. Falling back to mock execution.")
                self.mock = True

    def connect(self, key_path: str = None, password: str = None):
        """Establish the SSH connection."""
        if self.mock:
            log.debug(f"[MOCK SSH] Connected to {self.user}@{self.host}")
            return True

        try:
            self.client.connect(hostname=self.host, username=self.user,
                                key_filename=key_path, password=password)
            log.debug(f"Connected to {self.user}@{self.host} successfully")
            return True
        except Exception as e:
            log.error(f"SSH connection failed: {e}")
            return False

    def execute_command(self, command: str) -> dict:
        """Execute a remote command and return the status and output."""
        if self.mock:
            log.info(f"[MOCK SSH EXEC] {self.user}@{self.host}:~ $ {command}")
            return {"exit_code": 0, "stdout": f"Mock executed: {command}\nSuccess.\n", "stderr": ""}

        if not self.client:
            return {"exit_code": -1, "stdout": "", "stderr": "No active SSH client"}

        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8")
            err = stderr.read().decode("utf-8")

            log.debug(f"Remote command finished with exit code {exit_code}")
            return {"exit_code": exit_code, "stdout": out, "stderr": err}

        except Exception as e:
            log.error(f"Command execution failed over SSH: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}

    def close(self):
        """Close the SSH connection."""
        if self.mock:
            log.debug(f"[MOCK SSH] Connection to {self.host} closed")
            return

        if self.client:
            self.client.close()
            log.debug(f"SSH connection to {self.host} closed")
