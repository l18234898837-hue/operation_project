from __future__ import annotations

# Hard-rule routing vocabulary. Keep these terms here so routing coverage can be
# adjusted without touching the query understanding flow.

DOMAIN_TERMS = (
    "逆变器",
    "组件",
    "组串",
    "SVG",
    "无功",
    "箱变",
    "变压器",
    "电缆",
    "线缆",
    "接头",
    "绝缘",
    "漏电流",
    "发电量",
    "巡检",
    "热斑",
    "PID",
    "MPPT",
    "并网",
    "过压",
    "欠压",
)

FAULT_ACTION_TERMS = (
    "故障",
    "报警",
    "异常",
    "排查",
    "处理",
    "维修",
    "维护",
    "巡检",
    "跳闸",
    "停机",
    "不发电",
    "发电少",
    "效率低",
    "过温",
    "怎么",
    "如何",
    "该怎么",
)

REALTIME_TERMS = (
    "今天",
    "现在",
    "实时",
    "最新",
    "当前",
    "天气",
    "股价",
    "新闻",
    "价格",
    "汇率",
    "几点",
    "时间",
)
