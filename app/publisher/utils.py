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


def _md_to_plain(md: str) -> str:
    """Конвертирует markdown в plain text (strip всех HTML-тегов)."""
    html = _md_to_html(md)
    return re.sub(r"<[^>]+>", "", html).strip()


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
    bold_title=False → VK / MAX: description конвертируется markdown→plain text,
                        HTML-теги в результате отсутствуют.
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
            # VK / MAX: markdown → plain text
            converted = _md_to_plain(description)
        parts.append(converted)
    if tags_line:
        parts.append(tags_line)

    return "\n\n".join(parts)
