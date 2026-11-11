# Restricted Docker Container Control

Dependency-free Python tools for restricted Docker container management over SSH.

## Server commands

    list
    status NAME_OR_ID
    logs NAME_OR_ID [LINES]
    start NAME_OR_ID
    stop NAME_OR_ID
    restart NAME_OR_ID

The server controller rejects arbitrary Docker arguments, exec, attach, and image/volume/network operations. Logs are capped at 500 lines.

## Security model

Use a new SSH keypair exclusively for this integration. Do not reuse a key that can log in to an administrative account on the remote host. The restricted account can manage containers and read their logs, but cannot obtain a shell or issue arbitrary Docker/root commands.

The server controller has an unprivileged SSH phase and a root phase. It reads SSH_ORIGINAL_COMMAND, invokes itself through one narrowly-scoped sudo rule, validates the request, and then invokes Docker. It is not a daemon and has no external dependencies.

The included client.py is an example constrained SSH client. An automation agent should be allowed to execute that client script, not the ssh executable itself.

## Repository files

    server/container_control.py       Install on the remote Docker host.
    client.py                         Copy outside the repository and configure locally.
    deploy/sudoers.devops             Example sudoers policy.
    deploy/authorized_keys.example    Example forced-command public-key entry.

## Example installation

These commands are examples for Ubuntu/Debian. Replace placeholders before running them.

### 1. Create a dedicated client key

On the client machine:

    ssh-keygen -t ed25519 -a 64 \
      -f ~/.ssh/id_ed25519_container_control \
      -C "container-control-client" \
      -N ""

The unencrypted key supports non-interactive automation. Protect the client account and storage encryption. Do not authorize this public key for an administrative account.

Print the public key:

    cat ~/.ssh/id_ed25519_container_control.pub

### 2. Copy and install the server controller

From the client machine:

    scp server/container_control.py \
      <admin-user>@homelab.local:/tmp/container-control

Connect to the remote host:

    ssh <admin-user>@homelab.local

On the remote host:

    sudo useradd --create-home --user-group --shell /bin/bash devops
    sudo passwd --lock devops
    sudo install -o root -g root -m 0755 \
      /tmp/container-control \
      /usr/local/sbin/container-control
    rm /tmp/container-control

Do not add devops to the docker or sudo groups.

### 3. Install the forced-command public key

On the remote host:

    sudo install -d -o devops -g devops -m 700 /home/devops/.ssh
    sudoedit /home/devops/.ssh/authorized_keys

Add one line, replacing the placeholder with the entire public key from step 1:

    restrict,command="/usr/local/sbin/container-control" ssh-ed25519 PASTE_THE_PUBLIC_KEY_HERE container-control-client

Then secure it:

    sudo chown devops:devops /home/devops/.ssh/authorized_keys
    sudo chmod 600 /home/devops/.ssh/authorized_keys

The restrict option disables interactive shell/TTY access, port forwarding, agent forwarding, X11 forwarding, and ~/.ssh/rc for this key.

### 4. Add the narrowly-scoped sudo policy

On the remote host:

    sudo visudo -f /etc/sudoers.d/devops-container-control

Add exactly:

    devops ALL=(root) NOPASSWD: /usr/local/sbin/container-control --internal *

Validate it:

    sudo visudo -cf /etc/sudoers.d/devops-container-control
    sudo chmod 440 /etc/sudoers.d/devops-container-control

Do not broaden this to general passwordless sudo or direct Docker access.

## Configure the constrained client

Copy client.py to a protected local location outside the repository. Edit only its policy constants:

    HOST             The fixed remote host, for example homelab.local.
    USER             The fixed restricted user, for example devops.
    IDENTITY_FILE    The dedicated key created above.
    KNOWN_HOSTS_FILE The normal per-user ~/.ssh/known_hosts file.

The client enables StrictHostKeyChecking, so SSH verifies that the server presents the expected host key. Before automating it, connect to the fixed host manually with a trusted administrative account and confirm its fingerprint; this records the host key in the normal known_hosts file. Do not disable StrictHostKeyChecking.

The client has a fixed host, user, key, known-hosts file, and SSH safety options. It accepts only the six documented controller commands. It does not accept arbitrary SSH options, hosts, identities, or remote commands.

Allowlist the configured client script, not ssh. Keep the dedicated private key outside this repository.

## Test

After configuring client.py, run:

    python3 /protected/path/client.py list
    python3 /protected/path/client.py logs <container-name> 50

Running the client with no command must return an error rather than an interactive shell.

## Local checks

    python3 -m unittest discover -s tests -v

