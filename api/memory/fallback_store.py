import json


def recall(session):
    return json.loads(session.memory)


def remember(session, entry):
    entries = recall(session)
    entries.append(entry)
    session.memory = json.dumps(entries[-20:], ensure_ascii=False)
