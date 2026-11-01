from .schemas import Answer
from .tools import ToolRunner


def validate_answer(answer: Answer, runner: ToolRunner) -> list[str]:
    errors = []
    if answer.status == "answered" and not answer.citations:
        errors.append("answered 必须提供支持结论的原文引用")
    if answer.status == "clarification_required":
        if answer.clarification_reason is None:
            errors.append("clarification_required 必须指定 clarification_reason：conflict 或 missing_context")
        elif answer.clarification_reason == "conflict":
            anchors = {(citation.doc_id, citation.chunk_id) for citation in answer.citations}
            if len(anchors) < 2:
                errors.append("conflict 必须提供至少两个不同原文片段的引用，分别支持存在冲突的规定")
    elif answer.clarification_reason is not None:
        errors.append("只有 clarification_required 可以设置 clarification_reason，其他状态必须为 null")
    if answer.status in {"answered", "clarification_required", "insufficient_evidence"} and not runner.successful_searches:
        errors.append("必须先成功检索才能回答、澄清或判定资料不足；工具失败不等于资料缺失")
    if answer.status == "tool_error" and not runner.errors:
        errors.append("没有工具错误，不能返回 tool_error")
    if answer.status != "answered" and (not answer.gaps or any(not gap.strip() for gap in answer.gaps)):
        errors.append("未完成明确回答时须说明资料缺口、澄清问题或失败原因")
    for citation in answer.citations:
        source = runner.read_evidence.get(citation.chunk_id)
        if not source or source[0] != citation.doc_id:
            errors.append(f"引用 {citation.doc_id}/{citation.chunk_id} 未在本轮读取")
        elif citation.quote not in source[1]:
            errors.append(f"引用 {citation.chunk_id} 必须逐字来自原文")
    return errors

