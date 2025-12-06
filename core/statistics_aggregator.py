"""Statistics aggregator for privacy-focused output.

This module aggregates PII matches by privacy dimensions and detection modules
without storing individual PII instances or file paths.
"""

import os
from collections import defaultdict
from typing import Dict, Set

from matches import PiiMatch
from core.privacy_dimensions import get_dimension, get_sensitivity_level, get_all_dimensions


class StatisticsAggregator:
    """Aggregates PII matches by dimension, module, and file type.
    
    This class processes matches and creates aggregated statistics without
    storing individual PII text or file paths, ensuring privacy compliance.
    """
    
    def __init__(self):
        """Initialize the aggregator with empty statistics."""
        # Statistics by dimension
        self._by_dimension: Dict[str, Dict] = defaultdict(lambda: {
            "total_count": 0,
            "by_module": defaultdict(int),
            "by_type": defaultdict(int),
            "files_affected": set(),  # Use set to track unique files
            "sensitivity_level": None
        })
        
        # Statistics by module
        self._by_module: Dict[str, Dict] = defaultdict(lambda: {
            "total_matches": 0,
            "types_detected": set(),
            "files_processed": set(),
            "files_with_matches": set(),
            "confidence_scores": []  # For calculating avg confidence
        })
        
        # Statistics by file type
        self._by_file_type: Dict[str, Dict] = defaultdict(lambda: {
            "files_scanned": 0,
            "files_analyzed": 0,
            "matches_found": 0,
            "dimensions_detected": set()
        })
        
        # Track all unique files with matches (for summary)
        self._all_files_with_matches: Set[str] = set()
        
        # Track all unique types detected
        self._all_types_detected: Set[str] = set()
        
        # Initialize sensitivity levels for dimensions
        for dimension in get_all_dimensions():
            if dimension in self._by_dimension:
                self._by_dimension[dimension]["sensitivity_level"] = get_sensitivity_level(dimension)
    
    def add_match(self, match: PiiMatch) -> None:
        """Add a match to aggregation.
        
        Args:
            match: PiiMatch object to aggregate
        """
        detection_type = match.type
        engine = match.engine or "unknown"
        file_path = match.file
        
        # Get dimension for this detection type
        dimension = get_dimension(detection_type)
        
        # Update dimension statistics
        dim_stats = self._by_dimension[dimension]
        dim_stats["total_count"] += 1
        dim_stats["by_module"][engine] += 1
        dim_stats["by_type"][detection_type] += 1
        dim_stats["files_affected"].add(file_path)
        if dim_stats["sensitivity_level"] is None:
            dim_stats["sensitivity_level"] = get_sensitivity_level(dimension)
        
        # Update module statistics
        module_stats = self._by_module[engine]
        module_stats["total_matches"] += 1
        module_stats["types_detected"].add(detection_type)
        module_stats["files_with_matches"].add(file_path)
        if match.ner_score is not None:
            module_stats["confidence_scores"].append(match.ner_score)
        
        # Update file type statistics
        # Extract file extension from path
        file_ext = self._extract_extension(file_path)
        if file_ext:
            file_type_stats = self._by_file_type[file_ext]
            file_type_stats["matches_found"] += 1
            file_type_stats["dimensions_detected"].add(dimension)
        
        # Track globally
        self._all_files_with_matches.add(file_path)
        self._all_types_detected.add(detection_type)
    
    def add_file_scanned(self, file_path: str, was_analyzed: bool = False) -> None:
        """Record that a file was scanned (and optionally analyzed).
        
        Args:
            file_path: Path to the file
            was_analyzed: Whether the file was actually analyzed (not just scanned)
        """
        file_ext = self._extract_extension(file_path)
        if file_ext:
            file_type_stats = self._by_file_type[file_ext]
            file_type_stats["files_scanned"] += 1
            if was_analyzed:
                file_type_stats["files_analyzed"] += 1
    
    def add_file_processed(self, file_path: str, engine: str) -> None:
        """Record that a file was processed by a specific engine.
        
        Args:
            file_path: Path to the file
            engine: Engine name that processed the file
        """
        if engine in self._by_module:
            self._by_module[engine]["files_processed"].add(file_path)
    
    def get_statistics(self) -> Dict:
        """Get aggregated statistics as dictionary.
        
        Returns:
            Dictionary with aggregated statistics, ready for JSON serialization
        """
        # Convert sets to counts/lists for JSON serialization
        stats = {
            "statistics_by_dimension": {},
            "statistics_by_module": {},
            "statistics_by_file_type": {},
            "summary": self._get_summary()
        }
        
        # Process dimension statistics
        for dimension, dim_stats in self._by_dimension.items():
            stats["statistics_by_dimension"][dimension] = {
                "total_count": dim_stats["total_count"],
                "by_module": dict(dim_stats["by_module"]),
                "by_type": dict(dim_stats["by_type"]),
                "files_affected": len(dim_stats["files_affected"]),
                "sensitivity_level": dim_stats["sensitivity_level"]
            }
        
        # Process module statistics
        for module, module_stats in self._by_module.items():
            confidence_scores = module_stats["confidence_scores"]
            avg_confidence = (
                sum(confidence_scores) / len(confidence_scores)
                if confidence_scores else None
            )
            
            # Calculate confidence distribution
            confidence_dist = self._calculate_confidence_distribution(confidence_scores)
            
            stats["statistics_by_module"][module] = {
                "total_matches": module_stats["total_matches"],
                "types_detected": len(module_stats["types_detected"]),
                "files_processed": len(module_stats["files_processed"]),
                "files_with_matches": len(module_stats["files_with_matches"]),
            }
            
            if avg_confidence is not None:
                stats["statistics_by_module"][module]["avg_confidence"] = round(avg_confidence, 3)
                stats["statistics_by_module"][module]["confidence_distribution"] = confidence_dist
        
        # Process file type statistics
        for file_type, file_type_stats in self._by_file_type.items():
            stats["statistics_by_file_type"][file_type] = {
                "files_scanned": file_type_stats["files_scanned"],
                "files_analyzed": file_type_stats["files_analyzed"],
                "matches_found": file_type_stats["matches_found"],
                "top_dimensions": sorted(
                    file_type_stats["dimensions_detected"],
                    key=lambda d: self._by_dimension.get(d, {}).get("total_count", 0),
                    reverse=True
                )[:5]  # Top 5 dimensions
            }
        
        return stats
    
    def _get_summary(self) -> Dict:
        """Get summary statistics.
        
        Returns:
            Dictionary with summary information
        """
        total_matches = sum(
            dim_stats["total_count"]
            for dim_stats in self._by_dimension.values()
        )
        
        # Calculate risk assessment
        risk_counts = {
            "very_high_risk_count": 0,
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0
        }
        
        for dimension, dim_stats in self._by_dimension.items():
            sensitivity = dim_stats["sensitivity_level"]
            count = dim_stats["total_count"]
            
            if sensitivity == "very_high":
                risk_counts["very_high_risk_count"] += count
            elif sensitivity == "high":
                risk_counts["high_risk_count"] += count
            elif sensitivity == "medium":
                risk_counts["medium_risk_count"] += count
            elif sensitivity == "low":
                risk_counts["low_risk_count"] += count
        
        # Find highest risk dimension
        highest_risk_dimension = None
        highest_risk_count = 0
        for dimension, dim_stats in self._by_dimension.items():
            if dim_stats["sensitivity_level"] == "very_high":
                if dim_stats["total_count"] > highest_risk_count:
                    highest_risk_count = dim_stats["total_count"]
                    highest_risk_dimension = dimension
        
        return {
            "total_matches": total_matches,
            "unique_files_with_matches": len(self._all_files_with_matches),
            "dimensions_detected": len(self._by_dimension),
            "modules_used": len(self._by_module),
            "highest_risk_dimension": highest_risk_dimension,
            "risk_assessment": risk_counts
        }
    
    def _calculate_confidence_distribution(self, scores: list[float]) -> Dict[str, int]:
        """Calculate confidence score distribution.
        
        Args:
            scores: List of confidence scores
            
        Returns:
            Dictionary with distribution counts
        """
        dist = {
            "0.0-0.5": 0,
            "0.5-0.7": 0,
            "0.7-0.9": 0,
            "0.9-1.0": 0
        }
        
        for score in scores:
            if score < 0.5:
                dist["0.0-0.5"] += 1
            elif score < 0.7:
                dist["0.5-0.7"] += 1
            elif score < 0.9:
                dist["0.7-0.9"] += 1
            else:
                dist["0.9-1.0"] += 1
        
        return dist
    
    def _extract_extension(self, file_path: str) -> str:
        """Extract file extension from path.
        
        Args:
            file_path: File path
            
        Returns:
            File extension (e.g., ".pdf") or empty string
        """
        _, ext = os.path.splitext(file_path)
        return ext.lower() if ext else ""
