"""Dictionary-based skills pre-extractor for the hybrid NER pipeline.

Scans raw text for IT skill mentions using canonical_skills aliases.
Returns matched tool_ids BEFORE the LLM call, enabling a much shorter
LLM prompt — no need to embed the full ~8K-token canonical_skills dict.

Typical performance:
  - Build index from 467 tools: ~5 ms (once per session/batch)
  - Extract from a single document: ~0.5 ms
  - Recall vs. tools recorded in vacancy_requirements: 90.2 %
    (замер 28.08.2026, май; пересчёт — zsh ops/check/ner_recall.command.
     Август в том замере не показателен: при NER_PREEXTRACT=true
     требования по построению ⊆ pre_matched, полнота тавтологична)

Hybrid pipeline stages for extract_vacancy / extract_candidate:

  Stage 0 (template_extractor) — zero LLM, for fully structured posts
  Stage 1 (ner_extractor)      — dict-based, free, fast  ← this module
  Stage 2 (LLM)                — structural fields only, no skill dict embed

Usage::

    from kernel.ner_extractor import SkillExtractor

    extractor = SkillExtractor(mask["canonicalSkills"])   # build once per role
    tool_ids = extractor.extract_ids(raw_text)            # ~0.5 ms per doc
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillMatch:
    tool_id: str
    matched_alias: str
    start: int           # char offset in source text
    end: int


# ---------------------------------------------------------------------------
# Special-term overrides
# ---------------------------------------------------------------------------
# Skills that contain regex meta-chars or look like sub-strings of other
# skills need hand-crafted patterns.  Keys are lowercase.

_SPECIAL_PATTERNS: dict[str, str] = {
    # Dot-prefixed / Plus-suffixed
    "c++":          r"C\+\+",
    "c#":           r"C#",
    ".net":         r"\.NET",
    "asp.net":      r"ASP\.NET",
    "asp.net core": r"ASP\.NET\s+Core",
    "f#":           r"F#",
    "q#":           r"Q#",
    # JS frameworks / runtimes with dot
    "node.js":      r"Node\.js",
    "vue.js":       r"Vue\.js",
    "next.js":      r"Next\.js",
    "nuxt.js":      r"Nuxt\.js",
    "nest.js":      r"Nest\.js",
    "express.js":   r"Express\.js",
    "three.js":     r"Three\.js",
    "d3.js":        r"D3\.js",
    "ember.js":     r"Ember\.js",
    "backbone.js":  r"Backbone\.js",
    "socket.io":    r"Socket\.io",
    "react.js":     r"React\.js",
    "angular.js":   r"AngularJS",
    # Very short identifiers — need strict word boundaries
    "r":            r"\bR\b",
    # "C" but not "C++"/"C#" — и ТОЛЬКО заглавная: словарь компилируется с
    # IGNORECASE, и строчная «c» ловила латинскую c вместо русского «с»
    # («c 9am», «c опытом») и ссылки t.me/c/…, t.me/+-c-Mp5… (замер 11.09:
    # 1 413 вакансий окна, почти все — это). Остальное добирает сторож.
    "c":            r"(?-i:\bC\b)(?!\+\+|#)",
    "go":           r"\bGo\b",
    "ml":           r"\bML\b",
    "ai":           r"\bAI\b",
    "bi":           r"\bBI\b",
    "qa":           r"\bQA\b",
    "ui":           r"\bUI\b",
    "ux":           r"\bUX\b",
    "ux/ui":        r"\bUX/UI\b",
    "ui/ux":        r"\bUI/UX\b",
}


# ---------------------------------------------------------------------------
# Контекстные сторожа для ключей-ловушек
# ---------------------------------------------------------------------------
# Класс дефектов, найденный 10.09: ключ словаря совпадает с обычным словом и
# делает из мусора требование С требованиями — невидимое любому фильтру по
# «пусто%». Решение владельца 10.09 звучало как «снять пять алиасов», но
# СНЯТИЕ АЛИАСА ЗДЕСЬ НИЧЕГО НЕ МЕНЯЕТ: `populate_mask_skills.py` кладёт в
# canonical_skills `[name] + aliases`, то есть ИМЯ узла — тоже ключ. У четырёх
# из пяти ловушка сидела именно в имени (`SOLID`, `Enterprise`, `Requests`,
# `R`), и снятие алиаса было бы тихим ничем.
#
# Поэтому ключ гасится не удалением, а условием: совпадение засчитывается,
# только если рядом стоит то, что делает его настоящим. Это же решение по
# `ae` → `t_after_effects` («строить разбор контекста в матчере»): вердикт был
# классовым, а исполнить его до сих пор было нечем — `alias_trap_verdicts.jsonl`
# в проде никто не читает.
#
# Список ручной и неполный по определению — как `_COMMON_RAW` в
# `app/services/alias_guard.py`. Тот модуль ПРЕДУПРЕЖДАЕТ редактора при записи
# алиаса, этот — РЕШАЕТ при извлечении; списки разного назначения и намеренно
# не общие.

@dataclass(frozen=True)
class _Guard:
    """Условие, при котором совпадение ключа-ловушки засчитывается."""

    require: "re.Pattern | None" = None   # обязано стоять рядом
    forbid: "re.Pattern | None" = None    # не должно стоять рядом
    window: int = 80                      # символов влево и вправо
    never: bool = False                   # словарь различить не может — не зажигать


def _rx(pattern: str) -> "re.Pattern":
    return re.compile(pattern, re.IGNORECASE)


_CONTEXT_GUARDS: dict[tuple[str, str], _Guard] = {
    # SOLID — принципы ООП. Ловушка: «solid experience», «solid background».
    # 528 срабатываний в корпусе аналитика (замер 10.09), где принципов ООП
    # не спрашивают вовсе.
    ("solid", "st_solid"): _Guard(
        require=_rx(r"принцип|principle|ООП|OOP|\bSRP\b|\bOCP\b|\bLSP\b|\bISP\b|\bDIP\b|"
                    r"\bDRY\b|\bKISS\b|паттерн|design\s+pattern|чист\w+\s+код|clean\s+code"),
        forbid=_rx(r"solid\s+(experience|background|knowledge|understanding|grasp|track)"),
    ),
    # Requests — библиотека Python. Ловушка: «HTTP requests», «pull requests»,
    # «requests per second». 574 срабатывания.
    ("requests", "t_requests"): _Guard(
        require=_rx(r"import\s+requests|requests\.(get|post|put|session)|pip\s+install|"
                    r"\bpython\b|\brequests\b\s*[,/]\s*(beautifulsoup|bs4|aiohttp|httpx|selenium)|"
                    r"(beautifulsoup|bs4|aiohttp|httpx|selenium)\s*[,/]\s*\brequests\b"),
        forbid=_rx(r"(http|pull|merge|api|feature|change|user)\s+requests|"
                   r"requests?\s+(per|в)\s+(second|секунд|сек)"),
    ),
    # R — язык статистики. Ловушка: одна буква. `\bR\b` при IGNORECASE ловит
    # и «R&D», и «r» в перечислении. 609 срабатываний.
    ("r", "t_r"): _Guard(
        require=_rx(r"\bR\s*Studio|\bRStudio|язык\w*\s+R\b|\bна\s+R\b|\bв\s+R\b|"
                    r"\bR\s*[/+&]\s*Python|\bPython\s*[/+&]\s*R\b|ggplot|dplyr|tidyverse|shiny|"
                    r"\bR\b\s*[,;]\s*(python|sql|matlab|stata|sas)"),
        forbid=_rx(r"R\s*&\s*D|\bR&D\b|research\s+and\s+development"),
    ),
    # Logic Pro — звуковой редактор. Ловушка: «business logic», «логика».
    # Здесь имя узла («Logic Pro») безопасно, ловушка ровно в алиасе `Logic`:
    # это единственный из пяти, где снятие алиаса и было бы решением. Гасим
    # тем же механизмом, чтобы правило было в одном месте, а не в двух.
    ("logic", "t_logic_pro"): _Guard(
        require=_rx(r"Logic\s+Pro|ableton|cubase|fl\s*studio|pro\s*tools|garageband|"
                    r"сведени|мастеринг|аранжир|звукореж"),
        forbid=_rx(r"(business|бизнес|программн\w+|прикладн\w+)[\s-]*логик|business\s+logic"),
    ),
    # Enterprise — прилагательное почти в каждом объявлении («enterprise-
    # решения», «enterprise-級 клиенты»). 793 срабатывания. Отличить
    # компетенцию от прилагательного словарём НЕЛЬЗЯ: ключ не гасится
    # условием, он гасится совсем. Узел остаётся — руками его ставить можно.
    ("enterprise", "oc_enterprise"): _Guard(never=True),
    # AE — After Effects. Вердикт классовый (02.09), исполнять было нечем.
    ("ae", "t_after_effects"): _Guard(
        require=_rx(r"after\s+effects|premiere|photoshop|illustrator|cinema\s*4d|nuke|"
                    r"моушн|motion|анимац|видеомонтаж|композ|adobe"),
    ),
    # C — язык. Заглавная C сама по себе — категория прав («B, C, D»), C&B,
    # C-level, «план C», витамин. Ревизия 11.09: 10 из 12 окон — не язык;
    # у 18.3% свежих аналитических вакансий стояло требованием (C1). Язык
    # узнаётся по соседям: C/C++, «язык C», embedded, ядро, компилятор.
    ("c", "t_c"): _Guard(
        require=_rx(r"C\s*/\s*C\+\+|C\+\+\s*/\s*C\b|\bC\s*,\s*C\+\+|C\+\+\s*,\s*C\b|"
                    r"язык\w*\s+C\b|\bна\s+C\b|\bСи\b|\bC\s+(и|and)\s+C\+\+|"
                    r"embedded|низкоуровн|микроконтроллер|драйвер|kernel|\bядр[оа]\b|RTOS|"
                    r"bare-?metal|STM32|\bARM\b|\bgcc\b|clang|assembler|ассемблер|"
                    r"системн\w+\s+программ|POSIX|\bLinux\b|firmware|прошивк"),
        forbid=_rx(r"категори\w*[^.\n]{0,40}\bC\b|C\s*&\s*B|C-level|уровн\w*\s+C\b|level\s+C\b|"
                   r"vitamin\s+C|витамин\w*\s+C|план\w*\s+C\b|plan\s+C\b"),
    ),
    # Ключи опыта (seed_experience_keys, 11.09). Кириллический хвост открыт
    # по устройству, поэтому основа «банк» ловит и «банкротство» — ключ не
    # снимается, а гасится там, где основа ушла в другое слово. Замер по
    # 46 942 вакансиям окна: 1 637 совпадений, 36 из них — эти три.
    ("банк", "ex_fintech"): _Guard(forbid=_rx(r"банкет|банкрот|банкнот")),
    # «медицин» в объявлении — это прежде всего «медицинская страховка» из
    # блока льгот: 222 из 854 совпадений. Домен здравоохранения — остальное:
    # медицинские устройства, данные, сестра, копирайтер медицинского бренда.
    ("медицин", "ex_healthcare"): _Guard(
        forbid=_rx(r"медицинск\w*\s+(страхов\w*|обслуживани\w*|услуг\w*|"
                   r"документ\w*|осмотр\w*)|\bДМС\b"),
    ),
    # «клиник» — та же льгота другими словами: «ДМС в лучших клиниках Москвы».
    # Запрет тянется от льготы до самого слова, чтобы накрыть совпадение.
    ("клиник", "ex_healthcare"): _Guard(
        forbid=_rx(r"(\bДМС\b|страхов\w*)[^.\n]{0,60}клиник\w*"),
    ),
    # ── Замер ложных алиасов на не-вакансиях (13.09, `tree_alias_on_junk`) ──
    # Знаменатель — посты, где профессии нет ни в шапке, ни в теле: там
    # требований не может быть по устройству, и любое срабатывание ложно.
    # 3.1 % строк требований, класс не массовый — но узлы ниже названы
    # с механизмом, а не по ощущению.
    #
    # Room — Android-библиотека. Ловушка — само ИМЯ узла, алиасов нет:
    # «Room-Bar приглашает на работу», англ. «room». 7 из 14 срабатываний
    # на не-вакансиях. Узнаётся по соседям из Android-стека.
    ("room", "t_room"): _Guard(
        require=_rx(r"android|kotlin|jetpack|sqlite|\bdao\b|persistence|coroutines?|"
                    r"hilt|dagger|retrofit|compose|livedata|viewmodel|\borm\b"),
        forbid=_rx(r"room[\s\-]?bar|(meeting|conference|living|dining|show|chat|"
                   r"escape|control)[\s\-]?room|room\s+(for|to|service|type)"),
    ),
    # NEAR — блокчейн. Алиас `NEAR` — английский предлог: «Location: Near
    # Marina Bay». Имя «NEAR Protocol» безопасно, гасится только короткий.
    ("near", "t_near"): _Guard(
        require=_rx(r"protocol|blockchain|блокчейн|web3|\brust\b|solana|wasm|crypto|"
                    r"dapp|defi|smart[\s\-]?contract|смарт[\s\-]?контракт|"
                    r"validator|валидатор"),
        forbid=_rx(r"near\s+(the|a|an|to|by|me|you|us|future|term|marina|"
                   r"metro|station|city|centre|center)\b|\bnear\s+[A-Z][a-z]+"),
    ),
    # .NET — алиас `.net` зажигается на любом домене и почте («hr@ukr.net»,
    # «jobs2.net») и — что нашлось только при чтении убитых строк — на
    # зарплатной нотации: «Вилка: 250–280k .net», «5500–6500$.net» (net of
    # tax). Из 2 449 проверяемых требований t_dotnet ложными оказались
    # 1 148 (47 %) — крупнейший поимённо названный дефект словаря.
    # Запрет «слово перед точкой» не годится: он накрыл бы ASP.NET и VB.NET.
    # Поэтому условие — соседи платформы; домен в посте про C# не мешает.
    (".net", "t_dotnet"): _Guard(
        require=_rx(r"c#|c\s*sharp|asp|\.net\s*(core|framework|\d)|entity\s+framework|"
                    r"blazor|xamarin|maui|wpf|winforms|nuget|visual\s+studio|"
                    r"developer|разработ|программист|backend|бэкенд|engineer|"
                    r"\bvb\b|\bef\s+core|dotnet"),
        forbid=_rx(r"https?://\S*\.net|www\.\S*\.net"),
    ),
    # Google Analytics — алиас `GA` совпал с узбекским дательным аффиксом,
    # который пишут отдельно («ishga», «lavozimlarga» → «ga»), и с любой
    # аббревиатурой. 14 из 53 срабатываний на не-вакансиях. Только со
    # спутниками веб-аналитики.
    ("ga", "t_google_analytics"): _Guard(
        require=_rx(r"google|analytics|\bga4\b|\bgtm\b|tag\s+manager|метрик|metrika|"
                    r"веб[\s\-]?аналитик|web\s+analytics|utm|конверси|conversion"),
    ),
    # GCC — компилятор. В объявлениях о работе в Заливе — Gulf Cooperation
    # Council: 14 из 30 срабатываний в не-IT постах. Компилятор узнаётся по
    # соседям: C/C++, clang, make, embedded, toolchain.
    ("gcc", "t_gcc"): _Guard(
        require=_rx(r"\bC\+\+|\bC\b|clang|cmake|\bmake\b|toolchain|embedded|"
                    r"компилятор|compiler|linux|gdb|\bgnu\b|arm|стандарт\w*\s+c"),
        forbid=_rx(r"gcc\s+(countr|region|nationals?|market|visa)|gulf"),
    ),
    # Ajax — техника JS. «Ajax Systems» — украинская компания, 3 из 4
    # срабатываний на не-вакансиях были её объявлениями.
    ("ajax", "t_ajax"): _Guard(
        forbid=_rx(r"ajax\s+systems|ajax\s+alarm"),
    ),
    # Selenium — у узла два алиаса-КОМПЕТЕНЦИИ: «Тестирование ПО» и
    # «Тестирование сайтов». Это не имена инструмента: любая вакансия со
    # словами «тестирование ПО» получала требование Selenium. Тот же класс,
    # что `enterprise`: словарём не различить — гасится совсем, узел и алиас
    # остаются на месте (правка алиаса в БД — вопрос владельцу, §8 записки
    # 13.09).
    ("тестирование по", "t_selenium"): _Guard(never=True),
    ("тестирование сайтов", "t_selenium"): _Guard(never=True),
}


def _guard_for(alias: str, tool_id: str) -> "_Guard | None":
    return _CONTEXT_GUARDS.get((alias.strip().lower(), tool_id))


# Внутренняя точка в имени: `Node.js` → `Node\.?js`, чтобы ловить и `NodeJS`.
# Ведущая точка НЕ трогается: `\.?NET` совпал бы в «интернет» и «Netflix»
# (проверено 28.08).
_INNER_DOT = re.compile(r"(?<=[A-Za-z0-9])\\\.(?=[A-Za-z0-9])")


def _compile(alias: str) -> re.Pattern | None:
    """Return a compiled pattern for *alias*, or None on error."""
    lower = alias.lower()
    override = _SPECIAL_PATTERNS.get(lower)

    if override:
        raw = _INNER_DOT.sub(r"\\.?", override)
    else:
        escaped = _INNER_DOT.sub(r"\\.?", re.escape(alias))
        if len(alias) <= 2:
            raw = rf"\b{escaped}\b"
        else:
            # Хвостовой запрет БЕЗ `\.` — иначе инструмент перед точкой не
            # совпадает вовсе. Замер 28.08: `Python` в «опыт с Python.»,
            # `Docker` в «Docker.» и `Node.js` в «NodeJS» не находились.
            # Полнота против записанных требований: май +0.9, июль +3.1 п.п.
            # (`ops/check/ner_recall.command`).
            # Голова закрыта и для кириллицы: «ооп» совпадало внутри
            # «кооперативным», «код» — внутри «переход» (замер 11.09,
            # new_keys_firing: 313 «ооп», первый образец — Level Artist на
            # Unity). Закрыта ВСЕМ блоком кириллицы, а не русским алфавитом:
            # диапазон «А-Яа-яЁё» не знал украинских «і/ї/є/ґ» и казахских
            # букв, и «шим» совпадал внутри «важливішими» — ключ, стоящий
            # сразу после любой кириллической буквы, всегда внутри чужого
            # слова (замер 13.09, `ops/check/cyrillic_key_boundaries.command`:
            # ни одного настоящего попадания с такой головой за 45 дн.).
            # Хвост для кириллицы открыт НАМЕРЕННО и это не пять исключений
            # seed_math_stats, а норма словаря: 6 320 пар (ключ, пост) за
            # 45 дн. живут только на склонении («медицин», «высоконагруж»,
            # «логирован», «гипотез»), и украинские/казахские окончания
            # («ритейлі», «банківських», «медициналық») — тоже настоящие
            # попадания, а не ложные. Ключ, который зажигается как префикс
            # чужого слова («шим» в «шимолий»), лечится на уровне ключа —
            # списком отказов сида и `new_keys_firing`, не границей.
            raw = rf"(?<![A-Za-z0-9_\u0400-\u04FF]){escaped}(?![A-Za-z0-9_])"

    try:
        return re.compile(raw, re.IGNORECASE)
    except re.error:
        return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

def _first_allowed(pattern: "re.Pattern", text: str,
                   guard: "_Guard | None") -> "re.Match | None":
    """Первое совпадение, прошедшее сторожа.

    Перебираем ВСЕ вхождения, а не только первое: в одном посте «solid
    experience» вполне может стоять выше, чем «принципы SOLID», и брать только
    первое означало бы потерять настоящее требование из-за ловушки.
    """
    if guard is None:
        return pattern.search(text)
    for m in pattern.finditer(text):
        if _allowed(guard, text, m):
            return m
    return None


def _allowed(guard: "_Guard", text: str, m: "re.Match") -> bool:
    """Проходит ли одно совпадение сторожа. Вынесено отдельно, чтобы приборы
    (`ops/check/cyrillic_key_boundaries.command`) судили КАЖДОЕ вхождение той
    же логикой, что прод, а не своей копией."""
    lo = max(0, m.start() - guard.window)
    around = text[lo : m.end() + guard.window]
    # Запрет обязан НАКРЫВАТЬ само совпадение, а не просто стоять рядом:
    # иначе «solid experience» в начале поста гасит «принципы SOLID» пятью
    # словами ниже — то есть ловушка отнимает настоящее требование.
    if guard.forbid is not None and any(
        f.start() <= m.start() - lo < f.end()
        for f in guard.forbid.finditer(around)
    ):
        return False
    return guard.require is None or guard.require.search(around) is not None


class SkillExtractor:
    """
    Build *once* per role/session from a canonical_skills dict; reuse for
    every document in the batch.

    ``canonical_skills`` format (as returned by the backend mask API):

        {
            "t_python":  ["Python", "python3", "py"],
            "t_docker":  ["Docker", "docker-compose"],
            ...
        }

    Values may also be plain dicts (``{"name": ..., "aliases": [...]}``) —
    both shapes are normalised internally.
    """

    def __init__(self, canonical_skills: dict) -> None:
        # (compiled_pattern, tool_id) — ordered longest alias first
        self._rules: list[tuple[re.Pattern, str, _Guard | None]] = []
        self._build(canonical_skills)

    # ------------------------------------------------------------------
    # Internal build
    # ------------------------------------------------------------------

    def _iter_aliases(self, canonical_skills: dict):
        """Yield (alias, tool_id) pairs from any supported dict shape."""
        for tool_id, value in canonical_skills.items():
            if isinstance(value, list):
                names = value
            elif isinstance(value, dict):
                # {"name": "...", "aliases": [...]} or similar
                names = [value.get("name", "")]
                names += value.get("aliases", [])
            else:
                names = [str(value)]

            for name in names:
                if name and isinstance(name, str):
                    alias = name.strip()
                    if len(alias) >= 1:
                        yield alias, tool_id

    def _build(self, canonical_skills: dict) -> None:
        pairs: list[tuple[str, str]] = list(self._iter_aliases(canonical_skills))

        # Sort longest → shortest so multi-word aliases win over sub-tokens
        pairs.sort(key=lambda p: len(p[0]), reverse=True)

        # Ключ — ПАРА (алиас, инструмент). Раньше ключом был один алиас на
        # весь справочник, и при совпадении алиаса у двух инструментов второй
        # молча выпадал из индекса: совпасть он не мог никогда, сколько бы раз
        # его ни написали в тексте. Замер 28.08
        # (`ops/check/requirements_loss_layers.command` §3) нашёл пятерых:
        # t_aws_s3←t_aws, t_docker_compose←t_docker, t_gitlab_ci←t_gitlab,
        # t_jquery←t_js, t_mariadb←t_mysql — все вложенные понятия, у которых
        # общий алиас забрал «родитель». Теперь такой текст даёт оба id;
        # дубли одного и того же алиаса У ОДНОГО инструмента по-прежнему
        # схлопываются.
        seen_patterns: set[tuple[str, str]] = set()
        for alias, tool_id in pairs:
            key = (alias.lower(), tool_id)
            if key in seen_patterns:
                continue
            seen_patterns.add(key)

            pattern = _compile(alias)
            if pattern is not None:
                self._rules.append((pattern, tool_id, _guard_for(alias, tool_id)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, text: str) -> list[SkillMatch]:
        """
        Return all skill matches in *text*. At most one match per tool_id
        (first occurrence wins).  Results are **not** sorted.
        """
        seen: set[str] = set()
        matches: list[SkillMatch] = []

        for pattern, tool_id, guard in self._rules:
            if tool_id in seen:
                continue
            if guard is not None and guard.never:
                continue
            m = _first_allowed(pattern, text, guard)
            if m:
                matches.append(SkillMatch(
                    tool_id=tool_id,
                    matched_alias=m.group(0),
                    start=m.start(),
                    end=m.end(),
                ))
                seen.add(tool_id)

        return matches

    def extract_ids(self, text: str) -> list[str]:
        """Return tool_ids found in *text*, ordered by position in text."""
        matches = self.extract(text)
        matches.sort(key=lambda m: m.start)
        return [m.tool_id for m in matches]

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def recall_stats(self, texts: list[str]) -> dict:
        """
        Quick benchmark over a list of raw texts.

        Returns::

            {
                "documents": 100,
                "avg_tools_per_doc": 5.3,
                "total_matches": 530,
                "top_tools": [("t_python", 80), ...],   # top-20
            }
        """
        from collections import Counter
        counter: Counter = Counter()
        for text in texts:
            for tid in self.extract_ids(text):
                counter[tid] += 1

        total = sum(counter.values())
        n = len(texts) or 1

        return {
            "documents": len(texts),
            "avg_tools_per_doc": round(total / n, 2),
            "total_matches": total,
            "top_tools": counter.most_common(20),
        }
