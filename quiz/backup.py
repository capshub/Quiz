import sqlite3

from django.conf import settings
from django.utils import timezone


def make_backup(dest_dir=None):
    dest_dir = dest_dir or settings.BACKUP_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"quiz-{timezone.now():%Y%m%d-%H%M%S}.sqlite3"
    src = sqlite3.connect(settings.DATABASES["default"]["NAME"])
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


def prune_backups(keep=14, dest_dir=None):
    dest_dir = dest_dir or settings.BACKUP_DIR
    files = sorted(dest_dir.glob("quiz-*.sqlite3"))
    for old in files[:-keep] if keep > 0 else []:
        old.unlink()
