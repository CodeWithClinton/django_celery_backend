# 🚀 Production Deployment Guide

## Django + Gunicorn + Nginx + Redis + Celery (Systemd Setup)

This guide walks you through deploying a **Django API with background tasks** on a Linux VPS using:

* **Django API** → runs as a **Gunicorn systemd service**
* **Redis** → runs as a **system service**
* **Celery Worker** → runs as a **systemd service**
* **Celery Beat** (optional) → runs as a **systemd service**
* **Nginx** → proxies HTTPS → Gunicorn
* **Background jobs flow** → Django → Redis → Celery executes

---

# 🏗 Architecture Overview

```
User → Nginx → Gunicorn → Django
                          ↓
                        Redis
                          ↓
                       Celery Worker
```

* Nginx handles HTTP/HTTPS
* Gunicorn runs your Django app
* Redis stores task queues
* Celery workers process background jobs

---

# 1️⃣ Generate SSH Key (For Droplet Access)

On your local machine:

```bash
ssh-keygen -t ed25519 -C "django-celery" -f django_celery
```

Upload the public key (`django_celery.pub`) to your VPS provider.

---

# 2️⃣ Install Required System Packages

SSH into your server and run:

```bash
sudo apt update
sudo apt -y install python3-venv python3-pip nginx redis-server
```

(Optional for PostgreSQL projects)

```bash
sudo apt -y install libpq-dev
```

---

# 🔥 Configure Firewall (Recommended)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

# 3️⃣ Project Structure Setup (Recommended Layout)

### Suggested Directory Structure

| Component           | Path                           |
| ------------------- | ------------------------------ |
| Project Code        | `/home/deploy/apps/myproject`  |
| Virtual Environment | `/home/deploy/venvs/myproject` |

---

### Create Deployment User

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
su - deploy
```

---

### Create Project Directories

```bash
mkdir -p ~/apps/myproject ~/venvs
python3 -m venv ~/venvs/myproject
source ~/venvs/myproject/bin/activate
```

Deploy your code via `git pull`, `scp`, or `rsync`, then:

```bash
cd ~/apps/myproject
pip install -r requirements.txt
```

---

# 4️⃣ Configure Django for Celery + Redis

## Install Celery + Redis Client

```bash
pip install celery redis
```

---

## Create `myproject/celery.py`

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

app = Celery("myproject")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

---

## Update `myproject/__init__.py`

```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

---

## Add Celery Config in `settings.py`

```python
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/1"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Lagos"
```

---

# 5️⃣ Configure Gunicorn with Systemd (Socket Activation)

This setup:

* Auto-starts Gunicorn
* Restarts if it crashes
* Integrates cleanly with Nginx
* Uses Unix socket (recommended)

---

## Create Gunicorn Socket File

```bash
sudo nano /etc/systemd/system/gunicorn.socket
```

```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

---

## Create Gunicorn Service File

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=deploy
Group=www-data
WorkingDirectory=/home/deploy/apps/myproject
ExecStart=/home/deploy/venvs/myproject/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          myproject.wsgi:application

[Install]
WantedBy=multi-user.target
```

⚠️ Update:

* `User`
* `WorkingDirectory`
* Gunicorn path
* `myproject.wsgi:application`

---

## Start & Enable Gunicorn

```bash
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
```

---

## Verify Socket

```bash
sudo systemctl status gunicorn.socket
file /run/gunicorn.sock
```

Test activation:

```bash
curl --unix-socket /run/gunicorn.sock localhost
```

Check logs:

```bash
sudo journalctl -u gunicorn
```

---

# 6️⃣ Configure Nginx as Reverse Proxy

Create Nginx config:

```bash
sudo nano /etc/nginx/sites-available/myproject
```

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }

    location /static/ {
        alias /home/deploy/apps/myproject/staticfiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/myproject /etc/nginx/sites-enabled
```

Allow access to home directory:

```bash
sudo chmod 711 /home/deploy
```

Test and restart:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

# 7️⃣ Secure & Enable Redis

Redis should **never be exposed publicly**.

Check config:

```bash
sudo nano /etc/redis/redis.conf
```

Ensure:

```
bind 127.0.0.1 ::1
protected-mode yes
```

Restart:

```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server
sudo systemctl status redis-server
```

---

# 8️⃣ Create Systemd Services for Celery

This ensures Celery:

* Runs forever
* Restarts on crash
* Starts on reboot

---

## A) Celery Worker Service

```bash
sudo nano /etc/systemd/system/celery.service
```

```ini
[Unit]
Description=Celery Worker Service
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=deploy
Group=www-data
WorkingDirectory=/home/deploy/apps/myproject
Environment="DJANGO_SETTINGS_MODULE=myproject.settings"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/deploy/venvs/myproject/bin/celery -A myproject worker --loglevel=INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## B) Celery Beat (Optional)

```bash
sudo nano /etc/systemd/system/celerybeat.service
```

```ini
[Unit]
Description=Celery Beat Service
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=deploy
Group=www-data
WorkingDirectory=/home/deploy/apps/myproject
Environment="DJANGO_SETTINGS_MODULE=myproject.settings"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/deploy/venvs/myproject/bin/celery -A myproject beat --loglevel=INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Reload & Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl start redis-server
sudo systemctl enable redis-server

sudo systemctl start celery
sudo systemctl enable celery

sudo systemctl start celerybeat
sudo systemctl enable celerybeat
```

---

## Monitor Services

Check status:

```bash
sudo systemctl status celery --no-pager
sudo systemctl status celerybeat --no-pager
```

View logs:

```bash
sudo journalctl -u celery -f
sudo journalctl -u celerybeat -f
```

---

# ✅ Final Production Checklist

* [x] Django working
* [x] Gunicorn socket activation working
* [x] Nginx proxying correctly
* [x] Redis secured (localhost only)
* [x] Celery worker running
* [x] Celery Beat running (if needed)
* [x] All services enabled on boot

---


<!-- 

The goal:

* **Django API** runs as a **Gunicorn systemd service**
* **Redis** runs as a **system service**
* **Celery worker** (and optionally **Celery Beat**) run as **systemd services**
* Nginx proxies HTTPS → Gunicorn
* Your background jobs go to Redis → Celery pulls and executes them

---
Generating an SSH key for access into the droplet

ssh-keygen -t ed25519 -C "django-celery" -f django_celery

## 1) Install system packages

```bash
sudo apt update
sudo apt -y install python3-venv python3-pip nginx redis-server
```

(Optional but common for Postgres)

```bash
sudo apt -y install libpq-dev
```

---


Firewall (recommended):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```


## 2) Setup your project (recommended layout)

Example:

* Code: `/home/deploy/apps/myproject`
* Virtualenv: `/home/deploy/venvs/myproject`

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
su - deploy

mkdir -p ~/apps/myproject ~/venvs
python3 -m venv ~/venvs/myproject
source ~/venvs/myproject/bin/activate
```

Deploy your code (git pull or scp/rsync), then:

```bash
cd ~/apps/myproject
pip install -r requirements.txt
```

---

## 3) Configure Django for Celery + Redis

### Install celery + redis client

```bash
pip install celery redis
```

### Add Celery config (typical)

In `myproject/celery.py`:

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

app = Celery("myproject")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

In `myproject/__init__.py`:

```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

In `settings.py` (Redis broker/result backend):

```python
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/1"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Lagos"
```

If you want periodic tasks (beat), you’ll add it later.




Configuring Gunicorn with systemd

You’ve confirmed that Gunicorn works. Now we’ll configure it to run automatically using systemd.

This setup:

    Starts Gunicorn automatically
    Restarts it if it crashes
    Uses socket-based activation
    Integrates with Nginx

7. Create a Gunicorn Socket File

sudo nano /etc/systemd/system/gunicorn.socket

Paste this:

[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target

Save and exit: Ctrl + S, then Ctrl + X
8. Create a Gunicorn Service File

sudo nano /etc/systemd/system/gunicorn.service

Paste this:

[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=clinton
Group=www-data
WorkingDirectory=/home/clinton/deploy-practice-ii
ExecStart=/home/clinton/deploy-practice-ii/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          review_summarizer.wsgi:application

[Install]
WantedBy=multi-user.target

⚠️ Important: Do NOT copy this blindly. You must update:

    User=clinton
    WorkingDirectory=...
    Path to gunicorn
    review_summarizer.wsgi:application

To match your own project.
9. Start and Enable the Gunicorn Socket

sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket

This ensures:

    Gunicorn starts automatically on boot
    It activates when Nginx sends a request

✅ At This Stage, You Have:

    Django tested and working
    Gunicorn tested
    systemd socket configured
    systemd service configured
    Gunicorn running in production mode

🔍 Verifying Gunicorn Socket Activation

Now that we’ve configured Gunicorn with systemd, we need to verify that everything is working correctly.
1. Check Gunicorn Socket Status

Run:

sudo systemctl status gunicorn.socket

You should see output similar to:

● gunicorn.socket - gunicorn socket
   Loaded: loaded (/etc/systemd/system/gunicorn.socket; enabled)
   Active: active (listening)
   Triggers: ● gunicorn.service
   Listen: /run/gunicorn.sock

This means the socket is active and waiting for connections.
2. Confirm the Socket File Exists

file /run/gunicorn.sock

Expected output:

/run/gunicorn.sock: socket

If this file is missing, Gunicorn was not set up correctly.
3. Troubleshooting Socket Issues

If the socket is not active or the file is missing, check the logs:

sudo journalctl -u gunicorn.socket

Then re-open and verify:

sudo nano /etc/systemd/system/gunicorn.socket

Fix any errors before continuing.
🧪 Testing Socket Activation

Gunicorn is currently configured to start only when a request hits the socket. That means it won’t be running yet.

Let’s confirm that.
4. Check Gunicorn Service Status

sudo systemctl status gunicorn

You should see something like:

Active: inactive (dead)
TriggeredBy: ● gunicorn.socket

This is expected.
5. Trigger Gunicorn Using curl

Now we’ll manually trigger the socket.

curl --unix-socket /run/gunicorn.sock localhost

If everything is working, you’ll see your Django app’s HTML output in the terminal.

This means: ✅ Socket is working ✅ Gunicorn started automatically ✅ Django app is being served
6. Confirm Gunicorn Is Now Running

sudo systemctl status gunicorn

You should now see:

Active: active (running)

This confirms Gunicorn was started by the socket.
🛠️ Troubleshooting Gunicorn

If something goes wrong, check Gunicorn logs:

sudo journalctl -u gunicorn

7. Reload systemd If You Make Changes

If you edit the Gunicorn service or socket files, you must reload systemd:

sudo systemctl daemon-reload
sudo systemctl restart gunicorn

✅ At This Point, You Have:

    Gunicorn socket activation working
    Gunicorn auto-starting on demand
    Django app responding correctly
    Logs accessible for debugging

🌐 Configure Nginx as a Reverse Proxy for Gunicorn

Now that Gunicorn is running correctly, we need Nginx to handle incoming web traffic and forward requests to Gunicorn.

Nginx will:

    Accept requests from users (HTTP)
    Forward them to Gunicorn
    Serve static files
    Improve security and performance

1. Create an Nginx Server Block

Create a new Nginx configuration file:

sudo nano /etc/nginx/sites-available/myproject

Paste the following configuration:

server {
    listen 80;
    server_name server_domain_or_IP;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }

    location /static/ {
        alias /home/clinton/deploy-practice-ii/staticfiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}

⚠️ Important: Do NOT copy this blindly. You must update:

    server_name
    Your username (clinton)
    Your project directory path

Save and exit: Ctrl + S, then Ctrl + X
2. Enable the Nginx Configuration

Create a symbolic link to enable the site:

sudo ln -s /etc/nginx/sites-available/myproject /etc/nginx/sites-enabled

3. Allow Nginx to Access Your Home Directory

sudo chmod 711 /home/clinton

    Replace clinton with your actual username.

This allows Nginx to access your project files.
4. Test Nginx Configuration

Before restarting Nginx, always test for syntax errors:

sudo nginx -t

If everything looks good, restart Nginx:

sudo systemctl restart nginx


---

## 4) Secure and enable Redis (basic safe default)

Redis is usually safe if it only listens locally.

Check:

```bash
sudo nano /etc/redis/redis.conf
```

Ensure:

* `bind 127.0.0.1 ::1`
* `protected-mode yes`

Restart:

```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server
sudo systemctl status redis-server
```

---


## 4) Create systemd services for Celery (this is the real production part)

This is what makes Celery run *forever* and restart on crash/reboot.

### A) Celery Worker service

Create:

```bash
sudo nano /etc/systemd/system/celery.service
```

Paste (adjust paths + project name):

```ini
[Unit]
Description=Celery Worker Service
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=deploy
Group=www-data
WorkingDirectory=/var/www/myapp/backend
Environment="DJANGO_SETTINGS_MODULE=your_project.settings"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/var/www/myapp/backend/venv/bin/celery -A your_project worker --loglevel=INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### B) Celery Beat service (optional but common)

Create:

```bash
sudo nano /etc/systemd/system/celerybeat.service
```

Paste:

```ini
[Unit]
Description=Celery Beat Service
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=deploy
Group=www-data
WorkingDirectory=/var/www/myapp/backend
Environment="DJANGO_SETTINGS_MODULE=your_project.settings"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/var/www/myapp/backend/venv/bin/celery -A your_project beat --loglevel=INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and start them

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Start Redis (if not already):

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

Start Celery:

```bash
sudo systemctl start celery
sudo systemctl enable celery
```

Start Beat (if you created it):

```bash
sudo systemctl start celerybeat
sudo systemctl enable celerybeat
```

Check status:

```bash
sudo systemctl status celery --no-pager
sudo systemctl status celerybeat --no-pager
```

Logs:

```bash
sudo journalctl -u celery -f
sudo journalctl -u celerybeat -f
```

---



 -->
