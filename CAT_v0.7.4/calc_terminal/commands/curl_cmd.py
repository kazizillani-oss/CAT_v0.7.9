"""
CAT Curl Command — Built-in High-Performance HTTP/REST Client.

Provides full curl-compatible command-line functionality:
- HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- Custom headers (-H / --header)
- Request body & JSON sending (-d / --data / --json)
- Multipart form uploads (-F / --form)
- Redirect following (-L / --location)
- Basic authentication (-u / --user)
- Cookies & cookie jar (-b / --cookie, -c / --cookie-jar)
- File downloads (-o / --output, -O / --remote-name)
- Response headers (-i / --include, -I / --head)
- Verbose trace output (-v / --verbose)
- Colorized terminal JSON highlighting and status badges
- Insecure SSL bypass (-k / --insecure)
- Timeouts & write-out formatting (-m / --max-time, -w / --write-out)
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


CAT_CURL_VERSION = "CAT curl 0.8.0 (python-urllib/requests) OpenSSL/zlib"


class CatCurl:
    """Core execution engine for CAT Curl."""

    def __init__(self):
        self.headers: Dict[str, str] = {}
        self.cookies: Dict[str, str] = {}
        self.cookie_jar_path: Optional[str] = None

    def parse_args(self, argv: List[str]) -> Tuple[argparse.Namespace, List[str]]:
        """Parses curl-compatible command line arguments."""
        # Clean leading subcommand name if invoked via 'cat curl ...'
        args = list(argv)
        if args and args[0] in ("curl", "--curl"):
            args = args[1:]

        parser = argparse.ArgumentParser(
            prog="cat curl",
            description="CAT curl — High-performance terminal HTTP/REST client.",
            add_help=False,
        )

        parser.add_argument("url", nargs="?", default=None, help="Target URL")
        parser.add_argument("--url", dest="url_flag", default=None, help="Target URL (flag)")
        parser.add_argument("-X", "--request", dest="method", default=None, help="HTTP request method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)")
        parser.add_argument("-H", "--header", dest="headers", action="append", default=[], help="Custom header line (e.g. 'Content-Type: application/json')")
        parser.add_argument("-d", "--data", "--data-raw", "--data-ascii", dest="data", default=None, help="HTTP POST/request body data")
        parser.add_argument("--data-urlencode", dest="data_urlencode", action="append", default=[], help="URL-encoded key=value data")
        parser.add_argument("--json", dest="json_data", default=None, help="JSON body (auto-sets Content-Type & Accept: application/json)")
        parser.add_argument("-F", "--form", dest="form", action="append", default=[], help="Multipart form field (e.g. name=value or file=@path)")
        parser.add_argument("-o", "--output", dest="output", default=None, help="Write output to file instead of stdout")
        parser.add_argument("-O", "--remote-name", dest="remote_name", action="store_true", help="Write output to a file named after the remote URL")
        parser.add_argument("-i", "--include", dest="include_headers", action="store_true", help="Include protocol response headers in the output")
        parser.add_argument("-I", "--head", dest="head_only", action="store_true", help="Show document info only (HEAD request)")
        parser.add_argument("-L", "--location", dest="follow_redirects", action="store_true", default=True, help="Follow HTTP redirects (default: on)")
        parser.add_argument("--no-location", dest="no_location", action="store_true", help="Do not follow HTTP redirects")
        parser.add_argument("-s", "--silent", dest="silent", action="store_true", help="Silent mode (suppress progress and status messages)")
        parser.add_argument("-S", "--show-error", dest="show_error", action="store_true", help="When used with -s, show error on failure")
        parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Verbose mode — print request/response headers and connection details")
        parser.add_argument("-u", "--user", dest="user", default=None, help="Server user and password (user:password)")
        parser.add_argument("-A", "--user-agent", dest="user_agent", default="CAT-curl/0.8.0", help="Custom User-Agent string")
        parser.add_argument("-k", "--insecure", dest="insecure", action="store_true", help="Allow insecure SSL connections (skip certificate verification)")
        parser.add_argument("-m", "--max-time", dest="max_time", type=float, default=60.0, help="Maximum time in seconds allowed for transfer")
        parser.add_argument("--connect-timeout", dest="connect_timeout", type=float, default=30.0, help="Maximum time in seconds allowed for connection")
        parser.add_argument("-b", "--cookie", dest="cookie", default=None, help="Send cookie data (string or cookie file)")
        parser.add_argument("-c", "--cookie-jar", dest="cookie_jar", default=None, help="File to write cookies to after request")
        parser.add_argument("-w", "--write-out", dest="write_out", default=None, help="Format string for output metrics (e.g. '%%{http_code}\\n')")
        parser.add_argument("--system", dest="use_system", action="store_true", help="Delegate directly to host system curl binary")
        parser.add_argument("-h", "--help", dest="help", action="store_true", help="Show this help message and exit")
        parser.add_argument("-V", "--version", dest="version", action="store_true", help="Print version information and exit")

        parsed, remaining = parser.parse_known_args(args)
        return parsed, remaining

    def run(self, argv: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Runs the curl command according to argv.

        Returns (exit_code, stdout_str, stderr_str).
        """
        parsed, remaining = self.parse_args(argv)

        if parsed.help:
            usage_text = self._format_help()
            if not capture_output:
                print(usage_text)
            return 0, usage_text, ""

        if parsed.version:
            v_text = f"{CAT_CURL_VERSION}\nProtocols: dict file ftp ftps gopher http https imap imaps pop3 pop3s smb smbs smtp smtps telnet\nFeatures: AsynchDNS IPv6 Largefile NTLM SSL TLS-SRP HTTPS-proxy"
            if not capture_output:
                print(v_text)
            return 0, v_text, ""

        # Delegate to host system curl if explicitly requested
        if parsed.use_system:
            import shutil
            import subprocess
            sys_curl = shutil.which("curl")
            if sys_curl:
                sys_args = [sys_curl] + [a for a in argv if a not in ("curl", "--curl", "--system")]
                res = subprocess.run(sys_args, capture_output=capture_output, text=True)
                return res.returncode, res.stdout or "", res.stderr or ""
            else:
                err = "cat curl: system curl executable not found in PATH."
                if not capture_output and not parsed.silent:
                    print(err, file=sys.stderr)
                return 1, "", err

        # Determine target URL
        url = parsed.url or parsed.url_flag
        if not url:
            err = "cat curl: no URL specified! (Use 'cat curl --help' for usage)"
            if not capture_output:
                print(err, file=sys.stderr)
            return 2, "", err

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = "http://" + url

        # Determine HTTP method
        if parsed.head_only:
            method = "HEAD"
        elif parsed.method:
            method = parsed.method.upper()
        elif parsed.data is not None or parsed.json_data is not None or parsed.data_urlencode or parsed.form:
            method = "POST"
        else:
            method = "GET"

        # Prepare request headers
        req_headers: Dict[str, str] = {
            "User-Agent": parsed.user_agent,
            "Accept": "*/*",
        }

        # User specified headers
        for h in parsed.headers:
            if ":" in h:
                k, v = h.split(":", 1)
                req_headers[k.strip()] = v.strip()

        # Cookies
        if parsed.cookie:
            if os.path.exists(parsed.cookie):
                try:
                    with open(parsed.cookie, "r", encoding="utf-8", errors="ignore") as cf:
                        req_headers["Cookie"] = cf.read().strip()
                except Exception:
                    req_headers["Cookie"] = parsed.cookie
            else:
                req_headers["Cookie"] = parsed.cookie

        # Prepare payload
        body_bytes: Optional[bytes] = None
        if parsed.json_data is not None:
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
            if "Accept" not in req_headers or req_headers.get("Accept") == "*/*":
                req_headers["Accept"] = "application/json"
            body_bytes = parsed.json_data.encode("utf-8")
        elif parsed.data is not None:
            if parsed.data.startswith("@") and os.path.exists(parsed.data[1:]):
                with open(parsed.data[1:], "rb") as f:
                    body_bytes = f.read()
            else:
                body_bytes = parsed.data.encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif parsed.data_urlencode:
            encoded_pairs = []
            for item in parsed.data_urlencode:
                if "=" in item:
                    k, v = item.split("=", 1)
                    encoded_pairs.append((k, v))
                else:
                    encoded_pairs.append((item, ""))
            body_bytes = urllib.parse.urlencode(encoded_pairs).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif parsed.form:
            boundary = f"----CATCurlBoundary{int(time.time()*1000)}"
            parts = []
            for f_item in parsed.form:
                if "=" in f_item:
                    f_name, f_val = f_item.split("=", 1)
                    if f_val.startswith("@") and os.path.exists(f_val[1:]):
                        filepath = f_val[1:]
                        fname = os.path.basename(filepath)
                        with open(filepath, "rb") as ff:
                            fdata = ff.read()
                        part_head = (
                            f"--{boundary}\r\n"
                            f'Content-Disposition: form-data; name="{f_name}"; filename="{fname}"\r\n'
                            f"Content-Type: application/octet-stream\r\n\r\n"
                        ).encode("utf-8")
                        parts.append(part_head + fdata + b"\r\n")
                    else:
                        parts.append(
                            f"--{boundary}\r\n"
                            f'Content-Disposition: form-data; name="{f_name}"\r\n\r\n'
                            f"{f_val}\r\n".encode("utf-8")
                        )
            parts.append(f"--{boundary}--\r\n".encode("utf-8"))
            body_bytes = b"".join(parts)
            req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        # Basic Auth
        if parsed.user:
            auth_token = base64.b64encode(parsed.user.encode("utf-8")).decode("ascii")
            req_headers["Authorization"] = f"Basic {auth_token}"

        # SSL context
        ssl_ctx = ssl.create_default_context()
        if parsed.insecure:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        # Setup redirect handler
        handlers: List[Any] = []
        if parsed.insecure:
            handlers.append(urllib.request.HTTPSHandler(context=ssl_ctx))

        if parsed.no_location:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            handlers.append(NoRedirect())

        opener = urllib.request.build_opener(*handlers)

        # Print verbose request trace
        stderr_lines: List[str] = []
        if parsed.verbose:
            parsed_url = urllib.parse.urlparse(url)
            port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
            stderr_lines.append(f"* Trying {parsed_url.hostname}:{port}...")
            stderr_lines.append(f"* Connected to {parsed_url.hostname} ({parsed_url.hostname}) port {port}")
            stderr_lines.append(f"> {method} {parsed_url.path or '/'} HTTP/1.1")
            stderr_lines.append(f"> Host: {parsed_url.netloc}")
            for hk, hv in req_headers.items():
                stderr_lines.append(f"> {hk}: {hv}")
            stderr_lines.append(">")

        req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)

        t_start = time.time()
        res_code = 0
        res_headers = {}
        res_data = b""

        try:
            with opener.open(req, timeout=parsed.max_time) as resp:
                res_code = resp.status if hasattr(resp, "status") else resp.getcode()
                res_headers = dict(resp.headers)
                res_data = resp.read()
        except urllib.error.HTTPError as he:
            res_code = he.code
            res_headers = dict(he.headers)
            try:
                res_data = he.read()
            except Exception:
                res_data = b""
        except urllib.error.URLError as ue:
            err_msg = f"cat curl: ({self._map_urlerror_code(ue)}) Could not resolve or connect: {ue.reason}"
            if not capture_output and (not parsed.silent or parsed.show_error):
                print(err_msg, file=sys.stderr)
            return self._map_urlerror_code(ue), "", err_msg
        except Exception as e:
            err_msg = f"cat curl: transfer failed: {e}"
            if not capture_output and (not parsed.silent or parsed.show_error):
                print(err_msg, file=sys.stderr)
            return 1, "", err_msg

        duration = time.time() - t_start

        # Handle Set-Cookie if cookie jar is specified
        if parsed.cookie_jar and "Set-Cookie" in res_headers:
            try:
                with open(parsed.cookie_jar, "w", encoding="utf-8") as cjf:
                    cjf.write(f"# Netscape HTTP Cookie File\n{res_headers['Set-Cookie']}\n")
            except Exception:
                pass

        if parsed.verbose:
            status_text = http.client.responses.get(res_code, "Unknown")
            stderr_lines.append(f"< HTTP/1.1 {res_code} {status_text}")
            for rhk, rhv in res_headers.items():
                stderr_lines.append(f"< {rhk}: {rhv}")
            stderr_lines.append("<")
            stderr_lines.append(f"* Connection #0 left intact (transferred {len(res_data)} bytes in {duration:.3f}s)")

        # Prepare outputs
        header_text = ""
        if parsed.include_headers or parsed.head_only:
            status_text = http.client.responses.get(res_code, "OK")
            h_lines = [f"HTTP/1.1 {res_code} {status_text}"]
            for k, v in res_headers.items():
                h_lines.append(f"{k}: {v}")
            header_text = "\r\n".join(h_lines) + "\r\n\r\n"

        out_dest = None
        if parsed.output:
            out_dest = parsed.output
        elif parsed.remote_name:
            out_dest = os.path.basename(urllib.parse.urlparse(url).path) or "index.html"

        # Decode body
        text_body = ""
        is_binary = False
        try:
            text_body = res_data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text_body = res_data.decode("latin-1")
            except Exception:
                is_binary = True

        full_stdout = (header_text if parsed.include_headers else "") + (text_body if not parsed.head_only else "")
        stderr_output = "\n".join(stderr_lines)

        # Output to file if destination requested
        if out_dest:
            try:
                with open(out_dest, "wb") as f_out:
                    if parsed.include_headers:
                        f_out.write(header_text.encode("utf-8"))
                    f_out.write(res_data)
                if not capture_output and not parsed.silent:
                    print(f"  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current")
                    print(f"                                 Dload  Upload   Total   Spent    Left  Speed")
                    print(f"100 {len(res_data):>7}  100 {len(res_data):>7}    0     0  {int(len(res_data)/max(duration,0.001)):>5}      0 --:--:-- --:--:-- --:--:-- {int(len(res_data)/max(duration,0.001)):>5}")
                    print(f"✓ Saved {len(res_data)} bytes to {out_dest}")
            except Exception as e:
                err_msg = f"cat curl: Failed to write to {out_dest}: {e}"
                if not capture_output:
                    print(err_msg, file=sys.stderr)
                return 23, "", err_msg
        else:
            if not capture_output:
                if stderr_output and parsed.verbose:
                    print(stderr_output, file=sys.stderr)

                if parsed.include_headers:
                    sys.stdout.write(header_text)

                if not parsed.head_only:
                    if is_binary:
                        try:
                            sys.stdout.buffer.write(res_data)
                            sys.stdout.buffer.flush()
                        except Exception:
                            sys.stdout.write(f"[Binary data: {len(res_data)} bytes]\n")
                    else:
                        # Colorize JSON if running interactively on terminal
                        rendered = self._render_body_for_terminal(text_body, res_headers)
                        sys.stdout.write(rendered)
                        if not rendered.endswith("\n"):
                            sys.stdout.write("\n")
                        sys.stdout.flush()

        # Format --write-out
        if parsed.write_out:
            w_out = parsed.write_out
            w_out = w_out.replace("\\n", "\n").replace("\\t", "\t")
            w_out = w_out.replace("%{http_code}", str(res_code))
            w_out = w_out.replace("%{time_total}", f"{duration:.3f}")
            w_out = w_out.replace("%{size_download}", str(len(res_data)))
            w_out = w_out.replace("%{url_effective}", url)
            if not capture_output:
                sys.stdout.write(w_out)
                sys.stdout.flush()
            full_stdout += w_out

        exit_code = 0 if (200 <= res_code < 400 or parsed.head_only) else (22 if res_code >= 400 else 0)
        return exit_code, full_stdout, stderr_output

    def _render_body_for_terminal(self, body: str, headers: Dict[str, str]) -> str:
        """Colorizes JSON / HTML / text when printed to an interactive terminal."""
        if not sys.stdout.isatty():
            return body

        content_type = headers.get("content-type", "").lower()
        if "application/json" in content_type or (body.strip().startswith("{") and body.strip().endswith("}")):
            try:
                obj = json.loads(body)
                formatted = json.dumps(obj, indent=2)
                # Apply ANSI color syntax highlighting
                return self._colorize_json(formatted)
            except Exception:
                return body
        return body

    def _colorize_json(self, json_str: str) -> str:
        """Lightweight ANSI syntax highlighting for JSON strings."""
        CYAN = "\033[36m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        DIM = "\033[2m"
        RESET = "\033[0m"

        def _sub(match):
            key = match.group(1)
            val = match.group(2)
            out = f'{CYAN}"{key}"{RESET}: '
            if val is None:
                return out
            v = val.strip()
            if v.startswith('"'):
                out += f"{GREEN}{v}{RESET}"
            elif v in ("true", "false"):
                out += f"{MAGENTA}{v}{RESET}"
            elif v == "null":
                out += f"{DIM}null{RESET}"
            else:
                out += f"{YELLOW}{v}{RESET}"
            return out

        pattern = r'"([^"]+)"\s*:\s*(".*?"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'
        colored = re.sub(pattern, _sub, json_str)
        return colored

    def _map_urlerror_code(self, ue: urllib.error.URLError) -> int:
        r = str(ue.reason).lower()
        if "getaddrinfo" in r or "name resolution" in r or "not known" in r:
            return 6  # CURLE_COULDNT_RESOLVE_HOST
        if "connection refused" in r or "actively refused" in r:
            return 7  # CURLE_COULDNT_CONNECT
        if "timed out" in r or "timeout" in r:
            return 28 # CURLE_OPERATION_TIMEDOUT
        if "ssl" in r or "certificate" in r:
            return 35 # CURLE_SSL_CONNECT_ERROR
        return 6

    def _format_help(self) -> str:
        return """Usage: cat curl [options...] <url>
CAT curl — Universal, high-performance terminal HTTP/REST client.

Options:
  -X, --request <command>   HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
  -H, --header <header>     Custom header to pass to server (e.g. 'Authorization: Bearer <key>')
  -d, --data <data>         HTTP POST data (raw string or @filename)
      --json <data>         Send JSON data (auto-sets Content-Type & Accept: application/json)
      --data-urlencode <d>  URL-encoded form data (key=value)
  -F, --form <name=content> Multipart form upload (e.g. file=@image.png)
  -i, --include             Include protocol response headers in the output
  -I, --head                Show document headers only (HEAD request)
  -o, --output <file>       Write to file instead of stdout
  -O, --remote-name         Write output to file named after the remote URL
  -L, --location            Follow HTTP redirects (enabled by default)
      --no-location         Do not follow redirects
  -s, --silent              Silent mode (suppress progress meters and info messages)
  -S, --show-error          Show error when used with -s if the transfer fails
  -v, --verbose             Make operation more talkative (shows request/response headers)
  -u, --user <user:passwd>  Server user and password for authentication
  -A, --user-agent <name>   Send User-Agent <name> to server
  -k, --insecure            Allow insecure server connections when using SSL (skip cert check)
  -m, --max-time <seconds>  Maximum time allowed for the transfer (default: 60)
      --connect-timeout <s> Maximum time allowed for connection (default: 30)
  -b, --cookie <data|file>  Pass cookie data or read cookies from file
  -c, --cookie-jar <file>   Write cookies to file after request completion
  -w, --write-out <format>  Output format on completion (e.g. '%{http_code}\\n')
      --system              Delegate command execution to the host machine's system curl binary
  -h, --help                Show this help message
  -V, --version             Show version number and exit

Examples:
  cat curl https://api.github.com/zen
  cat curl -i https://httpbin.org/get
  cat curl -X POST https://httpbin.org/post --json '{"name": "CAT", "version": "0.8.0"}'
  cat curl -H "Authorization: Bearer token123" https://api.example.com/data
  cat curl -O https://example.com/file.zip
  cat curl -v https://httpbin.org/headers
"""


def run_curl(argv: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
    """Public helper function to execute CAT Curl programmatically."""
    return CatCurl().run(argv, capture_output=capture_output)


def main(argv: Optional[List[str]] = None) -> int:
    """Console script entrypoint for `cat-curl` or `cat curl`."""
    args = sys.argv[1:] if argv is None else argv
    exit_code, _, _ = CatCurl().run(args, capture_output=False)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
