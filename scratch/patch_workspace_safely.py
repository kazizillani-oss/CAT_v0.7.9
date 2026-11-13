with open('calc_terminal/ui/workspace.py', 'r', encoding='utf-8', newline='') as f:
    text = f.read()

old_ws = """                ch = saved.get("composer_height")
                if ch:
                    from .composer import StickyComposer
                    try:
                        composer = self._composer or self.query_one(StickyComposer)
                        total_h = self.size.height or 24
                        # Never let restored height exceed 32% of window height in floating/compact view
                        max_allowed = max(5, int(total_h * 0.32))
                        safe_ch = min(int(ch), max_allowed)
                        self.call_after_refresh(
                            lambda comp=composer, h=safe_ch:
                            comp.set_explicit_height(h))
                    except Exception:
                        pass"""

new_ws = """                ch = saved.get("composer_height")
                if ch:
                    from .composer import StickyComposer
                    from .resizers import COMPOSER_MIN_HEIGHT
                    try:
                        composer = self._composer or self.query_one(StickyComposer)
                        total_h = self.size.height or 24
                        if int(ch) <= COMPOSER_MIN_HEIGHT:
                            self.call_after_refresh(
                                lambda comp=composer:
                                comp.set_explicit_height(None))
                        else:
                            max_allowed = max(COMPOSER_MIN_HEIGHT, int(total_h * 0.40))
                            safe_ch = max(COMPOSER_MIN_HEIGHT, min(int(ch), max_allowed))
                            self.call_after_refresh(
                                lambda comp=composer, h=safe_ch:
                                comp.set_explicit_height(h))
                    except Exception:
                        pass"""

if old_ws in text:
    text = text.replace(old_ws, new_ws, 1)
    with open('calc_terminal/ui/workspace.py', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print('workspace.py safely patched!')
    compile(open('calc_terminal/ui/workspace.py', 'r', encoding='utf-8').read(), 'calc_terminal/ui/workspace.py', 'exec')
    print('workspace.py syntax check OK')
else:
    print('old_ws block not found in workspace.py')

