"""mkexam — 题库管理与组卷系统

设计：
  bank/         题库管理（增删改查、CSV导入导出）
  exam/         组卷引擎（选题、生成试卷）
  data/         题库数据存储
  output/       试卷输出

用法：
  python -m mkexam          # 交互式菜单
  python -m mkexam bank     # 题库管理
  python -m mkexam exam     # 组卷
"""
