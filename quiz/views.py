from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .backup import make_backup
from .models import Attempt, Chapter, Course, Enrollment
from .services import chapter_summary, course_summary, record_answer, reset_progress, start_attempt


@login_required
def dashboard(request):
    enrolled = Enrollment.objects.filter(user=request.user, course__is_active=True).select_related("course")
    courses = [course_summary(request.user, e.course) for e in enrolled]
    available = Course.objects.filter(is_active=True).exclude(enrollment__user=request.user)
    return render(request, "quiz/dashboard.html", {"courses": courses, "available": available})


@login_required
@require_POST
def subscribe(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    Enrollment.objects.get_or_create(user=request.user, course=course)
    return redirect("dashboard")


@login_required
def start(request, chapter_id):
    chapter = get_object_or_404(Chapter, pk=chapter_id, course__is_active=True)
    if not Enrollment.objects.filter(user=request.user, course=chapter.course).exists():
        messages.error(request, "Subscribe to the course first.")
        return redirect("dashboard")
    open_attempt = Attempt.objects.filter(user=request.user, chapter=chapter, completed_at__isnull=True).first()
    if open_attempt:
        return redirect("attempt", attempt_id=open_attempt.pk)
    info = chapter_summary(request.user, chapter)
    full = info["total"] > 0 and info["attended"] == info["total"]
    if request.method == "POST":
        if full and not request.POST.get("confirm"):
            messages.error(request, "Please tick the confirmation to continue.")
        else:
            attempt = start_attempt(request.user, chapter, bool(request.POST.get("wrong_first")))
            if attempt is None:
                messages.error(request, "This chapter has no active questions yet.")
            else:
                return redirect("attempt", attempt_id=attempt.pk)
    return render(request, "quiz/start.html", {"chapter": chapter, "info": info, "full": full})


def _own_attempt(request, attempt_id):
    return get_object_or_404(Attempt.objects.select_related("chapter"), pk=attempt_id, user=request.user)


@login_required
def attempt_entry(request, attempt_id):
    attempt = _own_attempt(request, attempt_id)
    nxt = attempt.items.filter(selected="").order_by("position").first()
    if nxt is None:
        return redirect("summary", attempt_id=attempt.pk)
    return redirect("question", attempt_id=attempt.pk, pos=nxt.position)


@login_required
def question(request, attempt_id, pos):
    attempt = _own_attempt(request, attempt_id)
    items = list(attempt.items.select_related("question").order_by("position"))
    pending = next((i for i in items if not i.selected), None)
    item = next((i for i in items if i.position == pos), None)
    if item is None:
        raise Http404
    if not item.selected and pending and item.position != pending.position:
        return redirect("question", attempt_id=attempt.pk, pos=pending.position)
    if request.method == "POST" and not item.selected:
        choice = request.POST.get("choice", "")
        if choice in [l for l, _ in item.question.options()]:
            record_answer(item, choice)
        else:
            messages.error(request, "Pick an answer.")
        return redirect("question", attempt_id=attempt.pk, pos=pos)
    return render(request, "quiz/question.html", {
        "attempt": attempt, "item": item, "q": item.question, "total": len(items),
        "is_last": pos == len(items),
    })


@login_required
def summary(request, attempt_id):
    attempt = _own_attempt(request, attempt_id)
    if attempt.completed_at is None:
        return redirect("attempt", attempt_id=attempt.pk)
    items = attempt.items.select_related("question").order_by("position")
    return render(request, "quiz/summary.html", {"attempt": attempt, "items": items})


@login_required
@require_POST
def reset(request):
    scope, pk = request.POST.get("scope"), request.POST.get("id")
    if scope == "course":
        course = get_object_or_404(Course, pk=pk)
        full = course_summary(request.user, course)["progress"] == 100
        chapters = list(course.chapters.all())
    else:
        chapter = get_object_or_404(Chapter, pk=pk)
        full = chapter_summary(request.user, chapter)["progress"] == 100
        chapters = [chapter]
    if not full:
        messages.error(request, "Reset is only available at 100% progress.")
    else:
        reset_progress(request.user, chapters)
        messages.success(request, "Progress reset.")
    return redirect("dashboard")


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
def backup(request):
    dest = make_backup()
    return FileResponse(open(dest, "rb"), as_attachment=True, filename=dest.name)
