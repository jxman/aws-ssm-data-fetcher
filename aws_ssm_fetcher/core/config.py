"""Configuration management for AWS SSM Data Fetcher."""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class Config:
    """Configuration settings for AWS SSM Data Fetcher."""
    
    # AWS Settings
    aws_region: str = "us-east-1"
    aws_profile: Optional[str] = None
    
    # Cache Settings
    cache_dir: str = ".cache"
    cache_hours: int = 24
    cache_enabled: bool = True
    
    # Output Settings
    output_dir: str = "output"
    
    # Performance Settings
    max_retries: int = 3
    max_workers: int = 10
    
    # S3 Cache Settings (for Lambda)
    s3_cache_bucket: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create config from environment variables."""
        return cls(
            aws_region=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
            aws_profile=os.getenv('AWS_PROFILE'),
            cache_dir=os.getenv('CACHE_DIR', '.cache'),
            cache_hours=int(os.getenv('CACHE_HOURS', '24')),
            cache_enabled=os.getenv('CACHE_ENABLED', 'true').lower() == 'true',
            output_dir=os.getenv('OUTPUT_DIR', 'output'),
            max_retries=int(os.getenv('MAX_RETRIES', '3')),
            max_workers=int(os.getenv('MAX_WORKERS', '10')),
            s3_cache_bucket=os.getenv('S3_CACHE_BUCKET')
        )
    
    @classmethod
    def for_lambda(cls, function_type: str = "data_fetcher") -> 'Config':
        """Create Lambda-optimized configuration."""
        config = cls.from_env()
        
        # Lambda-specific overrides
        config.cache_dir = "/tmp/cache"
        config.output_dir = "/tmp/output"
        
        # Function-specific optimizations
        if function_type == "data_fetcher":
            config.max_workers = 20  # High concurrency for API calls
        elif function_type == "processor":
            config.max_workers = 10  # Moderate for processing
        elif function_type == "report_generator":
            config.max_workers = 5   # Lower for memory-intensive Excel generation
            
        return config
    
    @classmethod
    def from_args(cls, args) -> 'Config':
        """Create config from command line arguments."""
        config = cls.from_env()
        
        # Override with CLI arguments if provided
        if hasattr(args, 'cache_dir') and args.cache_dir:
            config.cache_dir = args.cache_dir
        if hasattr(args, 'cache_hours') and args.cache_hours:
            config.cache_hours = args.cache_hours
        if hasattr(args, 'output_dir') and args.output_dir:
            config.output_dir = args.output_dir
        if hasattr(args, 'no_cache') and args.no_cache:
            config.cache_enabled = False
            
        return config