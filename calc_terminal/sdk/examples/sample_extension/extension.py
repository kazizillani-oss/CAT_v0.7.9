"""
Sample DevTools Extension implementation.
"""

from calc_terminal.sdk import (
    Extension,
    ExtensionManifest,
    CommandDefinition,
    ToolDefinition,
    register_command,
    register_tool,
)


class SampleDevToolsExtension(Extension):
    def on_init(self) -> None:
        self.logger.info("Initializing Sample DevTools Extension...")

    def on_load(self) -> None:
        self.logger.info("Sample DevTools Extension loaded.")

        # Register slash command /sampledev
        def _handle_sample(arg: str):
            return f"Sample DevTools active! Received argument: {arg or 'none'}"

        register_command(
            CommandDefinition(
                name="/sampledev",
                description="Demo command from Sample DevTools extension",
                handler=_handle_sample,
                category="sample",
            )
        )

        # Register tool
        def _sample_tool(query: str):
            return f"Sample tool executed query: {query}"

        register_tool(
            ToolDefinition(
                name="sample_devtools_tool",
                description="Sample tool provided by DevTools extension",
                handler=_sample_tool,
            )
        )


def create_extension_instance() -> Extension:
    manifest = ExtensionManifest(
        id="sample_devtools",
        name="Sample DevTools",
        version="1.0.0",
        description="Demonstration extension built with CAT Developer SDK",
        author="Google Deepmind CAT Team",
        entry_point="extension.py",
    )
    return SampleDevToolsExtension(manifest)

