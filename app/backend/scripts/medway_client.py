"""
Medway API Client with automated token refreshing and session extraction.
Communicates with Medway CMS (cms.medway.com.br) and Firebase Auth.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

FIREBASE_API_KEY = "AIzaSyCOOvkFhuLp-MXInY5AJNsnbNc9Qg41vo8"
DEFAULT_REFRESH_TOKEN = (
    "AMf-vBwTrDnbkiTbNZXO7-hQtPMzzwUJag8_YFvw_xewL2fwX-8tqsHLGbuEOcUON286hqMCAEDavFolAxajH"
    "ByVLzjMty_8sFTgBPOxeMbN_3iRHzE0SvExXZE9uiw3EY5CMm_koZ12OGQ34YWR28Ha51b9dMKe8RUzkEdIU"
    "j0tOg_JS2G15VTj9g6oec_TOA1bz5mLmtUPgJ9uvVC0ZyT-ZIMO8Up7PEAGhWt9HD6xJzcrzGb9xyQ"
)


CACHE_FILE = os.path.expanduser("~/.medway_session.json")

def load_cached_session() -> Dict[str, Any]:
    if os.path.isfile(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cached_session(refresh_token: str, access_token: str, expiry: float) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"refresh_token": refresh_token, "access_token": access_token, "expiry": expiry}, f)
    except Exception:
        pass

def find_refresh_token_from_browser() -> Optional[str]:
    """Attempts to find the latest active Firebase refresh token from Chrome's IndexedDB."""
    cached = load_cached_session().get("refresh_token")
    if cached:
        return cached

    candidates = [
        os.path.expanduser(
            "~/.var/app/com.google.Chrome/config/google-chrome/Default/IndexedDB/https_app.medway.com.br_0.indexeddb.leveldb"
        ),
        os.path.expanduser(
            "~/.config/google-chrome/Default/IndexedDB/https_app.medway.com.br_0.indexeddb.leveldb"
        ),
    ]

    for cdir in candidates:
        if not os.path.isdir(cdir):
            continue
        for fpath in glob.glob(os.path.join(cdir, "*.log")):
            try:
                with open(fpath, "rb") as fp:
                    data = fp.read()
                # Chromium LevelDB IndexedDB stores: stsTokenManagero" ... refreshToken"\xf7\x01<token>"
                matches = re.findall(rb'refreshToken"[\x00-\x1f]*([a-zA-Z0-9_\-]{60,})', data)
                if matches:
                    return matches[-1].decode("utf-8")
            except Exception:
                pass
    return None


class GlobalRateLimiter:
    """Thread-safe leaky-bucket rate limiter ensuring uniform inter-request spacing across all worker threads.

    Prevents triggering Cloudflare rate-limiting algorithms (HTTP 429) by enforcing a strict
    maximum uniform request throughput across concurrent workers.
    """

    def __init__(self, requests_per_second: float = 4.2):
        self.set_rate(requests_per_second)
        self.lock = threading.Lock()
        self.last_time = 0.0

    def set_rate(self, requests_per_second: float) -> None:
        self.requests_per_second = max(0.1, requests_per_second)
        self.interval = 1.0 / self.requests_per_second

    def acquire(self) -> None:
        env_rps = os.environ.get("MEDWAY_RPS")
        if env_rps:
            try:
                val = float(env_rps)
                if abs(val - self.requests_per_second) > 0.01:
                    self.set_rate(val)
            except ValueError:
                pass

        with self.lock:
            now = time.monotonic()
            wait = self.interval - (now - self.last_time)
            if wait > 0:
                time.sleep(wait)
            self.last_time = time.monotonic()


class MedwayClient:
    """Authenticated client for Medway CMS API."""

    def __init__(
        self,
        refresh_token: Optional[str] = None,
        base_url: str = "https://cms.medway.com.br",
        requests_per_second: float = 4.2,
    ):
        self.base_url = base_url.rstrip("/")
        cached = load_cached_session()
        self.refresh_token = (
            refresh_token
            or os.environ.get("MEDWAY_REFRESH_TOKEN")
            or cached.get("refresh_token")
            or find_refresh_token_from_browser()
            or DEFAULT_REFRESH_TOKEN
        )
        self.access_token: Optional[str] = cached.get("access_token")
        self.token_expiry: float = float(cached.get("expiry", 0))
        self.rate_limiter = GlobalRateLimiter(requests_per_second=requests_per_second)

    def refresh_access_token(self) -> str:
        """Exchanges the refresh token for a fresh Firebase ID token."""
        url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
        payload = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.access_token = data["id_token"]
                expires_in = int(data.get("expires_in", 3600))
                self.token_expiry = time.time() + expires_in
                save_cached_session(self.refresh_token, self.access_token, self.token_expiry)
                return self.access_token
        except urllib.error.HTTPError as e:
            # If the refresh token was revoked or invalid, fallback to default or raise
            err_body = e.read().decode("utf-8", errors="ignore")
            if self.refresh_token != DEFAULT_REFRESH_TOKEN:
                print(f"[AUTH] Token failed ({err_body[:60]}), falling back to saved token...")
                self.refresh_token = DEFAULT_REFRESH_TOKEN
                return self.refresh_access_token()
            raise RuntimeError(f"Failed to refresh Firebase token: HTTP {e.code} {err_body}")

    def get_token(self) -> str:
        """Returns a valid access token, renewing it if expired or expiring soon."""
        now = time.time()
        if not self.access_token or now >= (self.token_expiry - 120):
            return self.refresh_access_token()
        return self.access_token

    def request(
        self,
        endpoint: str,
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 6,
        delay_after: float = 0.05,
    ) -> Any:
        """Performs an authenticated API request with auto-retry and polite rate-limiting."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}
            qs = urllib.parse.urlencode(clean_params)
            url += ("&" if "?" in url else "?") + qs

        last_error = None
        for attempt in range(1, retries + 1):
            token = self.get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/153.0.0.0 Safari/537.36"
                ),
                "Origin": "https://app.medway.com.br",
                "Referer": "https://app.medway.com.br/",
                "Accept": "application/json, text/plain, */*",
            }

            req_data = None
            if body is not None:
                req_data = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json"

            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

            # Enforce uniform global inter-request pacing
            self.rate_limiter.acquire()

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" in content_type or raw.startswith(b"{") or raw.startswith(b"["):
                        return json.loads(raw.decode("utf-8"))
                    return raw.decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                last_error = e
                # Expired or rejected token
                if e.code == 401:
                    print("[AUTH] 401 Unauthorized encountered. Refreshing token...")
                    self.refresh_access_token()
                    time.sleep(1)
                    continue
                # Rate limit (429)
                if e.code == 429:
                    wait_sec = min(attempt * 4, 30)
                    retry_header = e.headers.get("Retry-After")
                    if retry_header and retry_header.isdigit():
                        wait_sec = max(wait_sec, int(retry_header) + 1)
                    print(f"[RATE-LIMIT] 429 Too Many Requests. Backing off for {wait_sec}s (attempt {attempt}/{retries})...")
                    time.sleep(wait_sec)
                    continue
                # If 404 or other 4xx client errors, do not retry blindly
                if 400 <= e.code < 500:
                    raise
                # 5xx server errors
                time.sleep(attempt * 2)
            except Exception as e:
                last_error = e
                time.sleep(attempt * 2)

        raise RuntimeError(f"Request to {url} failed after {retries} attempts: {last_error}")

    # ==========================================
    # High-level API Methods
    # ==========================================

    def list_exams(
        self,
        search: Optional[str] = None,
        year: Optional[int] = None,
        ordering: str = "-year",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Queries the Medway exam bank (/api/v2/exam/)."""
        params: Dict[str, Any] = {
            "ordering": ordering,
            "limit": limit,
            "offset": offset,
        }
        if search:
            params["search"] = search
        if year:
            params["year"] = year
        return self.request("/api/v2/exam/", params=params)

    def get_track_fast(self, track_id: int | str) -> Dict[str, Any]:
        """Fetches track metadata summary."""
        return self.request(f"/api/v3/track/{track_id}/fast/")

    def get_track_questions(self, track_id: int | str) -> List[Dict[str, Any]]:
        """Fetches the list of questions in a track."""
        data = self.request(f"/api/v3/track/{track_id}/questions/?expand=focus")
        if isinstance(data, dict):
            return data.get("results", []) or data.get("questions", [])
        if isinstance(data, list):
            return data
        return []

    def get_question_detail(self, question_id: int | str, track_id: Optional[int | str] = None) -> Dict[str, Any]:
        """Fetches complete question statement, alternatives, images, tags."""
        params = {"track": track_id} if track_id else None
        return self.request(f"/api/v3/questions/{question_id}/", params=params)

    def get_question_explanation(
        self, question_id: int | str, track_id: Optional[int | str] = None
    ) -> Dict[str, Any]:
        """Fetches the complete structured text explanation (introduction, conclusion, distractors)."""
        params = {"track": track_id} if track_id else None
        try:
            return self.request(f"/api/v3/questions/{question_id}/text-explanation/", params=params)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            raise

    def list_student_groups(self) -> List[Dict[str, Any]]:
        """Lists user's student courses/groups."""
        return self.request("/api/v2/student_group/?no_page=1")

    def list_subjects(self, student_group_id: int | str) -> List[Dict[str, Any]]:
        """Lists subjects under a student group."""
        return self.request(f"/api/v2/lesson-subject/?studentgroup={student_group_id}&no_page=1")

    def list_modules(self, subject_id: int | str) -> List[Dict[str, Any]]:
        """Lists lesson modules under a subject."""
        return self.request(f"/api/v2/lesson-subject/{subject_id}/modules/")

    def get_module_detail(self, module_id: int | str) -> Dict[str, Any]:
        """Gets module details including tracks and lesson items."""
        return self.request(f"/api/v2/lesson-module/{module_id}/")
