def format_tags(tags_str: str | None) -> str | None:
    """'тег один, тег два' → '#тег_один #тег_два'"""
    if not tags_str:
        return None
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not tags:
        return None
    return " ".join("#" + t.replace(" ", "_") for t in tags)


def build_text(channel, post, bold_title: bool = True) -> str:
    """Собирает итоговый текст: заголовок + описание + теги."""
    title = channel.effective_title
    description = channel.effective_description
    tags_line = format_tags(post.tags)

    parts = []
    if title:
        parts.append(f"<b>{title}</b>" if bold_title else title)
    if description:
        parts.append(description)
    if tags_line:
        parts.append(tags_line)

    return "\n\n".join(parts)
