"""Lambda-optimized configuration for core utilities."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LambdaConfig:
    """Lambda-specific configuration settings."""
    
    # AWS Lambda Environment
    aws_region: str = os.getenv('AWS_REGION', 'us-east-1')
    function_name: str = os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'aws-ssm-fetcher')
    
    # Lambda Storage (ephemeral /tmp has 10GB limit)
    cache_dir: str = "/tmp/cache"  # Lambda temp storage
    output_dir: str = "/tmp/output"  # Temporary output before S3 upload
    
    # Lambda Performance (15min timeout, 10GB memory max)
    lambda_timeout: int = int(os.getenv('LAMBDA_TIMEOUT', '900'))  # 15 minutes max
    lambda_memory: int = int(os.getenv('LAMBDA_MEMORY', '1024'))   # MB
    max_workers: int = min(10, lambda_memory // 100)  # Scale workers with memory
    
    # Lambda Caching Strategy
    cache_enabled: bool = True
    cache_backend: str = os.getenv('CACHE_BACKEND', 'local')  # local, s3, elasticache
    s3_cache_bucket: Optional[str] = os.getenv('S3_CACHE_BUCKET')
    elasticache_endpoint: Optional[str] = os.getenv('ELASTICACHE_ENDPOINT')
    
    # Lambda Output Strategy  
    output_backend: str = os.getenv('OUTPUT_BACKEND', 's3')  # s3, local
    s3_output_bucket: Optional[str] = os.getenv('S3_OUTPUT_BUCKET')
    
    # Performance Tuning
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    batch_size: int = int(os.getenv('BATCH_SIZE', '50'))  # Process services in batches
    
    @classmethod
    def for_lambda_function(cls, function_type: str) -> 'LambdaConfig':
        """Create config optimized for specific Lambda function type."""
        config = cls()
        
        if function_type == "data_fetcher":
            # High memory for concurrent API calls
            config.lambda_memory = 2048
            config.max_workers = 20
            config.cache_backend = "s3"  # Persist across invocations
            
        elif function_type == "processor":
            # Medium memory for data processing
            config.lambda_memory = 1024
            config.max_workers = 10
            config.cache_backend = "local"  # Fast processing
            
        elif function_type == "report_generator":
            # High memory for Excel generation
            config.lambda_memory = 3008
            config.max_workers = 5
            config.output_backend = "s3"  # Store large files
            
        return config