import socket
import struct
import json
import time
import threading
import argparse
import sys
import os
import psutil
import statistics

class LoadGeneratorClient:
    def __init__(self, client_id, host, port, payload_size=1024):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.payload = "X" * payload_size
        self.sock = None
        self.latencies = []
        self.success_count = 0
        self.error_count = 0
        self.is_running = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, self.port))

    def _recv_exact(self, n_bytes):
        data = bytearray()
        while len(data) < n_bytes:
            packet = self.sock.recv(n_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

    def run_worker(self, stop_event, record_event):
        req_seq = 0
        while not stop_event.is_set():
            req_seq += 1
            req_id = f"c{self.client_id}-seq{req_seq}"
            req_dict = {
                "requestId": req_id,
                "payload": self.payload
            }
            req_bytes = json.dumps(req_dict).encode("utf-8")
            header = struct.pack("!I", len(req_bytes))

            t_start = time.perf_counter()
            try:
                self.sock.sendall(header + req_bytes)

                resp_hdr = self._recv_exact(4)
                if not resp_hdr:
                    if record_event.is_set():
                        self.error_count += 1
                    break
                resp_len = struct.unpack("!I", resp_hdr)[0]
                resp_body = self._recv_exact(resp_len)
                if not resp_body:
                    if record_event.is_set():
                        self.error_count += 1
                    break

                resp_data = json.loads(resp_body.decode("utf-8"))
                t_end = time.perf_counter()

                # Verify requestId and payload integrity
                if resp_data.get("requestId") == req_id and resp_data.get("payload") == self.payload:
                    if record_event.is_set():
                        latency_ms = (t_end - t_start) * 1000.0
                        self.latencies.append(latency_ms)
                        self.success_count += 1
                else:
                    if record_event.is_set():
                        self.error_count += 1
            except Exception:
                if record_event.is_set():
                    self.error_count += 1
                break

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

class CPUMonitor(threading.Thread):
    def __init__(self, stop_event):
        super().__init__(daemon=True)
        self.stop_event = stop_event
        self.samples = []

    def run(self):
        psutil.cpu_percent(interval=None) # Prime
        while not self.stop_event.is_set():
            val = psutil.cpu_percent(interval=0.2)
            self.samples.append(val)

    def get_avg_cpu(self):
        return statistics.mean(self.samples) if self.samples else 0.0

def run_benchmark_trial(host, port, num_clients, warmup_sec=5, measure_sec=20, payload_size=1024):
    print(f"\n---> Starting trial: Clients={num_clients}, Warmup={warmup_sec}s, Measure={measure_sec}s, Payload={payload_size}B")

    clients = [LoadGeneratorClient(i, host, port, payload_size) for i in range(num_clients)]
    for c in clients:
        c.connect()

    stop_event = threading.Event()
    record_event = threading.Event()

    threads = []
    for c in clients:
        t = threading.Thread(target=c.run_worker, args=(stop_event, record_event), daemon=True)
        t.start()
        threads.append(t)

    # 1. Warm-up phase
    print(f"     [Warm-up] Warming up for {warmup_sec} seconds...")
    time.sleep(warmup_sec)

    # 2. Measurement phase
    print(f"     [Measure] Recording metrics for {measure_sec} seconds...")
    cpu_stop = threading.Event()
    cpu_monitor = CPUMonitor(cpu_stop)
    cpu_monitor.start()

    record_event.set()
    t_measure_start = time.perf_counter()
    time.sleep(measure_sec)
    t_measure_end = time.perf_counter()
    record_event.clear()
    stop_event.set()
    cpu_stop.set()
    cpu_monitor.join(timeout=1.0)

    for t in threads:
        t.join(timeout=2.0)
    for c in clients:
        c.close()

    actual_duration = t_measure_end - t_measure_start

    # Aggregate metrics
    all_latencies = []
    total_success = 0
    total_errors = 0
    for c in clients:
        all_latencies.extend(c.latencies)
        total_success += c.success_count
        total_errors += c.error_count

    total_requests = total_success + total_errors
    throughput = total_success / actual_duration if actual_duration > 0 else 0
    error_rate = (total_errors / total_requests * 100.0) if total_requests > 0 else 0.0

    mean_latency = statistics.mean(all_latencies) if all_latencies else 0.0
    p95_latency = statistics.quantiles(all_latencies, n=100)[94] if len(all_latencies) >= 100 else (max(all_latencies) if all_latencies else 0.0)
    avg_cpu = cpu_monitor.get_avg_cpu()

    result = {
        "num_clients": num_clients,
        "actual_duration_sec": round(actual_duration, 2),
        "total_requests": total_requests,
        "total_success": total_success,
        "total_errors": total_errors,
        "error_rate_pct": round(error_rate, 2),
        "throughput_req_per_sec": round(throughput, 2),
        "latency_mean_ms": round(mean_latency, 3),
        "latency_p95_ms": round(p95_latency, 3),
        "cpu_usage_pct": round(avg_cpu, 1)
    }

    print(f"     [Result] Throughput: {result['throughput_req_per_sec']} req/s | Mean Latency: {result['latency_mean_ms']} ms | p95 Latency: {result['latency_p95_ms']} ms | CPU: {result['cpu_usage_pct']}% | Errors: {result['total_errors']}")
    return result

def run_full_suite(host="127.0.0.1", port=9999, output_dir="experiments/raw-data", runs=3):
    os.makedirs(output_dir, exist_ok=True)
    client_levels = [1, 10, 50]
    all_results = []

    for c in client_levels:
        for r in range(1, runs + 1):
            print(f"\n==========================================")
            print(f"RUNNING EXPERIMENT: Clients={c}, Run={r}/{runs}")
            print(f"==========================================")
            res = run_benchmark_trial(host, port, num_clients=c, warmup_sec=5, measure_sec=20, payload_size=1024)
            res["run"] = r
            all_results.append(res)
            time.sleep(2) # Cool down between runs

    # Save to JSON
    json_path = os.path.join(output_dir, "benchmark_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    # Save to CSV
    csv_path = os.path.join(output_dir, "benchmark_results.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        headers = ["num_clients", "run", "total_requests", "total_success", "total_errors", "error_rate_pct", "throughput_req_per_sec", "latency_mean_ms", "latency_p95_ms", "cpu_usage_pct"]
        f.write(",".join(headers) + "\n")
        for r in all_results:
            row = [str(r[h]) for h in headers]
            f.write(",".join(row) + "\n")

    print(f"\n[ALL DONE] Saved benchmark data to {json_path} and {csv_path}")
    return all_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Load Generator for Client-Load Research Benchmark")
    parser.add_argument("--host", default="127.0.0.1", help="Target Server IP")
    parser.add_argument("--port", type=int, default=9999, help="Target Server Port")
    parser.add_argument("--runs", type=int, default=3, help="Number of repetitions per client level (default: 3)")
    parser.add_argument("--output-dir", default="experiments/raw-data", help="Output directory for raw data")
    args = parser.parse_args()

    run_full_suite(host=args.host, port=args.port, output_dir=args.output_dir, runs=args.runs)
