"""
AI Agent — OpenAI Function Calling 主循环
"""
import json
import os
from typing import List, Dict, Generator, Optional
from utils.tools import TOOL_SCHEMAS, execute_tool


SYSTEM_PROMPT = """你是一个专业的财务分析 AI Agent,能够通过调用工具获取上市公司财务数据并进行分析。

# 你的能力
- 通过 6 个工具获取数据并执行各种财务分析
- 用清晰、专业、易懂的中文回复用户(除非用户明显在用英文交流)
- 在分析中给出洞察,而不是只罗列数字

# 工作原则
1. **理解意图优先**:用户提到一家公司时,先 fetch_company 确认它存在,再决定后续动作
2. **按需调用工具**:不要一次调一堆工具,根据用户实际问题调相应工具
3. **复用已知信息**:同一对话中已经获取过的数据要复用,不要重复调用
4. **数据先行,解读跟上**:展示关键数字后,要给出**有洞察**的解读(为什么这个数字重要、好/坏在哪、对比基准)
5. **承认不确定性**:数据缺失或异常时,要明说并解释可能原因(yfinance 限制、公司特殊情况等)

# 回复风格
- 简洁专业,避免空话套话
- 多用 **加粗** 突出关键数据
- 比率类指标用百分比展示(如 ROE 25.30%),周转率用倍数(如 1.05 次)
- 大数额用 B(十亿)/T(万亿)表示
- 关键发现用 ✅ ⚠️ 等符号点出

# 何时调用 generate_full_report
- 用户明确说"完整报告"、"全面分析"、"下载报告"、"给我详细的"时
- 不要在用户只问简单问题时擅自生成完整报告

# 注意
- 你看到的工具返回值是结构化 JSON,**不要**把原始 JSON 复制给用户,要消化后用自然语言表达
- yfinance 通常只有 4 年年报,不是 bug
- 用户是中国大陆用户的可能性较高,但会有海外用户,适应他们的偏好"""


def get_openai_client(api_key: Optional[str] = None):
    """获取 OpenAI 客户端;延迟导入避免启动开销"""
    from openai import OpenAI
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("缺少 OpenAI API Key")
    return OpenAI(api_key=key)


def chat_with_tools(messages: List[Dict], api_key: Optional[str] = None,
                     model: str = "gpt-4o-mini",
                     max_iterations: int = 6) -> Generator[Dict, None, None]:
    """
    多轮工具调用循环,流式 yield 事件
    yield 的 event 字典格式:
      {"type": "tool_call",   "tool": "...", "args": {...}}
      {"type": "tool_result", "tool": "...", "result": {...}}
      {"type": "assistant",   "content": "..."}                  # 最终 AI 文本
      {"type": "report",      "filename": "...", "markdown": "..."}  # 报告产物
      {"type": "error",       "message": "..."}
    """
    client = get_openai_client(api_key)

    # 拼上 system prompt
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.3,
            )
        except Exception as e:
            yield {"type": "error", "message": f"OpenAI API 调用失败: {type(e).__name__}: {str(e)[:200]}"}
            return

        msg = resp.choices[0].message

        # 把 assistant 消息加入历史
        assistant_entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        full_messages.append(assistant_entry)

        # 没有工具调用 → 这是最终回答
        if not msg.tool_calls:
            yield {"type": "assistant", "content": msg.content or ""}
            return

        # 有工具调用 → 逐个执行
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            yield {"type": "tool_call", "tool": tool_name, "args": args}

            result = execute_tool(tool_name, args)
            yield {"type": "tool_result", "tool": tool_name, "result": result}

            # 如果是生成报告,额外发一个事件让 UI 渲染下载按钮
            if tool_name == "generate_full_report" and "report_markdown" in result:
                yield {
                    "type": "report",
                    "filename": result.get("filename", "report.md"),
                    "markdown": result["report_markdown"],
                    "ticker": result.get("ticker"),
                    "year": result.get("year"),
                }
                # 给 LLM 看的 result 不要包含完整 markdown(太大),只放摘要
                result_for_llm = {
                    "ticker": result.get("ticker"),
                    "year": result.get("year"),
                    "status": "报告已生成并展示给用户(包含下载按钮)",
                    "report_length_chars": len(result["report_markdown"]),
                }
            else:
                result_for_llm = result

            # 把工具结果加入历史
            full_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result_for_llm, ensure_ascii=False),
            })

    # 超过最大迭代
    yield {"type": "error", "message": f"工具调用迭代超过 {max_iterations} 次,可能陷入循环"}


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数,1 token ≈ 0.75 个英文单词 ≈ 1.5 个中文字"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
