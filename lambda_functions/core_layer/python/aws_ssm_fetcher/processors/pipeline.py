"""Processing pipeline orchestrator for AWS SSM data analysis."""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..core.logging import get_logger
from .base import (
    BaseProcessor,
    ProcessingContext,
    ProcessingError,
    ProcessingValidationError,
)
from .data_transformer import DataTransformer
from .regional_validator import (
    RegionalDataValidator,
    RegionDiscoverer,
    ServiceDiscoverer,
)
from .service_mapper import RegionalServiceMapper, ServiceMapper
from .statistics_analyzer import StatisticsAnalyzer


class PipelineStage(Enum):
    """Pipeline execution stages."""

    DISCOVERY = "discovery"
    MAPPING = "mapping"
    TRANSFORMATION = "transformation"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    OUTPUT = "output"


class PipelineError(ProcessingError):
    """Exception raised during pipeline execution."""

    pass


class PipelineExecutionContext:
    """Context for tracking pipeline execution state."""

    def __init__(self, pipeline_id: str):
        """Initialize pipeline execution context.

        Args:
            pipeline_id: Unique identifier for this pipeline execution
        """
        self.pipeline_id = pipeline_id
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.current_stage: Optional[PipelineStage] = None
        self.completed_stages: List[PipelineStage] = []
        self.failed_stages: List[PipelineStage] = []
        self.stage_results: Dict[str, Any] = {}
        self.stage_timings: Dict[str, Dict[str, Union[datetime, float]]] = {}
        self.errors: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

    def start_stage(self, stage: PipelineStage):
        """Mark the start of a pipeline stage."""
        self.current_stage = stage
        self.stage_timings[stage.value] = {"start": datetime.now()}

    def complete_stage(self, stage: PipelineStage, result: Any = None):
        """Mark the completion of a pipeline stage."""
        if stage.value in self.stage_timings:
            end_time = datetime.now()
            start_time = self.stage_timings[stage.value]["start"]
            self.stage_timings[stage.value]["end"] = end_time
            if isinstance(start_time, datetime):
                self.stage_timings[stage.value]["duration"] = (
                    end_time - start_time
                ).total_seconds()

        self.completed_stages.append(stage)
        if result is not None:
            self.stage_results[stage.value] = result
        self.current_stage = None

    def fail_stage(self, stage: PipelineStage, error: Exception):
        """Mark the failure of a pipeline stage."""
        if stage.value in self.stage_timings:
            end_time = datetime.now()
            start_time = self.stage_timings[stage.value]["start"]
            self.stage_timings[stage.value]["end"] = end_time
            if isinstance(start_time, datetime):
                self.stage_timings[stage.value]["duration"] = (
                    end_time - start_time
                ).total_seconds()

        self.failed_stages.append(stage)
        self.errors.append(
            {"stage": stage.value, "error": str(error), "timestamp": datetime.now()}
        )
        self.current_stage = None

    def finalize(self):
        """Finalize pipeline execution."""
        self.end_time = datetime.now()

    def get_summary(self) -> Dict[str, Any]:
        """Get pipeline execution summary."""
        total_duration = (
            (self.end_time or datetime.now()) - self.start_time
        ).total_seconds()

        return {
            "pipeline_id": self.pipeline_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_seconds": total_duration,
            "completed_stages": len(self.completed_stages),
            "failed_stages": len(self.failed_stages),
            "success_rate": (
                len(self.completed_stages)
                / (len(self.completed_stages) + len(self.failed_stages))
                if (self.completed_stages or self.failed_stages)
                else 0
            ),
            "stage_timings": self.stage_timings,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class ProcessingPipeline(BaseProcessor):
    """Orchestrates the complete AWS SSM data processing pipeline."""

    def __init__(self, context: ProcessingContext):
        """Initialize processing pipeline.

        Args:
            context: Processing context with SSM client and config
        """
        super().__init__(context)

        # Initialize all processors
        self.region_discoverer = RegionDiscoverer(context)
        self.service_discoverer = ServiceDiscoverer(context)
        self.service_mapper = ServiceMapper(context)
        self.regional_service_mapper = RegionalServiceMapper(context)
        self.data_transformer = DataTransformer(context)
        self.statistics_analyzer = StatisticsAnalyzer(context)
        self.validator = RegionalDataValidator(context)

        # Pipeline configuration
        self.pipeline_config = {
            "enable_validation": True,
            "enable_statistics": True,
            "enable_caching": True,
            "parallel_processing": True,
            "error_tolerance": 0.1,  # Allow 10% stage failures
            "timeout_seconds": 3600,  # 1 hour timeout
        }

        self.logger = get_logger("processing_pipeline")

    def validate_input(self, input_data: Any) -> bool:
        """Validate pipeline input parameters.

        Args:
            input_data: Pipeline configuration and parameters

        Returns:
            True if valid

        Raises:
            ProcessingValidationError: If validation fails
        """
        if input_data is not None and not isinstance(input_data, dict):
            raise ProcessingValidationError(
                "Pipeline input must be a dictionary of configuration parameters"
            )

        return True

    def process(self, input_data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Execute the complete processing pipeline.

        Args:
            input_data: Pipeline configuration parameters
            **kwargs: Additional processing parameters

        Returns:
            Dictionary with complete pipeline results

        Raises:
            ProcessingError: If pipeline execution fails
        """
        if not self.validate_input(input_data):
            raise ProcessingValidationError("Input validation failed")

        # Create pipeline execution context
        pipeline_id = f"pipeline_{int(time.time())}"
        execution_context = PipelineExecutionContext(pipeline_id)

        # Merge configuration
        config = {**self.pipeline_config, **(input_data or {}), **kwargs}

        self.logger.info(f"Starting processing pipeline {pipeline_id}")

        try:
            # Execute pipeline stages
            pipeline_results = self._execute_pipeline_stages(execution_context, config)

            execution_context.finalize()

            # Compile final results
            final_results = {
                "pipeline_execution": execution_context.get_summary(),
                "pipeline_results": pipeline_results,
                "success": len(execution_context.failed_stages) == 0,
                "stage_results": execution_context.stage_results,
            }

            self.logger.info(f"Pipeline {pipeline_id} completed successfully")
            return final_results

        except Exception as e:
            execution_context.finalize()
            self.logger.error(f"Pipeline {pipeline_id} failed: {e}", exc_info=True)
            raise PipelineError(f"Pipeline execution failed: {e}") from e

    def _execute_pipeline_stages(
        self, context: PipelineExecutionContext, config: Dict
    ) -> Dict[str, Any]:
        """Execute all pipeline stages in sequence."""
        results = {}

        try:
            # Stage 1: Discovery
            discovery_results = self._execute_discovery_stage(context, config)
            results["discovery"] = discovery_results

            # Stage 2: Service Mapping
            mapping_results = self._execute_mapping_stage(
                context, config, discovery_results
            )
            results["mapping"] = mapping_results

            # Stage 3: Data Transformation
            transformation_results = self._execute_transformation_stage(
                context, config, mapping_results
            )
            results["transformation"] = transformation_results

            # Stage 4: Statistical Analysis (if enabled)
            if config.get("enable_statistics", True):
                analysis_results = self._execute_analysis_stage(
                    context, config, mapping_results
                )
                results["analysis"] = analysis_results

            # Stage 5: Data Validation (if enabled)
            if config.get("enable_validation", True):
                validation_results = self._execute_validation_stage(
                    context, config, mapping_results
                )
                results["validation"] = validation_results

            # Stage 6: Output Generation
            output_results = self._execute_output_stage(context, config, results)
            results["output"] = output_results

            return results

        except Exception as e:
            self.logger.error(f"Pipeline stage execution failed: {e}")
            raise

    def _execute_discovery_stage(
        self, context: PipelineExecutionContext, config: Dict
    ) -> Dict[str, Any]:
        """Execute the discovery stage."""
        context.start_stage(PipelineStage.DISCOVERY)

        try:
            self.logger.info("Executing discovery stage...")

            # Discover regions and services in parallel if enabled
            if config.get("parallel_processing", True):
                regions_task = self._discover_regions_async(config)
                services_task = self._discover_services_async(config)

                # Wait for both to complete (simplified async simulation)
                discovered_regions = self.region_discoverer.process_with_cache(
                    config.get("region_discovery_params")
                )
                discovered_services = self.service_discoverer.process_with_cache(
                    config.get("service_discovery_params")
                )
            else:
                discovered_regions = self.region_discoverer.process_with_cache(
                    config.get("region_discovery_params")
                )
                discovered_services = self.service_discoverer.process_with_cache(
                    config.get("service_discovery_params")
                )

            discovery_results = {
                "regions": discovered_regions,
                "services": discovered_services,
                "region_count": len(discovered_regions),
                "service_count": len(discovered_services),
                "discovery_metadata": {
                    "regions_metadata": getattr(
                        self.region_discoverer.context, "metadata", {}
                    ),
                    "services_metadata": getattr(
                        self.service_discoverer.context, "metadata", {}
                    ),
                },
            }

            context.complete_stage(PipelineStage.DISCOVERY, discovery_results)
            self.logger.info(
                f"Discovery completed: {len(discovered_regions)} regions, {len(discovered_services)} services"
            )

            return discovery_results

        except Exception as e:
            context.fail_stage(PipelineStage.DISCOVERY, e)
            raise PipelineError(f"Discovery stage failed: {e}") from e

    def _execute_mapping_stage(
        self, context: PipelineExecutionContext, config: Dict, discovery_results: Dict
    ) -> Dict[str, Any]:
        """Execute the service mapping stage."""
        context.start_stage(PipelineStage.MAPPING)

        try:
            self.logger.info("Executing service mapping stage...")

            services = discovery_results["services"]

            # Use regional service mapper for enhanced mapping
            region_services_map = self.regional_service_mapper.process_with_cache(
                services
            )

            # Convert to flat service-region mappings
            service_region_mappings = []
            for region_code, region_services in region_services_map.items():
                for service_code in region_services:
                    # Get service name (fallback to code if not available)
                    service_name = (
                        service_code  # Could be enhanced with service name lookup
                    )

                    service_region_mappings.append(
                        {
                            "Region Code": region_code,
                            "Service Code": service_code,
                            "Service Name": service_name,
                        }
                    )

            # Get additional mapping statistics
            coverage_stats = self.service_mapper.get_coverage_stats(services)
            regional_analysis = (
                self.regional_service_mapper.analyze_regional_distribution(services)
            )

            mapping_results = {
                "service_region_mappings": service_region_mappings,
                "region_services_map": region_services_map,
                "total_mappings": len(service_region_mappings),
                "coverage_statistics": coverage_stats,
                "regional_analysis": regional_analysis,
                "mapping_metadata": {
                    "processing_stats": self.service_mapper.get_processing_stats()
                },
            }

            context.complete_stage(PipelineStage.MAPPING, mapping_results)
            self.logger.info(
                f"Mapping completed: {len(service_region_mappings)} service-region combinations"
            )

            return mapping_results

        except Exception as e:
            context.fail_stage(PipelineStage.MAPPING, e)
            raise PipelineError(f"Mapping stage failed: {e}") from e

    def _execute_transformation_stage(
        self, context: PipelineExecutionContext, config: Dict, mapping_results: Dict
    ) -> Dict[str, Any]:
        """Execute the data transformation stage."""
        context.start_stage(PipelineStage.TRANSFORMATION)

        try:
            self.logger.info("Executing data transformation stage...")

            service_region_mappings = mapping_results["service_region_mappings"]

            # Generate multiple data transformations
            transformations = {}

            # Service matrix
            transformations["service_matrix"] = self.data_transformer.process(
                service_region_mappings, transformation_type="service_matrix"
            )

            # Region summary
            transformations["region_summary"] = self.data_transformer.process(
                service_region_mappings, transformation_type="region_summary"
            )

            # Service summary
            transformations["service_summary"] = self.data_transformer.process(
                service_region_mappings,
                transformation_type="service_summary",
                all_services=mapping_results.get("region_services_map", {}).get(
                    "services", []
                ),
            )

            # Statistics
            transformations["statistics"] = self.data_transformer.process(
                service_region_mappings, transformation_type="statistics"
            )

            # Coverage analysis
            transformations["coverage_analysis"] = self.data_transformer.process(
                service_region_mappings, transformation_type="coverage_analysis"
            )

            transformation_results = {
                "transformations": transformations,
                "transformation_count": len(transformations),
                "transformation_metadata": {
                    "processing_stats": self.data_transformer.get_processing_stats()
                },
            }

            context.complete_stage(PipelineStage.TRANSFORMATION, transformation_results)
            self.logger.info(
                f"Transformation completed: {len(transformations)} data transformations generated"
            )

            return transformation_results

        except Exception as e:
            context.fail_stage(PipelineStage.TRANSFORMATION, e)
            raise PipelineError(f"Transformation stage failed: {e}") from e

    def _execute_analysis_stage(
        self, context: PipelineExecutionContext, config: Dict, mapping_results: Dict
    ) -> Dict[str, Any]:
        """Execute the statistical analysis stage."""
        context.start_stage(PipelineStage.ANALYSIS)

        try:
            self.logger.info("Executing statistical analysis stage...")

            service_region_mappings = mapping_results["service_region_mappings"]

            # Perform multiple types of statistical analysis
            analyses = {}

            # Comprehensive analysis
            analyses["comprehensive"] = self.statistics_analyzer.process(
                service_region_mappings, analysis_type="comprehensive"
            )

            # Regional distribution analysis
            analyses["regional_distribution"] = self.statistics_analyzer.process(
                service_region_mappings, analysis_type="regional_distribution"
            )

            # Service coverage analysis
            analyses["service_coverage"] = self.statistics_analyzer.process(
                service_region_mappings,
                analysis_type="service_coverage",
                all_services=list(
                    set(item["Service Code"] for item in service_region_mappings)
                ),
            )

            # Geographic distribution analysis
            analyses["geographic_distribution"] = self.statistics_analyzer.process(
                service_region_mappings, analysis_type="geographic_distribution"
            )

            # Availability zone analysis
            analyses["availability_zones"] = self.statistics_analyzer.process(
                service_region_mappings, analysis_type="availability_zones"
            )

            analysis_results = {
                "analyses": analyses,
                "analysis_count": len(analyses),
                "analysis_metadata": {
                    "processing_stats": self.statistics_analyzer.get_processing_stats()
                },
            }

            context.complete_stage(PipelineStage.ANALYSIS, analysis_results)
            self.logger.info(
                f"Analysis completed: {len(analyses)} statistical analyses performed"
            )

            return analysis_results

        except Exception as e:
            context.fail_stage(PipelineStage.ANALYSIS, e)
            raise PipelineError(f"Analysis stage failed: {e}") from e

    def _execute_validation_stage(
        self, context: PipelineExecutionContext, config: Dict, mapping_results: Dict
    ) -> Dict[str, Any]:
        """Execute the data validation stage."""
        context.start_stage(PipelineStage.VALIDATION)

        try:
            self.logger.info("Executing data validation stage...")

            service_region_mappings = mapping_results["service_region_mappings"]

            # Perform comprehensive validation
            validation_result = self.validator.process(
                service_region_mappings, validation_type="comprehensive"
            )

            validation_results = {
                "validation_result": validation_result,
                "overall_quality_score": validation_result.get("summary", {}).get(
                    "overall_validation_score", 0
                ),
                "data_quality_grade": validation_result.get("summary", {}).get(
                    "data_quality_grade", "F"
                ),
                "validation_metadata": {
                    "processing_stats": self.validator.get_processing_stats()
                },
            }

            context.complete_stage(PipelineStage.VALIDATION, validation_results)

            quality_score = validation_results["overall_quality_score"]
            quality_grade = validation_results["data_quality_grade"]
            self.logger.info(
                f"Validation completed: Overall quality score {quality_score} (Grade {quality_grade})"
            )

            return validation_results

        except Exception as e:
            context.fail_stage(PipelineStage.VALIDATION, e)
            raise PipelineError(f"Validation stage failed: {e}") from e

    def _execute_output_stage(
        self, context: PipelineExecutionContext, config: Dict, all_results: Dict
    ) -> Dict[str, Any]:
        """Execute the output generation stage."""
        context.start_stage(PipelineStage.OUTPUT)

        try:
            self.logger.info("Executing output generation stage...")

            # Compile comprehensive output package
            output_package = {
                "pipeline_summary": {
                    "execution_id": context.pipeline_id,
                    "execution_time": context.start_time.isoformat(),
                    "total_processing_time": (
                        datetime.now() - context.start_time
                    ).total_seconds(),
                    "stages_completed": len(context.completed_stages),
                    "stages_failed": len(context.failed_stages),
                },
                "discovery_results": all_results.get("discovery", {}),
                "mapping_results": all_results.get("mapping", {}),
                "transformation_results": all_results.get("transformation", {}),
                "analysis_results": all_results.get("analysis", {}),
                "validation_results": all_results.get("validation", {}),
                "data_summary": self._generate_data_summary(all_results),
                "quality_metrics": self._generate_quality_metrics(all_results),
                "recommendations": self._generate_recommendations(all_results),
            }

            context.complete_stage(PipelineStage.OUTPUT, output_package)
            self.logger.info("Output generation completed successfully")

            return output_package

        except Exception as e:
            context.fail_stage(PipelineStage.OUTPUT, e)
            raise PipelineError(f"Output stage failed: {e}") from e

    def _discover_regions_async(self, config: Dict) -> List[str]:
        """Discover regions (async simulation)."""
        result = self.region_discoverer.process_with_cache(
            config.get("region_discovery_params")
        )
        return result if isinstance(result, list) else []

    def _discover_services_async(self, config: Dict) -> List[str]:
        """Discover services (async simulation)."""
        result = self.service_discoverer.process_with_cache(
            config.get("service_discovery_params")
        )
        return result if isinstance(result, list) else []

    def _generate_data_summary(self, results: Dict) -> Dict[str, Any]:
        """Generate high-level data summary."""
        discovery = results.get("discovery", {})
        mapping = results.get("mapping", {})

        return {
            "total_regions_discovered": discovery.get("region_count", 0),
            "total_services_discovered": discovery.get("service_count", 0),
            "total_service_region_mappings": mapping.get("total_mappings", 0),
            "data_completeness": (
                "High"
                if mapping.get("total_mappings", 0) > 1000
                else "Medium" if mapping.get("total_mappings", 0) > 100 else "Low"
            ),
            "processing_efficiency": self._calculate_processing_efficiency(results),
        }

    def _generate_quality_metrics(self, results: Dict) -> Dict[str, Any]:
        """Generate data quality metrics."""
        validation = results.get("validation", {})
        analysis = results.get("analysis", {})

        return {
            "overall_data_quality_score": validation.get("overall_quality_score", 0),
            "data_quality_grade": validation.get("data_quality_grade", "N/A"),
            "data_integrity_score": validation.get("validation_result", {})
            .get("data_integrity", {})
            .get("validation_score", 0),
            "coverage_score": validation.get("validation_result", {})
            .get("coverage", {})
            .get("validation_score", 0),
            "consistency_score": validation.get("validation_result", {})
            .get("consistency", {})
            .get("validation_score", 0),
            "anomaly_score": validation.get("validation_result", {})
            .get("anomaly_detection", {})
            .get("validation_score", 0),
        }

    def _generate_recommendations(self, results: Dict) -> List[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []

        # Check data quality
        validation = results.get("validation", {})
        quality_score = validation.get("overall_quality_score", 0)

        if quality_score < 70:
            recommendations.append(
                "Consider investigating data quality issues - overall score below 70%"
            )

        # Check coverage
        mapping = results.get("mapping", {})
        coverage_stats = mapping.get("coverage_statistics", {})

        if isinstance(coverage_stats, dict) and "overview" in coverage_stats:
            avg_regions_per_service = coverage_stats["overview"].get(
                "avg_regions_per_service", 0
            )
            if avg_regions_per_service < 10:
                recommendations.append(
                    "Low average regional availability per service - consider expanding service deployment"
                )

        # Check processing efficiency
        if self._calculate_processing_efficiency(results) < 0.8:
            recommendations.append(
                "Consider optimizing processing performance - efficiency below 80%"
            )

        if not recommendations:
            recommendations.append(
                "Data processing completed successfully with good quality metrics"
            )

        return recommendations

    def _calculate_processing_efficiency(self, results: Dict) -> float:
        """Calculate overall processing efficiency score."""
        # Simple efficiency calculation based on cache hit rates and processing speeds
        mapping_meta = results.get("mapping", {}).get("mapping_metadata", {})
        transform_meta = results.get("transformation", {}).get(
            "transformation_metadata", {}
        )
        analysis_meta = results.get("analysis", {}).get("analysis_metadata", {})

        efficiency_scores = []

        for metadata in [mapping_meta, transform_meta, analysis_meta]:
            if "processing_stats" in metadata:
                stats = metadata["processing_stats"]
                cache_hit_rate = stats.get("cache_hit_rate", 0)
                success_rate = stats.get("success_rate", 0)
                efficiency_scores.append((cache_hit_rate + success_rate) / 2)

        return (
            sum(efficiency_scores) / len(efficiency_scores)
            if efficiency_scores
            else 0.5
        )


class PipelineOrchestrator:
    """High-level orchestrator for managing multiple pipeline executions."""

    def __init__(self, context: ProcessingContext):
        """Initialize pipeline orchestrator.

        Args:
            context: Processing context for pipeline operations
        """
        self.context = context
        self.logger = get_logger("pipeline_orchestrator")
        self.active_pipelines: Dict[str, ProcessingPipeline] = {}
        self.completed_pipelines: Dict[str, Dict[str, Any]] = {}
        self.failed_pipelines: Dict[str, Dict[str, Any]] = {}

    def create_pipeline(
        self, pipeline_config: Optional[Dict] = None
    ) -> ProcessingPipeline:
        """Create a new processing pipeline.

        Args:
            pipeline_config: Configuration for the pipeline

        Returns:
            Configured processing pipeline
        """
        pipeline = ProcessingPipeline(self.context)

        if pipeline_config:
            pipeline.pipeline_config.update(pipeline_config)

        return pipeline

    def execute_pipeline(
        self, pipeline_config: Optional[Dict] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a complete processing pipeline.

        Args:
            pipeline_config: Pipeline configuration parameters
            **kwargs: Additional execution parameters

        Returns:
            Complete pipeline results
        """
        pipeline = self.create_pipeline(pipeline_config)

        try:
            self.logger.info("Starting pipeline orchestration")

            # Execute pipeline
            results = pipeline.process(pipeline_config, **kwargs)

            # Track completion
            pipeline_id = results["pipeline_execution"]["pipeline_id"]
            self.completed_pipelines[pipeline_id] = results

            self.logger.info(
                f"Pipeline {pipeline_id} orchestration completed successfully"
            )
            return results

        except Exception as e:
            self.logger.error(f"Pipeline orchestration failed: {e}", exc_info=True)
            raise

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get status of all pipeline executions.

        Returns:
            Summary of pipeline execution status
        """
        return {
            "active_pipelines": len(self.active_pipelines),
            "completed_pipelines": len(self.completed_pipelines),
            "failed_pipelines": len(self.failed_pipelines),
            "total_executions": len(self.active_pipelines)
            + len(self.completed_pipelines)
            + len(self.failed_pipelines),
        }

    def cleanup_old_pipelines(self, max_age_hours: int = 24):
        """Clean up old pipeline execution records.

        Args:
            max_age_hours: Maximum age in hours for keeping pipeline records
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        # Clean up completed pipelines
        to_remove = []
        for pipeline_id, results in self.completed_pipelines.items():
            execution_time = results["pipeline_execution"]["start_time"]
            if datetime.fromisoformat(execution_time).timestamp() < cutoff_time:
                to_remove.append(pipeline_id)

        for pipeline_id in to_remove:
            del self.completed_pipelines[pipeline_id]

        self.logger.info(f"Cleaned up {len(to_remove)} old pipeline records")
