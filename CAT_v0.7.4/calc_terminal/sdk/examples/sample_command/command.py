"""
Sample Standalone Command Module.
"""

from calc_terminal.sdk import command


@command(name="/echosdk", description="Echo back input via SDK command decorator", category="sample")
def handle_echosdk(arg: str) -> str:
    return f"SDK Echo: {arg or 'Empty input'}"

