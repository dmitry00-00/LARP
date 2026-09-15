"""Near-duplicate detection for inbox posts using 64-bit SimHash.

No external dependencies — pure Python.

Algorithm
---------
SimHash (Charikar 2002) projects each document into a 64-bit integer such
that the *Hamming distance* between two hashes correlates with the
*cosine distance* between their term-frequency vectors.  Two posts are
considered near-duplicates when Hamming distance ≤ ``HAMMING_THRESHOLD``.

For job/resume Telegram posts a threshold of 8 bits (out of 64) catches:
  - Exact reposts across channels (distance 0).
  - Minor edits: salary changed, one emoji added (distance 1-3).
  - Same vacancy re-published with different phrasing (distance 4-8).
  - Same post with different contact info (@handle, email, URL — stripped
    before hashing so they do NOT contribute to distance at all).

Observed false-positive gap: genuinely different posts (different role/stack)
show hamming ≥ 24 in practice, leaving a 15-bit safety margin below threshold.

False-positive risk at threshold 6 is extremely low for texts ≥ 100 chars
because the probability that two unrelated texts share >90 % of bigrams is
negligible in practice.

Integration
-----------
``classify_post.run()`` calls ``deduplicate_batch()`` once per run:

    unique, duplicates = deduplicate_batch(raw_items, state, recruit)
    for item, original_id in duplicates:
        await recruit.patch_inbox(item["id"], status="skipped",
                                  errorText=f"duplicate:{original_id}")
    # Process `unique` normally.

Fingerprints are stored in the local State SQLite and retained for
``RETENTION_DAYS`` (default 30).  A cleanup pass runs automatically.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.state import State

# ── Tunables ──────────────────────────────────────────────────────────────────

HAMMING_THRESHOLD = 8   # bits; lower = stricter dedup
                         # 8/64 ≈ 87.5 % bit agreement ≈ ~93 % content overlap
RETENTION_DAYS    = 30  # days; fingerprints older than this are ignored
BITS              = 64  # SimHash size in bits (do not change without migrating DB)

# Minimum normalised token count to bother with SimHash.
# Very short posts (< 8 tokens) produce unreliable hashes — skip them.
_MIN_TOKENS = 8

# ── FNV-1a 64-bit hash ────────────────────────────────────────────────────────
# Deterministic, no external dependency.

_FNV_OFFSET = 14695981039346656037  # 64-bit FNV offset basis
_FNV_PRIME  = 1099511628211         # 64-bit FNV prime
_MASK64     = 0xFFFFFFFFFFFFFFFF


def _fnv1a_64(s: str) -> int:
    h = _FNV_OFFSET
    for byte in s.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _MASK64
    return h


# ── Text normalisation ────────────────────────────────────────────────────────

# Strip contact-info tokens first — they vary per channel/repost but carry no
# semantic content for the purpose of dedup matching.
# Order: URLs first (contain @), then emails (contain @), then bare @handles.
_RE_URL = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)
_RE_EMAIL = re.compile(r"\S+@\S+\.\w{2,}")
_RE_HANDLE = re.compile(r"@\w+")

# Preserve Cyrillic and Latin letters + digits; drop everything else.
_RE_KEEP = re.compile(r"[^\w\s]", re.UNICODE)
# Collapse multiple whitespace
_RE_WS = re.compile(r"\s+")
# Currency symbols and signs (stripped before tokenisation)
_RE_CURRENCY_SYMS = re.compile(r"[₽$€£]")
# Salary/magnitude suffixes that vary across reposts but mean the same thing.
# Removed BEFORE number normalisation so "280к" → "280" → "NUM".
_RE_SALARY_UNITS = re.compile(
    r"\b(?:тыс(?:яч)?\.?|руб(?:лей|ля)?\.?|rub|usd|eur|gbp)\b",
    re.IGNORECASE,
)
# Replace digit runs with a placeholder so salary "300к" vs "320к" don't
# diverge the hash.  Keep surrounding letter context intact (e.g. "3d" → "NUMd").
_RE_DIGITS = re.compile(r"\d+")

# Common Russian + English stop-words
_STOPWORDS: frozenset[str] = frozenset({
    # ── Russian function words ────────────────────────────────────────────────
    "в", "на", "с", "и", "а", "но", "по", "за", "к", "у", "от",
    "до", "из", "при", "об", "что", "как", "для", "или", "не", "же",
    "то", "так", "это", "этот", "его", "её", "их", "вы", "мы",
    # ── English function words ────────────────────────────────────────────────
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "is",
    "are", "with", "on", "at", "by", "as", "be", "we", "our",
    # ── Post-normalisation artefacts ──────────────────────────────────────────
    "num",   # leftover after digit → NUM replacement
    # ── Structural field labels common to every vacancy/resume post ───────────
    # These vary across templates ("Опыт:" vs "Требования:") but carry no
    # signal that distinguishes one vacancy from another.
    "вакансия", "вакансии", "резюме", "компания", "компании", "организация",
    "зарплата", "зп", "оплата", "вилка", "опыт", "требования", "требование",
    "обязанности", "условия", "условие", "формат", "контакт", "контакты",
    "стек", "технологии", "технология", "позиция", "должность", "проект",
    "предлагаем", "предлагаю", "описание",
    # ── CTA / contact call-to-action verbs ────────────────────────────────────
    # "Писать: @handle" vs "Пишите: @handle" — same intent, different form.
    "писать", "пишите", "напишите", "написать", "пиши", "напиши",
    "ищем", "ищу", "нужен", "нужна", "нужны", "разыскивается",
    "приглашаем", "приглашаю", "рассматриваю", "рассматриваем",
    # ── Time/experience quantifiers ───────────────────────────────────────────
    "года", "лет", "год", "месяц", "месяцев",
    # ── Work-format qualifiers (frequently added/dropped between reposts) ─────
    "удалённо", "удаленно", "полностью", "гибрид", "офис",
    "remote", "hybrid", "office", "full", "fully",
    # ── Possessive / filler words in Russian job posts ────────────────────────
    "наша", "наш", "наши", "наше",
})


def _normalise(text: str) -> str:
    """Aggressively normalise job-post text for SimHash.

    Steps:
      1. Unicode normalisation (NFKC).
      2. Lowercase.
      3. Strip URLs (https://, t.me/).
      4. Strip email addresses (word@domain.tld).
      5. Strip Telegram @handles.
      6. Strip currency symbols (₽, $, €).
      7. Strip salary-magnitude abbreviations (тыс, руб, usd, …).
      8. Replace digit runs with «NUM» (salary 300к ≈ 320к after this).
      9. Strip remaining punctuation.
      10. Collapse whitespace.

    The goal is that two reposts of the same vacancy with minor
    formatting/salary/contact variations produce identical or near-identical
    normalised strings.  Contact details (handles, emails, URLs) are the
    most volatile part of reposts and must be stripped first.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    # Strip volatile contact tokens before anything else (they vary per channel
    # but carry zero semantic signal for dedup purposes).
    text = _RE_URL.sub(" ", text)
    text = _RE_EMAIL.sub(" ", text)
    text = _RE_HANDLE.sub(" ", text)
    text = _RE_CURRENCY_SYMS.sub(" ", text)
    text = _RE_SALARY_UNITS.sub(" ", text)
    text = _RE_DIGITS.sub("NUM", text)
    text = _RE_KEEP.sub(" ", text)         # punctuation → space
    text = _RE_WS.sub(" ", text).strip()
    return text


def _tokenise(text: str) -> list[str]:
    """Return word-level tokens, excluding stop-words."""
    return [w for w in text.split() if w not in _STOPWORDS and len(w) > 1]


def _bigrams(tokens: list[str]) -> list[str]:
    """Return consecutive word bigrams as 'w1_w2' strings."""
    if len(tokens) < 2:
        return tokens
    return [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]


# ── SimHash ───────────────────────────────────────────────────────────────────

def simhash(text: str) -> int | None:
    """Compute a 64-bit SimHash for *text*.

    Returns ``None`` if the text is too short to produce a reliable hash.
    """
    tokens = _tokenise(_normalise(text))
    if len(tokens) < _MIN_TOKENS:
        return None

    shingles = _bigrams(tokens)

    v = [0] * BITS
    for shingle in shingles:
        h = _fnv1a_64(shingle)
        for i in range(BITS):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1

    result = 0
    for i in range(BITS):
        if v[i] > 0:
            result |= (1 << i)
    return result


def hamming(h1: int, h2: int) -> int:
    """Count differing bits between two 64-bit integers (popcount of XOR)."""
    x = (h1 ^ h2) & _MASK64
    # Brian Kernighan's bit-counting trick
    count = 0
    while x:
        x &= x - 1
        count += 1
    return count


# ── Batch deduplication ───────────────────────────────────────────────────────

def deduplicate_batch(
    items: list[dict],
    state: "State",
    *,
    threshold: int = HAMMING_THRESHOLD,
    retention_days: int = RETENTION_DAYS,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Split *items* into (unique, duplicates).

    For each item:
    1. Compute SimHash.
    2. Check against the in-memory fingerprint index (loaded once from SQLite).
    3. Also check within-batch to catch same post arriving from multiple channels.
    4. If duplicate: add to ``duplicates`` list with the original inbox_item_id.
    5. If unique: add fingerprint to the index AND record it in State for future runs.

    Returns:
        unique     — items to process normally
        duplicates — [(item, original_inbox_item_id), ...] to mark as skipped
    """
    # Load existing fingerprints once (covers the retention window)
    existing: list[tuple[int, str]] = state.load_fingerprints(retention_days=retention_days)

    unique:     list[dict]                   = []
    duplicates: list[tuple[dict, str]]       = []

    # In-batch index: new fingerprints added this run (not yet in SQLite)
    batch_index: list[tuple[int, str]] = []

    for item in items:
        text = (item.get("rawText") or "").strip()
        fp = simhash(text)

        if fp is None:
            # Text too short for reliable hashing → treat as unique, let LLM decide
            unique.append(item)
            continue

        item_id = item["id"]

        # Search existing DB fingerprints.
        # ⚠ Исключаем СОБСТВЕННЫЙ отпечаток поста (self_id): при повторной
        # обработке (`openclaw retry` после починки) пост уже есть в индексе с
        # прошлого прогона и без этого объявлял бы дублем САМ СЕБЯ → уходил в
        # skipped, не доходя до извлечения. 25.07 так впустую ушёл дренаж
        # бэклога: `dedup duplicates=200 unique=0`, `extract_vacancy: 0`.
        original_id = _find_match(fp, existing, threshold, self_id=item_id)
        # Also search within-batch fingerprints
        if original_id is None:
            original_id = _find_match(fp, batch_index, threshold, self_id=item_id)

        if original_id is not None:
            duplicates.append((item, original_id))
        else:
            unique.append(item)
            # Register in batch index immediately so subsequent items in the
            # same batch can deduplicate against it.
            batch_index.append((fp, item_id))
            # Persist to SQLite for future runs
            state.add_fingerprint(
                fp,
                item_id,
                channel_handle=item.get("channelHandle"),
            )

    return unique, duplicates


def _find_match(
    fp: int,
    index: list[tuple[int, str]],
    threshold: int,
    *,
    self_id: str | None = None,
) -> str | None:
    """Return inbox_item_id of first fingerprint within Hamming distance.

    ``self_id`` — идентификатор обрабатываемого поста; его отпечаток
    пропускается, иначе повторный прогон того же поста (retry) находит запись,
    оставленную им же в прошлый раз, и пост становится «дублем самого себя».
    """
    for stored_fp, stored_id in index:
        if self_id is not None and stored_id == self_id:
            continue
        if hamming(fp, stored_fp) <= threshold:
            return stored_id
    return None


def cleanup(state: "State", *, retention_days: int = RETENTION_DAYS) -> int:
    """Evict stale fingerprints from SQLite. Call periodically (e.g. daily)."""
    return state.cleanup_fingerprints(retention_days=retention_days)
