"""
Incident Management AI Assistant - Prototype
----------------------------------------------
A lightweight Flask backend that demonstrates the "hybrid model" proposed
for the Helix SRE incident chatbot:

  1. Predefined suggestions (popup quick-questions) derived from the most
     common ticket categories in historical data.
  2. Free-text question handling, using TF-IDF similarity search over a
     knowledge base of historical tickets + KB docs to retrieve the most
     relevant matches, then compose a summarized answer + suggested next
     steps.

This intentionally avoids any external LLM API dependency so it can run
fully offline (useful on a restricted office network) -- see README.md for
notes on how this slots into a production architecture that could later
call an LLM (e.g. Claude) for richer summarization, or connect directly
to the Jira Service Management REST API for live ticket data.
"""

import json
import os
from collections import Counter

from flask import Flask, jsonify, render_template, request
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(filename):
    path = os.path.join(BASE_DIR, "data", filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


TICKETS = load_json("tickets.json")
KB_DOCS = load_json("kb_docs.json")

# Build a unified corpus: each entry is searchable text + a pointer back to
# either a ticket or a KB doc.
CORPUS_ENTRIES = []

for t in TICKETS:
    text = " ".join([
        t["summary"],
        t["description"],
        t["category"],
        t.get("resolution", ""),
        " ".join(t.get("tags", [])),
    ])
    CORPUS_ENTRIES.append({"type": "ticket", "text": text, "ref": t})

for d in KB_DOCS:
    text = " ".join([d["title"], d["content"]])
    CORPUS_ENTRIES.append({"type": "doc", "text": text, "ref": d})

CORPUS_TEXTS = [e["text"] for e in CORPUS_ENTRIES]

vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
TFIDF_MATRIX = vectorizer.fit_transform(CORPUS_TEXTS)


# ---------------------------------------------------------------------------
# Predefined suggestions
# ---------------------------------------------------------------------------

def build_predefined_suggestions(limit=6):
    """Derive popup suggestions from the most common ticket categories,
    mimicking 'suggestions derived from previous queries and stored
    documents' from the proposal."""
    category_counts = Counter(t["category"] for t in TICKETS)
    suggestions = []
    for category, _count in category_counts.most_common(limit):
        # Use the most recent (last in list) ticket in that category to
        # phrase a natural question.
        sample = [t for t in TICKETS if t["category"] == category][-1]
        suggestions.append({
            "category": category,
            "question": f"How do we usually resolve issues like: \"{sample['summary']}\"?",
        })
    return suggestions


PREDEFINED_SUGGESTIONS = build_predefined_suggestions()


# ---------------------------------------------------------------------------
# Retrieval + answer composition
# ---------------------------------------------------------------------------

def search(query, top_k=3, min_score=0.08):
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, TFIDF_MATRIX).flatten()
    ranked = sorted(
        zip(scores, CORPUS_ENTRIES), key=lambda x: x[0], reverse=True
    )
    results = [(score, entry) for score, entry in ranked if score >= min_score]
    return results[:top_k]


def compose_answer(query, results):
    if not results:
        return {
            "summary": (
                "I couldn't find a close match in historical tickets or "
                "documentation for that question."
            ),
            "confidence": "low",
            "sources": [],
            "next_steps": [
                "Try rephrasing with a specific error message, ticket key, "
                "or component name.",
                "If this looks like a new issue, raise a ticket via the "
                "Incident Clone Portal so it can be triaged and added to "
                "the knowledge base once resolved.",
            ],
        }

    top_score, top_entry = results[0]
    confidence = "high" if top_score >= 0.35 else ("medium" if top_score >= 0.18 else "low")

    sources = []
    next_steps = []

    for score, entry in results:
        if entry["type"] == "ticket":
            t = entry["ref"]
            sources.append({
                "type": "ticket",
                "key": t["key"],
                "title": t["summary"],
                "status": t["status"],
                "score": round(float(score), 2),
            })
            if t["status"] == "Resolved":
                for step in t.get("resolution_steps", [])[:3]:
                    if step not in next_steps:
                        next_steps.append(step)
        else:
            d = entry["ref"]
            sources.append({
                "type": "doc",
                "key": d["doc_id"],
                "title": d["title"],
                "status": "Reference",
                "score": round(float(score), 2),
            })

    if top_entry["type"] == "ticket":
        t = top_entry["ref"]
        if t["status"] == "Resolved":
            summary = (
                f"This looks similar to {t['key']} (\"{t['summary']}\"). "
                f"That case was resolved: {t['resolution']}"
            )
        else:
            summary = (
                f"This looks similar to {t['key']} (\"{t['summary']}\"), "
                f"which is still {t['status']}. Current guidance: {t['resolution']}"
            )
    else:
        d = top_entry["ref"]
        summary = f"Based on \"{d['title']}\": {d['content']}"
        if not next_steps:
            next_steps.append(
                "Follow the documented procedure above; escalate to the "
                "team lead if the issue persists."
            )

    if not next_steps:
        next_steps.append(
            "No resolved precedent found yet — consider escalating and "
            "logging the outcome so future queries have a match."
        )

    return {
        "summary": summary,
        "confidence": confidence,
        "sources": sources,
        "next_steps": next_steps[:5],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/suggestions")
def api_suggestions():
    return jsonify({"suggestions": PREDEFINED_SUGGESTIONS})


@app.route("/api/query", methods=["POST"])
def api_query():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Empty query"}), 400

    results = search(query)
    answer = compose_answer(query, results)
    answer["query"] = query
    return jsonify(answer)


@app.route("/api/stats")
def api_stats():
    """Small transparency endpoint: shows what the bot is drawing from,
    useful when demoing to stakeholders."""
    return jsonify({
        "ticket_count": len(TICKETS),
        "kb_doc_count": len(KB_DOCS),
        "categories": list(Counter(t["category"] for t in TICKETS).keys()),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
