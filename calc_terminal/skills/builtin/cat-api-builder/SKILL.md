---
name: cat-api-builder
display_name: "CAT API Builder & Endpoint Scaffolder"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "coding"
description: "Rapidly generates REST, GraphQL, and FastAPI endpoints with validation, OpenAPI schemas, and mock tests."
tags: ["cat-native", "api", "rest", "graphql", "fastapi", "endpoints"]
permissions: ["read_files", "write_files"]
compatibility: ">=0.9.0"
---

# CAT API Builder & Endpoint Scaffolder

## Overview
Original CAT-native API engineering tool. Scaffolds production-ready REST and GraphQL endpoints with Pydantic/Zod schemas, OpenAPI documentation, and automated tests.

## Generation Standards
1. **Schema Validation First**:
   - Strict request body and query parameter validation schemas.
2. **Standardized HTTP Responses**:
   - Consistent error envelope (`status`, `error_code`, `message`, `details`).
3. **Automated Endpoint Testing**:
   - Generates mock-based test fixtures for all generated routes.
