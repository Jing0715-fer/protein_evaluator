"""
API utilities for error handling, retry mechanisms, and graceful degradation.
"""

import logging
import time
import functools
from typing import Callable, Any, Optional, Type, Union, List
from datetime import datetime

import requests

from .exceptions import (
    APIError,
    RetryExhaustedError,
    UniProtAPIError,
    PDBAPIError,
    BLASTSearchError,
    PubMedAPIError
)

logger = logging.getLogger(__name__)


def create_no_proxy_session() -> requests.Session:
    """Create a requests session that bypasses proxy settings."""
    session = requests.Session()
    session.trust_env = False
    return session


# Global HTTP session without proxy — lazily initialized to avoid import-time
# side-effects (important for pytest test isolation and environments where the
# session may need to be patched before any module imports it).
_http: Optional[requests.Session] = None


class _LazySessionProxy:
    """Proxy object that lazily initialises the shared requests.Session on first access.

    Provides backward compatibility: `from utils.api_utils import http_session`
    still works (the proxy is assigned to `http_session` below), but the actual
    session is only created when the proxy is first used.
    """

    __slots__ = ()

    def _get_session(self) -> requests.Session:
        global _http
        if _http is None:
            _http = create_no_proxy_session()
        return _http

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_session(), name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._get_session()(*args, **kwargs)

    def __repr__(self) -> str:
        return repr(self._get_session())


http_session: Any = _LazySessionProxy()  # backward-compatible lazy proxy


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
):
    """
    Decorator for retrying a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function called on each retry
                 Signature: on_retry(exception, attempt_number, next_delay)

    Returns:
        Decorated function

    Raises:
        RetryExhaustedError: If all retry attempts are exhausted
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff_factor ** attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time:.1f}s: {e}"
                        )

                        if on_retry:
                            on_retry(e, attempt + 1, wait_time)

                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )

            raise RetryExhaustedError(
                f"Function {func.__name__} failed after {max_retries} attempts",
                last_exception=last_exception,
                attempts=max_retries
            )

        return wrapper
    return decorator


def retry_on_api_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    status_codes: Optional[List[int]] = None
):
    """
    Decorator specifically for API calls with status code checking.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        status_codes: HTTP status codes that should trigger a retry
                     (default: [429, 500, 502, 503, 504])

    Returns:
        Decorated function
    """
    if status_codes is None:
        status_codes = [429, 500, 502, 503, 504]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    # If result is a Response object, check status code
                    if isinstance(result, requests.Response):
                        if result.status_code in status_codes:
                            raise APIError(
                                f"HTTP {result.status_code}",
                                status_code=result.status_code,
                                response_text=result.text[:500]
                            )
                    return result

                except (requests.RequestException, APIError) as e:
                    last_exception = e

                    # Check if we should retry
                    should_retry = True
                    if isinstance(e, APIError) and e.status_code is not None:
                        should_retry = e.status_code in status_codes

                    if should_retry and attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            f"{func.__name__} API call failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time:.1f}s: {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"{func.__name__} API call failed after {attempt + 1} attempts: {e}"
                        )
                        break

            # All retries exhausted or non-retryable error
            raise last_exception if last_exception else APIError("Unknown error")

        return wrapper
    return decorator


def fallback_on_error(
    fallback_value: Any = None,
    exceptions: tuple = (Exception,),
    log_level: int = logging.WARNING
):
    """
    Decorator that returns a fallback value on error instead of raising.

    Args:
        fallback_value: Value to return on error
        exceptions: Tuple of exceptions to catch
        log_level: Logging level for error messages

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.log(log_level, f"{func.__name__} failed, using fallback: {e}")
                return fallback_value
        return wrapper
    return decorator


def log_api_call(func: Callable) -> Callable:
    """
    Decorator to log API calls with timing information.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__

        logger.debug(f"API call started: {func_name}")

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"API call completed: {func_name} ({elapsed:.2f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"API call failed: {func_name} ({elapsed:.2f}s): {e}")
            raise

    return wrapper


def handle_api_response(
    response: requests.Response,
    expected_status: int = 200,
    error_class: Type[APIError] = APIError
) -> dict:
    """
    Handle API response with proper error handling.

    Args:
        response: requests Response object
        expected_status: Expected HTTP status code
        error_class: Exception class to raise on error

    Returns:
        Parsed JSON response

    Raises:
        APIError: If response status doesn't match expected
    """
    if response.status_code != expected_status:
        raise error_class(
            f"API returned status {response.status_code}, expected {expected_status}",
            status_code=response.status_code,
            response_text=response.text[:1000]
        )

    try:
        return response.json()
    except ValueError as e:
        raise error_class(
            f"Failed to parse JSON response: {e}",
            status_code=response.status_code,
            response_text=response.text[:1000]
        )


def safe_api_call(
    url: str,
    method: str = "GET",
    session: Optional[requests.Session] = None,
    timeout: int = 30,
    error_class: Type[APIError] = APIError,
    **kwargs
) -> requests.Response:
    """
    Make a safe API call with proper error handling.

    Args:
        url: API endpoint URL
        method: HTTP method
        session: Optional requests Session
        timeout: Request timeout in seconds
        error_class: Exception class to raise on error
        **kwargs: Additional arguments for requests

    Returns:
        Response object

    Raises:
        APIError: On request failure
    """
    session = session or http_session

    try:
        response = session.request(
            method=method,
            url=url,
            timeout=timeout,
            **kwargs
        )
        return response
    except requests.Timeout:
        raise error_class(f"Request timeout after {timeout}s", status_code=408)
    except requests.ConnectionError as e:
        raise error_class(f"Connection error: {e}")
    except requests.RequestException as e:
        raise error_class(f"Request failed: {e}")


class APICallContext:
    """Context manager for API calls with automatic retry and fallback."""

    def __init__(
        self,
        service_name: str,
        max_retries: int = 3,
        fallback_value: Any = None,
        raise_on_error: bool = True
    ):
        self.service_name = service_name
        self.max_retries = max_retries
        self.fallback_value = fallback_value
        self.raise_on_error = raise_on_error
        self.start_time: Optional[datetime] = None
        self.attempt = 0

    def __enter__(self):
        self.start_time = datetime.now()
        logger.debug(f"[{self.service_name}] API call started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()

        if exc_val:
            logger.error(f"[{self.service_name}] API call failed ({elapsed:.2f}s): {exc_val}")
            if not self.raise_on_error:
                logger.warning(f"[{self.service_name}] Using fallback value")
                return True  # Suppress exception
        else:
            logger.debug(f"[{self.service_name}] API call completed ({elapsed:.2f}s)")

        return False

    def should_retry(self, exception: Exception) -> bool:
        """Check if the exception warrants a retry."""
        self.attempt += 1
        if self.attempt >= self.max_retries:
            return False

        # Check for retryable exceptions
        if isinstance(exception, requests.RequestException):
            return True
        if isinstance(exception, APIError):
            if exception.status_code in [429, 500, 502, 503, 504]:
                return True

        return False


def get_error_class_for_service(service_name: str) -> Type[APIError]:
    """Get the appropriate error class for a service."""
    error_classes = {
        'uniprot': UniProtAPIError,
        'pdb': PDBAPIError,
        'rcsb': PDBAPIError,
        'blast': BLASTSearchError,
        'ncbi': BLASTSearchError,
        'pubmed': PubMedAPIError,
    }
    return error_classes.get(service_name.lower(), APIError)
