"""
AstrBot Zerochan 图片搜索插件
基于 Zerochan API 搜索并获取动漫图片
"""

import aiohttp
from typing import Optional, List, Dict, Any, AsyncGenerator
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image


ZEROCHAN_API_BASE = "https://www.zerochan.net"
USER_AGENT = "AstrBot-Zerochan-Plugin"


class ZerochanAPI:
    """Zerochan API 客户端"""

    def __init__(self, username: str = "AstrBotUser"):
        self.base_url = ZEROCHAN_API_BASE
        self.user_agent = f"{USER_AGENT} - {username}"
        self.headers = {"User-Agent": self.user_agent}

    async def _request(self, url: str, params: dict = None) -> Optional[Dict[str, Any]]:
        """发送 API 请求"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=self.headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            data = await response.json()
                            return data
                        else:
                            # 尝试解析 JSON，即使 Content-Type 不是 JSON
                            try:
                                text = await response.text()
                                import json
                                data = json.loads(text)
                                return data
                            except:
                                logger.warning(f"Zerochan API: 响应不是 JSON 格式 - {content_type}")
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
            tags: 标���，多个标签用逗号分隔
            page: 页码
            limit: 每页数量 (1-250)
            sort: 排序方式 (id|fav)
            strict: 是否严格模式
            dimensions: 尺寸过滤 (large|huge|landscape|portrait|square)
            color: 颜色过滤
            time_sort: 时间范围 (0|1|2)
        """
        # 构建URL
        if tags:
            # 处理标签中的空格，转换为 +
            tag_path = tags.replace(" ", "+").replace(",", ",")
            url = f"{self.base_url}/{tag_path}"
        else:
            url = f"{self.base_url}"

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

        return await self._request(url, params)

    async def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """获取单个条目详情"""
        url = f"{self.base_url}/{entry_id}"
        return await self._request(url, {"json": ""})


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
                "  /zc Lumine 1 5 - 搜索荧，第1页，5张图"
            )
            return

        # 解析标签和可选参数
        tags = parts[1]
        page = 1
        limit = 3  # 默认显示3张

        if len(parts) >= 3:
            try:
                page = int(parts[2])
            except ValueError:
                # 可能是标签的一部分
                tags = f"{parts[1]} {parts[2]}"

        if len(parts) >= 4:
            try:
                limit = int(parts[3])
                limit = min(limit, 10)  # 最多显示10张
            except ValueError:
                pass

        # 发送搜索中提示
        logger.info(f"搜索 Zerochan: 标签={tags}, 页码={page}, 数量={limit}")

        # 调用 API
        result = await self.api.search(tags=tags, page=page, limit=limit, sort="fav")

        if not result:
            yield event.plain_result("搜索失败，请稍后重试或检查网络连接。")
            return

        # 解析结果
        items = result.get("items", [])
        if not items:
            yield event.plain_result(f"未找到与 '{tags}' 相关的图片。")
            return

        # 构建回复消息
        total = result.get("total", 0)
        reply = f"搜索 '{tags}' 找到 {total} 张图片，显示第 {page} 页:\n"

        # 发送图片
        image_urls = []
        for item in items[:limit]:
            # 优先获取中等尺寸图片
            thumbnail = item.get("thumbnail", "")
            image_url = item.get("image", thumbnail)

            if image_url:
                image_urls.append(image_url)

        if image_urls:
            # 创建消息链，包含文本和图片
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
        thumbnail = result.get("thumbnail", image_url)
        width = result.get("width", "未知")
        height = result.get("height", "未知")
        size = result.get("size", "未知")
        source = result.get("source", "未知")
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
            "  /zc Lumine 1 5 - 搜索荧，第1页，5张\n"
            "  /zcid 3793685 - 获取指定图片\n"
            "\n"
            "提示:\n"
            "  - 标签支持空格和���号分隔\n"
            "  - 每次最多显示10张图片\n"
            "  - API限制60次/分钟"
        )
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁"""
        logger.info("Zerochan 插件已卸载")
