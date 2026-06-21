# Topic Document Template

Each topic document should use this structure.

```markdown
# 01_逆变器故障与维护

## 1. 适用范围
说明本文覆盖哪些设备、故障和运维场景。

## 2. 常见故障与处理

### 2.1 具体故障名称
用 1-2 段说明该故障的业务含义。需要引用图片时，把图片融入正文，例如：直流端子出现发黑、变形或熔化痕迹（见图 IMG_012）时，通常提示接触不良、局部过热或直流拉弧风险。

- 典型现象：
- 可能原因：
- 检查方法：
- 处理措施：
- 预防建议：
- 安全注意事项：

## 3. 巡检与预防维护
- 月度检查：
- 季度检查：
- 年度检查：

```

## Writing Rules

- Use structured, operational wording.
- Keep each fault point granular.
- Avoid raw source titles, article intros, marketing language, jokes, and unrelated story openings.
- Integrate extracted text and OCR text into the topic; do not paste article text wholesale.
- Do not add a source-material section.
- Use image references inline as `(见图 IMG_###)` only for device photos or fault photos worth preserving.
- Do not add simulated retrieval-question sections or comparison sections; retrieval questions belong to the query layer, not the source knowledge document.
- Do not add pending-work sections such as `待补充` or `待OCR` to final knowledge documents.
- Do not fabricate or expand details beyond the extracted source material.
- Avoid long paragraphs; prefer short explanatory paragraphs plus bullet lists.
