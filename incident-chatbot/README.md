# Incident Assist — Helix SRE Chatbot Prototype

A proof-of-concept AI assistant for incident management, built to demonstrate
the **hybrid model** proposed for the Helix SRE project: predefined
quick-question suggestions + free-text queries, both answered by pulling
summarized answers and next steps from historical tickets and KB docs.

This is a **demo-quality prototype**, meant to show the concept end-to-end
and support a conversation with your manager about a production build — not
a production system itself. See "From prototype to production" below for
what changes.

---

## What it does

- **Predefined suggestions (popup):** derived automatically from the most
  common ticket categories in the sample data — mirrors "suggestions derived
  from previous queries and stored documents" in the original proposal.
- **Free-text question box:** user describes a symptom or error; the backend
  searches historical tickets + KB docs and returns:
  - a summarized answer (what likely happened / how it was resolved)
  - a confidence level (high / medium / low)
  - suggested next steps (pulled from the matched ticket's resolution steps)
  - the source tickets/docs it drew from, for transparency and traceability
- **No external API or internet dependency.** Retrieval uses TF-IDF +
  cosine similarity (scikit-learn), so it runs fully offline — useful given
  the office network's outbound restrictions.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + Flask | Lightweight, matches Python skills already in use (JWT/Flask ticket in the sample data), easy to later wrap with Jira/JSM REST calls |
| Retrieval | scikit-learn TF-IDF + cosine similarity | No API key, no GPU, fast, deterministic, explainable — good for a first demo |
| Frontend | Plain HTML/CSS/JS served by Flask | Zero build step, runs anywhere Python runs, easy to screen-share/demo |
| Data | Synthetic JSON (`data/tickets.json`, `data/kb_docs.json`) | Stand-ins for real historical JSM tickets/KB articles; swap for exports later |

## Project structure

```
incident-chatbot/
├── app.py                 # Flask backend + retrieval/answer logic
├── requirements.txt
├── data/
│   ├── tickets.json        # 21 synthetic historical incident tickets
│   └── kb_docs.json         # 8 synthetic KB articles
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

## Running it locally

```bash
cd incident-chatbot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in a browser.

## API endpoints (for reference / future integration)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/suggestions` | Returns predefined popup questions |
| POST | `/api/query` | Body: `{"query": "..."}` → returns summary, confidence, sources, next steps |
| GET | `/api/stats` | Returns indexed ticket/doc counts + categories (useful in a demo to show what it's drawing from) |

---

## How this maps to the original proposal

- **Hybrid model (predefined Qs + user queries):** implemented — sidebar
  chips are predefined, the composer box handles free text, both go through
  the same retrieval/answer pipeline.
- **Instant answers pulling from data docs / historical tickets:** implemented
  via the TF-IDF search over `tickets.json` + `kb_docs.json`.
- **Summarized answers + proposed next steps:** implemented — each answer
  includes a plain-language summary and a short list of next steps sourced
  from the matched ticket's actual resolution steps.
- **Three-sprint iteration:** see roadmap in the companion design document.

## From prototype to production

This demo intentionally skips things a production rollout would need:

1. **Real data, not synthetic.** Pull historical tickets via the Jira REST
   API (`/rest/api/3/search` with JQL against `HLXSREINP`) instead of a
   static JSON file. Requires read access — no admin permissions needed for
   this part.
2. **Better retrieval / generation.** TF-IDF is fast and explainable but
   limited on paraphrased questions. A natural next step is swapping in
   embeddings + an LLM (e.g. Claude via the Anthropic API) for the
   summarization step, while keeping the same retrieval-then-summarize
   architecture — this is the "separate AI feature track for deeper
   capabilities" mentioned in the proposal.
3. **Live ticket creation / escalation from the chat.** Currently read-only;
   a production version could let a user create a ticket, attach the chat
   transcript, or notify the on-call channel directly, using the same
   Jira REST / webhook patterns already used in the ART Team Automation Flow.
4. **Access control & auditability.** Tie into existing SSO, log every
   query/answer pair for audit (mirrors the audit-log pattern already used
   for JSM automation), and restrict which ticket fields are visible per
   role.
5. **Hosting.** Containerize (Docker) and deploy to the existing AWS/EKS
   setup already used for other services, rather than running the Flask dev
   server — the same CI/CD pipeline (GitHub Actions → Docker Hub → EKS)
   already proven out could be reused as-is.
6. **Feedback loop.** Let users flag "not helpful" answers; route those into
   a queue for KB authors to close the gap — this is what turns the bot's
   answers into a growing, self-improving KB rather than a static snapshot.

## Known limitations of this prototype

- Sample data is synthetic — realistic in shape, but not real ticket history.
- TF-IDF retrieval matches on wording/vocabulary overlap; it won't handle
  heavily paraphrased or vague questions as well as an LLM-based approach
  would.
- No authentication, no persistence of conversation history, no write-back
  to Jira — all by design, to keep the demo simple and safe to run anywhere.# Incident Assist — Full Project Documentation

A production-grade AI chatbot for incident management, built end-to-end with a
complete GitOps pipeline: Flask → Docker → Kubernetes (EKS) → Jenkins CI →
ArgoCD CD.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Local Development](#4-local-development)
5. [Docker](#5-docker)
6. [AWS EKS Kubernetes](#6-aws-eks-kubernetes)
7. [Jenkins CI Pipeline](#7-jenkins-ci-pipeline)
8. [ArgoCD CD Pipeline](#8-argocd-cd-pipeline)
9. [Git Branch Strategy](#9-git-branch-strategy)
10. [Troubleshooting Log](#10-troubleshooting-log)
11. [Cost Cleanup](#11-cost-cleanup)

---

## 1. Project Overview

Incident Assist is a hybrid AI chatbot for the Helix SRE incident and problem
management workflow. It combines:

- **Predefined quick-question suggestions** — derived automatically from the
  most common ticket categories in historical data
- **Free-text question handling** — TF-IDF similarity search over historical
  tickets and KB docs, returning a summarized answer, confidence level,
  suggested next steps, and cited sources

Built as a proof-of-concept to demonstrate the value of AI-assisted incident
management, with a clear path to production integration with JSM/Jira.

**Tech stack:**
- Backend: Python + Flask + Gunicorn
- Retrieval: scikit-learn TF-IDF + cosine similarity
- Frontend: HTML/CSS/JS
- Data: JSON (synthetic tickets + KB docs — swap for real JSM data via Jira REST API)

---

## 2. Architecture

### Application Architecture
```
Browser (HTML/CSS/JS)
        ↓
Nginx (port 80, reverse proxy)
        ↓
Gunicorn (port 5000, WSGI server)
        ↓
Flask app (app.py)
        ↓
TF-IDF retrieval over data/tickets.json + data/kb_docs.json
```

### GitOps Pipeline Architecture
```
Developer pushes code to GitHub (dev branch)
        ↓ (webhook fires instantly)
Jenkins CI (on EC2 ip-172-31-4-223)
  Stage 1: Checkout — pulls latest code
  Stage 2: Build — docker build vinaykottour/incident-assist:<build_number>
  Stage 3: Push — docker push to Docker Hub
  Stage 4: Update Manifest — edits k8s/deployment.yaml, git push [skip ci]
        ↓
ArgoCD (running in EKS cluster)
  Detects deployment.yaml changed
  Runs kubectl apply automatically
        ↓
Kubernetes EKS (incident-assist-cluster, us-east-1)
  Rolling update: new pods with new image tag roll out
  Zero downtime (maxSurge: 1, maxUnavailable: 1)
        ↓
AWS Load Balancer → end users
```

---

## 3. Repository Structure

```
incident-assist-chatbot/
└── incident-chatbot/           ← actual project root (important: one level deep)
    ├── app.py                  ← Flask backend + TF-IDF retrieval logic
    ├── requirements.txt        ← Python dependencies
    ├── Dockerfile              ← Container definition
    ├── .dockerignore
    ├── Jenkinsfile             ← CI pipeline definition
    ├── README.md               ← this file
    ├── data/
    │   ├── tickets.json        ← 21 synthetic historical incident tickets
    │   └── kb_docs.json        ← 8 synthetic KB articles
    ├── templates/
    │   └── index.html          ← Chat UI HTML
    ├── static/
    │   ├── style.css           ← Dark theme CSS
    │   └── script.js           ← Frontend API calls
    └── k8s/
        ├── deployment.yaml     ← Kubernetes Deployment manifest
        └── service.yaml        ← Kubernetes Service (LoadBalancer)
```

**Why the double-nested structure (`incident-assist-chatbot/incident-chatbot/`)?**
The outer folder is the Git repo root. The inner folder was preserved from the
original zip extraction. All `git` commands run from the outer folder; all app
commands (`docker build`, `kubectl apply`, etc.) run from the inner folder.
Jenkins handles this with `dir('incident-chatbot') { ... }` wrappers.

---

## 4. Local Development

### Prerequisites
- Python 3.12
- Git

### Setup
```bash
cd incident-chatbot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:5000` in a browser.

### API Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Chat UI |
| GET | `/api/suggestions` | Predefined quick-question chips |
| POST | `/api/query` | Free-text question → answer + sources |
| GET | `/api/stats` | Index counts (tickets/docs) |

---

## 5. Docker

### Dockerfile explained (line by line)
```dockerfile
FROM python:3.12-slim        # base image: Python 3.12, minimal OS
WORKDIR /app                 # all subsequent commands run here
COPY requirements.txt .      # copy dependency list FIRST (Docker caching)
RUN pip install --no-cache-dir -r requirements.txt gunicorn  # install deps
COPY . .                     # copy app code AFTER deps (cache efficiency)
EXPOSE 5000                  # document the port (doesn't actually open it)
RUN useradd --create-home appuser   # create non-root user (security)
USER appuser                 # switch to non-root user
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

**Why python:3.12-slim and not the default?**
The server runs Ubuntu 26.04 with Python 3.14. scikit-learn/numpy/scipy don't
have pre-built wheels for Python 3.14, forcing source compilation (which needs
Fortran compilers, extra RAM, and disk space). Python 3.12 has pre-built wheels
— `pip install` just downloads instead of compiling.

**Why Gunicorn instead of `python3 app.py`?**
Flask's built-in server is single-threaded and explicitly not meant for real
traffic. Gunicorn is a production-grade WSGI server: multiple workers, handles
concurrent requests, restarts crashed workers automatically.

### Build and run locally
```bash
docker build -t incident-assist:dev .
docker run -d -p 5000:5000 --name incident-assist-test incident-assist:dev
curl http://127.0.0.1:5000/api/stats
```

### Push to Docker Hub
```bash
docker login -u vinaykottour
docker tag incident-assist:dev vinaykottour/incident-assist:dev
docker push vinaykottour/incident-assist:dev
```

---

## 6. AWS EKS Kubernetes

### Cluster setup
```bash
eksctl create cluster \
  --name incident-assist-cluster \
  --region us-east-1 \
  --node-type t3.small \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3
```

**Why t3.small not t3.micro?**
t3.micro has insufficient memory for Kubernetes system pods + application pods.
Pod scheduling fails with "Insufficient memory" on t3.micro.

**Why 2 nodes?**
Pod anti-affinity rules force the 2 app replicas onto different nodes. With only
1 node, anti-affinity can never be satisfied and pods stay Pending forever.

### Connect kubectl to the cluster
```bash
aws eks update-kubeconfig --region us-east-1 --name incident-assist-cluster
kubectl get nodes
```

### Namespaces
```bash
kubectl create namespace dev
kubectl create namespace staging    # for future use
```

### Deploy manually (first time)
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods -n dev
kubectl get service incident-assist-service -n dev  # get LoadBalancer URL
```

### Key manifest decisions

**deployment.yaml:**
- `replicas: 2` — basic redundancy; if one pod dies, the other keeps serving
- `maxSurge: 1, maxUnavailable: 1` — rolling update allows 1 extra pod during
  update AND allows 1 pod to be unavailable; prevents deadlock with anti-affinity
- `podAntiAffinity` — forces pods onto different nodes so a single node failure
  doesn't take down both replicas
- `livenessProbe` — Kubernetes restarts the pod if `/api/stats` stops responding
- `readinessProbe` — traffic only routes to a pod after `/api/stats` responds
  successfully; prevents routing to a half-started pod
- `resources.requests/limits` — prevents one pod from starving the node of
  memory (the same OOM problem we hit installing scikit-learn)

**service.yaml:**
- `type: LoadBalancer` — AWS automatically provisions an Elastic Load Balancer
  with a public DNS hostname
- `port: 80, targetPort: 5000` — external traffic on port 80 routes to the
  container's port 5000

---

## 7. Jenkins CI Pipeline

### Installation (EC2 ip-172-31-4-223)

```bash
# Java 21 (Jenkins 2.568+ requires Java 21 minimum — Java 17 is too old)
sudo apt install -y openjdk-21-jre
sudo update-alternatives --config java   # select java-21

# Jenkins signing key (fetch by key ID, not URL — Jenkins' hosted URLs serve expired keys)
gpg --no-default-keyring --keyring /tmp/jenkins-temp.gpg \
    --keyserver keyserver.ubuntu.com --recv-keys 7198F4B714ABFC68
gpg --no-default-keyring --keyring /tmp/jenkins-temp.gpg \
    --export --armor 7198F4B714ABFC68 | \
    sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null

echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] \
    https://pkg.jenkins.io/debian-stable binary/" | \
    sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

sudo apt update
sudo apt install -y jenkins
sudo systemctl enable --now jenkins
```

### Making Jenkins accessible through office network (port 8080 is blocked)

Office networks block non-standard ports. Solution: route Jenkins through Nginx
on port 80 under a `/jenkins/` path prefix.

**1. Tell Jenkins it lives at /jenkins prefix:**
```bash
sudo systemctl edit jenkins
# Add:
[Service]
Environment="JENKINS_PREFIX=/jenkins"
Environment="JAVA_OPTS=-Djava.io.tmpdir=/jenkins-tmp"

sudo mkdir -p /jenkins-tmp
sudo chown jenkins:jenkins /jenkins-tmp
sudo systemctl daemon-reload
sudo systemctl restart jenkins
```

**Why `JAVA_OPTS=-Djava.io.tmpdir=/jenkins-tmp`?**
`/tmp` on Ubuntu is RAM-backed (tmpfs), capped at ~455MB. Docker builds use
`/tmp` for scratch space and exceed this limit. Redirecting to real disk fixes it.

**2. Add Jenkins to Nginx config:**
```nginx
location /jenkins/ {
    proxy_pass http://127.0.0.1:8080/jenkins/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**3. Allow Jenkins user to run Docker:**
```bash
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

### Jenkins credentials
Store in Manage Jenkins → Credentials → (global):
- ID `dockerhub-creds` — Docker Hub username + Personal Access Token
- ID `github-creds` — GitHub username + Personal Access Token
  (fine-grained token, Contents: Read and write, on incident-assist-chatbot repo)

### Jenkinsfile pipeline stages

**Stage 1 — Checkout:**
Checks commit message for `[skip ci]` — if found, stops immediately.
This prevents an infinite loop: Jenkins pushes a manifest commit → webhook
fires → Jenkins builds again → infinite loop. `[skip ci]` breaks the cycle.

**Stage 2 — Build Docker Image:**
Runs inside `dir('incident-chatbot')` because Jenkins checks out the whole
repo root, but Dockerfile lives one level deeper. Uses `BUILD_NUMBER` as the
image tag so every build is uniquely traceable and rollbacks are possible.

**Stage 3 — Push to Docker Hub:**
Uses `withCredentials` to inject Docker Hub token at runtime — never hardcoded
in the script. `--password-stdin` avoids the token appearing in process lists.

**Stage 4 — Update Kubernetes Manifest:**
Uses `sed` to replace the image tag in `deployment.yaml`, commits, and pushes
with `HEAD:dev` (not just `dev`) because Jenkins checks out in detached HEAD
mode — `HEAD:dev` pushes the current commit to the remote dev branch regardless
of local branch state.

### GitHub webhook setup
Payload URL: `http://<jenkins-ec2-ip>/jenkins/github-webhook/`
Content type: `application/json`
Events: Just the push event

Jenkins trigger: "GitHub hook trigger for GITScm polling" (must be checked AND saved)

### Preventing push conflicts
Jenkins pushes a commit after every build. Always pull before pushing:
```bash
git pull --no-edit    # or: git config --global pull.rebase true
git push
```

With `pull.rebase true`, git pull stacks your commits on top of Jenkins'
commits cleanly, avoiding merge commits that would trigger another Jenkins build.

---

## 8. ArgoCD CD Pipeline

### Installation
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f \
    https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl get pods -n argocd   # wait for all 7 pods to show 1/1 Running
```

### Access the UI
```bash
# Expose via LoadBalancer
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'
kubectl get svc argocd-server -n argocd   # copy EXTERNAL-IP

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath="{.data.password}" | base64 -d && echo
```

Open `https://<EXTERNAL-IP>` — accept the self-signed certificate warning.
Login: username `admin`, password from above command.

### ArgoCD Application settings
- **Application Name:** `incident-assist-dev`
- **Project:** `default`
- **Sync Policy:** Automatic (enable Prune Resources + Self Heal)
- **Repository URL:** `https://github.com/vinaykottour/incident-assist-chatbot`
- **Revision:** `dev`
- **Path:** `incident-chatbot/k8s`
- **Cluster URL:** `https://kubernetes.default.svc`
- **Namespace:** `dev`

**Why `kubernetes.default.svc`?**
ArgoCD is installed inside the same EKS cluster it deploys to. This internal
address points back at the cluster itself — no external endpoint needed.

**Why Automatic sync with Self Heal?**
- Automatic: deploys immediately when deployment.yaml changes, no manual click
- Self Heal: if someone runs `kubectl apply` manually and changes something,
  ArgoCD reverts it to match Git — Git is always the single source of truth

---

## 9. Git Branch Strategy

```
dev branch    → dev namespace    (daily pushes, Jenkins auto-builds)
staging branch → staging namespace (merge after dev testing)
main branch   → prod namespace   (merge after staging sign-off)
```

Each branch maps to a Kubernetes namespace in the same EKS cluster (cost
efficient vs separate clusters per environment).

**Promoting dev → staging:**
```bash
git checkout staging
git merge dev
git push
```
ArgoCD (staging app) detects the change and deploys to the staging namespace.

**Daily workflow:**
```bash
git checkout dev
git pull                    # always pull first (Jenkins may have pushed)
# make changes
git add .
git commit -m "your message"
git push                    # webhook fires → Jenkins builds → ArgoCD deploys
```

---

## 10. Troubleshooting Log

Real issues hit during this project and how they were resolved.

### Python/pip issues on EC2

**Problem:** `pip install scikit-learn==1.5.1` fails with exit code 137 (OOM killed)
**Cause:** t3.micro has ~1GB RAM; building scikit-learn from source needs more
**Fix:** Add a 2GB swap file:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**Problem:** `pip install` fails with "Disk quota exceeded"
**Cause:** `/tmp` is RAM-backed (tmpfs), only 455MB — pip uses it for builds
**Fix:** Redirect pip temp directory to real disk:
```bash
mkdir -p ~/pip-tmp
export TMPDIR=~/pip-tmp
pip install -r requirements.txt
```

**Problem:** scikit-learn 1.5.1 fails to build — missing Fortran compiler (gfortran)
**Cause:** Old version pins (scikit-learn 1.5.1, numpy 1.26.4) don't have
pre-built wheels for Python 3.14; pip tries to compile from source
**Fix:** Upgrade to versions with Python 3.14 wheels:
```
Flask==3.1.3
scikit-learn==1.9.0
numpy==2.5.1
scipy==1.18.0
gunicorn==23.0.0
```

### Docker issues

**Problem:** `docker run` starts but `curl http://127.0.0.1:5000` fails
**Cause:** Docker's port publishing takes a moment to settle after container start
**Fix:** Test via container's internal IP directly first:
```bash
docker inspect --format '{{json .NetworkSettings.Networks}}' <container>
curl http://172.17.0.2:5000/api/stats
```
Then retry `127.0.0.1:5000` after a few seconds — usually resolves itself.

**Problem:** `docker build` inside Jenkins fails with "no such file or directory: Dockerfile"
**Cause:** Jenkins checks out the repo root, but Dockerfile is inside `incident-chatbot/` subfolder
**Fix:** Wrap build steps with `dir('incident-chatbot') { ... }` in Jenkinsfile

### Jenkins issues

**Problem:** Jenkins fails to start — `Running with Java 17 ... older than minimum required version (Java 21)`
**Fix:**
```bash
sudo apt install -y openjdk-21-jre
sudo update-alternatives --config java   # select java-21
sudo systemctl restart jenkins
```

**Problem:** `apt install jenkins` fails — `NO_PUBKEY 7198F4B714ABFC68`
**Cause:** Jenkins' hosted key URLs serve an expired key (expired 2023-03-30)
**Fix:** Fetch the current key directly by ID from a public keyserver:
```bash
gpg --no-default-keyring --keyring /tmp/jenkins-temp.gpg \
    --keyserver keyserver.ubuntu.com --recv-keys 7198F4B714ABFC68
gpg --no-default-keyring --keyring /tmp/jenkins-temp.gpg \
    --export --armor 7198F4B714ABFC68 | \
    sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
```

**Problem:** Jenkins UI shows 502 Bad Gateway
**Cause:** Jenkins was still starting up after a restart (takes 20-30 seconds)
**Fix:** Wait 30 seconds and refresh. If persistent, check `sudo systemctl status jenkins`

**Problem:** Jenkins pipeline shows "Waiting for next available executor"
**Cause:** Built-in node has 0 executors configured (Jenkins default security setting)
**Fix:** Manage Jenkins → Nodes → Built-In Node → Configure → set executors to 2

**Problem:** Jenkins config file `/etc/default/jenkins` changes have no effect
**Cause:** This Jenkins version (2.568+) doesn't read `/etc/default/jenkins` via systemd
**Fix:** Use systemd override instead:
```bash
sudo systemctl edit jenkins
# Add:
[Service]
Environment="JENKINS_PREFIX=/jenkins"
Environment="JENKINS_PORT=8080"
```

**Problem:** Jenkins pipeline infinitely loops — builds its own manifest commits
**Cause:** Jenkins pushes a commit → webhook fires → Jenkins builds again → infinite loop
**Fix:** Check commit message in Checkout stage; stop if it contains `[skip ci]`:
```groovy
def commitMsg = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
if (commitMsg.contains('[skip ci]')) {
    currentBuild.result = 'NOT_BUILT'
    error('Skipping build — commit made by Jenkins')
}
```
Also add `[skip ci]` to Jenkins' manifest commit message.

**Problem:** `git push` in Jenkins pipeline fails — `src refspec dev does not match any`
**Cause:** Jenkins checks out in detached HEAD mode — not "on" any branch
**Fix:** Use `HEAD:dev` instead of `dev` in git push:
```bash
git push https://... HEAD:dev
```

**Problem:** `git push` in Jenkins pipeline fails — 403 Permission Denied
**Cause:** GitHub Personal Access Token doesn't have write permission
**Fix:** Create a fine-grained PAT with Contents: Read and write on the specific repo

**Problem:** Laptop can't push — "Updates were rejected (fetch first)"
**Cause:** Jenkins pushed a commit while you were working; laptop is behind
**Fix:**
```bash
git pull --no-edit    # pulls and auto-accepts merge commit message
git push
```
Or permanently fix with: `git config --global pull.rebase true`

### Kubernetes issues

**Problem:** New pod stuck in `Pending` — `0/2 nodes are available: 2 node(s) didn't match pod anti-affinity rules`
**Cause:** Anti-affinity requires pods on different nodes. With `maxUnavailable: 0`,
old pods stay running (occupying both nodes) while new pod tries to schedule → deadlock
**Fix:** Change `maxUnavailable: 0` to `maxUnavailable: 1` in deployment.yaml.
This allows one old pod to terminate first, freeing a node for the new pod.

**Problem:** `aws eks update-kubeconfig` fails — `ResourceNotFoundException: No cluster found`
**Cause:** Cluster was deleted (cost cleanup) or wrong region/name
**Fix:** Check `aws eks list-clusters --region us-east-1` to see what exists

**Problem:** EKS cluster creation fails partway through
**Cause:** IAM permissions, VPC limits, or service quota limits
**Fix:** Check CloudFormation in AWS Console for the specific error;
`eksctl delete cluster` to clean up partial creation before retrying

### Network/Access issues

**Problem:** App/Jenkins/ArgoCD URL loads forever or "This Page Cannot Be Displayed"
**Cause:** Office network blocks non-standard ports (22, 5000, 8080, 8443, etc.)
**Fix:** Route everything through Nginx on port 80 (which offices always allow):
- App: `proxy_pass http://127.0.0.1:5000`
- Jenkins: `proxy_pass http://127.0.0.1:8080/jenkins/` (with prefix config)
- ArgoCD: expose via LoadBalancer on port 80 with `--insecure` flag

**Problem:** EC2 public IP changed after instance restart
**Cause:** No Elastic IP assigned (intentional cost decision)
**Fix:** Always get current IP with:
```bash
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/public-ipv4
```

**Problem:** GitHub webhook fires successfully but Jenkins doesn't build
**Cause:** "GitHub hook trigger for GITScm polling" checkbox was checked but not saved
**Fix:** Configure → Triggers → check the box → scroll to bottom → click Save
(the Save button at the very bottom is easy to miss)

### ArgoCD issues

**Problem:** ArgoCD UI shows certificate error in browser
**Cause:** ArgoCD uses a self-signed certificate by default
**Fix:** Click Advanced → Proceed anyway. Or type `thisisunsafe` on the error page in Chrome.

**Problem:** ArgoCD shows OutOfSync but won't sync automatically
**Cause:** Auto-sync not enabled, or Prune/Self Heal not checked
**Fix:** Application → App Details → Edit → Sync Policy → set to Automatic,
check Prune Resources and Self Heal

---

## 11. Cost Cleanup

**When you're done, delete everything to stop billing:**

### Delete EKS cluster (most expensive — ~$130/month)
```bash
# This also deletes worker nodes and load balancers
eksctl delete cluster --name incident-assist-cluster --region us-east-1
```
Takes 10-15 minutes. Removes cluster, node group, VPC, and all associated resources.

### Stop EC2 instances (saves ~$30/month while stopped)
AWS Console → EC2 → select instances → Instance State → Stop
- `ip-172-31-4-223` (Jenkins + Docker + Nginx)
- `ip-172-31-28-96` (kubectl control box)

Note: stopping (not terminating) preserves all installed software — you can
restart and continue exactly where you left off.

### Terminate EC2 instances (saves disk storage costs too)
If you don't need the instances at all:
AWS Console → EC2 → select instances → Instance State → Terminate

### Verify nothing is left running
```bash
aws eks list-clusters --region us-east-1          # should return []
aws ec2 describe-instances --region us-east-1 \
    --filters "Name=instance-state-name,Values=running" \
    --query 'Reservations[].Instances[].InstanceId'
```

---

## Future Enhancements

1. **Real JSM data** — replace synthetic JSON with live Jira REST API queries
   against HLXSREINP (read-only access sufficient):
   `GET /rest/api/3/search?jql=project=HLXSREINP&maxResults=500`

2. **Staging environment** — duplicate ArgoCD app pointing at `staging` branch
   and `staging` namespace; practice `dev → staging → main` promotion flow

3. **LLM-based summarization** — swap TF-IDF retrieval summary step for Claude
   API call; keeps same retrieval architecture, improves answer quality on
   paraphrased questions

4. **Feedback loop** — add "helpful / not helpful" buttons; route negative
   feedback to a KB authors queue; makes the knowledge base self-improving

5. **SSO + RBAC** — tie into existing corporate SSO; restrict ticket field
   visibility per role (same access model as JSM itself)

6. **Duplicate detection** — automation check for similar summary/category
   within a time window; reduces duplicate incident tickets (identified as a
   real pain point in HLXSREINP-1233)

  --------------------------------------------------------------------------

  
