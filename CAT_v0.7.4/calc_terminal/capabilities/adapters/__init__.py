"""
CAT Capability Adapters package.
Exposes concrete handlers registered into capability_bus.
"""

from .filesystem import register_filesystem_capabilities
from .terminal import register_terminal_capabilities
from .python_exec import register_python_capabilities
from .git_adapter import register_git_capabilities
from .browser_adapter import register_browser_capabilities
from .jupyter_adapter import register_jupyter_capabilities
from .ml_frameworks import register_ml_capabilities
from .bioinformatics import register_bio_capabilities
from .structural_bio import register_structural_bio_capabilities
from .scientific_comp import register_scientific_capabilities
from .platforms import register_platform_capabilities
from .quantum_adapter import register_quantum_capabilities


def register_all_adapters(bus):
    """Register all built-in capabilities into the given CapabilityBus."""
    register_filesystem_capabilities(bus)
    register_terminal_capabilities(bus)
    register_python_capabilities(bus)
    register_git_capabilities(bus)
    register_browser_capabilities(bus)
    register_jupyter_capabilities(bus)
    register_ml_capabilities(bus)
    register_bio_capabilities(bus)
    register_structural_bio_capabilities(bus)
    register_scientific_capabilities(bus)
    register_platform_capabilities(bus)
    register_quantum_capabilities(bus)
