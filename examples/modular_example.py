#!/usr/bin/env python3
"""Example of how the modular architecture would work."""

import boto3

from aws_ssm_fetcher.core.cache import CacheManager
from aws_ssm_fetcher.core.config import Config
from aws_ssm_fetcher.data_sources.aws_ssm_client import AWSSSMClient


def main():
    """Demonstrate modular architecture."""
    # 1. Configuration Management
    config = Config.from_env()
    print(
        f"Config loaded: AWS Region = {config.aws_region}, Cache TTL = {config.cache_hours}h"
    )

    # 2. Cache Management
    cache_manager = CacheManager(config.cache_dir, config.cache_hours)
    print(f"Cache manager initialized: {cache_manager.cache_dir}")

    # 3. AWS Session
    session = boto3.Session(
        profile_name=config.aws_profile, region_name=config.aws_region
    )

    # 4. Data Source (Clean separation!)
    ssm_client = AWSSSMClient(
        aws_session=session,
        cache_manager=cache_manager,
        region=config.aws_region,
        max_retries=config.max_retries,
    )

    # 5. Fetch Data (Simple, testable interface!)
    print("Fetching regions...")
    regions = ssm_client.fetch_data("regions")
    print(f"Discovered {len(regions)} regions")

    print("Fetching services...")
    services = ssm_client.fetch_data("services")
    print(f"Discovered {len(services)} services")

    # 6. This demonstrates clean separation:
    # - Configuration is centralized
    # - Caching is transparent
    # - Data fetching is isolated and testable
    # - Each component has a single responsibility

    print("\n✅ Modular architecture working perfectly!")
    print("Each component can now be:")
    print("  • Unit tested independently")
    print("  • Modified without affecting others")
    print("  • Extended with new features")
    print("  • Deployed as separate microservices")


if __name__ == "__main__":
    main()
