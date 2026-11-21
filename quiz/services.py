import random

from django.db import transaction
from django.utils import timezone

from .models import Attempt, AttemptQuestion, QuestionStat

QUIZ_SIZE = 20


def chapter_summary(user, chapter):
    ids = list(chapter.questions.filter(is_active=True).values_list("id", flat=True))
    stats = {s.question_id: s for s in QuestionStat.objects.filter(user=user, question_id__in=ids)}
    total = len(ids)
    attended = sum(1 for i in ids if i in stats and stats[i].times_attempted > 0)
    correct = sum(1 for i in ids if i in stats and stats[i].last_correct)
    rounds = min((stats[i].times_attempted if i in stats else 0) for i in ids) if ids else 0
    return {
        "chapter": chapter, "total": total, "attended": attended, "correct": correct, "rounds": rounds,
        "progress": attended * 100 // total if total else 0,
        "score": round(correct * 100 / total) if total else 0,
        "quizzes": Attempt.objects.filter(user=user, chapter=chapter, completed_at__isnull=False).count(),
        "open": Attempt.objects.filter(user=user, chapter=chapter, completed_at__isnull=True).exists(),
    }


def course_summary(user, course):
    chapters = [chapter_summary(user, c) for c in course.chapters.all()]
    total = sum(c["total"] for c in chapters)
    attended = sum(c["attended"] for c in chapters)
    correct = sum(c["correct"] for c in chapters)
    rounds = [c["rounds"] for c in chapters if c["total"]]
    recent = list(
        Attempt.objects.filter(user=user, chapter__course=course, completed_at__isnull=False)
        .order_by("-completed_at")[:10]
    )
    recent.reverse()
    return {
        "course": course, "chapters": chapters,
        "progress": attended * 100 // total if total else 0,
        "score": round(correct * 100 / total) if total else 0,
        "rounds": min(rounds) if rounds else 0,
        "quizzes": sum(c["quizzes"] for c in chapters),
        "recent": [{"label": a.completed_at.strftime("%d %b"), "pct": round(a.score * 100 / a.size) if a.size else 0} for a in recent],
        "chart_id": f"chart-{course.id}",
    }


def select_questions(user, chapter, wrong_first=False, size=QUIZ_SIZE):
    questions = list(chapter.questions.filter(is_active=True))
    stats = {s.question_id: s for s in QuestionStat.objects.filter(user=user, question__chapter=chapter)}

    def key(q):
        s = stats.get(q.id)
        n = s.times_attempted if s else 0
        wrong = 0 if (wrong_first and s is not None and s.last_correct is False) else 1
        return (n, wrong, random.random())

    return sorted(questions, key=key)[:size]


@transaction.atomic
def start_attempt(user, chapter, wrong_first=False):
    open_attempt = Attempt.objects.filter(user=user, chapter=chapter, completed_at__isnull=True).first()
    if open_attempt:
        return open_attempt
    picked = select_questions(user, chapter, wrong_first)
    if not picked:
        return None
    attempt = Attempt.objects.create(user=user, chapter=chapter, wrong_first=wrong_first, size=len(picked))
    AttemptQuestion.objects.bulk_create(
        [AttemptQuestion(attempt=attempt, question=q, position=i + 1) for i, q in enumerate(picked)]
    )
    return attempt


@transaction.atomic
def record_answer(item, selected):
    if item.selected:
        return item
    now = timezone.now()
    item.selected = selected
    item.is_correct = selected == item.question.correct
    item.answered_at = now
    item.save()
    stat, _ = QuestionStat.objects.get_or_create(user=item.attempt.user, question=item.question)
    stat.times_attempted += 1
    stat.times_correct += 1 if item.is_correct else 0
    stat.last_correct = item.is_correct
    stat.last_attempted_at = now
    stat.save()
    attempt = item.attempt
    if not attempt.items.filter(selected="").exists():
        attempt.completed_at = now
        attempt.score = attempt.items.filter(is_correct=True).count()
        attempt.save()
    return item


def reset_progress(user, chapters):
    QuestionStat.objects.filter(user=user, question__chapter__in=chapters).delete()
