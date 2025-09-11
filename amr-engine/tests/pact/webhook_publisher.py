"""
Webhook publisher for Pact verification results.

This module provides comprehensive webhook functionality for publishing
provider verification results to Pact brokers and other monitoring systems.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urljoin

import httpx
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .pact_config import get_pact_broker_config, PactBrokerConfig

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Individual verification result for a contract interaction."""
    
    interaction_id: str
    description: str
    status: str  # "passed", "failed", "skipped"
    duration_ms: float
    error_message: Optional[str] = None
    request_details: Optional[Dict[str, Any]] = None
    response_details: Optional[Dict[str, Any]] = None
    provider_state: Optional[str] = None
    timestamp: Optional[str] = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ProviderVerificationReport:
    """Complete provider verification report."""
    
    provider_name: str
    consumer_name: str
    contract_version: str
    verification_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    overall_status: str = "unknown"  # "passed", "failed", "partial"
    total_interactions: int = 0
    passed_interactions: int = 0
    failed_interactions: int = 0
    skipped_interactions: int = 0
    duration_ms: float = 0.0
    environment: str = "test"
    provider_version: Optional[str] = None
    build_url: Optional[str] = None
    git_commit: Optional[str] = None
    verification_results: List[VerificationResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_result(self, result: VerificationResult):
        """Add a verification result to the report."""
        self.verification_results.append(result)
        self.total_interactions += 1
        
        if result.status == "passed":
            self.passed_interactions += 1
        elif result.status == "failed":
            self.failed_interactions += 1
        elif result.status == "skipped":
            self.skipped_interactions += 1
        
        # Update overall status
        if self.failed_interactions > 0:
            self.overall_status = "failed"
        elif self.passed_interactions > 0 and self.failed_interactions == 0:
            self.overall_status = "passed" if self.skipped_interactions == 0 else "partial"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class WebhookPublisher:
    """
    Webhook publisher for Pact verification results.
    
    Handles publishing verification results to multiple endpoints including
    Pact brokers, monitoring systems, and custom webhooks.
    """
    
    def __init__(self, config: Optional[PactBrokerConfig] = None):
        self.config = config or self._get_default_config()
        self.session = self._create_http_session()
        self.async_client = None
        self.webhook_handlers: Dict[str, Callable] = {}
        self.retry_attempts = 3
        self.retry_delay = 1.0  # seconds
        
        # Register default webhook handlers
        self._register_default_handlers()
    
    def _get_default_config(self) -> PactBrokerConfig:
        """Get default configuration from environment."""
        try:
            return get_pact_broker_config()
        except ValueError:
            logger.warning("No Pact broker configuration found, using defaults")
            return PactBrokerConfig(broker_url="http://localhost:9292")
    
    def _create_http_session(self) -> requests.Session:
        """Create HTTP session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "PATCH"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default timeout
        session.timeout = 30
        
        return session
    
    def _register_default_handlers(self):
        """Register default webhook handlers."""
        self.webhook_handlers.update({
            "pact-broker": self._handle_pact_broker_webhook,
            "console": self._handle_console_webhook,
            "file": self._handle_file_webhook,
            "http": self._handle_http_webhook
        })
    
    async def publish_verification_results(
        self, 
        report: ProviderVerificationReport,
        webhooks: Optional[List[str]] = None,
        custom_handlers: Optional[Dict[str, Callable]] = None
    ) -> Dict[str, Any]:
        """
        Publish verification results to configured webhooks.
        
        Args:
            report: Provider verification report
            webhooks: List of webhook URLs/types to publish to
            custom_handlers: Custom webhook handlers
            
        Returns:
            Dict with publication results for each webhook
        """
        if custom_handlers:
            self.webhook_handlers.update(custom_handlers)
        
        # Default webhooks if none specified
        if not webhooks:
            webhooks = ["pact-broker", "console"]
        
        publication_results = {}
        
        # Initialize async client
        if not self.async_client:
            self.async_client = httpx.AsyncClient(timeout=30)
        
        try:
            # Publish to each webhook
            tasks = []
            for webhook in webhooks:
                task = self._publish_to_webhook(webhook, report)
                tasks.append((webhook, task))
            
            # Wait for all publications to complete
            for webhook, task in tasks:
                try:
                    result = await task
                    publication_results[webhook] = result
                except Exception as e:
                    logger.error(f"Failed to publish to webhook '{webhook}': {e}")
                    publication_results[webhook] = {
                        "status": "failed",
                        "error": str(e)
                    }
        
        finally:
            # Close async client
            if self.async_client:
                await self.async_client.aclose()
                self.async_client = None
        
        return publication_results
    
    async def _publish_to_webhook(self, webhook: str, report: ProviderVerificationReport) -> Dict[str, Any]:
        """
        Publish to a specific webhook.
        
        Args:
            webhook: Webhook identifier (URL or handler type)
            report: Verification report to publish
            
        Returns:
            Publication result
        """
        start_time = time.time()
        
        try:
            # Determine handler type
            if webhook.startswith(("http://", "https://")):
                handler = self.webhook_handlers.get("http")
                handler_args = {"url": webhook}
            else:
                handler = self.webhook_handlers.get(webhook)
                handler_args = {}
            
            if not handler:
                raise ValueError(f"No handler found for webhook: {webhook}")
            
            # Execute handler
            result = await handler(report, **handler_args)
            
            duration = (time.time() - start_time) * 1000
            
            return {
                "status": "success",
                "webhook": webhook,
                "duration_ms": duration,
                **result
            }
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return {
                "status": "failed",
                "webhook": webhook,
                "duration_ms": duration,
                "error": str(e)
            }
    
    async def _handle_pact_broker_webhook(self, report: ProviderVerificationReport) -> Dict[str, Any]:
        """Handle publishing to Pact broker."""
        if not self.config.broker_url:
            raise ValueError("Pact broker URL not configured")
        
        # Prepare Pact broker payload
        payload = {
            "providerApplicationVersion": report.provider_version or self.config.provider_version,
            "success": report.overall_status == "passed",
            "providerName": report.provider_name,
            "consumerName": report.consumer_name,
            "consumerVersion": report.contract_version,
            "verificationDate": report.verification_timestamp,
            "testResults": [
                {
                    "interactionId": result.interaction_id,
                    "description": result.description,
                    "success": result.status == "passed",
                    "status": result.status,
                    "duration": result.duration_ms,
                    "exception": {
                        "message": result.error_message
                    } if result.error_message else None
                }
                for result in report.verification_results
            ]
        }
        
        # Add build information if available
        if report.build_url or self.config.build_url:
            payload["buildUrl"] = report.build_url or self.config.build_url
        
        if report.git_commit:
            payload["tags"] = [report.git_commit]
        
        # Construct webhook URL
        webhook_url = urljoin(
            self.config.broker_url.rstrip('/') + '/',
            f"pacts/provider/{report.provider_name}/consumer/{report.consumer_name}/verification-results"
        )
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        elif self.config.username and self.config.password:
            auth = (self.config.username, self.config.password)
        else:
            auth = None
        
        # Make request
        if not self.async_client:
            self.async_client = httpx.AsyncClient(timeout=30)
        
        try:
            if self.config.token:
                response = await self.async_client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )
            else:
                response = await self.async_client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    auth=auth if 'auth' in locals() else None
                )
            
            response.raise_for_status()
            
            return {
                "broker_url": webhook_url,
                "response_status": response.status_code,
                "response_data": response.json() if response.content else None
            }
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error publishing to Pact broker: {e}")
            raise
        except Exception as e:
            logger.error(f"Error publishing to Pact broker: {e}")
            raise
    
    async def _handle_console_webhook(self, report: ProviderVerificationReport) -> Dict[str, Any]:
        """Handle console output publishing."""
        # Format report for console output
        console_output = self._format_console_output(report)
        
        # Print to console
        print(console_output)
        logger.info("Verification results printed to console")
        
        return {
            "output_lines": len(console_output.split('\n')),
            "output_length": len(console_output)
        }
    
    async def _handle_file_webhook(self, report: ProviderVerificationReport, filename: Optional[str] = None) -> Dict[str, Any]:
        """Handle file output publishing."""
        import os
        from pathlib import Path
        
        # Default filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pact_verification_results_{timestamp}.json"
        
        # Ensure output directory exists
        output_dir = Path("test-results")
        output_dir.mkdir(exist_ok=True)
        
        output_path = output_dir / filename
        
        # Write report to file
        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        
        logger.info(f"Verification results written to: {output_path}")
        
        return {
            "output_file": str(output_path),
            "file_size": os.path.getsize(output_path)
        }
    
    async def _handle_http_webhook(self, report: ProviderVerificationReport, url: str) -> Dict[str, Any]:
        """Handle generic HTTP webhook publishing."""
        if not self.async_client:
            self.async_client = httpx.AsyncClient(timeout=30)
        
        # Prepare payload
        payload = report.to_dict()
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AMR-Pact-Webhook-Publisher/1.0"
        }
        
        try:
            response = await self.async_client.post(
                url,
                json=payload,
                headers=headers
            )
            
            response.raise_for_status()
            
            return {
                "webhook_url": url,
                "response_status": response.status_code,
                "response_headers": dict(response.headers),
                "response_data": response.json() if response.content else None
            }
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error posting to webhook {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error posting to webhook {url}: {e}")
            raise
    
    def _format_console_output(self, report: ProviderVerificationReport) -> str:
        """Format verification report for console output."""
        lines = []
        lines.append("=" * 80)
        lines.append("PACT PROVIDER VERIFICATION RESULTS")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary
        lines.append(f"Provider: {report.provider_name}")
        lines.append(f"Consumer: {report.consumer_name}")
        lines.append(f"Contract Version: {report.contract_version}")
        lines.append(f"Provider Version: {report.provider_version}")
        lines.append(f"Verification Time: {report.verification_timestamp}")
        lines.append(f"Environment: {report.environment}")
        lines.append("")
        
        # Overall status
        status_symbol = "✅" if report.overall_status == "passed" else "❌" if report.overall_status == "failed" else "⚠️"
        lines.append(f"Overall Status: {status_symbol} {report.overall_status.upper()}")
        lines.append("")
        
        # Statistics
        lines.append("STATISTICS")
        lines.append("-" * 40)
        lines.append(f"Total Interactions:  {report.total_interactions}")
        lines.append(f"Passed:             {report.passed_interactions}")
        lines.append(f"Failed:             {report.failed_interactions}")
        lines.append(f"Skipped:            {report.skipped_interactions}")
        lines.append(f"Duration:           {report.duration_ms:.1f}ms")
        lines.append("")
        
        # Detailed results
        if report.verification_results:
            lines.append("DETAILED RESULTS")
            lines.append("-" * 40)
            
            for result in report.verification_results:
                symbol = "✅" if result.status == "passed" else "❌" if result.status == "failed" else "⚠️"
                lines.append(f"{symbol} {result.description}")
                
                if result.provider_state:
                    lines.append(f"   Provider State: {result.provider_state}")
                
                lines.append(f"   Status: {result.status} ({result.duration_ms:.1f}ms)")
                
                if result.error_message:
                    lines.append(f"   Error: {result.error_message}")
                
                lines.append("")
        
        # Build information
        if report.build_url or report.git_commit:
            lines.append("BUILD INFORMATION")
            lines.append("-" * 40)
            if report.build_url:
                lines.append(f"Build URL: {report.build_url}")
            if report.git_commit:
                lines.append(f"Git Commit: {report.git_commit}")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def register_custom_handler(self, name: str, handler: Callable):
        """
        Register a custom webhook handler.
        
        Args:
            name: Handler name/identifier
            handler: Async callable that takes (report, **kwargs) and returns Dict[str, Any]
        """
        self.webhook_handlers[name] = handler
        logger.info(f"Custom webhook handler registered: {name}")
    
    def publish_sync(self, report: ProviderVerificationReport, webhooks: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Synchronous wrapper for publishing verification results.
        
        Args:
            report: Provider verification report
            webhooks: List of webhook URLs/types to publish to
            
        Returns:
            Publication results
        """
        async def _publish():
            return await self.publish_verification_results(report, webhooks)
        
        # Run in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(_publish())
    
    def close(self):
        """Clean up resources."""
        if self.session:
            self.session.close()
        
        if self.async_client:
            # Note: async_client.aclose() should be called in async context
            # This is for cleanup when publisher is no longer needed
            pass


class VerificationResultCollector:
    """
    Collector for gathering verification results during test execution.
    
    Provides a convenient interface for accumulating results and building
    the final verification report.
    """
    
    def __init__(self, provider_name: str, consumer_name: str, contract_version: str):
        self.provider_name = provider_name
        self.consumer_name = consumer_name
        self.contract_version = contract_version
        self.results: List[VerificationResult] = []
        self.start_time = time.time()
        self.metadata: Dict[str, Any] = {}
    
    def add_result(
        self, 
        interaction_id: str,
        description: str,
        status: str,
        duration_ms: float,
        error_message: Optional[str] = None,
        request_details: Optional[Dict[str, Any]] = None,
        response_details: Optional[Dict[str, Any]] = None,
        provider_state: Optional[str] = None
    ):
        """Add a verification result."""
        result = VerificationResult(
            interaction_id=interaction_id,
            description=description,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            request_details=request_details,
            response_details=response_details,
            provider_state=provider_state
        )
        
        self.results.append(result)
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to the report."""
        self.metadata[key] = value
    
    def build_report(
        self,
        provider_version: Optional[str] = None,
        build_url: Optional[str] = None,
        git_commit: Optional[str] = None,
        environment: str = "test"
    ) -> ProviderVerificationReport:
        """
        Build the final verification report.
        
        Args:
            provider_version: Provider application version
            build_url: CI/CD build URL
            git_commit: Git commit hash
            environment: Test environment name
            
        Returns:
            Complete provider verification report
        """
        total_duration = (time.time() - self.start_time) * 1000
        
        report = ProviderVerificationReport(
            provider_name=self.provider_name,
            consumer_name=self.consumer_name,
            contract_version=self.contract_version,
            provider_version=provider_version,
            build_url=build_url,
            git_commit=git_commit,
            environment=environment,
            duration_ms=total_duration,
            metadata=self.metadata.copy()
        )
        
        # Add all results
        for result in self.results:
            report.add_result(result)
        
        return report


# Convenience functions for common use cases

def create_publisher(config: Optional[PactBrokerConfig] = None) -> WebhookPublisher:
    """Create a webhook publisher with optional configuration."""
    return WebhookPublisher(config)


def create_result_collector(provider_name: str, consumer_name: str, contract_version: str) -> VerificationResultCollector:
    """Create a verification result collector."""
    return VerificationResultCollector(provider_name, consumer_name, contract_version)


async def publish_results(
    report: ProviderVerificationReport,
    webhooks: Optional[List[str]] = None,
    config: Optional[PactBrokerConfig] = None
) -> Dict[str, Any]:
    """
    Quick function to publish verification results.
    
    Args:
        report: Provider verification report
        webhooks: List of webhook URLs/types
        config: Pact broker configuration
        
    Returns:
        Publication results
    """
    publisher = WebhookPublisher(config)
    try:
        return await publisher.publish_verification_results(report, webhooks)
    finally:
        publisher.close()


def publish_results_sync(
    report: ProviderVerificationReport,
    webhooks: Optional[List[str]] = None,
    config: Optional[PactBrokerConfig] = None
) -> Dict[str, Any]:
    """
    Synchronous function to publish verification results.
    
    Args:
        report: Provider verification report  
        webhooks: List of webhook URLs/types
        config: Pact broker configuration
        
    Returns:
        Publication results
    """
    publisher = WebhookPublisher(config)
    try:
        return publisher.publish_sync(report, webhooks)
    finally:
        publisher.close()