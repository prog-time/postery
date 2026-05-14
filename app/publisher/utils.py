import re

import mistune

_md_to_html = mistune.create_markdown(
    plugins=["strikethrough"],
    escape=False,
)

# Теги, которые Telegram поддерживает в parse_mode=HTML
_TG_ALLOWED = re.compile(
    r"</?(?!(?:b|strong|i|em|u|ins|s|strike|del|code|pre|a|blockquote|tg-spoiler)(?=[\s>/]))(?:[a-z][a-z0-9]*)(?:\s[^>]*)?>",
    re.IGNORECASE,
)


def _html_to_tg(html: str) -> str:
    """Конвертирует стандартный HTML (от mistune) в Telegram-совместимый."""
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"<b>\1</b>\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<li[^>]*>(.*?)</li>", r"• \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"</?(?:ul|ol)[^>]*>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<strong>", "<b>", html, flags=re.IGNORECASE)
    html = re.sub(r"</strong>", "</b>", html, flags=re.IGNORECASE)
    html = re.sub(r"<em>", "<i>", html, flags=re.IGNORECASE)
    html = re.sub(r"</em>", "</i>", html, flags=re.IGNORECASE)
    html = _TG_ALLOWED.sub("", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def _md_to_vk_text(md: str) -> str:
    """Конвертирует markdown → VK/MAX-совместимый plain text.

    Правила:
    - <h1..6>текст</h1> → пустая строка + текст + пустая строка
    - <li>текст</li>    → • текст\\n
    - <a href="URL">текст</a> → «текст — URL» (если текст == URL — только URL,
      без дублирования)
    - <strong>/<b>/<em>/<i> → текст без маркеров
    - <p>текст</p>      → текст\\n\\n
    - code-блоки (<pre><code>…</code></pre>) → текст без тегов (без отступов, для VK ок)
    - остальные теги    → strip
    - нормализация: три и более \\n → \\n\\n; strip на выходе
    """
    html = _md_to_html(md)

    # Заголовки: выделить пустой строкой сверху и снизу
    html = re.sub(
        r"<h[1-6][^>]*>(.*?)</h[1-6]>",
        r"\n\n\1\n\n",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Пункты списка: • текст\n
    html = re.sub(
        r"<li[^>]*>(.*?)</li>",
        lambda m: "• " + m.group(1).strip() + "\n",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Убрать <ul>/<ol>
    html = re.sub(r"</?(?:ul|ol)[^>]*>", "", html, flags=re.IGNORECASE)

    # Ссылки: <a href="URL">текст</a> → текст — URL (если текст == URL → только URL)
    def _expand_link(m: re.Match) -> str:
        href = m.group(1).strip()
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if text == href or not text:
            return href
        return f"{text} — {href}"

    html = re.sub(
        r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        _expand_link,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # <strong>/<b>/<em>/<i> → текст без маркеров
    html = re.sub(r"</?(?:strong|b|em|i)[^>]*>", "", html, flags=re.IGNORECASE)

    # <p>текст</p> → текст\n\n
    html = re.sub(
        r"<p[^>]*>(.*?)</p>",
        r"\1\n\n",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Убрать все оставшиеся теги (включая <pre>, <code>, <br> и т.п.)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)

    # Нормализация пробелов
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def format_tags(tags_str: str | None) -> str | None:
    """'тег один, тег два' → '#тег_один #тег_два'"""
    if not tags_str:
        return None
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not tags:
        return None
    return " ".join("#" + t.replace(" ", "_") for t in tags)


def build_text(channel, post, bold_title: bool = True) -> str:
    """Собирает итоговый текст: заголовок + описание (из markdown) + теги.

    bold_title=True  → Telegram: description конвертируется markdown→HTML,
                        заголовок обёртывается в <b>…</b>.
    bold_title=False → VK / MAX: description конвертируется через
                        _md_to_vk_text() — plain text с развёрнутыми ссылками
                        (text — URL), маркерами списков (•) и выделенными
                        заголовками (пустые строки). HTML-тегов нет.
    """
    title = channel.effective_title
    description = channel.effective_description
    tags_line = format_tags(post.tags)

    parts = []
    if title:
        parts.append(f"<b>{title}</b>" if bold_title else title)
    if description:
        if bold_title:
            # Telegram: markdown → Telegram-совместимый HTML
            converted = _html_to_tg(_md_to_html(description))
        else:
            # VK / MAX: markdown → читаемый plain text
            converted = _md_to_vk_text(description)
        parts.append(converted)
    if tags_line:
        parts.append(tags_line)

    return "\n\n".join(parts)
