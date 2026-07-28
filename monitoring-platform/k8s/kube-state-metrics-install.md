# Exposing kube-state-metrics to the monitoring VM

The monitoring VM scrapes the Kubernetes cluster **from outside** (Approach B —
the monitoring stack does not run inside the cluster it watches). We deploy
kube-state-metrics (KSM) in the cluster and expose it to the VM via a NodePort.

## Install (Helm)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install ksm prometheus-community/kube-state-metrics \
  --namespace monitoring --create-namespace \
  --set service.type=NodePort \
  --set service.nodePort=30080
```

KSM is read-only; keep the chart's default RBAC (list/watch of object metadata).

## Wire into Prometheus

Edit `prometheus/targets/kubernetes.yml` to point at any cluster node IP and the
NodePort:

```yaml
- targets:
    - '10.0.0.40:30080'
  labels:
    job: kube-state-metrics
```

Reload Prometheus: `curl -s -X POST http://localhost:9090/-/reload`

## Verify

```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="kube-state-metrics"}'
# expect value "1"
curl -s 'http://localhost:9090/api/v1/query?query=kube_pod_info' | head
```

## Notes / later

- For node-level CPU/memory of cluster nodes, also scrape kubelet/cAdvisor or run
  node_exporter as a DaemonSet exposed via NodePort. KSM alone gives object state
  (pods, deployments, restarts) which drives the KubePodCrashLooping alert.
- Restrict the NodePort to the monitoring VM via a network policy / firewall.
