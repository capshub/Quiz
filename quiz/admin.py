from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.contrib.admin.utils import unquote

from . import csvio
from .models import Attempt, Chapter, Course, Enrollment, Question, QuestionStat


class CsvAdminMixin:
    level = "course"
    change_form_template = "admin/quiz/change_form_csv.html"

    def _name(self, suffix):
        return f"quiz_{self.level}_{suffix}"

    def get_urls(self):
        wrap = self.admin_site.admin_view
        custom = [
            path("<path:object_id>/import/", wrap(self.import_view), name=self._name("import")),
            path("<path:object_id>/template/", wrap(self.template_view), name=self._name("template")),
            path("<path:object_id>/export/", wrap(self.export_view), name=self._name("export")),
        ]
        return custom + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra = dict(extra_context or {})
        for suffix in ("import", "template", "export"):
            extra[f"{suffix}_url"] = reverse(f"admin:{self._name(suffix)}", args=[object_id])
        return super().change_view(request, object_id, form_url, extra)

    def _obj(self, request, object_id):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        return obj

    def _scope(self, obj):
        return (obj, None) if self.level == "course" else (obj.course, obj)

    def import_view(self, request, object_id):
        obj = self._obj(request, object_id)
        course, default = self._scope(obj)
        ctx = {**self.admin_site.each_context(request), "opts": self.model._meta, "original": obj,
               "title": "Import questions from CSV", "back_url": reverse(f"admin:quiz_{self.level}_change", args=[obj.pk])}
        if request.method == "POST":
            try:
                if "payload" in request.POST:
                    plan = csvio.build_plan(course, csvio.parse_text(request.POST["payload"]), default)
                    done = csvio.apply_plan(course, plan)
                    messages.success(request, f"Imported: {done['add']} added, {done['update']} updated.")
                    return redirect(ctx["back_url"])
                upload = request.FILES.get("file")
                if not upload:
                    messages.error(request, "Choose a CSV file first.")
                else:
                    text = csvio.decode(upload.read())
                    plan = csvio.build_plan(course, csvio.parse_text(text), default)
                    ctx.update(plan=plan, counts=csvio.plan_counts(plan), payload=text)
            except ValueError as exc:
                messages.error(request, str(exc))
        return TemplateResponse(request, "admin/quiz/import.html", ctx)

    def template_view(self, request, object_id):
        self._obj(request, object_id)
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="questions-template.csv"'
        return csvio.write_csv(resp)

    def export_view(self, request, object_id):
        obj = self._obj(request, object_id)
        qs = Question.objects.select_related("chapter").order_by("chapter__order", "chapter_id", "id")
        qs = qs.filter(chapter__course=obj) if self.level == "course" else qs.filter(chapter=obj)
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="questions-{self.level}-{obj.pk}.csv"'
        return csvio.write_csv(resp, qs)


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1


@admin.register(Course)
class CourseAdmin(CsvAdminMixin, admin.ModelAdmin):
    level = "course"
    list_display = ("title", "is_active")
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(CsvAdminMixin, admin.ModelAdmin):
    level = "chapter"
    list_display = ("title", "course", "order")
    list_filter = ("course",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("short_text", "chapter", "correct", "is_active")
    list_filter = ("chapter__course", "chapter", "is_active")
    search_fields = ("text",)

    @admin.display(description="Question")
    def short_text(self, obj):
        return obj.text[:80]


admin.site.register(Enrollment)
admin.site.register(QuestionStat)
admin.site.register(Attempt)
