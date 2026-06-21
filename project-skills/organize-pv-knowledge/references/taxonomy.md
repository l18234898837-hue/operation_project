# PV O&M Knowledge Taxonomy

Use these 9 documents as the fixed formal knowledge-base output set.

| No. | Document | Scope |
| --- | --- | --- |
| 01 | 01_逆变器故障与维护.md | Inverter high temperature derating, shutdown, PV overvoltage, grid over/undervoltage, leakage current, explosion warning signs, post-replacement checks, maintenance points. |
| 02 | 02_组件故障与低效问题.md | Module low efficiency, hidden cracks, hot spots, degradation, bursting, junction box faults, EL inspection, mud belt impact. |
| 03 | 03_线缆接头与绝缘故障.md | Loose terminals, overheating joints, cable damage, insulation resistance abnormality, short circuit, fire sealing. |
| 04 | 04_SVG与无功设备故障.md | SVG shutdown, power unit faults, communication faults, grid-voltage abnormality, routine SVG troubleshooting. |
| 05 | 05_变压器箱变与电气设备.md | Transformer oil leakage, box transformer abnormalities, electrical equipment installation, equipment defects. |
| 06 | 06_发电量异常与效率损失.md | Low generation, dust cleaning, low-efficiency modules, shading, weather station, risks during high generation. |
| 07 | 07_巡检检测与预防维护.md | Aging station inspection, module inspection, inverter inspection, supports/foundations, grounding, lightning protection, neglected inspection points. |
| 08 | 08_安全风险与应急处理.md | Fire, DC arc, electric shock, equipment overheating, extreme weather, module bursting, emergency power-off. |
| 09 | 09_运维管理制度与人员配置.md | Staffing, defect management, defect elimination statistics, management indicators, duty responsibilities. |
## Classification Rules

- Classify by the future user question, not by source title.
- If a source covers multiple topics, split it into multiple knowledge points.
- If a knowledge point is safety-focused, place it in `08` and add operational details in the equipment-specific document only when needed.
- If content is mainly a maintenance checklist, place it in `07`.
- If content is management/process rather than technical troubleshooting, place it in `09`.
- Store PPT pages, text screenshots, training courseware, and OCR staging content in an intermediate document area, not as a formal knowledge-base document.
- Move successfully recognized OCR/PPT content to `01-09`.
- Do not include intermediate staging documents in the formal ingestion set.
