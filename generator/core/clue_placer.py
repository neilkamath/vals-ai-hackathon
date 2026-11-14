"""Places the buried clues and filler files in the task's data directory."""


def place(events, filler):
    files = dict(filler)
    for e in events:
        for name, text in e.clue_files(e.clue).items():
            files[name] = files[name] + "\n" + text if name in files and name.endswith(".txt") else text
    return files
