"""RSS data source client for fetching AWS region metadata and launch dates."""

import re
import time
from datetime import datetime
from typing import Any, Dict, Optional

import feedparser
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from ..core.error_handling import (
    CircuitBreakerConfig,
    NonRetryableError,
    RetryableError,
    RetryConfig,
    with_retry_and_circuit_breaker,
)
from ..core.logging import get_logger
from .base import DataSource


class RSSClient(DataSource):
    """Client for fetching AWS region metadata from RSS feeds.

    Provides functionality to:
    - Fetch region launch dates and metadata from AWS RSS feeds
    - Parse and validate RSS feed data
    - Handle network errors and retries
    - Cache RSS data for improved performance
    """

    def __init__(
        self, cache_manager=None, timeout=30, max_retries=3, backoff_factor=0.5
    ):
        """Initialize RSS client.

        Args:
            cache_manager: Optional cache manager for data persistence
            timeout: HTTP request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            backoff_factor: Backoff factor for exponential delay between retries
        """
        super().__init__(cache_manager)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = get_logger("rss_client")
        self._session = None

        # Configure enhanced error handling for RSS operations
        self._retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,  # Longer delay for RSS feeds
            max_delay=30.0,
            retryable_exceptions=(
                requests.exceptions.RequestException,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                ConnectionError,
                TimeoutError,
                RetryableError,
            ),
        )

        self._circuit_config = CircuitBreakerConfig(
            failure_threshold=2,  # More sensitive for RSS feeds
            recovery_timeout=120.0,  # Longer recovery time
            expected_exception=requests.exceptions.RequestException,
        )

        # AWS RSS feed URLs
        self.rss_urls = {
            "regions": "https://docs.aws.amazon.com/global-infrastructure/latest/regions/regions.rss",
            "services": "https://docs.aws.amazon.com/global-infrastructure/latest/services/services.rss",
        }

    def _get_session(self):
        """Get HTTP session with retry configuration."""
        if self._session is None:
            self._session = requests.Session()

            # Configure retry strategy
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=self.backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
            )

            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

            # Set default headers
            self._session.headers.update(
                {
                    "User-Agent": "AWS-SSM-Fetcher/1.0 (https://github.com/aws-samples/aws-ssm-data-fetcher)",
                    "Accept": "application/rss+xml, application/xml, text/xml",
                }
            )

        return self._session

    def fetch_data(
        self, data_type: str = "regions", **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Fetch RSS data based on type.

        Args:
            data_type: Type of data to fetch ('regions' or 'services')
            **kwargs: Additional parameters (url for custom URL)

        Returns:
            Dictionary of parsed RSS data or None if failed
        """
        if data_type == "regions":
            return self.fetch_region_rss_data()
        elif data_type == "services":
            return self.fetch_services_rss_data()
        elif data_type == "custom":
            url = kwargs.get("url")
            if url:
                return self.fetch_rss_feed(url)

        self.logger.error(f"Unknown RSS data type: {data_type}")
        return None

    def fetch_region_rss_data(self) -> Dict[str, Dict]:
        """Fetch region launch dates and metadata from AWS RSS feed.

        Returns:
            Dictionary mapping region codes to metadata dictionaries containing:
            - region_name: Human-readable region name
            - launch_date: Region launch date (YYYY-MM-DD format)
            - announcement_url: AWS announcement URL
            - rss_title: Original RSS entry title
            - description: RSS entry description
        """
        cache_key = "region_rss_data"

        # Try to load from cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached RSS region data")
            return cached_data

        self.logger.info("Fetching AWS regions RSS data...")
        return self._fetch_and_parse_regions(cache_key)

    def fetch_services_rss_data(self) -> Dict[str, Dict]:
        """Fetch AWS services metadata from RSS feed.

        Returns:
            Dictionary mapping service codes to metadata dictionaries
        """
        cache_key = "services_rss_data"

        # Try to load from cache first
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            self.logger.info("Using cached RSS services data")
            return cached_data

        self.logger.info("Fetching AWS services RSS data...")
        url = self.rss_urls.get("services")

        try:
            feed_data = self.fetch_rss_feed(url)
            if feed_data:
                # Cache the results
                self.cache_data(cache_key, feed_data)
            return feed_data or {}

        except Exception as e:
            self.logger.error(f"Failed to fetch services RSS data: {e}")
            return {}

    def fetch_rss_feed(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse RSS feed from URL.

        Args:
            url: RSS feed URL

        Returns:
            Dictionary containing parsed feed data or None if failed
        """
        try:
            session = self._get_session()
            self.logger.info(f"Fetching RSS feed from: {url}")

            # Fetch RSS feed with timeout and retries
            response = session.get(url, timeout=self.timeout)
            response.raise_for_status()

            self.logger.info(
                f"Successfully fetched RSS feed ({len(response.content)} bytes)"
            )

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                self.logger.warning(f"RSS feed parsing warning: {feed.bozo_exception}")

            # Extract feed metadata
            feed_info = {
                "title": getattr(feed.feed, "title", "Unknown"),
                "description": getattr(feed.feed, "description", ""),
                "link": getattr(feed.feed, "link", ""),
                "updated": getattr(feed.feed, "updated", ""),
                "entries_count": len(feed.entries),
                "entries": {},
            }

            self.logger.info(
                f"Parsed RSS feed: {feed_info['title']} ({feed_info['entries_count']} entries)"
            )

            return feed_info

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching RSS feed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing RSS feed: {e}")
            return None

    @with_retry_and_circuit_breaker()
    def _fetch_and_parse_regions(self, cache_key: str) -> Dict[str, Dict]:
        """Internal method to fetch and parse region RSS data.

        Args:
            cache_key: Cache key for storing results

        Returns:
            Dictionary mapping region codes to metadata
        """
        url = self.rss_urls.get("regions")

        try:
            session = self._get_session()

            # Fetch RSS feed
            response = session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            region_data = {}

            for entry in feed.entries:
                try:
                    # Extract information from RSS entry
                    title = entry.title
                    description = getattr(entry, "description", "")
                    published = getattr(entry, "published", "")
                    link = getattr(entry, "link", "")

                    # Parse region data from entry
                    parsed_region = self._parse_region_entry(
                        title, description, published, link
                    )

                    if parsed_region:
                        region_code = parsed_region["region_code"]
                        region_data[region_code] = {
                            "region_name": parsed_region["region_name"],
                            "launch_date": parsed_region["launch_date"],
                            "announcement_url": link,
                            "rss_title": title,
                            "description": description,
                        }

                        self.logger.debug(
                            f"Parsed region: {region_code} = {parsed_region['region_name']} ({parsed_region['launch_date']})"
                        )

                except Exception as e:
                    self.logger.warning(f"Failed to parse RSS entry: {e}")
                    continue

            # Save to cache
            self.cache_data(cache_key, region_data)

            self.logger.info(
                f"Successfully fetched RSS data for {len(region_data)} regions"
            )
            return region_data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching RSS data: {e}")
            raise RetryableError(f"Network error fetching RSS data: {e}") from e
        except Exception as e:
            self.logger.error(f"Failed to fetch RSS data: {e}")
            # For RSS parsing errors, don't retry - return empty dict
            return {}

    def _parse_region_entry(
        self, title: str, description: str, published: str, link: str
    ) -> Optional[Dict[str, str]]:
        """Parse region information from RSS entry.

        Args:
            title: RSS entry title
            description: RSS entry description
            published: RSS entry published date
            link: RSS entry link

        Returns:
            Dictionary with region_code, region_name, and launch_date or None if parsing fails
        """
        # Parse region code from title or description
        # Example titles: "Asia Pacific (New Zealand) - ap-southeast-6"
        region_code_match = re.search(
            r"([a-z]{2}-[a-z]+-[0-9]{1,2})", title + " " + description
        )

        if not region_code_match:
            return None

        region_code = region_code_match.group(1)

        # Extract region name (everything before the dash and region code)
        region_name_match = re.search(
            r"^(.+?)\\s*-\\s*" + re.escape(region_code), title
        )
        region_name = (
            region_name_match.group(1).strip()
            if region_name_match
            else title.split("-")[0].strip()
        )

        # Parse launch date from published date
        launch_date = self._parse_launch_date(published, description)

        return {
            "region_code": region_code,
            "region_name": region_name,
            "launch_date": launch_date,
        }

    def _parse_launch_date(self, published: str, description: str) -> str:
        """Parse launch date from RSS entry data.

        Args:
            published: Published date string
            description: Entry description (fallback for date extraction)

        Returns:
            Launch date in YYYY-MM-DD format or 'N/A' if not found
        """
        if not published:
            return "N/A"

        # Try different date formats
        date_formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%a, %d %b %Y %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ]

        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(published, date_format)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Try common date formats in published string
        date_patterns = [
            (r"(\w+ \d{1,2}, \d{4})", "%B %d, %Y"),
            (r"(\d{1,2}/\d{1,2}/\d{4})", "%m/%d/%Y"),
            (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
        ]

        for pattern, date_format in date_patterns:
            match = re.search(pattern, published)
            if match:
                try:
                    parsed_date = datetime.strptime(match.group(1), date_format)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # Try extracting date from description as fallback
        if description:
            for pattern, date_format in date_patterns:
                match = re.search(pattern, description)
                if match:
                    try:
                        parsed_date = datetime.strptime(match.group(1), date_format)
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue

        self.logger.debug(f"Could not parse date from: {published}")
        return "N/A"

    def validate_rss_data(self, data: Dict[str, Dict]) -> bool:
        """Validate RSS data structure and content.

        Args:
            data: RSS data dictionary to validate

        Returns:
            True if data is valid, False otherwise
        """
        if not isinstance(data, dict):
            self.logger.error("RSS data is not a dictionary")
            return False

        if not data:
            self.logger.warning("RSS data is empty")
            return True  # Empty is valid, just not useful

        # Check a few entries for proper structure
        sample_keys = list(data.keys())[:3]  # Check first 3 entries

        for region_code in sample_keys:
            if not re.match(r"^[a-z]{2}-[a-z]+-[0-9]{1,2}$", region_code):
                self.logger.error(f"Invalid region code format: {region_code}")
                return False

            region_info = data[region_code]
            if not isinstance(region_info, dict):
                self.logger.error(f"Region info for {region_code} is not a dictionary")
                return False

            required_fields = ["region_name", "launch_date"]
            for field in required_fields:
                if field not in region_info:
                    self.logger.error(
                        f"Missing required field '{field}' for region {region_code}"
                    )
                    return False

        self.logger.info(f"RSS data validation passed for {len(data)} regions")
        return True

    def get_feed_metadata(self, data_type: str = "regions") -> Optional[Dict[str, str]]:
        """Get metadata about the RSS feed.

        Args:
            data_type: Type of RSS feed to get metadata for

        Returns:
            Dictionary with feed metadata or None if not available
        """
        url = self.rss_urls.get(data_type)
        if not url:
            return None

        try:
            feed_data = self.fetch_rss_feed(url)
            if feed_data:
                return {
                    "title": feed_data.get("title"),
                    "description": feed_data.get("description"),
                    "link": feed_data.get("link"),
                    "updated": feed_data.get("updated"),
                    "entries_count": feed_data.get("entries_count", 0),
                    "url": url,
                }
        except Exception as e:
            self.logger.error(f"Failed to get feed metadata: {e}")

        return None
