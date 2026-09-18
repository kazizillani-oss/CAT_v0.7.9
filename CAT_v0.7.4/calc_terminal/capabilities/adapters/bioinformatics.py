"""
Bioinformatics & Genomics Capability Adapter per §45:
- blast.search
- ncbi.query
- biopython.parse
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
import urllib.parse
import json
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_bio_health() -> Tuple[AvailabilityStatus, str]:
    has_local = shutil.which("blastn") is not None or shutil.which("blastp") is not None
    try:
        import Bio  # noqa: F401
        has_biopython = True
    except ImportError:
        has_biopython = False

    if has_local or has_biopython:
        return AvailabilityStatus.AVAILABLE, f"Bioinformatics ready (local BLAST: {has_local}, Biopython: {has_biopython})"
    return AvailabilityStatus.AVAILABLE, "NCBI REST API available (local BLAST/Biopython not installed)"


def _blast_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    sequence = args.get("sequence", "")
    program = args.get("program", "blastp")  # blastp, blastn
    database = args.get("database", "nr")

    if not sequence:
        return ExecutionResult(success=False, error="sequence argument is required (FASTA or raw sequence)")

    # Check for local blast tool
    if shutil.which(program):
        try:
            proc = subprocess.run(
                [program, "-db", database, "-outfmt", "0"],
                input=sequence,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60.0,
            )
            if proc.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=proc.stdout,
                    metadata={"engine": "local", "program": program, "database": database},
                )
        except Exception:
            pass

    # Fallback to NCBI Web API
    try:
        url = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
        data = urllib.parse.urlencode({
            "CMD": "Put",
            "PROGRAM": program,
            "DATABASE": database,
            "QUERY": sequence,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"User-Agent": "CAT-AI-Platform/1.0"})
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        # Extract RID (Request ID)
        rid = ""
        for line in body.splitlines():
            if "RID =" in line:
                rid = line.split("RID =")[1].strip()
                break

        return ExecutionResult(
            success=True,
            output=f"BLAST job submitted to NCBI. Request ID (RID): {rid or 'pending'}",
            metadata={"engine": "ncbi_rest", "rid": rid, "program": program, "database": database},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"BLAST query failed: {e}")


def _ncbi_query_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    term = args.get("term", "")
    db = args.get("db", "protein")
    if not term:
        return ExecutionResult(success=False, error="term argument is required")

    try:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db={db}&term={urllib.parse.quote_plus(term)}&retmode=json&retmax=10"
        req = urllib.request.Request(url, headers={"User-Agent": "CAT-AI-Platform/1.0"})
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        id_list = data.get("esearchresult", {}).get("idlist", [])
        return ExecutionResult(
            success=True,
            output=id_list,
            metadata={"db": db, "count": len(id_list), "ids": id_list},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"NCBI query failed: {e}")


def _biopython_parse_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    file_path = args.get("path", "")
    fmt = args.get("format", "fasta")
    if not file_path:
        return ExecutionResult(success=False, error="path argument is required")
    file_path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(file_path):
        return ExecutionResult(success=False, error=f"File not found: {file_path}")

    try:
        from Bio import SeqIO
        records = []
        for rec in SeqIO.parse(file_path, fmt):
            records.append({
                "id": rec.id,
                "name": rec.name,
                "description": rec.description,
                "length": len(rec.seq),
                "sequence": str(rec.seq)[:100] + ("..." if len(rec.seq) > 100 else ""),
            })
        return ExecutionResult(success=True, output=records, metadata={"count": len(records)})
    except ImportError:
        # Simple fallback parser for FASTA if biopython not installed
        if fmt.lower() == "fasta":
            records = []
            with open(file_path, "r", encoding="utf-8") as f:
                cur_id = ""
                cur_seq = []
                for line in f:
                    line = line.strip()
                    if line.startswith(">"):
                        if cur_id:
                            records.append({"id": cur_id, "length": sum(len(s) for s in cur_seq)})
                        cur_id = line[1:]
                        cur_seq = []
                    else:
                        cur_seq.append(line)
                if cur_id:
                    records.append({"id": cur_id, "length": sum(len(s) for s in cur_seq)})
            return ExecutionResult(success=True, output=records, metadata={"count": len(records), "parser": "fallback"})
        return ExecutionResult(success=False, error="Biopython is required for this format (run: pip install biopython)", status=AvailabilityStatus.SOFTWARE_NOT_FOUND)


def register_bio_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="blast.search",
            version="1.0.0",
            category=CapabilityCategory.BIO,
            description="Run BLAST sequence similarity search via local BLAST+ or NCBI REST service.",
            input_schema={"sequence": "string", "program": "string?", "database": "string?"},
            output_schema={"output": "string"},
            permissions=["read_workspace"],
            documentation="Executes nucleotide or protein sequence alignment.",
        ),
        handler=_blast_handler,
        health_checker=_check_bio_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="ncbi.query",
            version="1.0.0",
            category=CapabilityCategory.BIO,
            description="Query NCBI Entrez database for proteins, nucleotides or PubMed identifiers.",
            input_schema={"term": "string", "db": "string?"},
            output_schema={"ids": "list"},
            permissions=["read_workspace"],
            documentation="Queries NCBI E-utilities.",
        ),
        handler=_ncbi_query_handler,
        health_checker=_check_bio_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="biopython.parse",
            version="1.0.0",
            category=CapabilityCategory.BIO,
            description="Parse biological sequence files (FASTA, GenBank, PDB).",
            input_schema={"path": "string", "format": "string?"},
            output_schema={"records": "list"},
            permissions=["read_workspace"],
            documentation="Extracts biological sequence records from files.",
        ),
        handler=_biopython_parse_handler,
        health_checker=_check_bio_health,
    ))
