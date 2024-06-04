#!/usr/bin/python3
"""
Benchmark QFS compression levels using our implementation.
"""
# pylint: disable=missing-module-docstring,missing-function-docstring,missing-class-docstring

import argparse
import concurrent.futures
import os
import statistics
import sys
import tempfile
import time
from multiprocessing import Manager

# Our modules are in the parent directory
# pylint: disable=wrong-import-position
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dbpf
import qfs

# Parse parameters
DEFAULT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "files", "ui.package"))
parser = argparse.ArgumentParser(description="Benchmark QFS compression levels")
parser.add_argument("-o", "--output", type=str, default="benchmark.csv", help="Write results to CSV file. Default: benchmark.csv", metavar="")
parser.add_argument("-f", "--test-file", type=str, default=DEFAULT_FILE, help="Path to the test file. Default is test file.", metavar="")
parser.add_argument("-t", "--threads", type=int, default=os.cpu_count(), help="Number of threads to run. Default is all.", metavar="")
parser.add_argument("-s", "--samples", type=int, default=3, help="Number of compression samples to take. Default is 3.", metavar="")
parser.add_argument("-m", "--min", type=int, default=2, help="Minimum level (2)", metavar="")
parser.add_argument("-x", "--max", type=int, default=255, help="Maximum level (255)", metavar="")

args = parser.parse_args()

INPUT_PATH = args.test_file
OUTPUT_CSV = args.output
ORIG_SIZE = os.path.getsize(INPUT_PATH)
THREADS = args.threads
SAMPLES = args.samples
MIN_LEVEL = args.min
MAX_LEVEL = args.max

print("\nBenchmark Parameters")
print("=============================")
print("Package:", INPUT_PATH, f"({ORIG_SIZE} bytes)")
print("Using", THREADS, "threads")
print("Testing levels", MIN_LEVEL, "to", MAX_LEVEL, "with", SAMPLES, "samples")

print("\nThis may take a long time to complete.")
print("Results will be written to", OUTPUT_CSV, "\n")


def print_progress(current: int, total: int, msg: str):
    print(f"\r[{(round(current / total, 1) * 100)}%] {msg}", end="\r")


def compress(package: dbpf.DBPF, level: int, path: str):
    qfs.QFS_MAXITER = level

    if os.path.exists(path):
        os.remove(path)

    start = time.time()
    package.save_package(path)
    end = time.time()

    return end - start


def decompress(level: int, path: str):
    qfs.QFS_MAXITER = level

    start = time.time()
    dbpf.DBPF(path)
    end = time.time()

    return end - start


def benchmark(package: dbpf.DBPF, level: int, _pid_list, current, total: int, output_csv: str):
    _pid_list.append(os.getpid())

    temp = tempfile.NamedTemporaryFile()
    c_samples = []
    d_samples = []

    # Compression
    for no in range(SAMPLES):
        current.value += 1
        print_progress(current.value, total, f"Benchmarking with level {level} (sample {no + 1} of {SAMPLES})          ")
        c_samples.append(compress(package, level, temp.name))

    # Decompression
    for no in range(SAMPLES * 8):
        d_samples.append(decompress(level, temp.name))

    # Write results
    file_size = round(os.path.getsize(temp.name) / 1000 / 1000, 3)
    with open(output_csv, "a", encoding="utf-8") as f:
        f.write(f"{level},{file_size},{round(statistics.mean(c_samples), 3)},{round(statistics.mean(d_samples), 3)}\n")


print("Starting benchmark...", end="\r")
with open(OUTPUT_CSV, "w", encoding="utf-8") as _f:
    _f.write("QFS Level,File Size (MB),Compress Time (Sec),Decompress Time (Sec)\n")

try:
    tasks = []
    with Manager() as manager:
        pid_list = manager.list()
        CURRENT = manager.Value("i", -1)
        RANGE = MAX_LEVEL - MIN_LEVEL + 1
        with concurrent.futures.ProcessPoolExecutor(max_workers=THREADS) as executor:
            PACKAGE = dbpf.DBPF(INPUT_PATH)
            tasks.extend([executor.submit(benchmark, PACKAGE, level, pid_list, CURRENT, RANGE * SAMPLES, OUTPUT_CSV) for level in range(MIN_LEVEL - 1, MAX_LEVEL + 1)])
    print("\nBenchmark completed.")

except KeyboardInterrupt:
    print("\nBenchmark aborted.\n")
    for task in tasks:
        assert isinstance(task, concurrent.futures.Future)
        task.cancel()
    for pid in pid_list:
        os.kill(pid, 9)
    try:
        executor.shutdown(wait=False)
    except FileNotFoundError:
        pass
    sys.exit(130)
