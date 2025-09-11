#!/usr/bin/env python3
"""
Project cleanup script for AMR Classification Service.

This script removes unnecessary files and directories that should not be
committed to version control, helping maintain a clean project structure.
"""

import os
import shutil
import glob
import logging
from pathlib import Path
from typing import List, Set

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Patterns for files and directories to clean
CLEANUP_PATTERNS = {
    'python_cache': [
        '**/__pycache__',
        '**/*.pyc',
        '**/*.pyo',
        '**/*.pyd',
        '**/.pytest_cache',
        '**/*.egg-info',
        '**/build',
        '**/dist',
        '**/.tox',
        '**/.nox'
    ],
    'coverage_reports': [
        '**/.coverage',
        '**/.coverage.*',
        '**/htmlcov',
        '**/coverage.xml',
        '**/*.cover'
    ],
    'ide_files': [
        '**/.vscode/settings.json',
        '**/.vscode/launch.json',
        '**/.idea',
        '**/*.swp',
        '**/*.swo',
        '**/.DS_Store',
        '**/Thumbs.db'
    ],
    'log_files': [
        '**/*.log',
        '**/logs/*',
        '**/app.log'
    ],
    'temporary_files': [
        '**/*.tmp',
        '**/*.temp',
        '**/tmp/*',
        '**/temp/*',
        '**/*.bak',
        '**/*.backup',
        '**/*.old'
    ],
    'generated_ci_files': [
        '**/docker-compose.pact-broker.yml',
        '**/.gitlab-ci.pact.yml',
        '**/Jenkinsfile.pact'
    ],
    'test_artifacts': [
        '**/test-results/*',
        '**/test-reports/*',
        '**/tests/pacts/*.json'  # Optional: Pact contract files
    ],
    'secrets_and_config': [
        '**/.env.local',
        '**/.env.production',
        '**/.env.staging',
        '**/config/secrets/*',
        '**/secrets/*'
    ]
}

def find_files_to_clean(patterns: List[str]) -> Set[Path]:
    """
    Find files matching cleanup patterns.
    
    Args:
        patterns: List of glob patterns to match
        
    Returns:
        Set of Path objects for files/directories to clean
    """
    files_to_clean = set()
    
    for pattern in patterns:
        full_pattern = PROJECT_ROOT / pattern
        for path in glob.glob(str(full_pattern), recursive=True):
            path_obj = Path(path)
            if path_obj.exists():
                files_to_clean.add(path_obj)
    
    return files_to_clean

def remove_file_or_dir(path: Path) -> bool:
    """
    Remove a file or directory.
    
    Args:
        path: Path to remove
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if path.is_dir():
            shutil.rmtree(path)
            logger.info(f"Removed directory: {path.relative_to(PROJECT_ROOT)}")
        else:
            path.unlink()
            logger.info(f"Removed file: {path.relative_to(PROJECT_ROOT)}")
        return True
    except Exception as e:
        logger.warning(f"Failed to remove {path.relative_to(PROJECT_ROOT)}: {e}")
        return False

def cleanup_category(category: str, patterns: List[str], dry_run: bool = False) -> int:
    """
    Clean up files for a specific category.
    
    Args:
        category: Category name for logging
        patterns: List of glob patterns to clean
        dry_run: If True, only show what would be cleaned
        
    Returns:
        Number of items cleaned
    """
    logger.info(f"\n--- Cleaning {category} ---")
    
    files_to_clean = find_files_to_clean(patterns)
    
    if not files_to_clean:
        logger.info(f"No {category} files found")
        return 0
    
    cleaned_count = 0
    for path in sorted(files_to_clean):
        if dry_run:
            logger.info(f"Would remove: {path.relative_to(PROJECT_ROOT)}")
            cleaned_count += 1
        else:
            if remove_file_or_dir(path):
                cleaned_count += 1
    
    logger.info(f"{'Would clean' if dry_run else 'Cleaned'} {cleaned_count} {category} items")
    return cleaned_count

def main():
    """Main cleanup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up AMR project unnecessary files")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be cleaned without actually removing")
    parser.add_argument("--categories", nargs="+", 
                       choices=list(CLEANUP_PATTERNS.keys()) + ["all"],
                       default=["all"],
                       help="Categories to clean")
    parser.add_argument("--keep-pacts", action="store_true",
                       help="Keep Pact contract files")
    
    args = parser.parse_args()
    
    logger.info(f"Starting cleanup of AMR project at: {PROJECT_ROOT}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will actually be removed")
    
    # Determine which categories to clean
    if "all" in args.categories:
        categories_to_clean = list(CLEANUP_PATTERNS.keys())
    else:
        categories_to_clean = args.categories
    
    # Remove test artifacts if keeping pacts
    if args.keep_pacts and "test_artifacts" in categories_to_clean:
        # Modify test_artifacts patterns to exclude pact files
        modified_patterns = [p for p in CLEANUP_PATTERNS["test_artifacts"] 
                           if "pacts" not in p]
        CLEANUP_PATTERNS["test_artifacts"] = modified_patterns
        logger.info("Keeping Pact contract files")
    
    total_cleaned = 0
    
    # Clean each category
    for category in categories_to_clean:
        if category in CLEANUP_PATTERNS:
            count = cleanup_category(category, CLEANUP_PATTERNS[category], args.dry_run)
            total_cleaned += count
    
    # Summary
    logger.info(f"\n--- Cleanup Summary ---")
    logger.info(f"Total items {'would be cleaned' if args.dry_run else 'cleaned'}: {total_cleaned}")
    
    if not args.dry_run and total_cleaned > 0:
        logger.info("Project cleanup completed successfully!")
    elif args.dry_run:
        logger.info("Run without --dry-run to actually clean the files")
    else:
        logger.info("Project is already clean!")

if __name__ == "__main__":
    main()