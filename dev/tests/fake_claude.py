"""ตัวปลอมของ claude CLI ใช้ทดสอบตัวเชื่อม claude_code โดยไม่ต้องล็อกอิน

เลียนแบบรูปแบบ JSON ที่ claude -p --output-format json ตอบจริง
ตั้งค่า FAKE_CLAUDE_MODE=error เพื่อจำลองกรณีไม่ได้ล็อกอิน
"""
import json
import os
import sys


def main() -> int:
    args = sys.argv[1:]
    prompt = args[-1] if args else ""
    model = args[args.index("--model") + 1] if "--model" in args else "?"
    system = args[args.index("--system-prompt") + 1] if "--system-prompt" in args else ""

    if os.environ.get("FAKE_CLAUDE_MODE") == "error":
        payload = {"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}
        sys.stdout.write(json.dumps(payload))
        return 1

    body = prompt.split("<<<", 1)[-1].rsplit(">>>", 1)[0].strip()
    if "Client's message" in prompt:
        text = f"[ไทย/{model}] {body}"
    else:
        text = f"[EN/{model}] {body}"
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": text,
        "duration_ms": 12,
        "total_cost_usd": 0,
        "system_prompt_len": len(system),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
