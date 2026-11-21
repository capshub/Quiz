from django.core.management.base import BaseCommand

from quiz.backup import make_backup, prune_backups


class Command(BaseCommand):
    help = "Write a consistent copy of the SQLite database and prune old copies."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=14)

    def handle(self, *args, **opts):
        dest = make_backup()
        prune_backups(opts["keep"])
        self.stdout.write(f"Backup written: {dest}")
