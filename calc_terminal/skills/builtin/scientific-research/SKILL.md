---
name: scientific-research
display_name: "Scientific Computing & Data Analysis"
version: "1.2.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "science"
description: "Conducts numerical modeling, statistical tests, symbolic algebra (SymPy), and data visualization with SciPy and NumPy."
tags: ["science", "math", "numpy", "scipy", "sympy", "data-analysis"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Scientific Computing & Data Analysis

## Overview
Performs rigorous numerical calculations, statistical hypothesis testing, symbolic mathematics, and reproducible data workflows.

## Standards & Best Practices
1. **Exact Symbolic Math First**:
   - Use SymPy for analytical solutions, limits, integrals, and matrix decompositions before resorting to floating-point approximations.
2. **Vectorized Numerical Computing**:
   - Leverage NumPy and SciPy vectorization; avoid slow pure-Python nested loops over large datasets.
   - Enforce explicit precision handling (`np.float64`) to avoid precision decay in iterative solvers.
3. **Statistical Rigor**:
   - Report confidence intervals, effect sizes, and p-values with appropriate multi-testing corrections.
   - Always state assumptions regarding data normality, homoscedasticity, and sample size.
