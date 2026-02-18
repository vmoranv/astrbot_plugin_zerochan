"""
AstrBot Zerochan 图片搜索插件
基于 Zerochan API 搜索并获取动漫图片
"""

import aiohttp
import json
import re
from typing import Optional, List, Dict, Any
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


ZEROCHAN_API_BASE = "https://www.zerochan.net"
USER_AGENT = "AstrBot-Zerochan-Plugin"


class ZerochanAPI:
    """Zerochan API 客户端"""

    def __init__(self, username: str = "AstrBotUser"):
        self.base_url = ZEROCHAN_API_BASE
        self.user_agent = f"{USER_AGENT} - {username}"
        self.headers = {"User-Agent": self.user_agent}
        self.cookies = {"z_lang": "en"}

    async def _request(self, url: str, params: dict = None) -> Optional[Dict[str, Any]]:
        """发送 API 请求"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=self.headers, cookies=self.cookies,
                    timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        # 尝试解析 JSON
                        try:
                            data = json.loads(text)
                            return {"data": data, "final_url": str(response.url)}
                        except json.JSONDecodeError:
                            # 不是 JSON，可能是重定向到了正确的标签页
                            # 尝试从 HTML 中提取正确的标签名
                            correct_tag = self._extract_tag_from_html(text)
                            if correct_tag:
                                logger.info(f"Zerochan API: 检测到重定向，正确标签为 '{correct_tag}'")
                                return {"redirect_tag": correct_tag}
                            logger.warning("Zerochan API: 响应不是 JSON 格式")
                            return None
                    elif response.status == 404:
                        logger.warning(f"Zerochan API: 资源未找到 - {url}")
                        return None
                    else:
                        logger.warning(f"Zerochan API: 请求失败 - 状态码 {response.status}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"Zerochan API 请求错误: {e}")
            return None
        except Exception as e:
            logger.error(f"Zerochan API 未知错误: {e}")
            return None

    def _extract_tag_from_html(self, html: str) -> Optional[str]:
        """从 HTML 页面中提取正确的标签名"""
        # 尝试从 title 中提取
        # 例如: <title>Furina de Fontaine - Zerochan</title>
        title_match = re.search(r'<title>([^-]+)\s*-\s*Zerochan', html)
        if title_match:
            return title_match.group(1).strip()

        # 尝试从 canonical 链接中提取
        canonical_match = re.search(r'<link[^>]*rel="canonical"[^>]*href="[^"]*/([^"/]+)"', html)
        if canonical_match:
            return canonical_match.group(1).replace("+", " ")

        return None

    def _generate_tag_variants(self, tag: str) -> List[str]:
        """生成标签变体列表"""
        variants = [tag]

        # 常见角色名变体
        common_variants = {
            "furina": ["Furina", "Furina de Fontaine", "Focalors"],
            "lumine": ["Lumine", "Traveler (Female)", "Female Traveler"],
            "aether": ["Aether", "Traveler (Male)", "Male Traveler"],
            "nahida": ["Nahida", "Lesser Lord Kusanali"],
            "raiden shogun": ["Raiden Shogun", "Raiden Ei", "Ei", "Baal"],
            "hu tao": ["Hu Tao", "Hutao"],
            "ganyu": ["Ganyu"],
            "keqing": ["Keqing"],
            "mona": ["Mona", "Mona Megistus"],
            "venti": ["Venti", "Barbatos"],
            "zhongli": ["Zhongli", "Rex Lapis"],
            "xiao": ["Xiao", "Alatus"],
            "kazuha": ["Kazuha", "Kaedehara Kazuha"],
            "scaramouche": ["Scaramouche", "Wanderer", "Kunikuzushi"],
            "yae miko": ["Yae Miko", "Guuji Yae"],
            "yoimiya": ["Yoimiya"],
            "ayaka": ["Ayaka", "Kamisato Ayaka"],
            "ayato": ["Ayato", "Kamisato Ayato"],
            "itto": ["Itto", "Arataki Itto"],
            "gorou": ["Gorou"],
            "kokomi": ["Kokomi", "Sangonomiya Kokomi"],
            "arlecchino": ["Arlecchino", "The Knave"],
            "clorinde": ["Clorinde"],
            "navia": ["Navia"],
            "furina": ["Furina", "Furina de Fontaine"],
            "neuvillette": ["Neuvillette"],
            "wriothesley": ["Wriothesley"],
            "lyney": ["Lyney"],
            "lynette": ["Lynette"],
            "freminet": ["Freminet"],
            "nilou": ["Nilou"],
            "cyno": ["Cyno"],
            "tighnari": ["Tighnari"],
            "dehya": ["Dehya"],
            "alhaitham": ["Alhaitham"],
            "kaveh": ["Kaveh"],
            "baizhu": ["Baizhu"],
            "yaoyao": ["Yaoyao"],
        }

        tag_lower = tag.lower()
        if tag_lower in common_variants:
            for variant in common_variants[tag_lower]:
                if variant not in variants:
                    variants.append(variant)

        # 首字母大写
        capitalized = tag.title()
        if capitalized not in variants:
            variants.append(capitalized)

        return variants

    async def search(
        self,
        tags: str = None,
        page: int = 1,
        limit: int = 10,
        sort: str = None,
        strict: bool = False,
        dimensions: str = None,
        color: str = None,
        time_sort: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        搜索图片

        Args:
            tags: 标签，多个标签用逗号分隔
            page: 页码
            limit: 每页数量 (1-250)
            sort: 排序方式 (id|fav)
            strict: 是否严格模式
            dimensions: 尺寸过滤 (large|huge|landscape|portrait|square)
            color: 颜色过滤
            time_sort: 时间范围 (0|1|2)
        """
        # 生成标签变体
        tag_variants = self._generate_tag_variants(tags)
        tried_tags = []

        for tag in tag_variants:
            tried_tags.append(tag)

            # 构建URL
            tag_path = tag.replace(" ", "+")
            url = f"{self.base_url}/{tag_path}"

            # 构建参数
            params = {"json": ""}

            if page:
                params["p"] = page
            if limit and 1 <= limit <= 250:
                params["l"] = limit
            if sort and sort in ("id", "fav"):
                params["s"] = sort
            if strict:
                params["strict"] = ""
            if dimensions and dimensions in ("large", "huge", "landscape", "portrait", "square"):
                params["d"] = dimensions
            if color:
                params["c"] = color
            if time_sort is not None and time_sort in (0, 1, 2):
                params["t"] = time_sort

            result = await self._request(url, params)

            if result is None:
                continue

            # 如果检测到重定向，尝试使用正确的标签
            if "redirect_tag" in result:
                correct_tag = result["redirect_tag"]
                if correct_tag and correct_tag not in tried_tags:
                    logger.info(f"Zerochan API: 尝试使用重定向标签 '{correct_tag}'")
                    correct_tag_path = correct_tag.replace(" ", "+")
                    correct_url = f"{self.base_url}/{correct_tag_path}"
                    result = await self._request(correct_url, params)
                    if result and "data" in result:
                        result["used_tag"] = correct_tag
                        return result
                continue

            if "data" in result:
                result["used_tag"] = tag
                return result

        return None

    async def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """获取单个条目详情"""
        url = f"{self.base_url}/{entry_id}"
        result = await self._request(url, {"json": ""})
        if result and "data" in result:
            return result["data"]
        return None


@register("astrbot_plugin_zerochan", "vmoranv", "Zerochan 图片搜索插件", "1.0.0")
class ZerochanPlugin(Star):
    """Zerochan 图片搜索插件"""

    def __init__(self, context: Context):
        super().__init__(context)
        self.api = ZerochanAPI()

    async def initialize(self):
        """插件初始化"""
        logger.info("Zerochan 插件初始化完成")

    @filter.command("zc")
    async def search_zerochan(self, event: AstrMessageEvent):
        """
        搜索 Zerochan 图片
        用法: /zc <标签> [页码] [数量]
        示例: /zc Genshin Impact
        """
        message_str = event.message_str.strip()

        # 解析参数
        parts = message_str.split(maxsplit=3)
        if len(parts) < 2:
            yield event.plain_result(
                "Zerochan 图片搜索\n"
                "用法: /zc <标签> [页码] [数量]\n"
                "示例:\n"
                "  /zc Genshin Impact - 搜索原神相关图片\n"
                "  /zc Lumine 1 5 - 搜索荧，第1页，5张图\n"
                "  /zc furina - 自动匹配正确标签名"
            )
            return

        # 解析标签和可选参数
        tags = parts[1]
        page = 1
        limit = 3

        if len(parts) >= 3:
            try:
                page = int(parts[2])
            except ValueError:
                tags = f"{parts[1]} {parts[2]}"

        if len(parts) >= 4:
            try:
                limit = int(parts[3])
                limit = min(limit, 10)
            except ValueError:
                pass

        logger.info(f"搜索 Zerochan: 标签={tags}, 页码={page}, 数量={limit}")

        # 调用 API
        result = await self.api.search(tags=tags, page=page, limit=limit, sort="fav")

        if not result:
            yield event.plain_result(f"搜索 '{tags}' 失败，请检查标签名或稍后重试。")
            return

        # 解析结果
        data = result.get("data", {})
        used_tag = result.get("used_tag", tags)
        items = data.get("items", [])

        if not items:
            yield event.plain_result(f"未找到与 '{tags}' 相关的图片。")
            return

        # 构建回复消息
        total = data.get("total", 0)
        reply = f"搜索 '{used_tag}' 找到 {total} 张图片，显示第 {page} 页:\n"

        # 发送图片
        image_urls = []
        for item in items[:limit]:
            thumbnail = item.get("thumbnail", "")
            image_url = item.get("image", thumbnail)
            if image_url:
                image_urls.append(image_url)

        if image_urls:
            yield event.plain_result(reply.rstrip())
            yield event.image_result(image_urls[0])
        else:
            yield event.plain_result(reply + "无法获取图片链接")

    @filter.command("zcid")
    async def get_by_id(self, event: AstrMessageEvent):
        """
        根据 ID 获取 Zerochan 图片详情
        用法: /zcid <图片ID>
        示例: /zcid 3793685
        """
        message_str = event.message_str.strip()
        parts = message_str.split()

        if len(parts) < 2:
            yield event.plain_result(
                "根据ID获取Zerochan图片\n"
                "用法: /zcid <图片ID>\n"
                "示例: /zcid 3793685"
            )
            return

        try:
            entry_id = int(parts[1])
        except ValueError:
            yield event.plain_result("请输入有效的数字ID。")
            return

        logger.info(f"获取 Zerochan 图片详情: ID={entry_id}")

        result = await self.api.get_entry(entry_id)

        if not result:
            yield event.plain_result(f"未找到ID为 {entry_id} 的图片。")
            return

        # 解析详情
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        image_url = result.get("image", "")
        width = result.get("width", "未知")
        height = result.get("height", "未知")
        size = result.get("size", "未知")
        author = result.get("author", "未知")
        tags_list = result.get("tags", [])

        # 构建回复
        reply = (
            f"Zerochan 图片详情\n"
            f"ID: {entry_id}\n"
            f"尺寸: {width}x{height}\n"
            f"大小: {size}\n"
            f"作者: {author}\n"
        )

        if tags_list:
            tags_str = ", ".join(tags_list[:10])
            if len(tags_list) > 10:
                tags_str += f" ...共{len(tags_list)}个标签"
            reply += f"标签: {tags_str}\n"

        if image_url:
            yield event.plain_result(reply)
            yield event.image_result(image_url)
        else:
            yield event.plain_result(reply)

    @filter.command("zchelp")
    async def show_help(self, event: AstrMessageEvent):
        """显示 Zerochan 插件帮助"""
        help_text = (
            "Zerochan 图片搜索插件\n"
            "====================\n"
            "命令:\n"
            "  /zc <标签> [页码] [数量] - 搜索图片\n"
            "  /zcid <ID> - 根据ID获取详情\n"
            "  /zchelp - 显示此帮助\n"
            "\n"
            "示例:\n"
            "  /zc Genshin Impact - 搜索原神\n"
            "  /zc furina - 自动匹配正确标签\n"
            "  /zcid 3793685 - 获取指定图片\n"
            "\n"
            "特性:\n"
            "  - 自动匹配标签变体\n"
            "  - 支持角色别名\n"
            "  - API限制60次/分钟"
        )
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁"""
        logger.info("Zerochan 插件已卸载")
