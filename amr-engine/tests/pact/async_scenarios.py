"""
Async classification scenario handlers for Pact provider verification.

This module provides comprehensive async scenario handling for testing
asynchronous classification endpoints, including task management,
result polling, and webhook notifications.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Async task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class AsyncTaskResult:
    """Result container for async classification tasks."""
    
    task_id: str
    status: TaskStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Classification input
    input_data: Optional[Dict[str, Any]] = None
    input_format: str = "unknown"  # "fhir", "hl7v2", "direct"
    
    # Classification result
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Processing metadata
    processing_duration_ms: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Webhook configuration
    callback_url: Optional[str] = None
    callback_headers: Optional[Dict[str, str]] = None
    
    def is_expired(self) -> bool:
        """Check if task has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "input_format": self.input_format,
            "processing_duration_ms": self.processing_duration_ms,
            "retry_count": self.retry_count,
            "result": self.result,
            "error": self.error
        }


class AsyncTaskManager:
    """
    Manager for async classification tasks.
    
    Handles task creation, execution, result storage, and cleanup
    for async classification scenarios in provider verification tests.
    """
    
    def __init__(self, max_concurrent_tasks: int = 10, default_ttl_hours: int = 24):
        self.tasks: Dict[str, AsyncTaskResult] = {}
        self.max_concurrent_tasks = max_concurrent_tasks
        self.default_ttl_hours = default_ttl_hours
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_tasks)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.webhook_client = httpx.AsyncClient(timeout=30)
        
        # Classification handlers for different input formats
        self.classification_handlers = {
            "fhir": self._handle_fhir_classification,
            "hl7v2": self._handle_hl7v2_classification,
            "direct": self._handle_direct_classification
        }
        
        # Start cleanup task
        asyncio.create_task(self._periodic_cleanup())
    
    async def create_async_task(
        self,
        input_data: Dict[str, Any],
        input_format: str = "direct",
        callback_url: Optional[str] = None,
        callback_headers: Optional[Dict[str, str]] = None,
        ttl_hours: Optional[int] = None,
        priority: int = 0
    ) -> str:
        """
        Create a new async classification task.
        
        Args:
            input_data: Classification input data
            input_format: Input format ("fhir", "hl7v2", "direct")
            callback_url: Optional webhook URL for completion notification
            callback_headers: Optional headers for webhook calls
            ttl_hours: Task time-to-live in hours
            priority: Task priority (higher = more important)
            
        Returns:
            Task ID for tracking the async operation
        """
        # Generate unique task ID
        task_id = f"async-{uuid.uuid4().hex[:12]}"
        
        # Calculate expiration time
        ttl = ttl_hours or self.default_ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)
        
        # Create task result container
        task_result = AsyncTaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            input_data=input_data,
            input_format=input_format,
            callback_url=callback_url,
            callback_headers=callback_headers or {},
            expires_at=expires_at
        )
        
        # Store task
        self.tasks[task_id] = task_result
        
        # Start async processing if capacity allows
        if len(self.active_tasks) < self.max_concurrent_tasks:
            await self._start_task_processing(task_id)
        
        logger.info(f"Created async task {task_id} with format {input_format}")
        return task_id
    
    async def _start_task_processing(self, task_id: str):
        """Start async processing for a specific task."""
        if task_id not in self.tasks:
            return
        
        task_result = self.tasks[task_id]
        
        # Update status
        task_result.status = TaskStatus.PROCESSING
        task_result.started_at = datetime.now(timezone.utc)
        
        # Create async task
        async_task = asyncio.create_task(self._process_classification_task(task_id))
        self.active_tasks[task_id] = async_task
        
        logger.info(f"Started processing task {task_id}")
    
    async def _process_classification_task(self, task_id: str):
        """Process a classification task asynchronously."""
        start_time = time.time()
        task_result = self.tasks[task_id]
        
        try:
            # Get appropriate handler
            handler = self.classification_handlers.get(task_result.input_format)
            if not handler:
                raise ValueError(f"Unknown input format: {task_result.input_format}")
            
            # Process classification
            classification_result = await handler(task_result.input_data)
            
            # Update task result
            task_result.result = classification_result
            task_result.status = TaskStatus.COMPLETED
            task_result.completed_at = datetime.now(timezone.utc)
            task_result.processing_duration_ms = (time.time() - start_time) * 1000
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            # Handle processing error
            task_result.error = str(e)
            task_result.status = TaskStatus.FAILED
            task_result.completed_at = datetime.now(timezone.utc)
            task_result.processing_duration_ms = (time.time() - start_time) * 1000
            task_result.retry_count += 1
            
            logger.error(f"Task {task_id} failed: {e}")
            
            # Retry if possible
            if task_result.can_retry():
                logger.info(f"Retrying task {task_id} (attempt {task_result.retry_count})")
                task_result.status = TaskStatus.PENDING
                # Schedule retry after delay
                await asyncio.sleep(2 ** task_result.retry_count)  # Exponential backoff
                await self._start_task_processing(task_id)
                return
        
        finally:
            # Remove from active tasks
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
        
        # Send webhook notification if configured
        if task_result.callback_url:
            await self._send_webhook_notification(task_id)
        
        # Start next pending task if available
        await self._start_next_pending_task()
    
    async def _handle_fhir_classification(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle FHIR Bundle classification."""
        # Simulate FHIR Bundle processing
        await asyncio.sleep(0.5)  # Simulate processing delay
        
        # Extract classification parameters from FHIR Bundle
        bundle = input_data
        organism = None
        antibiotic = None
        method = "MIC"
        value = None
        specimen_id = "FHIR-ASYNC-001"
        
        # Parse FHIR Bundle entries
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")
            
            if resource_type == "Specimen":
                specimen_id = resource.get("id", specimen_id)
            
            elif resource_type == "Observation":
                # Extract organism from components
                for component in resource.get("component", []):
                    code = component.get("code", {})
                    if "organism" in code.get("text", "").lower():
                        value_concept = component.get("valueCodeableConcept", {})
                        for coding in value_concept.get("coding", []):
                            organism = coding.get("display", organism)
                
                # Extract antibiotic and value from main observation
                code = resource.get("code", {})
                for coding in code.get("coding", []):
                    display = coding.get("display", "")
                    if "Susceptibility" in display:
                        # Extract antibiotic name
                        antibiotic = display.split()[0]
                
                value_quantity = resource.get("valueQuantity", {})
                if value_quantity:
                    value = value_quantity.get("value")
        
        # Perform mock classification
        if not organism or not antibiotic:
            raise ValueError("Missing organism or antibiotic information in FHIR Bundle")
        
        # Mock decision logic
        decision = self._mock_classification_decision(organism, antibiotic, value)
        
        return {
            "specimenId": specimen_id,
            "organism": organism,
            "antibiotic": antibiotic,
            "method": method,
            "input": {
                "organism": organism,
                "antibiotic": antibiotic,
                "method": method,
                "mic_mg_L": value,
                "specimenId": specimen_id
            },
            "decision": decision["decision"],
            "reason": decision["reason"],
            "ruleVersion": "EUCAST v2025.1"
        }
    
    async def _handle_hl7v2_classification(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle HL7v2 message classification."""
        # Simulate HL7v2 message processing
        await asyncio.sleep(0.3)
        
        # For testing, input_data contains the HL7v2 message
        if isinstance(input_data, str):
            hl7_message = input_data
        else:
            hl7_message = input_data.get("message", "")
        
        # Parse HL7v2 message (simplified)
        lines = hl7_message.split('\r')
        organism = None
        antibiotic = None
        value = None
        specimen_id = "HL7V2-ASYNC-001"
        
        for line in lines:
            if line.startswith("OBR"):
                # Extract specimen ID from OBR segment
                fields = line.split('|')
                if len(fields) > 14:
                    specimen_field = fields[14]
                    if '^' in specimen_field:
                        specimen_id = specimen_field.split('^')[0]
            
            elif line.startswith("OBX"):
                fields = line.split('|')
                if len(fields) > 5:
                    observation_value = fields[5]
                    
                    # Check for organism
                    if "ORG" in fields[3]:
                        organism = observation_value
                    
                    # Check for MIC values
                    elif "MIC" in fields[3]:
                        antibiotic_field = fields[3]
                        if '^' in antibiotic_field:
                            parts = antibiotic_field.split('^')
                            if len(parts) > 1:
                                antibiotic = parts[1].replace(" MIC", "")
                        
                        try:
                            value = float(observation_value)
                        except (ValueError, TypeError):
                            if observation_value.lower() == "missing":
                                value = None
        
        # Handle missing MIC scenario
        if value is None:
            return {
                "specimenId": specimen_id,
                "organism": organism,
                "antibiotic": antibiotic,
                "method": "MIC",
                "input": {
                    "organism": organism,
                    "antibiotic": antibiotic,
                    "method": "MIC",
                    "specimenId": specimen_id
                },
                "decision": "Requires Review",
                "reason": "Missing MIC value - manual review required",
                "ruleVersion": "EUCAST v2025.1"
            }
        
        # Perform mock classification
        if not organism or not antibiotic:
            raise ValueError("Missing organism or antibiotic information in HL7v2 message")
        
        decision = self._mock_classification_decision(organism, antibiotic, value)
        
        return {
            "specimenId": specimen_id,
            "organism": organism,
            "antibiotic": antibiotic,
            "method": "MIC",
            "input": {
                "organism": organism,
                "antibiotic": antibiotic,
                "method": "MIC",
                "mic_mg_L": value,
                "specimenId": specimen_id
            },
            "decision": decision["decision"],
            "reason": decision["reason"],
            "ruleVersion": "EUCAST v2025.1"
        }
    
    async def _handle_direct_classification(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle direct classification input."""
        # Simulate processing delay
        await asyncio.sleep(0.2)
        
        # Extract classification parameters
        organism = input_data.get("organism")
        antibiotic = input_data.get("antibiotic")
        method = input_data.get("method", "MIC")
        value = input_data.get("mic_mg_L")
        specimen_id = input_data.get("specimenId", "DIRECT-ASYNC-001")
        
        if not organism or not antibiotic:
            raise ValueError("Missing organism or antibiotic information")
        
        # Perform mock classification
        decision = self._mock_classification_decision(organism, antibiotic, value)
        
        return {
            "specimenId": specimen_id,
            "organism": organism,
            "antibiotic": antibiotic,
            "method": method,
            "input": input_data,
            "decision": decision["decision"],
            "reason": decision["reason"],
            "ruleVersion": "EUCAST v2025.1"
        }
    
    def _mock_classification_decision(self, organism: str, antibiotic: str, mic_value: Optional[float]) -> Dict[str, str]:
        """Mock classification decision logic."""
        if mic_value is None:
            return {
                "decision": "Requires Review",
                "reason": "Missing MIC value"
            }
        
        # Simple breakpoint logic for common organisms/antibiotics
        breakpoints = {
            ("Escherichia coli", "Ampicillin"): {"S": 8.0, "R": 8.0},
            ("Escherichia coli", "Ciprofloxacin"): {"S": 0.5, "R": 1.0},
            ("Staphylococcus aureus", "Vancomycin"): {"S": 2.0, "R": 2.0},
            ("Staphylococcus aureus", "Oxacillin"): {"S": 2.0, "R": 2.0}
        }
        
        key = (organism, antibiotic)
        if key in breakpoints:
            bp = breakpoints[key]
            if mic_value <= bp["S"]:
                return {
                    "decision": "S",
                    "reason": f"MIC {mic_value} mg/L is <= susceptible breakpoint {bp['S']} mg/L"
                }
            elif mic_value > bp["R"]:
                return {
                    "decision": "R",
                    "reason": f"MIC {mic_value} mg/L is > resistant breakpoint {bp['R']} mg/L"
                }
            else:
                return {
                    "decision": "I",
                    "reason": f"MIC {mic_value} mg/L is in intermediate range"
                }
        
        # Default logic for unknown combinations
        if mic_value <= 1.0:
            return {
                "decision": "S",
                "reason": f"MIC {mic_value} mg/L - likely susceptible"
            }
        elif mic_value <= 4.0:
            return {
                "decision": "I",
                "reason": f"MIC {mic_value} mg/L - intermediate range"
            }
        else:
            return {
                "decision": "R",
                "reason": f"MIC {mic_value} mg/L - likely resistant"
            }
    
    async def _send_webhook_notification(self, task_id: str):
        """Send webhook notification for task completion."""
        task_result = self.tasks[task_id]
        
        if not task_result.callback_url:
            return
        
        try:
            payload = {
                "task_id": task_id,
                "status": task_result.status.value,
                "completed_at": task_result.completed_at.isoformat() if task_result.completed_at else None,
                "result": task_result.result,
                "error": task_result.error,
                "processing_duration_ms": task_result.processing_duration_ms
            }
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "AMR-Async-Task-Manager/1.0",
                **task_result.callback_headers
            }
            
            response = await self.webhook_client.post(
                task_result.callback_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Webhook notification sent for task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to send webhook notification for task {task_id}: {e}")
    
    async def _start_next_pending_task(self):
        """Start the next pending task if capacity allows."""
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return
        
        # Find next pending task
        for task_id, task_result in self.tasks.items():
            if task_result.status == TaskStatus.PENDING and task_id not in self.active_tasks:
                await self._start_task_processing(task_id)
                break
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of expired and completed tasks."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                current_time = datetime.now(timezone.utc)
                expired_tasks = []
                
                for task_id, task_result in self.tasks.items():
                    # Mark expired tasks
                    if task_result.is_expired():
                        if task_result.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                            task_result.status = TaskStatus.EXPIRED
                        expired_tasks.append(task_id)
                    
                    # Clean up old completed/failed tasks (older than 1 hour)
                    elif task_result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        if task_result.completed_at:
                            age = current_time - task_result.completed_at
                            if age > timedelta(hours=1):
                                expired_tasks.append(task_id)
                
                # Remove expired tasks
                for task_id in expired_tasks:
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id].cancel()
                        del self.active_tasks[task_id]
                    del self.tasks[task_id]
                
                if expired_tasks:
                    logger.info(f"Cleaned up {len(expired_tasks)} expired/old tasks")
                    
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task."""
        if task_id not in self.tasks:
            return None
        
        task_result = self.tasks[task_id]
        
        # Check if task has expired
        if task_result.is_expired() and task_result.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
            task_result.status = TaskStatus.EXPIRED
            # Cancel active task if running
            if task_id in self.active_tasks:
                self.active_tasks[task_id].cancel()
                del self.active_tasks[task_id]
        
        return task_result.to_dict()
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task."""
        if task_id not in self.tasks:
            return False
        
        task_result = self.tasks[task_id]
        
        if task_result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.EXPIRED]:
            return False  # Already finished
        
        task_result.status = TaskStatus.CANCELLED
        task_result.completed_at = datetime.now(timezone.utc)
        
        # Cancel active task
        if task_id in self.active_tasks:
            self.active_tasks[task_id].cancel()
            del self.active_tasks[task_id]
        
        logger.info(f"Task {task_id} cancelled")
        return True
    
    async def list_tasks(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        tasks = []
        
        for task_result in self.tasks.values():
            if status_filter and task_result.status.value != status_filter:
                continue
            
            tasks.append(task_result.to_dict())
        
        return tasks
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        status_counts = {}
        for task_result in self.tasks.values():
            status = task_result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_tasks": len(self.tasks),
            "active_tasks": len(self.active_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "status_counts": status_counts,
            "uptime_seconds": time.time() - getattr(self, '_start_time', time.time())
        }
    
    async def shutdown(self):
        """Shutdown the task manager gracefully."""
        logger.info("Shutting down async task manager...")
        
        # Cancel all active tasks
        for task in self.active_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        # Close webhook client
        await self.webhook_client.aclose()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        logger.info("Async task manager shutdown complete")


class AsyncScenarioHandler:
    """
    Handler for async classification scenarios in provider verification tests.
    
    Provides high-level interface for testing async endpoints with various
    scenarios including success, failure, timeout, and webhook notifications.
    """
    
    def __init__(self, task_manager: Optional[AsyncTaskManager] = None):
        self.task_manager = task_manager or AsyncTaskManager()
        self.scenario_handlers = {
            "happy_path": self._handle_happy_path_scenario,
            "missing_data": self._handle_missing_data_scenario,
            "invalid_format": self._handle_invalid_format_scenario,
            "timeout": self._handle_timeout_scenario,
            "webhook_notification": self._handle_webhook_scenario,
            "batch_processing": self._handle_batch_scenario
        }
    
    async def run_scenario(
        self, 
        scenario_name: str, 
        scenario_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a specific async classification scenario.
        
        Args:
            scenario_name: Name of the scenario to run
            scenario_params: Parameters for the scenario
            
        Returns:
            Scenario execution results
        """
        if scenario_name not in self.scenario_handlers:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        handler = self.scenario_handlers[scenario_name]
        return await handler(scenario_params)
    
    async def _handle_happy_path_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful async classification scenario."""
        input_data = params.get("input_data", {
            "organism": "Escherichia coli",
            "antibiotic": "Ciprofloxacin",
            "method": "MIC",
            "mic_mg_L": 0.25,
            "specimenId": "HAPPY-PATH-001"
        })
        
        input_format = params.get("input_format", "direct")
        
        # Create async task
        task_id = await self.task_manager.create_async_task(
            input_data=input_data,
            input_format=input_format
        )
        
        # Wait for completion
        max_wait = 10  # seconds
        wait_interval = 0.5
        waited = 0
        
        while waited < max_wait:
            status = await self.task_manager.get_task_status(task_id)
            if status and status["status"] in ["completed", "failed", "cancelled", "expired"]:
                break
            
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        final_status = await self.task_manager.get_task_status(task_id)
        
        return {
            "scenario": "happy_path",
            "task_id": task_id,
            "success": final_status["status"] == "completed",
            "final_status": final_status,
            "waited_seconds": waited
        }
    
    async def _handle_missing_data_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle async classification with missing data."""
        # Input with missing organism
        input_data = {
            "antibiotic": "Unknown Drug",
            "method": "MIC"
            # Missing organism and mic_mg_L
        }
        
        task_id = await self.task_manager.create_async_task(
            input_data=input_data,
            input_format="direct"
        )
        
        # Wait for task to fail
        max_wait = 5
        wait_interval = 0.5
        waited = 0
        
        while waited < max_wait:
            status = await self.task_manager.get_task_status(task_id)
            if status and status["status"] == "failed":
                break
            
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        final_status = await self.task_manager.get_task_status(task_id)
        
        return {
            "scenario": "missing_data",
            "task_id": task_id,
            "failed_as_expected": final_status["status"] == "failed",
            "final_status": final_status,
            "waited_seconds": waited
        }
    
    async def _handle_invalid_format_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle async classification with invalid format."""
        input_data = {"malformed": "data"}
        
        task_id = await self.task_manager.create_async_task(
            input_data=input_data,
            input_format="unsupported_format"
        )
        
        # Wait for task to fail
        await asyncio.sleep(1)
        final_status = await self.task_manager.get_task_status(task_id)
        
        return {
            "scenario": "invalid_format",
            "task_id": task_id,
            "failed_as_expected": final_status["status"] == "failed",
            "final_status": final_status
        }
    
    async def _handle_timeout_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle async classification timeout scenario."""
        # Create task with short TTL
        input_data = {
            "organism": "Escherichia coli",
            "antibiotic": "Ampicillin",
            "method": "MIC",
            "mic_mg_L": 4.0
        }
        
        task_id = await self.task_manager.create_async_task(
            input_data=input_data,
            input_format="direct",
            ttl_hours=0.001  # Very short TTL for testing
        )
        
        # Wait for expiration
        await asyncio.sleep(2)
        final_status = await self.task_manager.get_task_status(task_id)
        
        return {
            "scenario": "timeout",
            "task_id": task_id,
            "expired_as_expected": final_status["status"] == "expired",
            "final_status": final_status
        }
    
    async def _handle_webhook_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle async classification with webhook notification."""
        # Mock webhook endpoint
        webhook_url = params.get("webhook_url", "http://localhost:8080/webhook/test")
        webhook_headers = params.get("webhook_headers", {"X-Test-Webhook": "true"})
        
        input_data = {
            "organism": "Staphylococcus aureus",
            "antibiotic": "Vancomycin",
            "method": "MIC",
            "mic_mg_L": 1.0
        }
        
        task_id = await self.task_manager.create_async_task(
            input_data=input_data,
            input_format="direct",
            callback_url=webhook_url,
            callback_headers=webhook_headers
        )
        
        # Wait for completion
        await asyncio.sleep(2)
        final_status = await self.task_manager.get_task_status(task_id)
        
        return {
            "scenario": "webhook_notification",
            "task_id": task_id,
            "webhook_url": webhook_url,
            "success": final_status["status"] == "completed",
            "final_status": final_status
        }
    
    async def _handle_batch_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch async classification scenario."""
        batch_inputs = params.get("batch_inputs", [
            {
                "organism": "Escherichia coli",
                "antibiotic": "Ampicillin",
                "method": "MIC",
                "mic_mg_L": 8.0
            },
            {
                "organism": "Staphylococcus aureus",
                "antibiotic": "Oxacillin",
                "method": "MIC",
                "mic_mg_L": 1.0
            }
        ])
        
        # Create multiple async tasks
        task_ids = []
        for i, input_data in enumerate(batch_inputs):
            task_id = await self.task_manager.create_async_task(
                input_data=input_data,
                input_format="direct"
            )
            task_ids.append(task_id)
        
        # Wait for all tasks to complete
        max_wait = 10
        wait_interval = 0.5
        waited = 0
        
        while waited < max_wait:
            all_done = True
            for task_id in task_ids:
                status = await self.task_manager.get_task_status(task_id)
                if status and status["status"] not in ["completed", "failed", "cancelled", "expired"]:
                    all_done = False
                    break
            
            if all_done:
                break
            
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        # Collect final statuses
        final_statuses = []
        for task_id in task_ids:
            status = await self.task_manager.get_task_status(task_id)
            final_statuses.append(status)
        
        completed_count = sum(1 for status in final_statuses if status["status"] == "completed")
        
        return {
            "scenario": "batch_processing",
            "task_ids": task_ids,
            "total_tasks": len(task_ids),
            "completed_tasks": completed_count,
            "success_rate": completed_count / len(task_ids) if task_ids else 0,
            "final_statuses": final_statuses,
            "waited_seconds": waited
        }


# Global instances for use in tests
async_task_manager = AsyncTaskManager()
async_scenario_handler = AsyncScenarioHandler(async_task_manager)