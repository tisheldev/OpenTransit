#!/bin/bash
# OpenTransit H-1 build host: first-boot setup (EC2 user data, runs once at launch).
# Rendered by deploy/aws/tools/build_host.py, which replaces the {{...}} values. It installs the
# distribution packages (dnf is locked to the AMI's release version), clones the repository at the
# ref stored in SSM Parameter Store and runs install.sh. Later boots run the daily refresh unit.
set -euxo pipefail
exec > >(tee -a /var/log/opentransit-user-data.log) 2>&1

install -d -m 0755 /etc/opentransit
cat > /etc/opentransit/build-host.env <<'ENV'
OT_REGION={{REGION}}
OT_BUCKET={{BUCKET}}
OT_LOG_GROUP={{LOG_GROUP}}
OT_REF_PARAMETER={{REF_PARAMETER}}
OT_REPO_URL={{REPO_URL}}
OT_ALB_ENI_DESCRIPTION={{ALB_ENI_DESCRIPTION}}
ENV

dnf install -y git docker amazon-cloudwatch-agent
systemctl enable --now docker

# 2 GiB swap on the root volume: headroom for the 6 GiB graph import next to the Python process.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  echo '/swapfile none swap defaults 0 0' >> /etc/fstab
fi
swapon -a

ref=$(aws ssm get-parameter --region {{REGION}} --name {{REF_PARAMETER}} --query Parameter.Value --output text)
repo=/opt/opentransit/repo
if [ ! -d "$repo/.git" ]; then
  git init -q "$repo"
  git -C "$repo" remote add origin {{REPO_URL}}
fi
git -C "$repo" fetch -q --depth 1 origin "$ref"
git -C "$repo" checkout -q --detach FETCH_HEAD
bash "$repo/deploy/aws/build-host/install.sh"
