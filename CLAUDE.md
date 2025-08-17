# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ComfyUI custom node plugin that enables automatic import and tagging of AI-generated images to Hydrus Network. The project consists of three main ComfyUI nodes:

- **Hydrus Image Importer**: Imports generated images to Hydrus with metadata and tags
- **Hydrus Image Exporter**: Exports images from Hydrus back to ComfyUI workflows 
- **Hydrus Image Dedupe**: Manages duplicate relationships between original and upscaled images

## Development Commands

This project uses Python with pip for dependency management:

```bash
# Install dependencies
pip install -r requirements.txt

# For development, install in editable mode if needed
pip install -e .
```

No specific test, lint, or build commands are configured in this repository.

## Architecture

### Core Components

1. **hydrus_node.py** - Main implementation containing three ComfyUI node classes:
   - `HydrusImport`: Handles image import to Hydrus with metadata embedding
   - `HydrusExport`: Retrieves images and metadata from Hydrus for ComfyUI workflows
   - `HydrusDuplicates`: Manages duplicate relationships in Hydrus

2. **submit.py** - Standalone script for batch processing images with specific tags through ComfyUI workflows

3. **__init__.py** - ComfyUI plugin entry point exposing NODE_CLASS_MAPPINGS

### Key Integration Points

- **Hydrus API Configuration**: Uses environment variables `HYDRUS_KEY` and `HYDRUS_URL`, with fallback to `hydrus_api.txt` file
- **ComfyUI Workflows**: Includes `BasicWorkflow.json` and `upscale_workflow.json` for standard operations
- **Metadata Handling**: Embeds ComfyUI workflow metadata into PNG files during import
- **Tag Management**: Uses namespaced tags (e.g., `positive:`, `modelname:`, `lora:`) for structured metadata

### Dependencies

- `hydrus-api`: Primary interface to Hydrus Network
- `Pillow`: Image processing and metadata handling  
- `torch`: ComfyUI tensor operations
- `numpy`: Array operations for image data

## Configuration

Set these environment variables or create `hydrus_api.txt`:
- `HYDRUS_KEY`: Your Hydrus API access key
- `HYDRUS_URL`: Hydrus server URL (e.g., http://localhost:45869)

The API key requires permissions for importing files and adding tags.