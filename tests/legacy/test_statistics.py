#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from aws_ssm_data_fetcher import AWSSSMDataFetcher

# Create a minimal test for statistics generation
fetcher = AWSSSMDataFetcher()

# Create sample data (like what would be in Regional Services)
test_data = [
    {'Region Code': 'us-east-1', 'Service Name': 'ec2'},
    {'Region Code': 'us-east-1', 'Service Name': 's3'},
    {'Region Code': 'us-west-2', 'Service Name': 'ec2'},
]

# Create mock all_services list
all_services = ['ec2', 's3', 'lambda', 'dynamodb', 'rds']  # 5 services

print(f"Test data contains {len(test_data)} entries with {len(set([d['Service Name'] for d in test_data]))} unique services")
print(f"all_services parameter contains {len(all_services)} services")
print()

# Test the statistics generation
stats_df = fetcher.generate_statistics(test_data, all_services)
print("Generated Statistics:")
print(stats_df.to_string(index=False))