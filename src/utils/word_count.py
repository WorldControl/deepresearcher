import re


def count_chinese_characters(text: str) -> int:
    """
    统计中文字符数量
    """
    # 匹配中文字符（包括汉字）
    chinese_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf]'
    chinese_chars = re.findall(chinese_pattern, text)
    return len(chinese_chars)


def count_words(text: str) -> int:
    """
    统计总字数（中英文混合）
    """
    # 统计中文字符
    chinese_count = count_chinese_characters(text)

    # 统计英文单词（以空格分隔的连续字母数字）
    english_words = re.findall(r'[a-zA-Z0-9]+', text)

    return chinese_count + len(english_words)