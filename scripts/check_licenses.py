#!/usr/bin/env python3
"""
License compatibility checker for the PII Toolkit project.

This script checks all dependencies and their license compatibility with EUPL v1.2.
"""

import json
import sys
from typing import Dict, List, Tuple, Optional
import urllib.request
import urllib.error
import urllib.parse

# EUPL v1.2 compatible licenses (from the EUPL license appendix)
EUPL_COMPATIBLE_LICENSES = [
    "GPL-2.0",
    "GPL-3.0",
    "GPL-2.0-or-later",
    "GPL-3.0-or-later",
    "AGPL-3.0",
    "AGPL-3.0-or-later",
    "OSL-2.1",
    "OSL-3.0",
    "EPL-1.0",
    "EPL-2.0",  # EPL-2.0 is also generally compatible
    "CeCILL-2.0",
    "CeCILL-2.1",
    "MPL-2.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "LGPL-2.1-or-later",
    "LGPL-3.0-or-later",
    "EUPL-1.1",
    "EUPL-1.2",
    "LiLiQ-R",
    "LiLiQ-R+",
    # Also compatible: permissive licenses (MIT, BSD, Apache) can be used
    # but derivative works must still be under EUPL
    "MIT",
    "BSD",
    "Apache-2.0",
    "ISC",
    "Python-2.0",
]

# Permissive licenses that are compatible (can be used, but don't require copyleft)
PERMISSIVE_LICENSES = [
    "MIT",
    "BSD",
    "Apache-2.0",
    "ISC",
    "Python-2.0",
    "ZPL-2.0",
    "ZPL-2.1",
    "PSF",
    "Public-Domain",
    "Unlicense",
    "CC0-1.0",
]

# Potentially problematic licenses (copyleft that may conflict)
POTENTIALLY_PROBLEMATIC = [
    "GPL-2.0-only",  # GPL-2.0-only (not -or-later) can be problematic
    "AGPL-3.0-only",
]


def get_package_info(package_name: str) -> Optional[Dict]:
    """Get package information from PyPI."""
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        # Validate URL scheme to prevent file:/ or other unsafe schemes
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ("https", "http"):
            raise ValueError(f"Unsafe URL scheme: {parsed_url.scheme}")
        # URL scheme is validated above, only https/http allowed
        with urllib.request.urlopen(url, timeout=10) as response:  # nosec B310
            data = json.loads(response.read())
            info = data.get("info", {})

            # Prefer license_expression over license field
            if not info.get("license") or info.get("license") == "UNKNOWN":
                if info.get("license_expression"):
                    info["license"] = info["license_expression"]

            # Also check classifiers for license info
            if (
                not info.get("license") or info.get("license") == "UNKNOWN"
            ) and info.get("classifiers"):
                for classifier in info.get("classifiers", []):
                    if classifier.startswith("License ::"):
                        # Extract license from classifier
                        license_parts = classifier.split("::")
                        if len(license_parts) >= 2:
                            license_from_classifier = license_parts[-1].strip()
                            # Map common classifier licenses to SPDX
                            if "Apache Software License" in license_from_classifier:
                                info["license"] = "Apache-2.0"
                                break
                            elif (
                                "GNU General Public License (GPL)"
                                in license_from_classifier
                            ):
                                # Try to determine version from description or default to GPL-3.0
                                desc = info.get("description", "").upper()
                                if (
                                    "GPL V3" in desc
                                    or "GPL-3" in desc
                                    or "GPLV3" in desc
                                ):
                                    info["license"] = "GPL-3.0"
                                elif (
                                    "GPL V2" in desc
                                    or "GPL-2" in desc
                                    or "GPLV2" in desc
                                ):
                                    info["license"] = "GPL-2.0"
                                else:
                                    info["license"] = "GPL-3.0"  # Default to GPL-3.0
                                break
                            elif (
                                "GNU Library or Lesser General Public License (LGPL)"
                                in license_from_classifier
                            ):
                                info["license"] = "LGPL-3.0"
                                break
                            elif "MIT" in license_from_classifier:
                                info["license"] = "MIT"
                                break
                            elif "BSD" in license_from_classifier:
                                info["license"] = "BSD"
                                break

            return info
    except urllib.error.URLError as e:
        print(
            f"  Warning: Could not fetch info for {package_name}: {e}", file=sys.stderr
        )
        return None
    except Exception as e:
        print(f"  Warning: Error fetching {package_name}: {e}", file=sys.stderr)
        return None


def normalize_license(license_str: str) -> List[str]:
    """Normalize license string to standard SPDX identifiers."""
    if not license_str:
        return []

    license_str = license_str.strip()

    # Handle multiple licenses (separated by commas, "or", "AND", etc.)
    licenses = []
    for sep in [",", " or ", " OR ", " and ", " AND "]:
        if sep in license_str:
            licenses.extend(
                [license_item.strip() for license_item in license_str.split(sep)]
            )
            break

    if not licenses:
        licenses = [license_str]

    # Normalize common variations
    normalized = []
    for lic in licenses:
        lic = lic.strip()
        lic_upper = lic.upper()
        # Common variations
        if "MIT" in lic_upper:
            normalized.append("MIT")
        elif "BSD" in lic_upper:
            if "3-Clause" in lic or "3-clause" in lic or "3 CLAUSE" in lic_upper:
                normalized.append("BSD-3-Clause")
            elif "2-Clause" in lic or "2-clause" in lic or "2 CLAUSE" in lic_upper:
                normalized.append("BSD-2-Clause")
            else:
                normalized.append("BSD")
        elif "Apache" in lic_upper:
            if "2.0" in lic or "2" in lic:
                normalized.append("Apache-2.0")
            else:
                normalized.append("Apache-2.0")  # Default to 2.0
        elif "GPL" in lic_upper and "LGPL" not in lic_upper:
            if "V3" in lic_upper or "3.0" in lic or "3" in lic:
                normalized.append("GPL-3.0")
            elif "V2" in lic_upper or "2.0" in lic or "2" in lic:
                normalized.append("GPL-2.0")
            else:
                # Default to GPL-3.0 for "GPL" without version
                normalized.append("GPL-3.0")
        elif "LGPL" in lic_upper:
            if "V3" in lic_upper or "3.0" in lic or "3" in lic:
                normalized.append("LGPL-3.0")
            elif "V2" in lic_upper or "2.1" in lic or "2" in lic:
                normalized.append("LGPL-2.1")
            else:
                normalized.append("LGPL-3.0")
        elif "MPL" in lic_upper:
            normalized.append("MPL-2.0")
        elif "EUPL" in lic_upper:
            normalized.append("EUPL-1.2")
        else:
            normalized.append(lic)

    return normalized


def check_license_compatibility(license_str: str) -> Tuple[bool, str, List[str]]:
    """Check if license is compatible with EUPL v1.2."""
    if not license_str:
        return False, "UNKNOWN", []

    normalized = normalize_license(license_str)

    compatible = False
    issues = []

    for lic in normalized:
        lic_upper = lic.upper()

        # Check if explicitly compatible
        if any(comp.upper() in lic_upper for comp in EUPL_COMPATIBLE_LICENSES):
            compatible = True
            continue

        # Check if permissive (compatible but don't require copyleft)
        if any(perm.upper() in lic_upper for perm in PERMISSIVE_LICENSES):
            compatible = True
            continue

        # Check for potentially problematic licenses
        if any(prob.upper() in lic_upper for prob in POTENTIALLY_PROBLEMATIC):
            issues.append(f"Potentially problematic: {lic}")

    if not compatible and not issues:
        issues.append(f"License '{license_str}' not in known compatible list")

    status = "COMPATIBLE" if compatible else "UNKNOWN"
    if issues:
        status = "REVIEW_NEEDED"

    return compatible, status, issues


def read_requirements() -> List[str]:
    """Read dependencies from requirements.txt."""
    dependencies = []
    try:
        with open("requirements.txt", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Extract package name (before version specifiers)
                package_name = (
                    line.split("~=")[0]
                    .split("==")[0]
                    .split(">=")[0]
                    .split(">")[0]
                    .split("<=")[0]
                    .split("<")[0]
                    .strip()
                )
                if package_name:
                    dependencies.append(package_name)
    except FileNotFoundError:
        print("Error: requirements.txt not found", file=sys.stderr)
        sys.exit(1)

    return dependencies


def main():
    """Main function to check all dependencies."""
    print("=" * 80)
    print("License Compatibility Check for PII Toolkit")
    print("Project License: EUPL v1.2")
    print("=" * 80)
    print()

    dependencies = read_requirements()

    print(f"Checking {len(dependencies)} dependencies...")
    print()

    results = []
    compatible_count = 0
    unknown_count = 0
    review_needed_count = 0

    for dep in dependencies:
        print(f"Checking {dep}...", end=" ", flush=True)
        info = get_package_info(dep)

        if not info:
            print("ERROR: Could not fetch package info")
            results.append(
                {
                    "package": dep,
                    "license": "UNKNOWN",
                    "status": "ERROR",
                    "issues": ["Could not fetch package information"],
                }
            )
            unknown_count += 1
            continue

        license_str = info.get("license", "UNKNOWN")
        if license_str == "UNKNOWN" or not license_str:
            # Try to get from classifiers
            classifiers = info.get("classifiers", [])
            for classifier in classifiers:
                if classifier.startswith("License ::"):
                    license_str = classifier.split("::")[-1].strip()
                    break

        compatible, status, issues = check_license_compatibility(license_str)

        results.append(
            {
                "package": dep,
                "version": info.get("version", "unknown"),
                "license": license_str,
                "status": status,
                "issues": issues,
                "compatible": compatible,
            }
        )

        if status == "COMPATIBLE":
            compatible_count += 1
            print(f"✓ {status} ({license_str})")
        elif status == "REVIEW_NEEDED":
            review_needed_count += 1
            print(f"⚠ {status} ({license_str})")
        else:
            unknown_count += 1
            print(f"? {status} ({license_str})")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total dependencies: {len(dependencies)}")
    print(f"Compatible: {compatible_count}")
    print(f"Review needed: {review_needed_count}")
    print(f"Unknown/Error: {unknown_count}")
    print()

    # Detailed report
    print("=" * 80)
    print("Detailed Report")
    print("=" * 80)
    print()

    for result in results:
        print(f"Package: {result['package']} (v{result.get('version', 'unknown')})")
        print(f"  License: {result['license']}")
        print(f"  Status: {result['status']}")
        if result["issues"]:
            print("  Issues:")
            for issue in result["issues"]:
                print(f"    - {issue}")
        print()

    # Save to JSON
    with open("license_report.json", "w") as f:
        json.dump(
            {
                "project_license": "EUPL-1.2",
                "summary": {
                    "total": len(dependencies),
                    "compatible": compatible_count,
                    "review_needed": review_needed_count,
                    "unknown": unknown_count,
                },
                "dependencies": results,
            },
            f,
            indent=2,
        )

    print("Detailed report saved to license_report.json")
    print()

    # Exit code based on results
    if review_needed_count > 0 or unknown_count > 0:
        print("⚠ WARNING: Some dependencies need review!")
        return 1
    else:
        print("✓ All dependencies appear compatible!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
