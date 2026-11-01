#!/bin/bash
# OpenTransit H-1 build host: one boot = one refresh, then power off.
# Installed as /usr/local/libexec/opentransit-run-refresh (a copy, so updating the repository
# checkout cannot change this script while it runs) and started by opentransit-refresh.service.
#
# Instance tag OpenTransitMode=maintenance skips the refresh and leaves the host running (for SSM
# sessions); any other value or no tag runs the refresh. Logs: CloudWatch group $OT_LOG_GROUP,
# streams <stamp>/host (this script) and <stamp>/job (deploy/aws/tools/daily_refresh.py).
set -uo pipefail
source /etc/opentransit/build-host.env
export PATH=/opt/opentransit/bin:/usr/local/bin:/usr/bin:/bin HOME=/root
export UV_CACHE_DIR=/var/cache/uv UV_PYTHON_INSTALL_DIR=/opt/opentransit/python
export AWS_REGION=$OT_REGION AWS_DEFAULT_REGION=$OT_REGION
repo=/opt/opentransit/repo
stamp=$(date -u +%Y%m%dT%H%MZ)
host_log=/srv/ot/logs/host-$stamp.log
mkdir -p /srv/ot/logs
exec > >(tee -a "$host_log") 2>&1

imds() {
  local token
  token=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 300') || return 1
  curl -fsS -H "X-aws-ec2-metadata-token: $token" "http://169.254.169.254/latest/meta-data/$1"
}

mode=$(imds tags/instance/OpenTransitMode 2>/dev/null || echo refresh)
instance=$(imds instance-id || echo unknown)
echo "=== $(date -u +%FT%TZ) boot on $instance, mode $mode, stamp $stamp"
if [ "$mode" = maintenance ]; then
  echo "maintenance mode: no refresh, no power-off"
  exit 0
fi

# Ship this run's two log files to CloudWatch Logs (the agent uploads the newest matching file).
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<JSON
{"agent": {"run_as_user": "root"},
 "logs": {"force_flush_interval": 5, "logs_collected": {"files": {"collect_list": [
   {"file_path": "/srv/ot/logs/host-*.log", "log_group_name": "$OT_LOG_GROUP",
    "log_stream_name": "$stamp/host", "retention_in_days": -1},
   {"file_path": "/srv/ot/logs/daily-*.log", "log_group_name": "$OT_LOG_GROUP",
    "log_stream_name": "$stamp/job", "retention_in_days": -1}]}}}}
JSON
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

finish() {  # exit code; flush logs and power off
  echo "=== $(date -u +%FT%TZ) host exit $1; powering off"
  sleep 20
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a stop
  systemctl poweroff
  exit "$1"
}

host_failed() {  # step; a failure before the job starts gets its own result line and summary
  echo "OPENTRANSIT_REFRESH_RESULT outcome=failed mode=- stamp=$stamp step=$1"
  printf '{"stamp":"%s","outcome":"failed","failedStep":"host:%s","finishedAt":"%s"}\n' \
    "$stamp" "$1" "$(date -u +%FT%TZ)" > "/srv/ot/logs/host-$stamp.json"
  aws s3 cp --only-show-errors "/srv/ot/logs/host-$stamp.json" "s3://$OT_BUCKET/runs/$stamp.json"
  finish 1
}

# 1. The pinned repository ref (SSM parameter); reinstall when it moved.
ref=$(aws ssm get-parameter --name "$OT_REF_PARAMETER" --query Parameter.Value --output text) \
  || host_failed ref-parameter
if [ "$(git -C "$repo" rev-parse HEAD)" != "$ref" ]; then
  git -C "$repo" fetch -q --depth 1 origin "$ref" && git -C "$repo" checkout -q --detach FETCH_HEAD \
    || host_failed checkout
fi
echo "repository at $(git -C "$repo" rev-parse HEAD)"
if [ "$(cat /opt/opentransit/installed-ref 2>/dev/null)" != "$ref" ]; then
  bash "$repo/deploy/aws/build-host/install.sh" || host_failed install
fi

# 2. The serving release on first run: the operator machine's record, kept in the archive.
if [ ! -f /srv/ot/releases/current.json ]; then
  aws s3 cp --only-show-errors --recursive "s3://$OT_BUCKET/bootstrap/releases/" /srv/ot/releases/ \
    || host_failed bootstrap-release
fi

# 3. The ALB's private address in the H-1 VPC (its security group admits this host's group).
alb_ip=$(aws ec2 describe-network-interfaces \
  --filters "Name=description,Values=$OT_ALB_ENI_DESCRIPTION" \
  --query 'NetworkInterfaces[0].PrivateIpAddress' --output text) || host_failed alb-address
[ -n "$alb_ip" ] && [ "$alb_ip" != None ] || host_failed alb-address
echo "ALB private address $alb_ip"

# 4. The refresh itself (3 h cap; the backstop timer powers off at 4.5 h regardless).
timeout 3h uv run --project "$repo/services/api" --locked python \
  "$repo/deploy/aws/tools/daily_refresh.py" \
  --source-root /srv/ot/src --generations-root /srv/ot/generations --logs /srv/ot/logs \
  --releases /srv/ot/releases --photon-jar /opt/opentransit/photon/photon-1.3.0.jar \
  --osm-reader-path /opt/opentransit/osm-reader --profile '' --alb-url "http://$alb_ip" \
  --archive-bucket "$OT_BUCKET" --min-free-gib 12 --host-cleanup
rc=$?
[ $rc -eq 124 ] && echo "OPENTRANSIT_REFRESH_RESULT outcome=failed mode=- stamp=$stamp step=timeout"
df -h /srv/ot | tail -1
finish $rc
