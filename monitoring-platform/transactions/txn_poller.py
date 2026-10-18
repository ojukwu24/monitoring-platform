#!/usr/bin/env python3
"""Transaction-log poller.

Reads the transaction-log API on a schedule and turns what it returns into:
  * Prometheus metrics on :9488/metrics — counts, success rate and response-time
    histograms, cheap to put on a wall and to alert on;
  * Loki records — one JSON line per transaction, for drill-down by client,
    reference, status and anything else that is too varied to be a metric label.

Grafana never calls the API itself. The API is hit once per poll however many
screens show the wall, and the time picker and filters on the wall work on the
data already in Prometheus and Loki.

How a poll works
  Each service has a watermark: the end of the last window read successfully.
  A poll asks for  [watermark - TXN_OVERLAP, now - TXN_LAG]  so rows written a
  little late are still picked up, and skips any transactionRef it has already
  counted. The watermark only moves when a service's read succeeds, so a failed
  poll is retried by the next one. Watermarks and recently seen references are
  kept in TXN_STATE_FILE, so a restart neither loses nor double-counts.

Settings come from the environment (see .env.example, "Transaction logs").
Depends only on the Python standard library.
"""
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def env(name, default=""):
    return os.environ.get(name, default).strip()


def env_int(name, default):
    raw = env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        sys.exit("ERROR: %s must be a whole number, got %r" % (name, raw))


API_URL = env("TXN_API_URL")
API_KEY = env("TXN_API_KEY")
API_KEY_HEADER = env("TXN_API_KEY_HEADER", "api-key")
SERVICE_IDS = [s.strip() for s in env("TXN_SERVICE_IDS").split(",") if s.strip()] or [""]
INTERVAL = env_int("TXN_POLL_INTERVAL", 60)
LAG = env_int("TXN_LAG", 30)
OVERLAP = env_int("TXN_OVERLAP", 120)
MAX_BACKFILL = env_int("TXN_MAX_BACKFILL", 900)
TIMEOUT = env_int("TXN_TIMEOUT", 30)
PAGE_PARAM = env("TXN_PAGE_PARAM")
PAGE_SIZE_PARAM = env("TXN_PAGE_SIZE_PARAM")
PAGE_SIZE = env_int("TXN_PAGE_SIZE", 0)
FIRST_PAGE = env_int("TXN_FIRST_PAGE", 1)
TIME_UNIT = env("TXN_RESPONSE_TIME_UNIT", "ms").lower()
INSECURE = env("TXN_INSECURE", "false").lower() == "true"
MASK_PHONE = env("TXN_MASK_PHONE", "true").lower() != "false"
ENV_LABEL = env("TXN_ENV")
LOKI_URL = env("TXN_LOKI_URL", "http://loki:3100").rstrip("/")
LOKI_BUFFER = env_int("TXN_LOKI_BUFFER", 50000)
MAX_LABEL_VALUES = env_int("TXN_MAX_LABEL_VALUES", 200)
STATE_FILE = env("TXN_STATE_FILE", "/data/state.json")
PORT = env_int("TXN_PORT", 9488)

BUCKETS = (0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20, 30, 60)
LABELS = ("service", "service_type", "channel", "provider", "result")


def log(msg, *args):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("%s %s" % (stamp, msg % args if args else msg), flush=True)


# ----------------------------------------------------------------- metrics
class Metrics:
    """A tiny Prometheus registry: counters, gauges and histograms by label set."""

    def __init__(self):
        self.lock = threading.Lock()
        self.series = {}    # (name, labels-tuple) -> value
        self.hist = {}      # (name, labels-tuple) -> [bucket counts..., count, sum]
        self.meta = {}      # name -> (type, help)

    def declare(self, name, kind, help_text):
        self.meta[name] = (kind, help_text)

    def inc(self, name, labels=(), by=1.0):
        with self.lock:
            key = (name, tuple(labels))
            self.series[key] = self.series.get(key, 0.0) + by

    def set(self, name, value, labels=()):
        with self.lock:
            self.series[(name, tuple(labels))] = float(value)

    def observe(self, name, value, labels=()):
        with self.lock:
            h = self.hist.setdefault((name, tuple(labels)), [0] * len(BUCKETS) + [0, 0.0])
            for i, le in enumerate(BUCKETS):
                if value <= le:
                    h[i] += 1
            h[-2] += 1
            h[-1] += value

    def render(self):
        out = []
        with self.lock:
            names = sorted(self.meta)
            for name in names:
                kind, help_text = self.meta[name]
                out.append("# HELP %s %s" % (name, help_text))
                out.append("# TYPE %s %s" % (name, kind))
                if kind == "histogram":
                    for (n, labels), h in sorted(self.hist.items()):
                        if n != name:
                            continue
                        for i, le in enumerate(BUCKETS):
                            out.append("%s_bucket%s %d" % (name, _fmt(labels + (("le", str(le)),)), h[i]))
                        out.append("%s_bucket%s %d" % (name, _fmt(labels + (("le", "+Inf"),)), h[-2]))
                        out.append("%s_count%s %d" % (name, _fmt(labels), h[-2]))
                        out.append("%s_sum%s %r" % (name, _fmt(labels), h[-1]))
                else:
                    for (n, labels), v in sorted(self.series.items()):
                        if n == name:
                            out.append("%s%s %r" % (name, _fmt(labels), v))
        return "\n".join(out) + "\n"


def _fmt(labels):
    if not labels:
        return ""
    esc = lambda v: v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return "{" + ",".join('%s="%s"' % (k, esc(v)) for k, v in labels) + "}"


M = Metrics()
M.declare("txn_transactions_total", "counter", "Transactions read from the API.")
M.declare("txn_operations_total", "counter", "Sum of operationCount over the transactions read.")
M.declare("txn_provider_response_seconds", "histogram", "Content provider response time.")
M.declare("txn_coure_response_seconds", "histogram", "Coure (own platform) response time.")
M.declare("txn_poll_success", "gauge", "1 if the last poll read every service, else 0.")
M.declare("txn_poll_duration_seconds", "gauge", "How long the last poll took.")
M.declare("txn_last_success_timestamp_seconds", "gauge", "When a poll last succeeded.")
M.declare("txn_last_record_timestamp_seconds", "gauge", "Newest transactionTimeStamp seen.")
M.declare("txn_window_end_timestamp_seconds", "gauge", "Watermark: data is complete up to here.")
M.declare("txn_poll_errors_total", "counter", "Failed API reads, by reason (http_401, timeout...).")
M.declare("txn_records_fetched_total", "counter", "Records returned by the API, duplicates included.")
M.declare("txn_records_duplicate_total", "counter", "Records skipped because already counted.")
M.declare("txn_records_invalid_total", "counter", "Records skipped because they could not be read.")
M.declare("txn_pages_skipped_total", "counter", "Pages NOT read because TXN_PAGE_PARAM is unset.")
M.declare("txn_loki_push_errors_total", "counter", "Failed pushes to Loki (records are retried).")
M.declare("txn_loki_pending", "gauge", "Records waiting to be pushed to Loki.")
M.declare("txn_loki_dropped_total", "counter", "Records dropped because the Loki buffer was full.")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/metrics"):
            body = M.render().encode()
            ctype = "text/plain; version=0.0.4; charset=utf-8"
        elif self.path.startswith("/healthz"):
            body, ctype = b"ok\n", "text/plain"
        else:
            body, ctype = b"txn-poller: see /metrics\n", "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):   # keep scrapes out of the container log
        pass


# ------------------------------------------------------------------- state
class State:
    def __init__(self, path):
        self.path = path
        self.watermarks = {}    # serviceId -> epoch seconds
        self.seen = {}          # dedupe key -> epoch seconds of the record
        self.newest = 0.0       # newest transactionTimeStamp seen
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.watermarks = {k: float(v) for k, v in data.get("watermarks", {}).items()}
            self.seen = {k: float(v) for k, v in data.get("seen", {}).items()}
            self.newest = float(data.get("newest", 0))
            log("loaded state from %s (%d services, %d recent refs)",
                path, len(self.watermarks), len(self.seen))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            log("WARNING: could not read %s (%s) — starting fresh", path, exc)

    def prune(self, before):
        self.seen = {k: v for k, v in self.seen.items() if v >= before}

    def save(self):
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"watermarks": self.watermarks, "seen": self.seen, "newest": self.newest}, fh)
            os.replace(tmp, self.path)
        except OSError as exc:
            log("WARNING: could not save %s (%s)", self.path, exc)


# --------------------------------------------------------------------- API
class ApiError(Exception):
    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason


SSL_CTX = ssl._create_unverified_context() if INSECURE else None


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_page(service_id, start, end, page):
    params = {"serviceId": service_id, "from": iso(start), "to": iso(end)}
    if PAGE_PARAM:
        params[PAGE_PARAM] = str(page)
    if PAGE_SIZE_PARAM and PAGE_SIZE:
        params[PAGE_SIZE_PARAM] = str(PAGE_SIZE)
    sep = "&" if "?" in API_URL else "?"
    req = urllib.request.Request(API_URL + sep + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json"})
    if API_KEY:
        req.add_header(API_KEY_HEADER, API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise ApiError("http_%d" % exc.code, "HTTP %d from the API" % exc.code)
    except (TimeoutError, OSError) as exc:   # URLError is an OSError
        reason = "timeout" if "timed out" in str(exc) else "connection"
        raise ApiError(reason, str(exc))
    try:
        body = json.loads(raw)
    except ValueError:
        raise ApiError("bad_response", "the API did not return JSON")
    if not isinstance(body, dict) or body.get("status") is False:
        raise ApiError("api_status_false", "API said: %s" % (body.get("message") if isinstance(body, dict) else body))
    data = body.get("data") or []
    if not isinstance(data, list):
        raise ApiError("bad_response", "'data' is not a list")
    return data, int(body.get("totalPages") or 1)


def fetch_window(service_id, start, end):
    records, total_pages = fetch_page(service_id, start, end, FIRST_PAGE)
    if total_pages > 1 and not PAGE_PARAM:
        M.inc("txn_pages_skipped_total", by=total_pages - 1)
        log("WARNING: the API split %s..%s into %d pages but TXN_PAGE_PARAM is not set, "
            "so only the first page was read. Set TXN_PAGE_PARAM (and TXN_PAGE_SIZE_PARAM).",
            iso(start), iso(end), total_pages)
        return records
    for page in range(FIRST_PAGE + 1, FIRST_PAGE + total_pages):
        more, _ = fetch_page(service_id, start, end, page)
        records.extend(more)
    return records


# ----------------------------------------------------------------- records
def parse_ts(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class LabelGuard:
    """Caps distinct values per label so a free-text field can't explode Prometheus."""

    def __init__(self, limit):
        self.limit = limit
        self.values = {k: set() for k in LABELS}
        self.warned = set()

    def __call__(self, label, value):
        value = (str(value).strip() if value is not None else "")[:64] or "unknown"
        known = self.values[label]
        if value in known or len(known) < self.limit:
            known.add(value)
            return value
        if label not in self.warned:
            self.warned.add(label)
            log("WARNING: label %r has more than %d values; new ones are grouped as 'other'",
                label, self.limit)
        return "other"


GUARD = LabelGuard(MAX_LABEL_VALUES)


def seconds(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return v / 1000.0 if TIME_UNIT == "ms" else v


def mask(phone):
    phone = str(phone or "")
    return phone if len(phone) <= 4 else "*" * (len(phone) - 4) + phone[-4:]


def labels_for(rec, service_id):
    return (
        ("service", GUARD("service", rec.get("service") or rec.get("serviceId") or service_id)),
        ("service_type", GUARD("service_type", rec.get("serviceType"))),
        ("channel", GUARD("channel", rec.get("channel"))),
        ("provider", GUARD("provider", rec.get("contentProviderName"))),
        ("result", "success" if rec.get("operationSuccessful") is True else "failed"),
    )


def record(rec, service_id, ts, outbox):
    labels = labels_for(rec, service_id)
    M.inc("txn_transactions_total", labels)
    try:
        M.inc("txn_operations_total", labels, float(rec.get("operationCount") or 0))
    except (TypeError, ValueError):
        pass
    by = (labels[0], labels[3])     # service, provider
    t = seconds(rec.get("contentProviderResponseTime"))
    if t is not None:
        M.observe("txn_provider_response_seconds", t, by)
    t = seconds(rec.get("coureResponseTime"))
    if t is not None:
        M.observe("txn_coure_response_seconds", t, labels[:1])
    if LOKI_URL:
        line = dict(rec)
        if MASK_PHONE and "phoneNumber" in line:
            line["phoneNumber"] = mask(line["phoneNumber"])
        outbox.append((labels, int(ts * 1e9), json.dumps(line, separators=(",", ":"))))


# -------------------------------------------------------------------- Loki
def push_loki(pending):
    """Push pending records to Loki; returns those that could not be sent."""
    if not pending:
        return pending
    sent = 0
    for i in range(0, len(pending), 5000):
        chunk = pending[i:i + 5000]
        streams = {}
        for labels, ns, line in chunk:
            streams.setdefault(labels, []).append([str(ns), line])
        payload = {"streams": [
            {"stream": dict((("job", "transactions"),) + ((("env", ENV_LABEL),) if ENV_LABEL else ())
                            + labels),
             "values": sorted(values)}
            for labels, values in streams.items()]}
        req = urllib.request.Request(LOKI_URL + "/loki/api/v1/push",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT):
                pass
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                # Loki rejected the batch itself (e.g. too old); retrying won't help.
                detail = exc.read()[:300].decode(errors="replace")
                log("WARNING: Loki rejected %d records (HTTP %d): %s", len(chunk), exc.code, detail)
                M.inc("txn_loki_dropped_total", by=len(chunk))
                sent += len(chunk)
                continue
            M.inc("txn_loki_push_errors_total")
            log("WARNING: Loki push failed (HTTP %d); will retry", exc.code)
            break
        except OSError as exc:
            M.inc("txn_loki_push_errors_total")
            log("WARNING: Loki push failed (%s); will retry", exc)
            break
        sent += len(chunk)
    rest = pending[sent:]
    if len(rest) > LOKI_BUFFER:
        M.inc("txn_loki_dropped_total", by=len(rest) - LOKI_BUFFER)
        rest = rest[-LOKI_BUFFER:]
    return rest


# -------------------------------------------------------------------- loop
def poll(state, pending):
    started = time.time()
    end = int(started) - LAG
    ok = True
    outbox = []
    for sid in SERVICE_IDS:
        mark = state.watermarks.get(sid, end - INTERVAL)
        mark = max(mark, end - MAX_BACKFILL)
        start = int(mark) - OVERLAP
        if start >= end:
            continue
        try:
            records = fetch_window(sid, start, end)
        except ApiError as exc:
            ok = False
            M.inc("txn_poll_errors_total", (("reason", exc.reason),))
            log("ERROR: reading service %r for %s..%s failed: %s", sid or "(all)", iso(start), iso(end), exc)
            continue
        M.inc("txn_records_fetched_total", by=len(records))
        new = dup = bad = 0
        for rec in records:
            if not isinstance(rec, dict):
                bad += 1
                continue
            try:
                ts = parse_ts(rec.get("transactionTimeStamp"))
            except (TypeError, ValueError):
                bad += 1
                continue
            key = str(rec.get("transactionRef") or rec.get("id") or json.dumps(rec, sort_keys=True))
            if key in state.seen:
                dup += 1
                continue
            state.seen[key] = ts
            record(rec, sid, ts, outbox)
            new += 1
            state.newest = max(state.newest, ts)
        M.inc("txn_records_duplicate_total", by=dup)
        M.inc("txn_records_invalid_total", by=bad)
        state.watermarks[sid] = end
        log("service %r %s..%s: %d new, %d already counted%s", sid or "(all)", iso(start), iso(end),
            new, dup, (", %d unreadable" % bad) if bad else "")

    marks = [state.watermarks[s] for s in SERVICE_IDS if s in state.watermarks]
    if marks:
        M.set("txn_window_end_timestamp_seconds", min(marks))
        state.prune(min(marks) - OVERLAP - 60)
    if state.newest:
        M.set("txn_last_record_timestamp_seconds", state.newest)
    state.save()

    pending = push_loki(pending + outbox)
    M.set("txn_loki_pending", len(pending))
    M.set("txn_poll_success", 1 if ok else 0)
    M.set("txn_poll_duration_seconds", round(time.time() - started, 3))
    if ok:
        M.set("txn_last_success_timestamp_seconds", int(time.time()))
    return pending


def main():
    if not API_URL:
        sys.exit("ERROR: TXN_API_URL is not set (see .env.example, 'Transaction logs').")
    if TIME_UNIT not in ("ms", "s"):
        sys.exit("ERROR: TXN_RESPONSE_TIME_UNIT must be 'ms' or 's'.")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log("txn-poller: %s every %ds for %s; metrics on :%d; Loki %s",
        urllib.parse.urlsplit(API_URL).netloc, INTERVAL,
        ", ".join(s or "(all services)" for s in SERVICE_IDS), PORT, LOKI_URL or "off")

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    state, pending = State(STATE_FILE), []
    while not stop.is_set():
        try:
            pending = poll(state, pending)
        except Exception as exc:  # never let one bad poll kill the feed
            M.set("txn_poll_success", 0)
            M.inc("txn_poll_errors_total", (("reason", "internal"),))
            log("ERROR: poll crashed: %r", exc)
        stop.wait(INTERVAL - (time.time() % INTERVAL))
    log("txn-poller: stopping")


if __name__ == "__main__":
    main()
