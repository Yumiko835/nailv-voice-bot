"""Native AstrBot adapter; requires persona context, with no API spending cap."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import asyncio
import copy
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(project_path(''))
sys.path.insert(0, str(ROOT / 'tools'))
import nailv_text_core as core
from astrbot.core.provider.sources.openai_source import ProviderOpenAIOfficial
from astrbot.core.provider.register import register_provider_adapter

MARKER = 'NAILV_CONTEXT_V1'
CALL_LOCK = asyncio.Lock()


@register_provider_adapter('nailv_openai', '奶绿人设适配的 OpenAI 兼容接口（无调用预算上限）')
class NailvProvider(ProviderOpenAIOfficial):
    async def _query(self, payloads, tools, *, request_max_retries=None, conversation_id=None):
        if payloads.get('model') != core.MODEL:
            raise RuntimeError('聊天模型变更需要重新核对费用配置。')
        if MARKER not in json.dumps(payloads.get('messages', []), ensure_ascii=False):
            raise RuntimeError('奶绿人设适配未加载，本次未发送模型请求。')
        async with CALL_LOCK:
            payloads['max_tokens'] = 1024
            payloads['temperature'] = .85
            # Keep native tool calls; the user explicitly removed the API cap.
            result = await super()._query(payloads, tools, request_max_retries=1, conversation_id=conversation_id)
            return result

    async def text_chat_stream(self, **kwargs):
        raise RuntimeError('当前奶绿适配采用完整回复，保留隐藏情绪字段解析。')
        yield  # preserve the async-generator interface
