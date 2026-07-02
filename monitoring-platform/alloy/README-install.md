# Installing Grafana Alloy on monitored hosts (log shipping → Loki)

Alloy runs on each **host you want logs from**, not on the monitoring VM. It
tails logs and pushes them to the central Loki with a `tenant` label.

## Linux

1. Install Alloy (Debian/RHEL packages): https://grafana.com/docs/alloy/latest/set-up/install/
2. Copy `config.alloy` to `/etc/alloy/config.alloy`.
3. Set env vars for the service (e.g. `/etc/default/alloy` or a systemd drop-in):
   ```
   LOKI_URL=http://<monitoring-vm-ip>:3100/loki/api/v1/push
   TENANT=acme
   ```
4. `systemctl enable --now alloy`
5. Verify on the monitoring VM:
   `curl -s http://localhost:3100/loki/api/v1/label/job/values` → should list `varlogs`.

## Windows

1. Install the Alloy Windows package (MSI).
2. Use the `loki.source.windowsevent` block (commented in `config.alloy`) instead
   of the file block, to ship the Windows Event Log.
3. Set `LOKI_URL` and `TENANT` as machine environment variables.
4. Start the Alloy service.

## Notes

- Open the host firewall outbound to the monitoring VM on 3100 only.
- The `tenant` external label keeps logs multi-tenant-ready (matches the metrics label).
