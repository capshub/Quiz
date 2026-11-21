import csv
import io

from django.db import transaction

from .models import Chapter, Question

FIELDS = ["chapter", "question", "option_a", "option_b", "option_c", "option_d", "correct", "explanation"]
REQUIRED_HEADERS = ["chapter", "question", "option_a", "option_b", "correct", "explanation"]
SAMPLE_ROWS = [
    ["Basics", "What is 2 + 3?", "4", "5", "6", "", "b", "Adding 2 and 3 gives 5."],
    ["Basics", "Which keyword defines a function in Python?", "func", "def", "lambda", "define", "b",
     "def introduces a function definition."],
]
TRUE = {"1", "true", "yes", "y"}
FALSE = {"0", "false", "no", "n"}


def norm(s):
    return " ".join((s or "").split()).lower()


def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def parse_text(text):
    """Return list of (line_number, dict). Raises ValueError on bad headers."""
    text = text.lstrip("\ufeff")
    first = text.splitlines()[0] if text.strip() else ""
    delim = max([",", ";", "\t"], key=first.count)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = [norm(h).replace(" ", "_") for h in (reader.fieldnames or [])]
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise ValueError("Missing column(s): " + ", ".join(missing))
    reader.fieldnames = headers
    rows = []
    for row in reader:
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue
        rows.append((reader.line_num, row))
    return rows


def build_plan(course, rows, default_chapter=None):
    chapters = {norm(c.title): c for c in course.chapters.all()}
    seen, plan = set(), []
    for line, row in rows:
        r = {k: (row.get(k) or "").strip() for k in FIELDS}
        title = " ".join(r["chapter"].split())
        errors = []
        if not title:
            if default_chapter:
                title = default_chapter.title
            else:
                errors.append("chapter is required")
        for f in ("question", "option_a", "option_b", "explanation"):
            if not r[f]:
                errors.append(f"{f} is required")
        correct = r["correct"].lower()
        if correct not in ("a", "b", "c", "d"):
            errors.append("correct must be a, b, c or d")
        elif not r[f"option_{correct}"]:
            errors.append(f"correct points to empty option_{correct}")
        active = None
        raw_active = (row.get("is_active") or "").strip().lower()
        if raw_active:
            if raw_active in TRUE:
                active = True
            elif raw_active in FALSE:
                active = False
            else:
                errors.append("is_active must be 1/0 or yes/no")
        key = (norm(title), norm(r["question"]))
        if not errors and key in seen:
            errors.append("duplicate question in this file")
        seen.add(key)
        item = {"line": line, "chapter": title, "text": r["question"], "status": "reject", "reason": "; ".join(errors)}
        if not errors:
            data = {k: r[k] for k in ("option_a", "option_b", "option_c", "option_d", "explanation")}
            data["correct"] = correct
            if active is not None:
                data["is_active"] = active
            item["data"] = data
            chapter = chapters.get(norm(title))
            existing = Question.objects.filter(chapter=chapter, text=r["question"]).first() if chapter else None
            if existing is None:
                item["status"] = "add"
            else:
                changed = any(getattr(existing, k) != v for k, v in data.items())
                item["status"] = "update" if changed else "unchanged"
        plan.append(item)
    return plan


def plan_counts(plan):
    counts = {"add": 0, "update": 0, "unchanged": 0, "reject": 0}
    for p in plan:
        counts[p["status"]] += 1
    return counts


@transaction.atomic
def apply_plan(course, plan):
    chapters = {norm(c.title): c for c in course.chapters.all()}
    next_order = max([c.order for c in chapters.values()], default=0)
    counts = {"add": 0, "update": 0}
    for p in plan:
        if p["status"] not in ("add", "update"):
            continue
        key = norm(p["chapter"])
        chapter = chapters.get(key)
        if chapter is None:
            next_order += 1
            chapter = Chapter.objects.create(course=course, title=p["chapter"], order=next_order)
            chapters[key] = chapter
        data = dict(p["data"])
        if p["status"] == "add":
            data.setdefault("is_active", True)
            Question.objects.create(chapter=chapter, text=p["text"], **data)
        else:
            Question.objects.filter(chapter=chapter, text=p["text"]).update(**data)
        counts[p["status"]] += 1
    return counts


def write_csv(response, questions=None):
    response.write("\ufeff")
    w = csv.writer(response)
    if questions is None:
        w.writerow(FIELDS)
        w.writerows(SAMPLE_ROWS)
        return response
    w.writerow(FIELDS + ["is_active"])
    for q in questions:
        w.writerow([q.chapter.title, q.text, q.option_a, q.option_b, q.option_c, q.option_d,
                    q.correct, q.explanation, 1 if q.is_active else 0])
    return response
