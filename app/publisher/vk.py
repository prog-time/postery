"""Публикация PostChannel в ВКонтакте через VK API."""
import logging
import httpx

log = logging.getLogger("publisher.vk")

VK_API = "https://api.vk.com/method/{method}"
VK_VERSION = "5.199"


async def publish(text: str, source, image_paths: list[str]) -> tuple[bool, str | None]:
    """
    text        — готовый plain-текст поста.
    source      — ORM VKSource (только простые атрибуты).
    image_paths — абсолютные пути к файлам.
    """
    token = source.access_token
    owner_id = -abs(source.group_id)
    message = text

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            attachment = None
            if image_paths:
                try:
                    attachment = await _upload_photos(client, token, owner_id, image_paths)
                    log.info("VK attachments ready: %s", attachment)
                except RuntimeError as e:
                    if "error 27" in str(e):
                        log.warning(
                            "Group token cannot upload photos (error 27). "
                            "Use a user access token. Publishing text only."
                        )
                    else:
                        raise

            params = {
                "access_token": token,
                "owner_id": owner_id,
                "from_group": 1,
                "message": message or "—",
                "v": VK_VERSION,
            }
            if attachment:
                params["attachments"] = attachment

            log.info("VK wall.post params (no token): owner_id=%s attachments=%s",
                     owner_id, attachment)

            r = await client.post(VK_API.format(method="wall.post"), data=params)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                return False, f"VK error {data['error']['error_code']}: {data['error']['error_msg']}"

            log.info("VK wall.post response: %s", data)
        return True, None

    except httpx.HTTPStatusError as e:
        return False, f"HTTP {e.response.status_code}: {e.response.text[:500]}"
    except Exception as e:
        log.exception("VK publish failed")
        return False, str(e)[:500]


def _vk_check(data: dict, method: str):
    if "error" in data:
        err = data["error"]
        raise RuntimeError(
            f"VK {method} error {err.get('error_code')}: {err.get('error_msg')}"
        )
    if "response" not in data:
        raise RuntimeError(f"VK {method} unexpected response: {data}")
    return data["response"]


async def _upload_one_photo(client, token, group_id: int, img_path: str) -> str:
    r = await client.post(VK_API.format(method="photos.getWallUploadServer"), data={
        "access_token": token,
        "group_id": group_id,
        "v": VK_VERSION,
    })
    r.raise_for_status()
    upload_url = _vk_check(r.json(), "photos.getWallUploadServer")["upload_url"]
    log.info("VK upload URL obtained for group %d", group_id)

    with open(img_path, "rb") as f:
        up = await client.post(upload_url, files={"photo": f})
    up.raise_for_status()
    up_data = up.json()
    log.info("VK upload response: %s", up_data)

    save_r = await client.post(VK_API.format(method="photos.saveWallPhoto"), data={
        "access_token": token,
        "group_id": group_id,
        "photo": up_data["photo"],
        "server": up_data["server"],
        "hash": up_data["hash"],
        "v": VK_VERSION,
    })
    save_r.raise_for_status()
    saved = _vk_check(save_r.json(), "photos.saveWallPhoto")[0]
    result = f"photo{saved['owner_id']}_{saved['id']}"
    log.info("VK photo saved: %s", result)
    return result


async def _upload_photos(client, token, owner_id: int, image_paths: list[str]) -> str:
    group_id = abs(owner_id)
    attachments = []
    for path in image_paths[:10]:
        att = await _upload_one_photo(client, token, group_id, path)
        attachments.append(att)
    return ",".join(attachments)
