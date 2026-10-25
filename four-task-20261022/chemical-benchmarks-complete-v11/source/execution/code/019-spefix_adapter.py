"""Explicit 2025 SPE-output adapter, never an author-native tokenizer."""
from types import MethodType

NAME = "peptideclm2025_spe_cccc_to_cc_cc_v1"


def adapt_tokens(tokens, vocab):
    """Only split the verified absent SPE piece; leave every other piece alone."""
    if vocab.get("cc") != 92 or "cccc" in vocab:
        raise ValueError("Unexpected original vocabulary; adapter is not applicable")
    result = []
    for token in tokens:
        result.extend(["cc", "cc"] if token == "cccc" else [token])
    if "".join(result) != "".join(tokens):
        raise ValueError("Adapter must preserve the exact character string")
    return result


def patch_tokenizer(tokenizer):
    if hasattr(tokenizer, "_peptideclm2025_spefix"):
        raise ValueError("Adapter already applied")
    vocab = tokenizer.get_vocab()
    adapt_tokens([], vocab)
    original = tokenizer._tokenize

    def adapted(self, text):
        return adapt_tokens(original(text), vocab)

    tokenizer._tokenize = MethodType(adapted, tokenizer)
    tokenizer._peptideclm2025_spefix = NAME
    return tokenizer
