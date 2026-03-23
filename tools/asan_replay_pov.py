#!/usr/bin/env python3
"""Run CGC PoV binaries against ASAN-instrumented challenge binaries.

Captures ASAN stderr output from the challenge binary to extract precise
bug locations (function, file, line, bug kind).

Usage:
    python tools/asan_replay_pov.py \
        --cb build64_asan/challenges/SPIFFS/SPIFFS \
        --pov build64/challenges/SPIFFS/pov_1.pov \
        --timeout 15

    # Batch: run all PoVs for all challenges
    python tools/asan_replay_pov.py \
        --asan-dir build64_asan \
        --pov-dir build64 \
        --timeout 15 --batch \
        -o asan_ground_truth.json
"""

import argparse
import json
import multiprocessing as mp
import os
import re
import signal
import struct
import subprocess as sp
import sys
from pathlib import Path
from time import time, sleep


def parse_asan_output(stderr: str) -> list[dict]:
    """Parse ASAN/UBSAN stderr into structured findings."""
    findings = []

    # Build a map from SUMMARY lines: position → bug_kind
    # SUMMARY: AddressSanitizer: allocation-size-too-big ...
    summary_kinds: dict[int, str] = {}
    for sm in re.finditer(r"SUMMARY: \w+Sanitizer: ([\w-]+)", stderr):
        summary_kinds[sm.start()] = sm.group(1)

    # Match ASAN ERROR blocks with stack frames (exclude SEGV, handled below)
    for m in re.finditer(
        r"==\d+==ERROR: (?:Address|Memory)Sanitizer: (?!SEGV)([^\n]+)\n"
        r"(?:(?!\s+#\d+)[^\n]*\n)*?"  # optional info lines before frames
        r"((?:\s+#\d+ .+\n)+)",       # stack frames
        stderr,
    ):
        raw_frames = m.group(2)
        frames = _parse_frames(raw_frames)
        if not frames:
            continue
        # Find the nearest SUMMARY line after this ERROR block
        bug_kind = None
        for pos, kind in summary_kinds.items():
            if pos > m.start():
                bug_kind = kind
                break
        if not bug_kind:
            # Fall back to first word from ERROR line
            em = re.match(r"([\w-]+)", m.group(1))
            bug_kind = em.group(1) if em else "unknown"
        findings.append({
            "sanitizer": "asan",
            "bug_kind": _normalise_kind(bug_kind),
            "raw_kind": bug_kind,
            "frames": frames,
            "top_frame": frames[0],
        })

    # Match ASAN SEGV (e.g., null deref) — allow Hint: lines between ERROR and frames
    for m in re.finditer(
        r"==\d+==ERROR: (?:Address|Memory)Sanitizer: (SEGV) on (?:unknown )?address (0x[0-9a-f]+).+?\n"
        r"(?:==\d+==.*\n)*?"  # optional Hint:/info lines
        r"((?:\s+#\d+ .+\n)+)",
        stderr,
    ):
        addr = m.group(2)
        raw_frames = m.group(3)
        frames = _parse_frames(raw_frames)
        bug_kind = "null_deref" if int(addr, 16) < 0x10000 else "segv"
        # Use first frame with source info as top_frame
        top = frames[0] if frames else {"function": None, "file": None, "line": None}
        findings.append({
            "sanitizer": "asan",
            "bug_kind": bug_kind,
            "raw_kind": f"SEGV at {addr}",
            "frames": frames,
            "top_frame": top,
        })

    # Match UBSan runtime errors
    for m in re.finditer(
        r"([^\s:]+:\d+:\d+): runtime error: (.+)",
        stderr,
    ):
        location = m.group(1)
        description = m.group(2)
        loc_m = re.match(r"(.+):(\d+):(\d+)", location)
        if loc_m:
            findings.append({
                "sanitizer": "ubsan",
                "bug_kind": _ubsan_kind(description),
                "raw_kind": description,
                "frames": [],
                "top_frame": {
                    "file": loc_m.group(1),
                    "line": int(loc_m.group(2)),
                    "function": None,
                },
            })

    return findings


def _parse_frames(raw: str) -> list[dict]:
    """Parse ASAN stack frames."""
    frames = []
    for line in raw.rstrip().split("\n"):
        # Frame with full source info: #N 0xADDR in func file:line[:col]
        # file path may contain ':' (e.g. C:\...) but line:col are always
        # :digits at the end, so we match the last :line or :line:col.
        m = re.match(
            r"\s+#(\d+) 0x[0-9a-f]+ in (.+) (\S+?):(\d+)(?::\d+)?\s*$",
            line,
        )
        if m:
            frames.append({
                "frame": int(m.group(1)),
                "function": m.group(2).rstrip(),
                "file": m.group(3),
                "line": int(m.group(4)),
            })
            continue
        # Frame without source info: #N 0xADDR (<unknown module>) or (exe+0xOFF)
        m = re.match(r"\s+#(\d+) (0x[0-9a-f]+)\s", line)
        if m:
            frames.append({
                "frame": int(m.group(1)),
                "function": None,
                "file": None,
                "line": None,
                "address": m.group(2),
            })
    return frames


def _normalise_kind(raw: str) -> str:
    """Map ASAN bug kind strings to our issue_kind taxonomy."""
    mapping = {
        "heap-buffer-overflow": "buffer_overflow",
        "stack-buffer-overflow": "buffer_overflow",
        "global-buffer-overflow": "buffer_overflow",
        "heap-use-after-free": "use_after_free",
        "stack-use-after-return": "use_after_free",
        "stack-use-after-scope": "use_after_free",
        "double-free": "double_free",
        "alloc-dealloc-mismatch": "double_free",
        "use-after-poison": "use_after_free",
        "container-overflow": "buffer_overflow",
        "dynamic-stack-buffer-overflow": "buffer_overflow",
        "SEGV": "null_deref",
        "allocation-size-too-big": "integer_overflow",
        "requested-allocation-size-too-big": "integer_overflow",
    }
    return mapping.get(raw, raw)


def _ubsan_kind(desc: str) -> str:
    """Map UBSan description to issue_kind."""
    if "overflow" in desc:
        return "integer_overflow"
    if "shift" in desc:
        return "integer_overflow"
    if "null pointer" in desc:
        return "null_deref"
    if "undefined" in desc:
        return "undefined_behavior"
    return "undefined_behavior"


class PovRunner:
    """Run a PoV binary against a challenge binary, capturing sanitizer output."""

    def __init__(self, cb_path: str, pov_path: str, timeout: int = 15,
                 debug: bool = False):
        self.cb_path = cb_path
        self.pov_path = pov_path
        self.timeout = timeout
        self.debug = debug

    def log(self, msg: str) -> None:
        if self.debug:
            print(f"# {msg}", file=sys.stderr)

    def _find_build_root(self, binary_path: str) -> Path:
        """Walk up from a binary to find the build root (parent of challenges/)."""
        p = Path(binary_path).resolve()
        while p.name != "challenges" and p != p.parent:
            p = p.parent
        return p.parent

    def _lib_dirs(self, build_root: Path) -> list[str]:
        return [
            str(build_root / "include"),
            str(build_root / "include" / "tiny-AES128-C"),
            str(build_root / "include" / "libpov"),
        ]

    def run(self) -> dict:
        """Run the PoV and return results with ASAN output."""
        seed = os.urandom(48).hex()

        cb_build = self._find_build_root(self.cb_path)
        pov_build = self._find_build_root(self.pov_path)

        cb_env = {
            "seed": seed,
            "ASAN_OPTIONS": "detect_leaks=0:print_stacktrace=1:symbolize=1",
            "UBSAN_OPTIONS": "print_stacktrace=1",
            "LD_LIBRARY_PATH": ":".join(self._lib_dirs(cb_build)),
        }
        pov_ld = ":".join(self._lib_dirs(pov_build))

        # Launch CB with ASAN, capture stderr
        cb_proc = sp.Popen(
            self.cb_path, env=cb_env,
            stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
        )
        self.log(f"CB pid={cb_proc.pid}")

        # Negotiation socketpair — parent keeps neg_parent, child gets neg_child on fd 3
        import socket
        neg_parent, neg_child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        # Fork for the PoV (must use os.fork to control fd layout before execve)
        pov_pid = os.fork()
        if pov_pid == 0:
            # --- child: becomes the PoV process ---
            neg_parent.close()
            if self.timeout > 0:
                signal.alarm(self.timeout)

            # Wire: stdin=CB stdout, stdout=CB stdin, fd3=negotiation
            os.dup2(cb_proc.stdout.fileno(), 0)
            os.dup2(cb_proc.stdin.fileno(), 1)
            os.dup2(neg_child.fileno(), 3)
            neg_child.close()

            # Silence stderr
            null = os.open("/dev/null", os.O_WRONLY)
            os.dup2(null, 2)
            os.close(null)

            # Close CB's pipe fds in child (parent owns them)
            cb_proc.stdin.close()
            cb_proc.stdout.close()
            cb_proc.stderr.close()

            os.execve(self.pov_path, [self.pov_path],
                      {"LD_LIBRARY_PATH": pov_ld})
            os._exit(1)

        # --- parent ---
        neg_child.close()
        self.log(f"PoV pid={pov_pid}")

        # Negotiate over the socket
        negotiation = {}
        try:
            negotiation = self._negotiate(neg_parent.fileno())
        except Exception as e:
            self.log(f"negotiation error: {e}")

        # Wait for CB to finish (or timeout)
        pov_done = False
        start = time()
        while time() - start < self.timeout:
            if cb_proc.poll() is not None:
                break
            # Also check if PoV exited
            if not pov_done:
                try:
                    pid, _ = os.waitpid(pov_pid, os.WNOHANG)
                    if pid != 0:
                        self.log("PoV exited")
                        pov_done = True
                        # Don't break — let CB continue processing and crash
                except ChildProcessError:
                    pov_done = True
            sleep(0.1)

        # Use communicate() to drain all stderr before/after termination
        cb_stderr = b""
        if cb_proc.poll() is None:
            # CB still alive after timeout — kill it
            cb_proc.terminate()
        try:
            _, cb_stderr = cb_proc.communicate(timeout=5)
        except sp.TimeoutExpired:
            cb_proc.kill()
            _, cb_stderr = cb_proc.communicate()

        # Reap PoV
        try:
            os.waitpid(pov_pid, 0)
        except ChildProcessError:
            pass

        neg_parent.close()

        stderr_text = cb_stderr.decode("utf-8", errors="replace")
        findings = parse_asan_output(stderr_text)

        return {
            "returncode": cb_proc.returncode,
            "signal": abs(cb_proc.returncode) if cb_proc.returncode and cb_proc.returncode < 0 else 0,
            "negotiation": negotiation,
            "findings": findings,
            "stderr": stderr_text if self.debug else "",
        }

    def _negotiate(self, pipefd: int) -> dict:
        """Handle PoV type negotiation."""
        data = self._read_all(pipefd, 4)
        pov_type = struct.unpack("<L", data)[0]
        self.log(f"negotiation type: {pov_type}")

        result = {"type": pov_type}

        if pov_type == 1:
            data = self._read_all(pipefd, 12)
            ipmask, regmask, regnum = struct.unpack("<LLL", data)
            result["ipmask"] = ipmask
            result["regmask"] = regmask
            result["regnum"] = regnum

            ip = 0x41414141 & ipmask
            reg = 0x42424242 & regmask
            os.write(pipefd, struct.pack("<LL", ip, reg))

        elif pov_type == 2:
            PAGE_ADDR = 0x4347C000
            PAGE_LENGTH = 0x1000
            PAGE_BYTES = 4
            os.write(pipefd, struct.pack("<LLL", PAGE_ADDR, PAGE_LENGTH, PAGE_BYTES))
            data = self._read_all(pipefd, 4)
            result["secret"] = data.hex()

        return result

    def _read_all(self, fd: int, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = os.read(fd, n - len(data))
            if not chunk:
                raise EOFError("pipe closed during negotiation")
            data += chunk
        return data


def find_challenges(asan_dir: Path, pov_dir: Path) -> list[tuple[str, str, str]]:
    """Find all (challenge_name, cb_path, pov_path) triples."""
    results = []
    asan_chal_dir = asan_dir / "challenges"
    pov_chal_dir = pov_dir / "challenges"

    if not asan_chal_dir.exists() or not pov_chal_dir.exists():
        return results

    for chal_dir in sorted(asan_chal_dir.iterdir()):
        if not chal_dir.is_dir():
            continue
        name = chal_dir.name
        # Find the CB binary (same name as directory)
        cb_path = chal_dir / name
        if not cb_path.exists():
            continue

        # Find PoVs in the non-ASAN build
        pov_chal = pov_chal_dir / name
        if not pov_chal.exists():
            continue

        for pov_file in sorted(pov_chal.glob("pov_*.pov")):
            results.append((name, str(cb_path), str(pov_file)))

    return results


def run_single(cb: str, pov: str, timeout: int, debug: bool) -> dict:
    runner = PovRunner(cb, pov, timeout=timeout, debug=debug)
    return runner.run()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CGC PoVs against ASAN-instrumented binaries"
    )
    parser.add_argument("--cb", help="Path to ASAN-instrumented challenge binary")
    parser.add_argument("--pov", help="Path to PoV binary (non-ASAN)")
    parser.add_argument("--asan-dir", help="ASAN build directory (for batch mode)")
    parser.add_argument("--pov-dir", help="Non-ASAN build directory (for batch mode)")
    parser.add_argument("--batch", action="store_true", help="Run all challenges")
    parser.add_argument("--reparse", action="store_true",
                        help="Re-parse saved logs instead of re-running PoVs")
    parser.add_argument("--log-dir", help="Directory to save/read raw ASAN stderr logs")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-o", "--output", help="Output JSON file")
    args = parser.parse_args()

    if args.reparse:
        # Re-parse saved logs without re-running PoVs
        log_dir = Path(args.log_dir) if args.log_dir else None
        if not log_dir or not log_dir.exists():
            parser.error("--reparse requires --log-dir pointing to saved logs")
        results = {}
        log_files = sorted(log_dir.glob("*.log"))
        print(f"Re-parsing {len(log_files)} log files from {log_dir}",
              file=sys.stderr)
        for log_file in log_files:
            key = log_file.stem.replace("__", "/")  # challenge__pov_1 -> challenge/pov_1
            name = key.split("/")[0]
            pov_name = key.split("/")[1] if "/" in key else log_file.stem
            stderr_text = log_file.read_text(errors="replace")
            findings = parse_asan_output(stderr_text)
            # Read metadata if saved
            meta_file = log_file.with_suffix(".meta.json")
            meta = {}
            if meta_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)
            n = len(findings)
            print(f"  {key}: {n} findings", file=sys.stderr)
            results[key] = {
                "challenge": name,
                "pov": pov_name,
                "signal": meta.get("signal", 0),
                "findings": findings,
            }

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            json.dump(results, sys.stdout, indent=2)

    elif args.batch:
        if not args.asan_dir or not args.pov_dir:
            parser.error("--batch requires --asan-dir and --pov-dir")
        triples = find_challenges(Path(args.asan_dir), Path(args.pov_dir))
        print(f"Found {len(triples)} challenge/PoV pairs", file=sys.stderr)

        # Set up log directory
        log_dir = Path(args.log_dir) if args.log_dir else None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        for name, cb, pov in triples:
            pov_name = Path(pov).stem
            key = f"{name}/{pov_name}"
            print(f"Running {key}...", file=sys.stderr, end=" ", flush=True)
            try:
                runner = PovRunner(cb, pov, timeout=args.timeout, debug=True)
                result = runner.run()

                # Save raw stderr log
                if log_dir and result.get("stderr"):
                    log_file = log_dir / f"{name}__{pov_name}.log"
                    log_file.write_text(result["stderr"])
                    meta_file = log_dir / f"{name}__{pov_name}.meta.json"
                    meta_file.write_text(json.dumps({
                        "signal": result["signal"],
                        "returncode": result["returncode"],
                    }))

                n = len(result["findings"])
                print(f"{'CRASH' if result['signal'] else 'ok'} "
                      f"(findings: {n})", file=sys.stderr)
                results[key] = {
                    "challenge": name,
                    "pov": pov_name,
                    "signal": result["signal"],
                    "findings": result["findings"],
                }
            except Exception as e:
                print(f"ERROR: {e}", file=sys.stderr)
                results[key] = {
                    "challenge": name,
                    "pov": pov_name,
                    "error": str(e),
                }

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            json.dump(results, sys.stdout, indent=2)

    else:
        if not args.cb or not args.pov:
            parser.error("--cb and --pov are required (or use --batch)")
        result = run_single(args.cb, args.pov, args.timeout, args.debug)
        if result["findings"]:
            for f in result["findings"]:
                tf = f["top_frame"]
                print(f"{f['bug_kind']} ({f['raw_kind']}) at "
                      f"{tf.get('function', '?')} {tf.get('file', '?')}:{tf.get('line', '?')}")
                for frame in f.get("frames", [])[:5]:
                    print(f"  #{frame['frame']} {frame['function']} "
                          f"{frame['file']}:{frame['line']}")
        else:
            sig = result["signal"]
            if sig:
                print(f"Crashed with signal {sig} but no ASAN output captured")
            else:
                print("No crash / no findings")

        if args.debug and result.get("stderr"):
            print("\n--- STDERR ---", file=sys.stderr)
            print(result["stderr"], file=sys.stderr)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
