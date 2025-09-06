import yaml
from typing import Dict, List

from src.core.state import ReportSection, AnalysisIntent


class TemplateManager:
    """
    报告模板管理器
    """
    def __init__(self, config_path: str = "configs/templates.yml"):
        self.config_path = config_path
        self.templates = self.load_templates()

    def create_report_structure(self, intent: str, domain: str) -> List[ReportSection]:
        template = self.templates["templates"].get(intent)
        if not template:
            template = self.templates['templates'][AnalysisIntent.OVERVIEW]

        sections_data = template['sections']
        sections_data = self.apply_domain_adjustments(sections_data, domain)

        sections = []
        for section_data in sections_data:
            section = ReportSection(
                title=section_data['title'],
                key_questions=section_data['key_questions'],
                content="",
                status="outlined"
            )
            sections.append(section)

        return sections

    def load_templates(self) -> Dict:
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return self.get_default_tempaltes()

    def get_default_tempaltes(self):
        """
        获取默认模板
        """
        return {
            "templates": {
                "overview": {
                    "title": "概述报告",
                    "sections": [
                        {"title": "执行摘要",
                         "key_questions": ["核心结论是什么？"]},
                        {"title": "引言",
                         "key_questions": ["背景和目的是什么？"]},
                        {"title": "现状分析",
                         "key_questions": ["当前状况如何？"]},
                        {"title": "发展趋势",
                         "key_questions": ["未来方向是什么？"]},
                        {"title": "结论", "key_questions": ["主要结论是什么？"]}
        ]
        }
        },
        "domain_adjustments": {}
        }

    def apply_domain_adjustments(self, sections_data, domain):
        if 'domain_adjustments' not in self.templates:
            return sections_data

        domain_adjustments = self.templates['domain_adjustments'].get(domain, {})

        adjusted_sections = []
        for section in sections_data:
            adjusted_section = section.copy()
            if 'key_questions' in domain_adjustments:
                adjusted_section['key_questions'].extend(
                    domain_adjustments['key_questions'])

            adjusted_sections.append(adjusted_section)
        return adjusted_sections


