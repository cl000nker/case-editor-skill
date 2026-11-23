#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Типографика для кейсов портфолио.

Что делает:
  * расставляет неразрывные пробелы (NBSP) после коротких предлогов,
    между числом и существительным, между числом и единицей;
  * меняет прямые кавычки на ёлочки, вложенные — на лапки;
  * приводит дефисы-тире к правильному виду, диапазоны к en dash;
  * убирает двойные пробелы и пробелы перед знаками;
  * сообщает о висячих предлогах, которые остались.

Использование:
    python typograph.py case.md            # отчёт, файл не меняется
    python typograph.py case.md --write    # переписать файл
    python typograph.py case.md --check    # только проверки, exit code 1 если есть ошибки

Зависимостей нет, Python 3.8+.
"""

import re
import sys
import argparse
from pathlib import Path

NBSP = "\u00A0"

# Короткие предлоги и союзы, которые не должны оставаться в конце строки.
# Только служебные слова: местоимения и наречия сюда не входят, иначе
# получается мусор вида «она·держит» и «вся·система».
SHORT_WORDS = {
    "в", "во", "к", "ко", "с", "со", "у", "о", "об", "обо", "на", "за", "по",
    "из", "изо", "от", "ото", "до", "для", "при", "над", "под", "подо", "без",
    "безо", "про", "через", "и", "а", "но", "не", "ни", "сквозь",
}

CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def split_code(text: str):
    """Возвращает список (is_code, chunk), чтобы не портить код."""
    parts = []
    pos = 0
    for m in CODE_FENCE.finditer(text):
        if m.start() > pos:
            parts.append((False, text[pos:m.start()]))
        parts.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        parts.append((False, text[pos:]))
    return parts


def fix_quotes(text: str) -> str:
    """Прямые двойные кавычки -> ёлочки, вложенные -> лапки."""
    out = []
    depth = 0
    for ch in text:
        if ch == '"':
            if depth == 0:
                out.append("«")
                depth = 1
            else:
                out.append("»")
                depth = 0
        else:
            out.append(ch)
    text = "".join(out)
    # вложенные: «... "..." ...» уже превращены, обработаем вложенность от руки
    return text


def fix_nested_quotes(text: str) -> str:
    """Если внутри ёлочек оказались ёлочки — заменяет внутренние на лапки."""
    def repl(m):
        inner = m.group(1)
        if "«" in inner or "»" in inner:
            inner = inner.replace("«", "„").replace("»", "“")
        return "«" + inner + "»"

    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"«([^«»]*)«([^«»]*)»([^«»]*)»", repl, text)
    return text


def fix_dashes(text: str) -> str:
    # диапазоны чисел: 10-15 -> 10–15
    text = re.sub(r"(\d)\s*-\s*(\d)", lambda m: m.group(1) + "–" + m.group(2), text)
    # дефис между словами с пробелами -> длинное тире
    text = re.sub(r"(?<=\S)\s+-\s+(?=\S)", " — ", text)
    # двойное тире
    text = text.replace("--", "—")
    # тире в начале строки не должно быть
    text = re.sub(r"^\s*—\s*", "— ", text, flags=re.MULTILINE)
    return text


def fix_spaces(text: str) -> str:
    text = text.replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r" +([,.;:!?…])", r"\1", text)
    text = re.sub(r"\( +", "(", text)
    text = re.sub(r" +\)", ")", text)
    text = re.sub(r"\.\.\.", "…", text)
    text = re.sub(r"[ \u00A0]+$", "", text, flags=re.MULTILINE)
    return text


def add_nbsp(text: str) -> str:
    """Расставляет NBSP: предлоги, числа, единицы."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        # не трогаем заголовки-разделители, таблицы и маркеры описаний кадров
        if stripped.startswith("|") or stripped.startswith("```"):
            lines.append(line)
            continue

        # 1) короткое слово + пробел + слово
        def short_repl(m):
            word, space, nxt = m.group(1), m.group(2), m.group(3)
            if word.lower() in SHORT_WORDS:
                return word + NBSP + nxt
            return m.group(0)

        line = re.sub(
            r"(?<![\w\-])([А-Яа-яЁёA-Za-z]{1,5})([ \u00A0])([А-Яа-яЁёA-Za-z0-9«„])",
            short_repl,
            line,
        )

        # 2) число + существительное / единица
        def num_repl(m):
            return m.group(1) + NBSP + m.group(2)

        line = re.sub(
            r"(\d)\s+([А-Яа-яЁёA-Za-z%])",
            num_repl,
            line,
        )

        # 3) число + знак валюты/процента отдельно
        line = re.sub(r"(\d)\s+(%|₽|\$|€|°|мм|см|м|кг|г|п\.\s?п\.)", lambda m: m.group(1) + NBSP + m.group(2), line)

        # 4) перед длинным тире — NBSP, чтобы тире не начинало строку
        line = re.sub(r"(\S)\s+—", lambda m: m.group(1) + NBSP + "—", line)

        # 5) после тире — обычный пробел (не NBSP)
        line = line.replace(NBSP + "—" + NBSP, NBSP + "— ")

        # 6) инициалы и сокращения
        line = re.sub(r"\bт\.\s?е\.", "т." + NBSP + "е.", line)
        line = re.sub(r"\bт\.\s?д\.", "т." + NBSP + "д.", line)
        line = re.sub(r"\bи\.\s?т\.\s?п\.", "и." + NBSP + "т." + NBSP + "п.", line)

        lines.append(line)
    return "\n".join(lines)


def normalize(text: str) -> str:
    text = fix_quotes(text)
    text = fix_nested_quotes(text)
    text = fix_dashes(text)
    text = fix_spaces(text)
    text = add_nbsp(text)
    return text


def find_hanging(text: str):
    """Ищет строки, оканчивающиеся коротким словом (висячий предлог)."""
    problems = []
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith(("|", "```")):
            continue
        words = re.findall(r"[А-Яа-яЁёA-Za-z]+", line)
        if not words:
            continue
        last = words[-1].lower()
        if last in SHORT_WORDS:
            problems.append((i, last, line.strip()[:70]))
    return problems


def check(text: str):
    errors = []

    for i, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("```"):
            continue
        if '"' in line:
            errors.append((i, "прямая кавычка"))
        if "„" in line and line.count("«") == 0:
            errors.append((i, "лапка вне ёлочек"))
        if re.search(r"\d\s*-\s*\d", line):
            errors.append((i, "дефис в диапазоне, нужен –"))
        if " - " in line:
            errors.append((i, "дефис вместо тире"))
        if "  " in line:
            errors.append((i, "двойной пробел"))
        if line.rstrip().endswith((" —", " –")):
            errors.append((i, "тире в конце строки"))

    for line_no, word, snippet in find_hanging(text):
        errors.append((line_no, f"висячий предлог «{word}»: {snippet}"))

    return errors


def process(path: Path, write: bool, check_only: bool):
    raw = path.read_text(encoding="utf-8")
    chunks = split_code(raw)

    result = []
    for is_code, chunk in chunks:
        result.append(chunk if is_code else normalize(chunk))
    new_text = "".join(result)

    errors_before = check(raw)
    errors_after = check(new_text)

    print(f"Файл: {path}")
    if check_only:
        if errors_before:
            print(f"Найдено замечаний: {len(errors_before)}")
            for line_no, msg in errors_before[:60]:
                print(f"  строка {line_no}: {msg}")
            if len(errors_before) > 60:
                print(f"  … и ещё {len(errors_before) - 60}")
            return 1
        print("Замечаний нет.")
        return 0

    print(f"Замечаний до: {len(errors_before)}")
    print(f"Замечаний после: {len(errors_after)}")
    for line_no, msg in errors_after[:60]:
        print(f"  осталось, строка {line_no}: {msg}")

    if write:
        if new_text != raw:
            path.write_text(new_text, encoding="utf-8")
            print("Файл перезаписан.")
        else:
            print("Изменений нет, файл не тронут.")
    else:
        print("Режим отчёта. Добавьте --write, чтобы переписать файл.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Типографика для кейсов портфолио")
    ap.add_argument("path", help="файл .md или .txt")
    ap.add_argument("--write", action="store_true", help="перезаписать файл")
    ap.add_argument("--check", action="store_true", help="только проверка")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"Файл не найден: {p}")
        return 2

    return process(p, args.write, args.check)


if __name__ == "__main__":
    sys.exit(main())
