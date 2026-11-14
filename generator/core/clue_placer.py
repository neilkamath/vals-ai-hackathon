"""Places the buried clue for each change event."""


def place(kind, events):
    if kind == "changelog":
        return {"CHANGELOG.txt": "\n".join(e.clue_text() for e in events) + "\n"}
    raise ValueError(f"unknown clue kind: {kind}")
