"""Словарный экстрактор: три бага, найденные замером 28.08.2026.

Каждый тест написан по следам конкретной цифры, а не «на всякий случай»:
поэтому в них зашиты примеры из живых постов, а не выдуманные строки.
Пересчёт полноты — `zsh ops/check/ner_recall.command`.
"""

import pytest

from kernel.ner_extractor import SkillExtractor, _compile


class TestInstrumentBeforePeriod:
    """Хвостовой запрет содержал `\\.` — инструмент перед точкой не совпадал.

    Замер 28.08: `Python` в «опыт с Python.» не находился вовсе. В русских
    постах точка в конце пункта списка — норма, поэтому потеря была тихой и
    системной (полнота: май +0.9, июль +3.1 п.п. после правки).
    """

    def test_tool_at_end_of_sentence(self) -> None:
        assert _compile("Python").search("нужен опыт с Python.")
        assert _compile("Docker").search("деплой в Docker.")

    def test_word_boundary_still_holds(self) -> None:
        assert not _compile("Python").search("Pythonic")
        assert not _compile("Docker").search("Dockerfile")


class TestDottedNames:
    """`Node.js` не ловил `NodeJS`: точка была обязательной."""

    def test_both_spellings(self) -> None:
        pat = _compile("Node.js")
        for text in ("Node.js", "NodeJS", "nodejs"):
            assert pat.search(text), text

    def test_leading_dot_not_relaxed(self) -> None:
        """`.NET` НЕ становится `\\.?NET` — иначе совпало бы в «интернет».

        Регистронезависимый поиск делает это ошибкой первого рода на ровном
        месте: «Netflix», «интернет», «магнетизм» — обычные слова.
        """
        pat = _compile(".NET")
        assert pat.search("стек .NET")
        assert not pat.search("интернет")
        assert not pat.search("Netflix")


class TestAliasCollision:
    """Ключом дедупликации был один алиас на весь справочник.

    Инструмент, чей алиас уже занял другой tool_id, выпадал из индекса
    насовсем. Замер 28.08 (`requirements_loss_layers.command` §3) нашёл
    пятерых: t_aws_s3, t_docker_compose, t_gitlab_ci, t_jquery, t_mariadb —
    во всех случаях алиас забрал «родитель».
    """

    def test_child_and_parent_both_match(self) -> None:
        canonical = {
            "t_js": ["JavaScript", "JS", "jQuery"],
            "t_jquery": ["jQuery"],
            "t_docker": ["Docker", "Docker Compose"],
            "t_docker_compose": ["Docker Compose"],
        }
        found = set(SkillExtractor(canonical).extract_ids(
            "Пишем на jQuery, деплой через Docker Compose",
        ))
        assert {"t_jquery", "t_docker_compose"} <= found, "выпавшие не вернулись"
        assert {"t_js", "t_docker"} <= found, "родители пропали"

    def test_same_alias_one_tool_still_collapses(self) -> None:
        """Дубли алиаса У ОДНОГО инструмента по-прежнему схлопываются."""
        ex = SkillExtractor({"t_py": ["Python", "python", "PYTHON"]})
        assert len(ex._rules) == 1


# ── Контекстные сторожа (10.09.2026) ─────────────────────────────────

_TRAPS = {
    "st_solid": ["SOLID", "solid"],
    "t_requests": ["Requests", "requests"],
    "t_r": ["R", "r"],
    "t_logic_pro": ["Logic Pro", "Logic", "Logic Pro X"],
    "oc_enterprise": ["Enterprise", "enterprise"],
    "t_after_effects": ["After Effects", "ae"],
    "t_python": ["Python"],
    "t_sql": ["SQL"],
}


def _traps() -> SkillExtractor:
    return SkillExtractor(_TRAPS)


@pytest.mark.parametrize(("text", "expected"), [
    # Ловушка: обычное слово в лексике самого объявления.
    ("Ищем разработчика с solid experience", []),
    ("Знание принципов SOLID и чистого кода", ["st_solid"]),
    ("Опыт работы с HTTP requests и REST API", []),
    ("Python, requests, BeautifulSoup — парсинг", ["t_python", "t_requests"]),
    ("Отдел R&D ищет аналитика", []),
    ("Аналитик: SQL, R, Python", ["t_python", "t_r", "t_sql"]),
    ("Понимание business logic приложения", []),
    ("Сведение и мастеринг в Logic Pro", ["t_logic_pro"]),
    ("Моушн-дизайнер: AE, Premiere", ["t_after_effects"]),
    ("Специалист по AE в области бухгалтерии", []),
])
def test_trap_keys_need_context(text, expected):
    """Ключ-ловушка зажигается только при подтверждающем контексте.

    Класс найден 10.09: `solid`, `requests`, `r`, `Logic`, `enterprise`
    совпадают с обычными словами и делают из мусора требование С
    требованиями — невидимое фильтру по «пусто%».
    """
    assert sorted(_traps().extract_ids(text)) == sorted(expected)


def test_removing_the_alias_would_not_have_helped():
    """Имя узла — тоже ключ словаря, и ловушка сидела именно в нём.

    `populate_mask_skills.py` кладёт в canonical_skills `[name] + aliases`.
    Поэтому «снять алиас `solid`» у четырёх узлов из пяти было бы тихим
    ничем: имя (`SOLID`, `Requests`, `R`, `Enterprise`) продолжило бы
    совпадать. Сторож обязан работать и без алиасов вовсе.
    """
    only_names = SkillExtractor({"st_solid": ["SOLID"], "t_requests": ["Requests"]})
    assert only_names.extract_ids("Ищем solid experience и HTTP requests") == []


def test_forbidden_phrase_does_not_eat_a_real_mention():
    """Запрет накрывает совпадение, а не окрестность.

    Иначе «solid experience» в начале поста гасит «принципы SOLID» строкой
    ниже — ловушка отнимала бы настоящее требование.
    """
    text = "solid experience; ниже: принципы SOLID обязательны"
    assert _traps().extract_ids(text) == ["st_solid"]


def test_never_guard_silences_the_key_entirely():
    """`enterprise` словарём не отличить от прилагательного — гасим совсем.

    Узел остаётся в дереве: руками его поставить можно, автоматически — нет.
    """
    assert _traps().extract_ids("Разработка enterprise-решений для банков") == []


def test_cyrillic_alias_does_not_start_mid_word():
    """Голова алиаса закрыта и для кириллицы: «ооп» не должно совпадать
    внутри «кооперативным» (замер 11.09). Хвост открыт: «ооп,» и «ооп-» —
    совпадают, как и основа «гипотез» в «гипотезой»."""
    from kernel.ner_extractor import SkillExtractor

    ex = SkillExtractor({"sk_oop": {"name": "ООП", "aliases": ["ооп"]},
                         "sk_h": {"name": "Проверка гипотез", "aliases": ["гипотез"]}})
    assert ex.extract_ids("работа над кооперативным экшеном") == []
    assert ex.extract_ids("знание принципов ООП, SOLID") == ["sk_oop"]
    assert ex.extract_ids("работа с гипотезой роста") == ["sk_h"]


def test_cyrillic_head_is_the_whole_block_not_the_russian_alphabet():
    """Голова закрыта всем блоком кириллицы, а не «А-Яа-яЁё»: украинская
    «і» (U+0456) в диапазон не входила, и «шим» совпадал внутри
    «важливішими» (замер 12.09, 68 из 80). Хвост при этом остаётся
    открытым и для чужой кириллицы: «медициналық» — настоящее попадание
    основы «медицин», как и «ритейлі» (замер 13.09,
    `ops/check/cyrillic_key_boundaries.command`: все 63 такие пары за
    45 дн. — склонения тех же слов)."""
    from kernel.ner_extractor import SkillExtractor

    ex = SkillExtractor({"t_pwm": {"name": "ШИМ", "aliases": ["шим"]},
                         "ex_h": {"name": "Healthcare", "aliases": ["медицин"]}})
    assert ex.extract_ids("одним із найважливішими завдань") == []
    assert ex.extract_ids("генерация ШИМ-сигнала на таймере") == ["t_pwm"]
    assert ex.extract_ids("медициналық көмек көрсету") == ["ex_h"]


def _experience():
    return SkillExtractor({
        "ex_fintech": {"name": "Финтех / Банки", "aliases": ["банк", "финтех"]},
        "ex_healthcare": {"name": "Healthcare / MedTech", "aliases": ["медицин", "клиник"]},
    })


@pytest.mark.parametrize(("text", "expected"), [
    # Кириллический хвост открыт, и основа «банк» уходит в чужое слово.
    ("Юрист по банкротству физических лиц", []),
    ("Ведущий банкетов и корпоративов", []),
    ("Стажёр-маркетолог в Альфа-Банк, гибрид", ["ex_fintech"]),
    ("Опыт работы системным аналитиком в банке/финтехе", ["ex_fintech"]),
    # «медицин» и «клиник» — блок льгот, а не домен.
    ("Условия: официальное оформление, медицинская страховка, ДМС", []),
    ("ДМС с первого месяца, включая стоматологию, в лучших клиниках Москвы", []),
    ("Компенсация медицинских услуг после испытательного срока", []),
    ("Продакт в команду дистанционного мониторинга и медицинских устройств", ["ex_healthcare"]),
    ("SMM-специалист в клинику пластической хирургии", ["ex_healthcare"]),
])
def test_experience_keys_skip_benefits_and_foreign_stems(text, expected):
    """Ключи опыта (seed_experience_keys, 11.09) гасятся там, где основа ушла
    в другое слово или в блок льгот. Замер: «медицинская страховка» — 222 из
    854 совпадений «медицин»; «банкрот/банкет/банкнот» — 36 из 1 637 «банк».
    """
    assert sorted(_experience().extract_ids(text)) == sorted(expected)


def test_benefit_line_does_not_eat_a_real_healthcare_mention():
    """Запрет накрывает совпадение, а не пост: льгота выше не гасит домен ниже."""
    text = "ДМС в клиниках Москвы. Проект: платформа для медицинских лабораторий"
    assert _experience().extract_ids(text) == ["ex_healthcare"]


@pytest.mark.parametrize(("text", "expected"), [
    ("Работа по Калифорнийскому времени c 9am до 6pm", []),
    ("Подробнее: https://t.me/c/1976258972/18776 и https://t.me/+-c-Mp5-l1PwzMWNi", []),
    ("Удостоверение категории B, C, D с правом управления трактором", []),
    ("Канал для HR — Вакансии в Кадрах, C&B, HR", []),
    ("Английский уровня C — обязательно", []),
    ("Знание C/C++ на продвинутом уровне", ["t_c", "t_cpp"]),
    ("Отличное знание языка C, опыт embedded development", ["t_c"]),
    ("Разработка драйверов на C под Linux", ["t_c"]),
])
def test_c_is_a_language_only_next_to_language_context(text, expected):
    """`t_c` — ложный узел не словаря, а одной буквы: у 18.3% свежих аналитических
    вакансий стоял требованием при 3 упоминаниях C++ из 111 текстов (C1,
    10.09). Заглавная C только с соседями про язык; строчная — не C вовсе."""
    ex = SkillExtractor({"t_c": {"name": "C", "aliases": []},
                         "t_cpp": {"name": "C++", "aliases": []}})
    assert sorted(ex.extract_ids(text)) == sorted(expected)


# ── Ловушки, найденные замером на не-вакансиях (13.09) ────────────────
#
# `scripts/tree_alias_on_junk.py`: знаменатель — посты, где профессии нет
# ни в шапке, ни в теле; там требований не может быть по устройству, и
# любое срабатывание ложно. Каждый узел ниже назван с механизмом.


def _junk_traps() -> SkillExtractor:
    return SkillExtractor({
        "t_room": ["Room"],
        "t_near": ["NEAR Protocol", "NEAR"],
        "t_dotnet": [".NET", ".net"],
        "t_google_analytics": ["Google Analytics", "GA"],
        "t_gcc": ["GCC", "gcc", "g++"],
        "t_ajax": ["Ajax", "AJAX"],
        "t_selenium": ["Selenium", "Тестирование ПО", "Тестирование сайтов"],
        "t_kotlin": ["Kotlin"],
    })


@pytest.mark.parametrize(("text", "expected"), [
    # Room — ловушка в ИМЕНИ узла, алиасов нет: «Room-Bar», англ. room.
    ("Элитный Room-Bar приглашает на работу", []),
    ("Android: Kotlin, Room, Retrofit", ["t_kotlin", "t_room"]),
    # NEAR — английский предлог в адресе.
    ("Location: Near Marina Bay, Singapore", []),
    ("Rust developer for NEAR Protocol smart contracts", ["t_near"]),
    # .net — любой домен.
    ("Подробнее на hrdf.org.net и на site.net", []),
    ("Backend developer C# / .NET Core", ["t_dotnet"]),
    # GA — узбекский дательный аффикс, написанный отдельно, и любая аббревиатура.
    ("Rossiyada ishlash uchun xodimlar ishga taklif qilinadi ga", []),
    ("Веб-аналитик: Google Analytics (GA4), GTM", ["t_google_analytics"]),
    # GCC — Gulf Cooperation Council в объявлениях о работе в Заливе.
    ("Jobs in GCC countries, Dubai, visa provided", []),
    ("Embedded C developer: gcc, cmake, gdb", ["t_gcc"]),
    # Ajax Systems — украинская компания.
    ("Ajax Systems запрошує студентів технічних спеціальностей", []),
    ("Frontend: JavaScript, AJAX, jQuery", ["t_ajax"]),
    # Selenium — алиасы-компетенции: «тестирование ПО» ≠ имя инструмента.
    ("Ручное тестирование ПО, тест-кейсы, баг-репорты", []),
    ("Тестирование сайтов вручную", []),
    ("QA Automation: Selenium, pytest", ["t_selenium"]),
])
def test_junk_measured_traps_need_context(text, expected):
    assert sorted(_junk_traps().extract_ids(text)) == sorted(expected)
