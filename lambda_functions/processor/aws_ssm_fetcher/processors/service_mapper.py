"""Service mapping processor for AWS SSM data analysis."""

import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseProcessor, ProcessingContext, ProcessingError, ProcessingValidationError
from ..core.error_handling import with_retry_and_circuit_breaker, ErrorHandler


class ServiceMapper(BaseProcessor):
    """Processor for mapping AWS services to regions using SSM data."""
    
    def __init__(self, context: ProcessingContext):
        """Initialize service mapper processor.
        
        Args:
            context: Processing context with SSM client and config
        """
        super().__init__(context)
        self.error_handler = ErrorHandler()
        
        # Get SSM client from context (injected dependency)
        if not hasattr(context, 'ssm_client'):
            raise ProcessingError("SSM client not found in processing context")
        
        self.ssm_client = context.ssm_client
        
        # Configure retry and circuit breaker for AWS operations
        retry_config = self.error_handler.get_aws_retry_config()
        circuit_config = self.error_handler.get_aws_circuit_breaker_config()
        
        # Decorate SSM operations with reliability patterns
        self._fetch_service_regions_with_reliability = with_retry_and_circuit_breaker(
            retry_config, circuit_config
        )(self._fetch_service_regions)
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate input service list.
        
        Args:
            input_data: List of AWS service codes to validate
            
        Returns:
            True if valid
            
        Raises:
            ProcessingValidationError: If validation fails
        """
        if not isinstance(input_data, list):
            raise ProcessingValidationError("Input must be a list of service codes")
        
        if not input_data:
            raise ProcessingValidationError("Service list cannot be empty")
        
        # Validate service code format
        for service_code in input_data:
            if not isinstance(service_code, str):
                raise ProcessingValidationError(f"Service code must be string: {service_code}")
            
            if not service_code.strip():
                raise ProcessingValidationError("Service code cannot be empty")
            
            # Basic AWS service code validation
            if not all(c.isalnum() or c in '-_' for c in service_code):
                raise ProcessingValidationError(f"Invalid service code format: {service_code}")
        
        return True
    
    def process(self, input_data: List[str], **kwargs) -> Dict[str, List[str]]:
        """Map services to regions using actual AWS SSM data.
        
        Args:
            input_data: List of AWS service codes to map
            **kwargs: Additional processing parameters
            
        Returns:
            Dictionary mapping region codes to lists of available services
            
        Raises:
            ProcessingError: If mapping fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")
        
        self.logger.info(f"Mapping {len(input_data)} services to regions using AWS SSM data")
        
        region_services = {}
        processing_stats = {
            'services_processed': 0,
            'services_failed': 0,
            'total_mappings': 0,
            'regions_discovered': 0
        }
        
        try:
            for i, service_code in enumerate(input_data, 1):
                self.logger.info(f"Processing service {i:3d}/{len(input_data)}: {service_code}")
                
                try:
                    # Fetch regions for this service with reliability patterns
                    service_regions = self._fetch_service_regions_with_reliability(service_code)
                    
                    # Add service to each region it's available in
                    for region_code in service_regions:
                        if region_code not in region_services:
                            region_services[region_code] = []
                        
                        if service_code not in region_services[region_code]:
                            region_services[region_code].append(service_code)
                            processing_stats['total_mappings'] += 1
                    
                    processing_stats['services_processed'] += 1
                    self.logger.info(f"  {service_code} available in {len(service_regions)} regions")
                    
                    # Add delay to prevent throttling (every 10 services)
                    if i % 10 == 0:
                        time.sleep(0.5)
                    
                except Exception as e:
                    processing_stats['services_failed'] += 1
                    self.logger.warning(f"Failed to process service {service_code}: {e}")
                    continue
            
            # Sort services within each region for consistent output
            for region_code in region_services:
                region_services[region_code].sort()
            
            processing_stats['regions_discovered'] = len(region_services)
            
            self.logger.info(
                f"Service mapping completed: "
                f"{processing_stats['regions_discovered']} regions, "
                f"{processing_stats['total_mappings']} total mappings, "
                f"{processing_stats['services_failed']} failures"
            )
            
            # Store processing stats in context metadata
            self.context.metadata.update({
                'service_mapping_stats': processing_stats,
                'processing_completed_at': datetime.now().isoformat()
            })
            
            return region_services
            
        except Exception as e:
            self.logger.error(f"Service mapping failed: {e}", exc_info=True)
            raise ProcessingError(f"Failed to map services to regions: {e}") from e
    
    def _fetch_service_regions(self, service_code: str) -> List[str]:
        """Fetch regions where a specific service is available.
        
        Args:
            service_code: AWS service code to check
            
        Returns:
            List of region codes where service is available
            
        Raises:
            Exception: If SSM query fails
        """
        service_path = f"/aws/service/global-infrastructure/services/{service_code}/regions"
        service_regions = []
        
        try:
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            page_iterator = paginator.paginate(
                Path=service_path,
                Recursive=False,
                MaxResults=10
            )
            
            for page in page_iterator:
                for param in page['Parameters']:
                    # Parameter value contains the region code
                    region_code = param['Value']
                    if region_code and region_code.strip():
                        service_regions.append(region_code.strip())
            
            # Remove duplicates and sort
            service_regions = sorted(list(set(service_regions)))
            
        except Exception as e:
            # Let retry/circuit breaker handle the error
            self.logger.debug(f"SSM query failed for {service_code}: {e}")
            raise
        
        return service_regions
    
    def map_services_to_regions(self, services: List[str], **kwargs) -> Dict[str, List[str]]:
        """Map services to regions where they are available.
        
        This implements the abstract method from ServiceMappingProcessor.
        
        Args:
            services: List of service codes to map
            **kwargs: Additional mapping parameters
            
        Returns:
            Dictionary mapping region codes to lists of available services
        """
        return self.process_with_cache(services, **kwargs)
    
    def get_service_regions(self, service_code: str) -> List[str]:
        """Get regions where a specific service is available.
        
        This implements the abstract method from ServiceMappingProcessor.
        
        Args:
            service_code: AWS service code
            
        Returns:
            List of region codes where service is available
        """
        try:
            return self._fetch_service_regions_with_reliability(service_code)
        except Exception as e:
            self.logger.error(f"Failed to get regions for service {service_code}: {e}")
            return []
    
    def get_region_services(self, region_code: str, all_services: List[str]) -> List[str]:
        """Get services available in a specific region.
        
        Args:
            region_code: AWS region code to check
            all_services: List of all services to check
            
        Returns:
            List of service codes available in the region
        """
        self.logger.info(f"Finding services available in region: {region_code}")
        
        # Use the full mapping and filter for this region
        region_services_map = self.process_with_cache(all_services)
        
        return region_services_map.get(region_code, [])
    
    def get_coverage_stats(self, services: List[str]) -> Dict[str, Any]:
        """Get coverage statistics for service-to-region mapping.
        
        Args:
            services: List of services to analyze
            
        Returns:
            Dictionary with coverage statistics
        """
        region_services_map = self.process_with_cache(services)
        
        total_regions = len(region_services_map)
        total_services = len(services)
        total_mappings = sum(len(svc_list) for svc_list in region_services_map.values())
        
        # Service coverage analysis
        service_coverage = {}
        for service in services:
            regions_with_service = sum(
                1 for region_services in region_services_map.values()
                if service in region_services
            )
            service_coverage[service] = {
                'region_count': regions_with_service,
                'coverage_percentage': (regions_with_service / total_regions * 100) if total_regions > 0 else 0
            }
        
        # Region coverage analysis
        region_coverage = {}
        for region, region_services in region_services_map.items():
            coverage_pct = (len(region_services) / total_services * 100) if total_services > 0 else 0
            region_coverage[region] = {
                'service_count': len(region_services),
                'coverage_percentage': coverage_pct
            }
        
        # Overall statistics
        avg_services_per_region = total_mappings / total_regions if total_regions > 0 else 0
        avg_regions_per_service = total_mappings / total_services if total_services > 0 else 0
        
        return {
            'overview': {
                'total_regions': total_regions,
                'total_services': total_services,
                'total_mappings': total_mappings,
                'avg_services_per_region': round(avg_services_per_region, 1),
                'avg_regions_per_service': round(avg_regions_per_service, 1)
            },
            'service_coverage': service_coverage,
            'region_coverage': region_coverage,
            'processing_stats': self.get_processing_stats()
        }


class RegionalServiceMapper(ServiceMapper):
    """Specialized service mapper that focuses on regional analysis."""
    
    def analyze_regional_distribution(self, services: List[str]) -> Dict[str, Any]:
        """Analyze service distribution patterns across regions.
        
        Args:
            services: List of services to analyze
            
        Returns:
            Dictionary with regional distribution analysis
        """
        region_services_map = self.process_with_cache(services)
        
        # Region size analysis
        region_sizes = [(region, len(svc_list)) for region, svc_list in region_services_map.items()]
        region_sizes.sort(key=lambda x: x[1], reverse=True)
        
        # Service availability analysis
        service_availability = {}
        for service in services:
            available_regions = [
                region for region, region_services in region_services_map.items()
                if service in region_services
            ]
            service_availability[service] = {
                'regions': available_regions,
                'count': len(available_regions)
            }
        
        # Sort services by availability
        service_by_availability = sorted(
            service_availability.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        return {
            'region_rankings': {
                'by_service_count': region_sizes[:10],  # Top 10
                'largest_region': region_sizes[0] if region_sizes else None,
                'smallest_region': region_sizes[-1] if region_sizes else None
            },
            'service_availability': dict(service_by_availability),
            'distribution_metrics': {
                'regions_with_all_services': sum(
                    1 for region, svc_list in region_services_map.items()
                    if len(svc_list) == len(services)
                ),
                'services_in_all_regions': sum(
                    1 for service in services
                    if service_availability[service]['count'] == len(region_services_map)
                ),
                'coverage_variance': self._calculate_coverage_variance(region_services_map, services)
            }
        }
    
    def _calculate_coverage_variance(self, region_services_map: Dict[str, List[str]], 
                                   services: List[str]) -> float:
        """Calculate variance in service coverage across regions."""
        if not region_services_map:
            return 0.0
        
        # Calculate coverage percentages
        total_services = len(services)
        coverage_percentages = [
            len(svc_list) / total_services * 100
            for svc_list in region_services_map.values()
        ]
        
        if not coverage_percentages:
            return 0.0
        
        # Calculate variance
        mean_coverage = sum(coverage_percentages) / len(coverage_percentages)
        variance = sum((x - mean_coverage) ** 2 for x in coverage_percentages) / len(coverage_percentages)
        
        return round(variance, 2)