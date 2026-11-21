from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("subscribe/<int:course_id>/", views.subscribe, name="subscribe"),
    path("chapter/<int:chapter_id>/start/", views.start, name="start"),
    path("attempt/<int:attempt_id>/", views.attempt_entry, name="attempt"),
    path("attempt/<int:attempt_id>/q/<int:pos>/", views.question, name="question"),
    path("attempt/<int:attempt_id>/summary/", views.summary, name="summary"),
    path("reset/", views.reset, name="reset"),
    path("backup/", views.backup, name="backup"),
]
