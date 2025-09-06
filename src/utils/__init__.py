import json
import re


def format_result(input_str):
    formatted_json = input_str
    json_match = re.search(r'\{.*\}', input_str, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)

        # 使用json.loads()解析字符串为Python字典
        data = json.loads(json_str)

        # 格式化为标准JSON字符串（带缩进和确保中文正确显示）
        formatted_json = json.dumps(data, ensure_ascii=False, indent=2)

    else:
        print("未找到有效的JSON内容")
    return formatted_json

def rm_think(input_str):
    cleaned_str = re.sub(r'^<think>.*?</think>\s*', '', input_str,
                         flags=re.DOTALL)

    # 确保字符串以有效的JSON开头
    if not cleaned_str.strip().startswith('['):
        # 如果处理后仍然不以[开头，尝试找到第一个[
        start_idx = cleaned_str.find('[')
        if start_idx != -1:
            cleaned_str = cleaned_str[start_idx:]

    # 解析为Python对象以确保有效性
    data = json.loads(cleaned_str)

    # 格式化为标准JSON字符串（带缩进和中文支持）
    formatted_json = json.dumps(data, ensure_ascii=False, indent=2)

    return formatted_json


def rm_only_think(input_str):
    cleaned_str = re.sub(r'^<think>.*?</think>\s*', '', input_str,
                         flags=re.DOTALL)

    # 解析为Python对象以确保有效性
    try:
        data = json.loads(cleaned_str)
        formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return cleaned_str
    return formatted_json


def save_to_file(path, result):
    with open(f'{path}/result.txt', 'w') as f:
        f.write(result)

