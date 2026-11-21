from django.contrib.auth import get_user_model
from django.test import TestCase

from . import csvio
from .models import Chapter, Course, Question
from .services import chapter_summary, record_answer, select_questions, start_attempt


def mk(chapter, n, **kw):
    return Question.objects.create(chapter=chapter, text=f"Q{n}", option_a="a", option_b="b",
                                   correct="a", explanation="because", **kw)


class QuizTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", password="x" * 12)
        self.course = Course.objects.create(title="C")
        self.ch = Chapter.objects.create(course=self.course, title="Ch", order=1)
        self.qs = [mk(self.ch, i) for i in range(25)]

    def test_quiz_size_and_progress(self):
        att = start_attempt(self.user, self.ch)
        self.assertEqual(att.size, 20)
        for item in att.items.all():
            record_answer(item, "a")
        att.refresh_from_db()
        self.assertEqual(att.score, 20)
        info = chapter_summary(self.user, self.ch)
        self.assertEqual(info["progress"], 80)
        self.assertEqual(info["rounds"], 0)

    def test_unattended_first(self):
        att = start_attempt(self.user, self.ch)
        first = {i.question_id for i in att.items.all()}
        for item in att.items.all():
            record_answer(item, "a")
        second = {q.id for q in select_questions(self.user, self.ch)}
        self.assertTrue(set(q.id for q in self.qs) - first <= second)

    def test_wrong_first(self):
        small = Chapter.objects.create(course=self.course, title="Small", order=2)
        qa, qb = mk(small, 100), mk(small, 101)
        att = start_attempt(self.user, small)
        for item in att.items.all():
            record_answer(item, "b" if item.question_id == qb.id else "a")
        got = select_questions(self.user, small, wrong_first=True, size=1)
        self.assertEqual(got[0].id, qb.id)


class ImportTests(TestCase):
    def test_import_routes_and_updates(self):
        course = Course.objects.create(title="C")
        text = ("chapter,question,option_a,option_b,option_c,option_d,correct,explanation\n"
                "One,Q1,a,b,,,a,e\nTwo,Q2,a,b,,,c,e\nOne,Q1,a,b,,,a,e\n")
        plan = csvio.build_plan(course, csvio.parse_text(text))
        self.assertEqual(csvio.plan_counts(plan)["add"], 1)
        self.assertEqual(csvio.plan_counts(plan)["reject"], 2)
        csvio.apply_plan(course, plan)
        self.assertEqual(Question.objects.count(), 1)
        plan = csvio.build_plan(course, csvio.parse_text(text.replace(",a,e\nTwo", ",b,e\nTwo", 1)))
        self.assertEqual(plan[0]["status"], "update")
