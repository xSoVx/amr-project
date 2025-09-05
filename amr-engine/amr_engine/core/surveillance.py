from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path

from .schemas import ClassificationResult, Decision

logger = logging.getLogger(__name__)


@dataclass
class AntibiogramEntry:
    """Single entry in antibiogram."""
    organism: str
    antibiotic: str
    total_tested: int
    susceptible: int
    intermediate: int
    resistant: int
    percent_susceptible: float
    percent_resistant: float
    site_id: Optional[str] = None
    period: Optional[str] = None


@dataclass
class SurveillanceFilters:
    """Filters for surveillance data."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    site_ids: Optional[List[str]] = None
    organism_names: Optional[List[str]] = None
    antibiotic_names: Optional[List[str]] = None
    specimen_types: Optional[List[str]] = None
    patient_locations: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    gender: Optional[str] = None


@dataclass
class OutbreakAlert:
    """Outbreak detection alert."""
    alert_id: str
    organism: str
    site_id: str
    detection_date: datetime
    alert_type: str  # threshold_exceeded, spike_detected, cluster_identified
    description: str
    case_count: int
    baseline_count: int
    significance: str  # low, medium, high, critical
    metadata: Dict[str, Any]


class SurveillanceAnalytics:
    """AMR surveillance analytics and antibiogram generation."""
    
    def __init__(self):
        self.data_store: List[Dict[str, Any]] = []  # In production, use database
        self.alerts: List[OutbreakAlert] = []
        
    def store_classification_result(
        self,
        result: ClassificationResult,
        site_id: str,
        specimen_type: Optional[str] = None,
        patient_location: Optional[str] = None,
        patient_age: Optional[int] = None,
        patient_gender: Optional[str] = None,
        collection_date: Optional[datetime] = None
    ):
        """Store classification result for surveillance."""
        record = {
            "result_id": f"result_{len(self.data_store) + 1}",
            "timestamp": datetime.utcnow(),
            "site_id": site_id,
            "organism": result.organism,
            "antibiotic": result.antibiotic,
            "method": result.method,
            "decision": result.decision,
            "specimen_id": result.specimenId,
            "patient_id": result.patientId,
            "specimen_type": specimen_type,
            "patient_location": patient_location,
            "patient_age": patient_age,
            "patient_gender": patient_gender,
            "collection_date": collection_date or datetime.utcnow(),
            "input_data": result.input,
            "rule_version": result.ruleVersion
        }
        self.data_store.append(record)
        
        # Check for outbreak conditions
        self._check_outbreak_conditions(record)
    
    def generate_antibiogram(
        self,
        filters: SurveillanceFilters,
        grouping: str = "organism_antibiotic",  # organism_antibiotic, site, location
        min_isolates: int = 30,
        deduplication_days: int = 30
    ) -> List[AntibiogramEntry]:
        """Generate antibiogram following CLSI M39 guidelines."""
        
        # Filter and deduplicate data
        filtered_data = self._filter_data(filters)
        deduplicated_data = self._deduplicate_isolates(filtered_data, deduplication_days)
        
        # Group data for antibiogram
        grouped_data = self._group_antibiogram_data(deduplicated_data, grouping)
        
        antibiogram_entries = []
        
        for group_key, isolates in grouped_data.items():
            if len(isolates) < min_isolates:
                continue  # CLSI M39 minimum isolate requirement
            
            # Parse group key
            if grouping == "organism_antibiotic":
                organism, antibiotic = group_key
                site_id = None
            elif grouping == "site":
                organism, antibiotic, site_id = group_key
            else:
                organism, antibiotic = group_key[:2]
                site_id = group_key[2] if len(group_key) > 2 else None
            
            # Calculate statistics
            total_tested = len(isolates)
            susceptible = len([i for i in isolates if i["decision"] == "S"])
            intermediate = len([i for i in isolates if i["decision"] == "I"])
            resistant = len([i for i in isolates if i["decision"] == "R"])
            
            percent_susceptible = (susceptible / total_tested) * 100
            percent_resistant = (resistant / total_tested) * 100
            
            entry = AntibiogramEntry(
                organism=organism,
                antibiotic=antibiotic,
                total_tested=total_tested,
                susceptible=susceptible,
                intermediate=intermediate,
                resistant=resistant,
                percent_susceptible=percent_susceptible,
                percent_resistant=percent_resistant,
                site_id=site_id,
                period=f"{filters.start_date.strftime('%Y-%m')} to {filters.end_date.strftime('%Y-%m')}" if filters.start_date and filters.end_date else None
            )
            
            antibiogram_entries.append(entry)
        
        # Sort by organism, then antibiotic
        antibiogram_entries.sort(key=lambda x: (x.organism, x.antibiotic))
        
        return antibiogram_entries
    
    def get_resistance_trends(
        self,
        filters: SurveillanceFilters,
        organism: str,
        antibiotic: str,
        time_window: str = "monthly"  # weekly, monthly, quarterly, yearly
    ) -> List[Dict[str, Any]]:
        """Get resistance trends over time."""
        filtered_data = self._filter_data(filters)
        
        # Filter for specific organism/antibiotic combination
        specific_data = [
            record for record in filtered_data
            if record.get("organism", "").lower() == organism.lower()
            and record.get("antibiotic", "").lower() == antibiotic.lower()
        ]
        
        # Group by time periods
        time_groups = self._group_by_time_period(specific_data, time_window)
        
        trends = []
        for period, records in time_groups.items():
            total = len(records)
            resistant = len([r for r in records if r["decision"] == "R"])
            percent_resistant = (resistant / total * 100) if total > 0 else 0
            
            trends.append({
                "period": period,
                "total_isolates": total,
                "resistant_count": resistant,
                "percent_resistant": percent_resistant,
                "organism": organism,
                "antibiotic": antibiotic
            })
        
        return sorted(trends, key=lambda x: x["period"])
    
    def get_mdro_report(
        self,
        filters: SurveillanceFilters,
        mdro_definitions: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate Multi-Drug Resistant Organism (MDRO) report."""
        
        if not mdro_definitions:
            mdro_definitions = self._get_default_mdro_definitions()
        
        filtered_data = self._filter_data(filters)
        
        # Group by patient to assess multi-drug resistance patterns
        patient_isolates = defaultdict(list)
        for record in filtered_data:
            if record.get("patient_id"):
                patient_isolates[record["patient_id"]].append(record)
        
        mdro_cases = []
        
        for patient_id, isolates in patient_isolates.items():
            # Group isolates by organism
            organism_isolates = defaultdict(list)
            for isolate in isolates:
                organism_isolates[isolate["organism"]].append(isolate)
            
            for organism, org_isolates in organism_isolates.items():
                if organism in mdro_definitions:
                    mdro_def = mdro_definitions[organism]
                    if self._meets_mdro_criteria(org_isolates, mdro_def):
                        mdro_cases.append({
                            "patient_id": patient_id,
                            "organism": organism,
                            "isolate_count": len(org_isolates),
                            "resistant_antibiotics": [
                                iso["antibiotic"] for iso in org_isolates 
                                if iso["decision"] == "R"
                            ],
                            "collection_dates": [
                                iso["collection_date"] for iso in org_isolates
                            ],
                            "sites": list(set(iso["site_id"] for iso in org_isolates)),
                            "mdro_type": mdro_def.get("name", organism)
                        })
        
        return {
            "period": f"{filters.start_date} to {filters.end_date}" if filters.start_date else "All time",
            "total_mdro_cases": len(mdro_cases),
            "cases_by_organism": self._group_mdro_by_organism(mdro_cases),
            "cases_by_site": self._group_mdro_by_site(mdro_cases),
            "detailed_cases": mdro_cases[:100]  # Limit for performance
        }
    
    def detect_outbreaks(
        self,
        site_id: str,
        lookback_days: int = 30,
        threshold_multiplier: float = 2.0
    ) -> List[OutbreakAlert]:
        """Detect potential outbreaks using statistical methods."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        site_data = [
            record for record in self.data_store
            if record["site_id"] == site_id and record["timestamp"] >= cutoff_date
        ]
        
        # Group by organism
        organism_counts = defaultdict(list)
        for record in site_data:
            organism_counts[record["organism"]].append(record)
        
        alerts = []
        
        for organism, records in organism_counts.items():
            current_count = len(records)
            
            # Get baseline (same period in previous months)
            baseline_count = self._get_baseline_count(site_id, organism, lookback_days)
            
            # Check threshold
            if baseline_count > 0 and current_count > (baseline_count * threshold_multiplier):
                alert = OutbreakAlert(
                    alert_id=f"alert_{len(self.alerts) + 1}",
                    organism=organism,
                    site_id=site_id,
                    detection_date=datetime.utcnow(),
                    alert_type="threshold_exceeded",
                    description=f"{organism} cases ({current_count}) exceed baseline ({baseline_count}) by {threshold_multiplier}x",
                    case_count=current_count,
                    baseline_count=baseline_count,
                    significance=self._calculate_significance(current_count, baseline_count),
                    metadata={
                        "lookback_days": lookback_days,
                        "threshold_multiplier": threshold_multiplier,
                        "records": [r["result_id"] for r in records]
                    }
                )
                alerts.append(alert)
                self.alerts.append(alert)
        
        return alerts
    
    def export_surveillance_data(
        self,
        filters: SurveillanceFilters,
        format: str = "csv",
        include_phi: bool = False
    ) -> str:
        """Export surveillance data for external analysis."""
        filtered_data = self._filter_data(filters)
        
        if not include_phi:
            # Remove PHI fields
            filtered_data = self._remove_phi(filtered_data)
        
        if format.lower() == "csv":
            return self._export_to_csv(filtered_data)
        elif format.lower() == "json":
            return json.dumps(filtered_data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _filter_data(self, filters: SurveillanceFilters) -> List[Dict[str, Any]]:
        """Apply filters to surveillance data."""
        filtered = self.data_store.copy()
        
        if filters.start_date:
            filtered = [r for r in filtered if r["collection_date"] >= filters.start_date]
        
        if filters.end_date:
            filtered = [r for r in filtered if r["collection_date"] <= filters.end_date]
        
        if filters.site_ids:
            filtered = [r for r in filtered if r["site_id"] in filters.site_ids]
        
        if filters.organism_names:
            organism_names_lower = [o.lower() for o in filters.organism_names]
            filtered = [r for r in filtered if r.get("organism", "").lower() in organism_names_lower]
        
        if filters.antibiotic_names:
            antibiotic_names_lower = [a.lower() for a in filters.antibiotic_names]
            filtered = [r for r in filtered if r.get("antibiotic", "").lower() in antibiotic_names_lower]
        
        return filtered
    
    def _deduplicate_isolates(
        self, 
        data: List[Dict[str, Any]], 
        deduplication_days: int
    ) -> List[Dict[str, Any]]:
        """Deduplicate isolates per CLSI M39 guidelines."""
        # Group by patient, organism, antibiotic
        groups = defaultdict(list)
        for record in data:
            key = (
                record.get("patient_id", "unknown"),
                record.get("organism", "unknown"),
                record.get("antibiotic", "unknown")
            )
            groups[key].append(record)
        
        deduplicated = []
        
        for group_records in groups.values():
            # Sort by collection date
            group_records.sort(key=lambda x: x["collection_date"])
            
            # Keep first isolate, then only those outside deduplication window
            deduplicated.append(group_records[0])
            last_date = group_records[0]["collection_date"]
            
            for record in group_records[1:]:
                if (record["collection_date"] - last_date).days >= deduplication_days:
                    deduplicated.append(record)
                    last_date = record["collection_date"]
        
        return deduplicated
    
    def _group_antibiogram_data(
        self, 
        data: List[Dict[str, Any]], 
        grouping: str
    ) -> Dict[Tuple, List[Dict[str, Any]]]:
        """Group data for antibiogram generation."""
        groups = defaultdict(list)
        
        for record in data:
            if grouping == "organism_antibiotic":
                key = (record["organism"], record["antibiotic"])
            elif grouping == "site":
                key = (record["organism"], record["antibiotic"], record["site_id"])
            else:  # location or other grouping
                key = (record["organism"], record["antibiotic"], record.get("patient_location", "Unknown"))
            
            groups[key].append(record)
        
        return groups
    
    def _group_by_time_period(
        self, 
        data: List[Dict[str, Any]], 
        time_window: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group data by time periods."""
        groups = defaultdict(list)
        
        for record in data:
            date = record["collection_date"]
            
            if time_window == "weekly":
                # Get week number
                period = f"{date.year}-W{date.isocalendar()[1]:02d}"
            elif time_window == "monthly":
                period = f"{date.year}-{date.month:02d}"
            elif time_window == "quarterly":
                quarter = (date.month - 1) // 3 + 1
                period = f"{date.year}-Q{quarter}"
            elif time_window == "yearly":
                period = str(date.year)
            else:
                period = date.strftime("%Y-%m-%d")
            
            groups[period].append(record)
        
        return groups
    
    def _check_outbreak_conditions(self, record: Dict[str, Any]):
        """Check if new record triggers outbreak conditions."""
        # This would implement real-time outbreak detection
        # For now, just log high-priority organisms
        high_priority_organisms = [
            "carbapenem-resistant enterobacteriaceae",
            "methicillin-resistant staphylococcus aureus",
            "vancomycin-resistant enterococcus",
            "multidrug-resistant acinetobacter"
        ]
        
        organism = record.get("organism", "").lower()
        if any(priority_org in organism for priority_org in high_priority_organisms):
            logger.warning(f"High-priority organism detected: {record['organism']} at site {record['site_id']}")
    
    def _get_default_mdro_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get default MDRO definitions."""
        return {
            "Escherichia coli": {
                "name": "MDR E. coli",
                "criteria": {
                    "resistant_count": 3,
                    "antibiotic_classes": ["beta_lactam", "fluoroquinolone", "aminoglycoside"]
                }
            },
            "Klebsiella pneumoniae": {
                "name": "MDR K. pneumoniae", 
                "criteria": {
                    "resistant_count": 3,
                    "antibiotic_classes": ["beta_lactam", "fluoroquinolone", "aminoglycoside"]
                }
            },
            "Acinetobacter baumannii": {
                "name": "MDR Acinetobacter",
                "criteria": {
                    "resistant_count": 3,
                    "antibiotic_classes": ["beta_lactam", "fluoroquinolone", "aminoglycoside"]
                }
            }
        }
    
    def _meets_mdro_criteria(
        self, 
        isolates: List[Dict[str, Any]], 
        mdro_def: Dict[str, Any]
    ) -> bool:
        """Check if isolates meet MDRO criteria."""
        resistant_count = len([iso for iso in isolates if iso["decision"] == "R"])
        required_count = mdro_def["criteria"]["resistant_count"]
        
        return resistant_count >= required_count
    
    def _group_mdro_by_organism(self, mdro_cases: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group MDRO cases by organism."""
        organism_counts = defaultdict(int)
        for case in mdro_cases:
            organism_counts[case["organism"]] += 1
        return dict(organism_counts)
    
    def _group_mdro_by_site(self, mdro_cases: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group MDRO cases by site."""
        site_counts = defaultdict(int)
        for case in mdro_cases:
            for site in case["sites"]:
                site_counts[site] += 1
        return dict(site_counts)
    
    def _get_baseline_count(
        self, 
        site_id: str, 
        organism: str, 
        lookback_days: int
    ) -> int:
        """Get baseline count for outbreak detection."""
        # Look at same period in previous months for baseline
        end_date = datetime.utcnow() - timedelta(days=lookback_days)
        start_date = end_date - timedelta(days=lookback_days * 3)  # 3-month baseline
        
        baseline_data = [
            record for record in self.data_store
            if (record["site_id"] == site_id and
                record["organism"] == organism and
                start_date <= record["timestamp"] <= end_date)
        ]
        
        return len(baseline_data) // 3  # Average per period
    
    def _calculate_significance(self, current: int, baseline: int) -> str:
        """Calculate alert significance level."""
        if baseline == 0:
            return "high" if current > 10 else "medium"
        
        ratio = current / baseline
        if ratio >= 5:
            return "critical"
        elif ratio >= 3:
            return "high"
        elif ratio >= 2:
            return "medium"
        else:
            return "low"
    
    def _remove_phi(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove PHI fields from data."""
        phi_fields = ["patient_id", "specimen_id"]
        
        cleaned_data = []
        for record in data:
            cleaned_record = record.copy()
            for field in phi_fields:
                if field in cleaned_record:
                    cleaned_record[field] = f"***REDACTED***"
            cleaned_data.append(cleaned_record)
        
        return cleaned_data
    
    def _export_to_csv(self, data: List[Dict[str, Any]]) -> str:
        """Export data to CSV format."""
        if not data:
            return ""
        
        # Get all unique field names
        fieldnames = set()
        for record in data:
            fieldnames.update(record.keys())
        
        fieldnames = sorted(fieldnames)
        
        # Create CSV content
        csv_lines = [",".join(fieldnames)]
        
        for record in data:
            row_values = []
            for field in fieldnames:
                value = record.get(field, "")
                # Handle special characters in CSV
                if isinstance(value, str) and ("," in value or '"' in value):
                    value = f'"{value.replace('"', '""')}"'
                row_values.append(str(value))
            csv_lines.append(",".join(row_values))
        
        return "\n".join(csv_lines)


# Global surveillance analytics instance
surveillance_analytics = SurveillanceAnalytics()