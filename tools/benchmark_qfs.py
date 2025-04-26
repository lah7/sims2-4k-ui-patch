#!/usr/bin/python3
"""
Benchmark QFS compression levels using our implementation.
"""
# pylint: disable=missing-module-docstring,missing-function-docstring,missing-class-docstring
# pyright: reportPossiblyUnboundVariable=false

import argparse
import concurrent.futures
import os
import statistics
import sys
import tempfile
import time
from multiprocessing import Manager

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, qfs

# Parse parameters
parser = argparse.ArgumentParser(description="Benchmark QFS compression levels")
parser.add_argument("-o", "--output", type=str, default="benchmark.csv", help="Write results to CSV file. Default: benchmark.csv", metavar="")
parser.add_argument("-f", "--test-file", type=str, help="Required. Path to a package file.", metavar="")
parser.add_argument("-t", "--threads", type=int, default=os.cpu_count(), help="Number of threads to run. Default is all.", metavar="")
parser.add_argument("-s", "--samples", type=int, default=3, help="Number of compression samples to take. Default is 3.", metavar="")
parser.add_argument("-m", "--min", type=int, default=2, help="Minimum level (2)", metavar="")
parser.add_argument("-x", "--max", type=int, default=255, help="Maximum level (255)", metavar="")

args = parser.parse_args()

if not args.test_file:
    parser.print_help()
    sys.exit(0)

if not os.path.exists(args.test_file):
    print("Error: Package file does not exist.")
    sys.exit(1)

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


def compress(package: dbpf.DBPF, level: int, path: str):
    qfs.QFS_MAXITER = level

    if os.path.exists(path):
        os.remove(path)

    start = time.time()
    for entry in package.entries:
        if entry.compress:
            entry.data = entry.data
    package.save_package(path)
    end = time.time()

    return end - start


def decompress(path: str):
    start = time.time()
    package = dbpf.DBPF(path)
    for entry in package.entries:
        if entry.compress:
            entry.clear_cache()
            entry.data # pylint: disable=pointless-statement
            entry.clear_cache()
    end = time.time()

    return end - start


def benchmark(package: dbpf.DBPF, level: int, _pid_list, current, total: int, output_csv: str):
    _pid_list.append(os.getpid())

    temp = tempfile.NamedTemporaryFile()
    c_samples = []
    d_samples = []
    start = time.time()

    # Compression
    for no in range(SAMPLES):
        current.value += 1
        print(f"[{current.value}/{total}] Starting benchmark for level {level} (sample {no + 1} of {SAMPLES})")
        c_samples.append(compress(package, level, temp.name))

    # Decompression
    for no in range(SAMPLES * 8):
        d_samples.append(decompress(temp.name))

    # Write results
    file_size = round(os.path.getsize(temp.name) / 1000 / 1000, 3)
    with open(output_csv, "a", encoding="utf-8") as f:
        f.write(f"{level},{file_size},{round(statistics.mean(c_samples), 3)},{round(statistics.mean(d_samples), 3)}\n")

    end = time.time()
    temp.close()
    print(f"[{current.value}/{total}] Finished benchmarking level {level} (took {round(end - start, 3)} secs)")


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

            # Preload files into memory
            print("Loading files: ", end="\r")
            for i, _entry in enumerate(PACKAGE.entries):
                print(f"Loading files: {i}/{len(PACKAGE.entries)}", end="\r")
                if _entry.compress:
                    _entry.data # pylint: disable=pointless-statement

            tasks.extend([executor.submit(benchmark, PACKAGE, level, pid_list, CURRENT, RANGE * SAMPLES, OUTPUT_CSV) for level in range(MIN_LEVEL - 1, MAX_LEVEL + 1)])

    # Sort results (except first line)
    with open(OUTPUT_CSV, "r", encoding="utf-8") as _f:
        lines = _f.readlines()
        header = lines[0]
        lines = lines[1:]
        lines.sort(key=lambda x: int(x.split(",")[0]))
        lines.insert(0, header)

    with open(OUTPUT_CSV, "w", encoding="utf-8") as _f:
        _f.writelines(lines)

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
