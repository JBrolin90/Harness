"""HTTP retry handling for LLM API calls."""
import time

import requests


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def calculate_backoff(attempt: int) -> int:
    """Calculate exponential backoff: 1s, 2s, 4s, ..."""
    return 2 ** attempt


class RetryHandler:
    """Handles HTTP requests with exponential backoff retry.
    
    Responsibilities:
    - Execute HTTP POST with timeout
    - Detect retryable errors (429, 5xx)
    - Apply exponential backoff or Retry-After header
    - Handle connection errors and timeouts
    
    Usage:
        handler = RetryHandler(max_retries=3)
        response = handler.execute(url, headers, payload)
    """
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
    
    def execute(self, url: str, headers: dict, payload: dict) -> requests.Response:
        """Execute HTTP POST with retry logic.
        
        Args:
            url: Request URL
            headers: Request headers
            payload: Request body (JSON)
        
        Returns:
            requests.Response object
        
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=(5, 180))
                
                if response.status_code not in RETRYABLE_STATUSES:
                    response.raise_for_status()
                    return response
                
                wait_time = self._get_wait_time(response, attempt)
                self._log_retry(response.status_code, wait_time, attempt + 1)
                time.sleep(wait_time)
                last_exception = requests.HTTPError(response=response)
                
            except requests.exceptions.ConnectionError as e:
                wait_time = calculate_backoff(attempt)
                print(f"[BRAIN] Connection error. Retrying in {wait_time}s ({attempt + 1}/{self.max_retries})...")
                time.sleep(wait_time)
                last_exception = e
            except requests.exceptions.Timeout as e:
                wait_time = calculate_backoff(attempt)
                print(f"[BRAIN] Request timeout. Retrying in {wait_time}s ({attempt + 1}/{self.max_retries})...")
                time.sleep(wait_time)
                last_exception = e
            except Exception:
                # Non-retryable exception, re-raise immediately
                raise
        
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Request failed: max retries reached without a specific exception")
    
    def _get_wait_time(self, response: requests.Response, attempt: int) -> int:
        """Determine wait time based on response headers or exponential backoff."""
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                return int(retry_after)
        return calculate_backoff(attempt)
    
    def _log_retry(self, status_code: int, wait_time: int, attempt: int) -> None:
        """Log retry attempt."""
        if status_code == 429:
            print(f"[BRAIN] Rate limited. Waiting {wait_time}s before retry {attempt}/{self.max_retries}...")
        else:
            print(f"[BRAIN] Server error {status_code}. Retrying in {wait_time}s ({attempt}/{self.max_retries})...")