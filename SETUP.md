# Personal Quiz System - Setup

## Part 1: Your laptop (Windows / Linux / macOS)

Needs Python 3.12+ and Git (optional).

1. Unzip the project and open a terminal inside the `quiz-system` folder.
2. Create a virtual environment and install packages
   - Windows:  `py -m venv .venv`  then  `.venv\Scripts\activate`
   - Linux/Mac: `python3 -m venv .venv`  then  `source .venv/bin/activate`
   - then: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` (keep DJANGO_DEBUG=1 for local use).
4. Create the database tables (first time only creates the migration files):
   - `python manage.py makemigrations quiz`
   - `python manage.py migrate`
5. `python manage.py createsuperuser`
6. Run tests: `python manage.py test`
7. `python manage.py runserver`  (other devices on your Wi-Fi: `python manage.py runserver 0.0.0.0:8000`
   and add your laptop IP to DJANGO_ALLOWED_HOSTS in .env)
8. Open http://127.0.0.1:8000/admin/ -> add a Course (and optionally chapters).
9. On the course page click "Download template", fill it, then "Import CSV" -> preview -> confirm.
   A ready sample is in `sample_questions.csv`.
10. Create learner users in admin (Users -> Add). Log in at http://127.0.0.1:8000/ , Subscribe, Start 20.
11. Commit `quiz/migrations/` to Git. Backup: `python manage.py backup_db` (files in ./backups).

## Part 2: Oracle Cloud Always Free VM (Docker + Caddy)

1. Create an Ubuntu VM (Compute -> Instances). Save the SSH key. Note the public IP.
   Make the IP reserved/static so it does not change.
2. Get a hostname pointing at that IP (HTTPS certificates need a name, not a bare IP).
   Free option: duckdns.org -> create e.g. myquiz.duckdns.org -> set it to the VM IP.
3. Open ports 80 and 443 in OCI: Networking -> VCN -> Security List -> add Ingress rules
   (source 0.0.0.0/0, TCP, destination ports 80 and 443).
4. SSH in, then open the same ports in the VM firewall (Oracle Ubuntu images block them):
       sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
       sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
       sudo netfilter-persistent save
   (if that command is missing: sudo apt install -y iptables-persistent)
5. Install Docker:
       curl -fsSL https://get.docker.com | sudo sh
       sudo usermod -aG docker $USER      # log out and back in
6. Copy the project to the VM (git clone your repo, or: scp -r quiz-system ubuntu@IP:~/quiz).
   Make sure quiz/migrations/ (from your laptop step 4) is included.
7. In ~/quiz create `.env`:
       DJANGO_SECRET_KEY=<long random string>
       DJANGO_ALLOWED_HOSTS=myquiz.duckdns.org
       DJANGO_CSRF_TRUSTED_ORIGINS=https://myquiz.duckdns.org
       DJANGO_ADMIN_URL=my-secret-admin/
       DOMAIN=myquiz.duckdns.org
   Generate a key: python3 -c "import secrets; print(secrets.token_urlsafe(50))"
8. `docker compose up -d --build`  (Caddy fetches the HTTPS certificate automatically)
9. `docker compose exec app python manage.py createsuperuser`
10. Visit https://myquiz.duckdns.org/ and https://myquiz.duckdns.org/my-secret-admin/
11. Nightly backup (crontab -e):
       0 2 * * * cd ~/quiz && docker compose exec -T app python manage.py backup_db
    Copies land in ~/quiz/data/backups. Copy them off the VM now and then (scp, or OCI Object Storage).
12. Update later: git pull && docker compose up -d --build
    Move your laptop data: stop the app, copy db.sqlite3 to ~/quiz/data/db.sqlite3, start again.
    Logs: docker compose logs -f app
