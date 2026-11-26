"""Turn a story cluster into a Hinglish KhabarKaro post using Google Gemini."""
import json
import os
import re
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = """Tum KhabarKaro ke news writer ho. KhabarKaro ek Hinglish (Roman script mein Hindi + English) news website hai.

STRICT RULES:
1. Sirf neeche diye gaye SOURCE MATERIAL ke facts use karo. Koi naya number, naam, quote, date ya claim mat banao. Agar koi detail source mein nahi hai, to mat likho.
2. Apne shabdon mein likho. Source ke sentences copy mat karo. Kisi bhi source se 10 shabdon se lamba direct quote mat do.
3. Bhasha: aasaan, conversational Hinglish, Roman script only (Devanagari nahi). Technical/proper nouns English mein hi rakho.
4. Tone neutral rakho. Koi political opinion, side lena, ya sensational/clickbait headline nahi.
5. Agar source material kam hai, aapas mein contradict karta hai, ya story sensitive hai (communal, sexual violence, suicide, minors, ongoing court case ka faisla), to "skip": true do.
6. Headline 70-100 characters, informative, clickbait nahi.

Output sirf JSON, is shape mein:
{
  "skip": false,
  "skip_reason": "",
  "title": "Hinglish headline",
  "summary": "1-2 line Hinglish saar (max 200 chars)",
  "category": "india|world|tech|business|sports|entertainment|auto|viral",
  "key_points": ["3-4 chhote points"],
  "body": ["3-5 paragraphs, har ek 2-4 sentences"],
  "why_it_matters": "2-3 sentences: aam padhne wale par iska kya asar",
  "slug_en": "short-english-url-words-5-to-8",
  "sensitive": false,
  "product_keywords": ["0-3 Amazon India search phrases jo is khabar se seedhe jude ho, warna empty list"]
}

product_keywords rules: sirf tab do jab product reader ke liye naturally kaam ka ho (jaise phone launch -> wahi phone; cricket series -> cricket bat; budget/tax news -> personal finance book). Death, disaster, crime, war, accident wali khabar mein HAMESHA empty list aur "sensitive": true."""


def build_prompt(cluster, articles):
    parts = [f"CATEGORY HINT: {cluster['cat_hint']}", f"SOURCES COVERING THIS: {', '.join(cluster['sources'])}", ""]
    for i, it in enumerate(cluster["items"][:6], 1):
        parts.append(f"--- SOURCE {i}: {it['source']}\nHEADLINE: {it['title']}\nRSS SUMMARY: {it['summary']}")
        if articles.get(it["link"]):
            parts.append(f"ARTICLE TEXT:\n{articles[it['link']]}")
        parts.append("")
    parts.append("Upar ke SOURCE MATERIAL se KhabarKaro post ka JSON banao.")
    return "\n".join(parts)


def call_gemini(prompt, models, log):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY secret is not set")
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    last_err = None
    for model in models:
        for attempt in range(2):
            try:
                r = requests.post(API.format(model=model), params={"key": key}, json=body, timeout=120)
                if r.status_code == 429:
                    log(f"gemini {model}: rate limited, waiting 30s")
                    time.sleep(30)
                    continue
                if r.status_code == 404:
                    log(f"gemini {model}: model not found, trying next")
                    break
                r.raise_for_status()
                data = r.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text), model
            except Exception as e:
                last_err = e
                log(f"gemini {model} attempt {attempt + 1} failed: {e}")
                time.sleep(5)
    raise RuntimeError(f"All Gemini models failed: {last_err}")


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:80].strip("-") or "khabar"


def validate(post, categories):
    """Return an error string, or '' if the post is usable."""
    if post.get("skip"):
        return f"model skipped: {post.get('skip_reason', '')}"
    for f in ("title", "summary", "body", "key_points", "why_it_matters"):
        if not post.get(f):
            return f"missing field {f}"
    if post.get("category") not in categories:
        return f"bad category {post.get('category')}"
    if not (30 <= len(post["title"]) <= 140):
        return "title length out of range"
    if not isinstance(post["body"], list) or len(post["body"]) < 2:
        return "body too short"
    if sum(len(p) for p in post["body"]) < 400:
        return "body too thin"
    if re.search(r"[ऀ-ॿ]", json.dumps(post, ensure_ascii=False)):
        return "contains Devanagari (should be Roman Hinglish)"
    return ""
