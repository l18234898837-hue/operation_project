# Image Policy

Create one image asset table for the whole knowledge set, but include only images that remain as image assets.

## Image Types

| Type | Handling |
| --- | --- |
| 文字截图 | OCR, manually correct text, merge the text into the relevant topic document. Do not add successfully recognized text screenshots to the image asset table. |
| PPT页 | OCR, manually correct text, merge content into the relevant topic document or temporarily place it in document 10. Do not add successfully recognized PPT text pages to the image asset table. |
| 故障照片 | Write an image explanation and reference it inline in the relevant fault section. |
| 设备照片 | Write an image explanation and reference it inline if it clarifies equipment structure or risk. |
| 装饰图 / 封面图 | Archive only; do not include in the knowledge base. |

## Inline Reference Rule

Do not append images at the end as a gallery. Integrate fault photos and device photos into the body:

```text
光伏电站中变压器（见图 IMG_001）是升压站的核心设备，负责将光伏阵列产生的低电压升高并输送至电网。一旦变压器漏油，不仅会影响绝缘性能，还可能导致设备过热、短路，甚至引发火灾。
```

## Image Asset Table Fields

Use CSV or XLSX-compatible table columns:

```text
图片编号
图片类型
所属主题文档
正文引用位置
图片存储路径
图片说明
是否入库
备注
```

## Validation

- Every fault-photo/device-photo `IMG_###` in a topic document must exist in the image asset table.
- Text screenshot image ids may appear in working notes, but should not be in the final table once OCR text has been merged.
- Every included image must have `图片说明`.
- Decorative images must have `是否入库 = 否`.
