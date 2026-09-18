sp = "I'mheretoassistyouwithcodingandscientifictasks"
apos_idx = sp.rfind("'")
before = sp[:apos_idx]
contraction = sp[apos_idx:]
print(f"before: {before!r}")
print(f"contraction: {contraction!r}")

from calc_terminal.agent_runtime import _segment_words
if before and len(before) > 5:
    words = _segment_words(before)
    before = " ".join(words) if len(words) > 1 else before
    print(f"before after seg: {before!r}")

contraction_word = contraction[1:] if len(contraction) > 1 else ""
if contraction_word and len(contraction_word) > 5:
    words = _segment_words(contraction_word)
    contraction = "'" + (" ".join(words) if len(words) > 1 else contraction_word)
    print(f"contraction after seg: {contraction!r}")

print(f"result: {before + contraction!r}")
