"""One Latitude.sh server, ready to run Turf Tools with Docker Compose.

Creates the server with an SSH key and a firewall open to SSH, HTTP, and
HTTPS. A first-boot script installs Docker; everything after that (the compose
file, configuration, images) is pushed over SSH, as `deploy.sh` and the app
repo's deploy/README.md describe.
"""

import base64
import os

import pulumi
import pulumi_latitudesh as latitudesh

config = pulumi.Config()
name = config.require("name")
project = config.require("project")
site = config.require("site")
size = config.require("size")
billing = config.get("billing") or "hourly"
ssh_public_key_path = config.get("ssh_public_key_path") or "~/.ssh/id_ed25519.pub"
# Changing the first-boot script reinstalls the OS and wipes the disk on
# Latitude, so such a change fails the plan unless this is set for that run.
allow_reinstall = config.get_bool("allow_reinstall") or False

# Runs once, at first boot. Keep it to what the machine needs before anything
# else arrives: Docker, and the directory deploys write into.
FIRST_BOOT = """\
#cloud-config
package_update: true
runcmd:
  - install -d -m 0750 /etc/turf-tools
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable --now docker
"""

with open(os.path.expanduser(ssh_public_key_path)) as f:
    ssh_public_key = f.read().strip()

ssh_key = latitudesh.SshKey("ssh", name=f"turf-tools-{name}", public_key=ssh_public_key)

firewall = latitudesh.Firewall(
    "firewall",
    name=f"turf-tools-{name}",
    project=project,
    rules=[
        latitudesh.FirewallRuleArgs(from_="0.0.0.0/0", to="0.0.0.0/0", port=port, protocol="tcp")
        for port in ("22", "80", "443")
    ],
)

first_boot = latitudesh.UserData(
    "first-boot",
    description=f"turf-tools-{name}",
    # The API takes the script base64-encoded.
    content=base64.b64encode(FIRST_BOOT.encode()).decode(),
)

server = latitudesh.Server(
    "server",
    hostname=f"turf-tools-{name}",
    operating_system="ubuntu_24_04_x64_lts",
    plan=size,
    site=site,
    project=project,
    billing=billing,
    ssh_keys=[ssh_key.id],
    user_data=first_boot.id,
    allow_reinstall=allow_reinstall,
)

latitudesh.FirewallAssignment("firewall-assignment", firewall_id=firewall.id, server_id=server.id)

pulumi.export("public_ip", server.primary_ipv4)
pulumi.export("ssh", server.primary_ipv4.apply(lambda ip: f"ssh ubuntu@{ip}"))
