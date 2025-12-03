# License Compatibility Report

## Project License

**EUPL v1.2** (European Union Public Licence v1.2)

The project is licensed under EUPL v1.2, which is a copyleft license. According to the EUPL v1.2 license text, compatible licenses include:

- GNU General Public License (GPL) v. 2, v. 3
- GNU Affero General Public License (AGPL) v. 3
- Open Software License (OSL) v. 2.1, v. 3.0
- Eclipse Public License (EPL) v. 1.0
- CeCILL v. 2.0, v. 2.1
- Mozilla Public Licence (MPL) v. 2
- GNU Lesser General Public Licence (LGPL) v. 2.1, v. 3
- European Union Public Licence (EUPL) v. 1.1, v. 1.2
- Québec Free and Open-Source Licence — Reciprocity (LiLiQ-R) or Strong Reciprocity (LiLiQ-R+)

Additionally, permissive licenses (MIT, BSD, Apache-2.0, etc.) are compatible as they can be used with copyleft projects, though derivative works must still comply with the EUPL copyleft requirements.

## Dependency Analysis

All direct dependencies have been checked for license compatibility with EUPL v1.2.

### Summary

- **Total dependencies**: 16
- **Compatible**: 16 (100%)
- **Review needed**: 0
- **Incompatible**: 0

### Detailed Dependency List

#### Core Dependencies

1. **python-docx** (v1.2.0)
   - License: MIT
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

2. **beautifulsoup4** (v4.14.3)
   - License: MIT License
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

3. **gliner** (v0.2.24)
   - License: Apache-2.0
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

4. **pdfminer.six** (v20251107)
   - License: MIT
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

5. **tqdm** (v4.67.1)
   - License: MPL-2.0 AND MIT
   - Status: ✅ COMPATIBLE
   - Notes: Dual-licensed (MPL-2.0 is explicitly compatible with EUPL, MIT is permissive)

6. **striprtf** (v0.0.29)
   - License: BSD-3-Clause
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

7. **odfpy** (v1.4.1)
   - License: Apache-2.0 (dual-licensed: Apache, GPL, LGPL)
   - Status: ✅ COMPATIBLE
   - Notes: Multiple license options available; Apache-2.0 is permissive and compatible

8. **openpyxl** (v3.1.5)
   - License: MIT
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

9. **xlrd** (v2.0.2)
   - License: BSD
   - Status: ✅ COMPATIBLE
   - Notes: Permissive license, fully compatible

10. **extract-msg** (v0.55.0)
    - License: GPL v3 (verified from source repository)
    - Status: ✅ COMPATIBLE
    - Notes: GPL-3.0 is explicitly listed as compatible with EUPL v1.2 in the EUPL license appendix. Verified from the project's LICENSE.txt file.

11. **python-pptx** (v1.0.2)
    - License: MIT
    - Status: ✅ COMPATIBLE
    - Notes: Permissive license, fully compatible

12. **PyYAML** (v6.0.3)
    - License: MIT
    - Status: ✅ COMPATIBLE
    - Notes: Permissive license, fully compatible

13. **spacy** (v3.8.11)
    - License: MIT
    - Status: ✅ COMPATIBLE
    - Notes: Permissive license, fully compatible

14. **requests** (v2.32.5)
    - License: Apache-2.0
    - Status: ✅ COMPATIBLE
    - Notes: Permissive license, fully compatible

#### Development Dependencies

15. **pytest** (v9.0.1)
    - License: MIT
    - Status: ✅ COMPATIBLE
    - Notes: Permissive license, fully compatible (development dependency)

16. **pytest-cov** (v7.0.0)
    - License: MIT
    - Status: ✅ COMPATIBLE
    - Notes: Permissive license, fully compatible (development dependency)

## Important Notes

### Copyleft Considerations

1. **extract-msg (GPL-3.0)**: This package uses GPL-3.0, which is compatible with EUPL v1.2. However, since both are copyleft licenses, any derivative works must comply with both licenses. The EUPL v1.2 compatibility clause allows distribution under the compatible license (GPL-3.0) when combining works.

2. **tqdm (MPL-2.0 AND MIT)**: This package is dual-licensed. You can choose to use it under either MPL-2.0 (which is explicitly compatible with EUPL) or MIT (permissive).

3. **odfpy (Multiple licenses)**: This package offers multiple license options. The Apache-2.0 option is recommended as it's permissive and fully compatible.

### Transitive Dependencies

This report covers only direct dependencies listed in `requirements.txt`. Transitive dependencies (dependencies of dependencies) should also be checked, especially if they have copyleft licenses. Common transitive dependencies that may need attention include:

- PyTorch (used by gliner/spacy) - typically BSD-style
- Transformers library (used by gliner) - Apache-2.0
- Other ML/AI libraries

### Recommendations

1. ✅ **All direct dependencies are compatible** - No immediate action required
2. ⚠️ **Consider checking transitive dependencies** - Use `pip-licenses` or similar tools to audit all dependencies
3. 📝 **Document license choices** - For dual-licensed packages (tqdm, odfpy), document which license option is being used
4. 🔄 **Regular audits** - Re-check licenses when updating dependencies

## Verification

This report was generated using an automated license checker script (`check_licenses.py`) that:
- Fetches package metadata from PyPI
- Checks license expressions and classifiers
- Normalizes license names to standard SPDX identifiers
- Verifies compatibility with EUPL v1.2 based on the official EUPL compatibility list

## Conclusion

**All 16 direct dependencies are compatible with EUPL v1.2.** The project can safely use these libraries without license conflicts. The majority of dependencies use permissive licenses (MIT, BSD, Apache-2.0), which pose no compatibility issues. The one copyleft dependency (extract-msg with GPL-3.0) is explicitly listed as compatible with EUPL v1.2.

---

*Report generated: $(date)*
*Tool: check_licenses.py*
