import re

import mistune

_md_to_html = mistune.create_markdown(
    plugins=["strikethrough"],
    escape=False,
)


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
            # Telegram: markdown → HTML
            converted = _md_to_html(description).strip()
        else:
            # VK / MAX: markdown → plain text
            converted = _md_to_plain(description)
        parts.append(converted)
    if tags_line:
        parts.append(tags_line)

    return "\n\n".join(parts)
