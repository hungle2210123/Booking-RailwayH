---
paths:
  - "templates/ai_assistant.html"
  - "app_parts/p09_*.py"
---
# Mẫu Câu (message templates) — read docs/messages.md ("Mẫu Câu page") for the full notes
- Pictures live IN THE DB (`template_images.image_data`); Railway's disk is wiped on every deploy. Max 3 pictures per template.
- The page caches templates in `window.templates`: after adding / deleting a picture update that cache too
  (`deleteTemplateImage(imageId, templateId, btn)`), or the gallery redraws the old picture.
- One tap must open the phone's share sheet (no in-between sheet); 🇻🇳 only on check-in guide templates.
- After changes: `python -m pytest tests/test_flows.py::test_template_image_delete tests/test_pages.py`.
