---
name: seo-optimization
display_name: "Search Engine Optimization (SEO) & Web Vitals"
version: "1.1.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "marketing"
description: "Optimizes meta tags, OpenGraph schemas, semantic HTML, Core Web Vitals, sitemaps, and search indexability."
tags: ["seo", "web-vitals", "meta-tags", "performance", "indexing"]
permissions: ["read_files", "write_files"]
compatibility: ">=0.9.0"
---

# Search Engine Optimization (SEO) & Web Vitals

## Overview
Technical SEO engineering and optimization for web apps, documentation portals, and static landing sites.

## Technical Audit & Implementation
1. **Semantic DOM Hierarchy**:
   - Single authoritative `<h1>` per page reflecting primary topic.
   - Logical sequential headings (`<h2>`, `<h3>`) with zero skip levels.
2. **Metadata & OpenGraph**:
   - Concise title tags (<60 characters) and meta descriptions (<155 characters).
   - Comprehensive OpenGraph (`og:title`, `og:image`, `og:type`) and Twitter card tags.
   - JSON-LD structured data schemas (Organization, Article, SoftwareApplication).
3. **Core Web Vitals Engineering**:
   - LCP (Largest Contentful Paint) < 2.5s.
   - INP (Interaction to Next Paint) < 200ms.
   - CLS (Cumulative Layout Shift) < 0.1.
