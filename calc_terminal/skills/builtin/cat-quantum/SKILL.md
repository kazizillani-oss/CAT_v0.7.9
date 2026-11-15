---
name: cat-quantum
display_name: "CAT Quantum Circuit & Qiskit Engine"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "science"
description: "Constructs quantum circuits, implements quantum algorithms (Grover, VQE, Shor), and performs statevector simulations."
tags: ["cat-native", "quantum", "qiskit", "circuits", "algorithms", "physics"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# CAT Quantum Circuit & Qiskit Engine

## Overview
Original CAT-native quantum computing workflow engine. Designs quantum circuits using Qiskit, simulates statevectors, and implements quantum algorithms.

## Quantum Capabilities
1. **Circuit Synthesis**: Construct parameterized quantum circuits with Hadamard, CNOT, Phase, and Pauli rotations.
2. **Statevector Simulation**: Execute ideal and noisy density-matrix simulations with Qiskit Aer.
3. **Quantum Algorithms**: Scaffold Variational Quantum Eigensolver (VQE), Grover Search, and Quantum Fourier Transform (QFT).
