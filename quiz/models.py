from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

LETTERS = ("a", "b", "c", "d")


class Course(models.Model):
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["course", "order", "id"]
        constraints = [models.UniqueConstraint(fields=["course", "title"], name="uniq_chapter_title_per_course")]

    def __str__(self):
        return f"{self.course.title} / {self.title}"


class Question(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500, blank=True)
    option_d = models.CharField(max_length=500, blank=True)
    correct = models.CharField(max_length=1, choices=[(l, l.upper()) for l in LETTERS])
    explanation = models.TextField()
    is_active = models.BooleanField(default=True, help_text="Untick to retire a question instead of deleting it.")

    class Meta:
        ordering = ["chapter", "id"]
        constraints = [models.UniqueConstraint(fields=["chapter", "text"], name="uniq_question_text_per_chapter")]

    def __str__(self):
        return self.text[:80]

    def options(self):
        return [(l, getattr(self, f"option_{l}")) for l in LETTERS if getattr(self, f"option_{l}")]

    def option_text(self, letter):
        return getattr(self, f"option_{letter}", "") if letter in LETTERS else ""

    def clean(self):
        if self.correct in LETTERS and not self.option_text(self.correct):
            raise ValidationError({"correct": "The correct answer must point to a filled option."})


class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment")]


class QuestionStat(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    times_attempted = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    last_correct = models.BooleanField(null=True, blank=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "question"], name="uniq_stat")]


class Attempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    wrong_first = models.BooleanField(default=False)
    size = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]


class AttemptQuestion(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="items")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    selected = models.CharField(max_length=1, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["attempt", "position"], name="uniq_attempt_position")]

    @property
    def selected_text(self):
        return self.question.option_text(self.selected)

    @property
    def correct_text(self):
        return self.question.option_text(self.question.correct)
