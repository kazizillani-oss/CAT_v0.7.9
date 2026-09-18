"""Headless Textual pilot: widget-level attachment behaviors."""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, ".")


async def main():
    from calc_terminal.ui.attachments import AttachmentBar
    if AttachmentBar is None:
        print("Textual unavailable — skip")
        return True

    from textual.app import App
    from textual.containers import Vertical

    class T(App):
        def compose(self):
            yield Vertical(AttachmentBar())

    app = T()
    async with app.run_test() as pilot:
        bar = app.query_one(AttachmentBar)
        # 1. directories are rejected -> no chip, returns None
        d = tempfile.mkdtemp(prefix="cct-dir-")
        rc = bar.add_file(d, source="drag_and_drop")
        await pilot.pause()
        assert rc is None, "directory was attached!"
        assert len(list(bar.children)) == 0, "dir chip mounted"
        print("  ✓ directory rejected at widget level")

        # 2. real file attaches and reports source
        fd, p = tempfile.mkstemp(suffix=".txt")
        os.write(fd, b"hello import")
        os.close(fd)
        chip_id = bar.add_file(p, source="drag_and_drop")
        await pilot.pause(0.3)
        assert chip_id is not None
        att = bar.get_attachment(chip_id)
        assert att is not None and att.source == "drag_and_drop"
        print("  ✓ file chip mounted with source recorded:", att.source)

        # 3. double-click posts the event the app handles
        from calc_terminal.ui.events import AttachmentChipDoubleClicked
        received = []
        original_post = bar.post_message
        def spy(msg):
            if isinstance(msg, AttachmentChipDoubleClicked):
                received.append(msg)
            return original_post(msg)
        bar.post_message = spy
        bar._double_clicked(chip_id)
        await pilot.pause(0.1)
        assert received and received[0].path == p
        print("  ✓ double-click dispatches AttachmentChipDoubleClicked")

    return True


ok = asyncio.run(main())
print("PILOT OK" if ok else "FAILED")
