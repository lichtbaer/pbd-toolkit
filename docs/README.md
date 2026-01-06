# Documentation

This directory contains the MkDocs-based documentation for the PII Toolkit fork.

## Building the Documentation

### Prerequisites

Install MkDocs and the Material theme:

```bash
pip install mkdocs mkdocs-material mkdocs-git-revision-date-localized-plugin
```

### Serve Locally

To view the documentation locally while editing:

```bash
mkdocs serve
```

Then open `http://127.0.0.1:8000` in your browser.

### Build Static Site

To build a static HTML site:

```bash
mkdocs build
```

The output will be in the `site/` directory.

### Deploy

To deploy to GitHub Pages or another hosting service:

```bash
mkdocs gh-deploy
```

(Requires `mkdocs` with GitHub Pages support)

## Documentation Structure

- **index.md**: Main landing page with fork disclaimer
- **getting-started/**: Installation and setup guides
- **user-guide/**: User documentation (CLI, formats, methods)
- **developer/**: Developer documentation (architecture, extending)
- **about/**: Project status, contributing, license
- **archive/**: Archived development notes (for reference only)

## Editing Documentation

1. Edit Markdown files in this directory
2. Run `mkdocs serve` to preview changes
3. Commit changes to version control

## Note

This documentation is for the **fork** of the HBDI PII Toolkit. It is not official documentation from HBDI.

For installation and feature extras (recommended), see `getting-started/installation.md`.
