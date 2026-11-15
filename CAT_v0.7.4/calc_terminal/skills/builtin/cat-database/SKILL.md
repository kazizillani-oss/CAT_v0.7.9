---
name: cat-database
display_name: "CAT Database Architect & Query Optimizer"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "coding"
description: "Models relational and NoSQL schemas, generates migrations, indexes tables, and optimizes slow queries."
tags: ["cat-native", "database", "sql", "migrations", "indexing", "postgresql"]
permissions: ["read_files", "write_files"]
compatibility: ">=0.9.0"
---

# CAT Database Architect & Query Optimizer

## Overview
Original CAT-native database engine. Designs robust relational and document database schemas, writes lossless migrations, and optimizes SQL queries.

## Optimization & Modeling Rules
1. **Schema Normalization & Integrity**:
   - Foreign key constraints, unique indexes, and appropriate column types.
2. **Query Plan Optimization**:
   - Analyze `EXPLAIN ANALYZE` outputs to eliminate sequential table scans on large tables.
   - Author composite indexes for multi-column filter queries.
3. **Zero-Downtime Migrations**:
   - Safe additive migrations; avoiding blocking table locks.
