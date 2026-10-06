# JARVIS-1 — Document Intelligence (Bước 3) — Báo cáo hoàn thành

## FILES CREATED
```
core/document_intelligence/__init__.py     39 dòng — public API của package
core/document_intelligence/types.py       220 dòng — DocType, DocumentRecord, mô hình nội dung chuẩn hoá, DocumentTask
core/document_intelligence/router.py       73 dòng — Document Type Router
core/document_intelligence/extractors.py  208 dòng — Extraction Layer (PDF/DOCX/XLSX/CSV/PPTX/TXT/code)
core/document_intelligence/operations.py  193 dòng — READ/EXTRACT/SUMMARIZE/QA/COMPARE/SEARCH/MULTI_DOC
core/document_intelligence/verification.py 84 dòng — xác minh artifact đầu ra
core/document_intelligence/checkpoint.py  103 dòng — DocumentTask persistence + retry/timeout có giới hạn
actions/document_intelligence.py          143 dòng — tool Gemini gọi được (đa tài liệu)
tests/test_document_intelligence.py       389 dòng — 29 test, tất cả PASS
docs/DOCUMENT_INTELLIGENCE_REPORT.md      (file này)
```
Tổng: 1.452 dòng code mới, 9 file mới, **0 file bị xoá**.

## FILES MODIFIED
```
requirements.txt   +3 dòng: pdfplumber, python-docx, pandas
```
Ba gói này đã được `actions/file_processor.py` import từ trước (PDF/DOCX/CSV/Excel)
nhưng **chưa từng được khai báo trong requirements.txt** — trên máy cài mới,
`setup.py`/`setup.ps1` không cài chúng, nên các action đó âm thầm rơi vào
nhánh `except ImportError` mà không ai biết. Đây là lỗ hổng có sẵn trong repo,
không phải do Bước 3 tạo ra, nhưng chặn thẳng lối vào Extraction Layer mới nên
phải sửa cùng lúc.

**`main.py`, `ui.py`, `floating_button.py`, `actions/file_processor.py`: KHÔNG đổi
một dòng nào.** Đúng yêu cầu "không redesign UI, không thay kiến trúc đang chạy
tốt nếu không bắt buộc" — `document_intelligence` là tool auto-discover thêm vào
qua `core/action_loader.py` có sẵn, main.py không cần biết gì về nó.

## SUPPORTED FORMATS
| Định dạng | Trích xuất | Ghi chú |
|---|---|---|
| PDF | ✅ | text + bảng theo từng trang, cần `pdfplumber` |
| DOCX | ✅ | đoạn văn + bảng, cần `python-docx` |
| XLSX | ✅ | mọi sheet, cần `openpyxl` (đã có sẵn) |
| CSV | ✅ | stdlib `csv`, không cần cài thêm |
| PPTX | ✅ | text từng slide, cần `python-pptx` (đã có sẵn) |
| TXT / MD / RST / LOG | ✅ | đọc trực tiếp |
| Code (.py/.js/.ts/…) | ✅ | đọc như text, dùng cho search/summarize — **sửa code vẫn dùng `code_helper` như cũ** |
| XML / JSON | ✅ đọc thô | cố tình KHÔNG dùng chung logic với nhau (test riêng đảm bảo `.xml` không bị route thành JSON) |
| .doc (Word cũ, nhị phân) | ❌ có chủ đích | không có thư viện thuần Python đáng tin cậy để đọc — báo lỗi rõ ràng thay vì đoán mò qua DOCX (test riêng đảm bảo không bị route nhầm) |
| Định dạng khác | → `UNSUPPORTED_FORMAT` | không đoán, không crash |

## EXTRACTION PIPELINE
```
detect_type(path)                     — router.py, chỉ nhìn phần mở rộng
    ↓
extract(path)                         — extractors.py
    → DocumentRecord (metadata: id, tên, kích thước, page/sheet/slide_count…)
    → ExtractedDocument (Section → Paragraph/Table | Sheet | Slide)
      mỗi mẩu nội dung giữ SourceRef (file/page/sheet/slide/index) để truy ngược
    ↓
run_operation(op, paths, ...)         — operations.py
    read / extract / search_within_document  → CỤC BỘ, không gọi Gemini
    summarize / question_answer / compare / multi_document_analysis → gọi Gemini
```
Một file lỗi không làm hỏng cả batch: `extract()` không bao giờ raise ra ngoài —
lỗi được ghi vào `record.error` + `extraction_status="failed"`, các file còn lại
trong cùng lệnh vẫn xử lý bình thường (test: `test_one_bad_file_does_not_abort_batch`).

## OUTPUT VERIFICATION
`verify_artifact(path, type)` — không bao giờ chỉ báo "đã tạo file":
kiểm tra tồn tại → không rỗng → mở/đọc lại được đúng định dạng (txt/csv/json/docx/xlsx/pdf
có hàm kiểm tra riêng) → trả về `artifact_path / artifact_type / verification_status /
verification_error`. Test: file rỗng, JSON hỏng, file không tồn tại đều bị bắt đúng.

## RETRY / RECOVERY
`retry_with_backoff()` — số lần thử có giới hạn (mặc định 1 lần thử + `retries`
lần thử lại, KHÔNG bao giờ vô hạn), timeout cứng theo từng lần thử, chạy trong
thread riêng nên một cuộc gọi bị treo không giữ luôn tiến trình chính. Trong lúc
viết test bắt được một lỗi thật: dùng `with ThreadPoolExecutor` khiến hàm vẫn bị
chặn đến khi luồng treo tự xong dù đã timeout — đã sửa bằng `shutdown(wait=False)`.
`run_batch_isolated()` — lỗi một item không dừng các item còn lại (spec §8).

## CHECKPOINT
`DocumentTask` (task_id, documents[], current_document, completed_documents[],
failed_documents[], current_operation, artifacts[], status) — lưu xuống
`memory/doc_tasks/<task_id>.json` sau mỗi lần gọi tool, kể cả tác vụ 1 file.
Đây là state có thể *đọc lại và kiểm tra* (`load_task`, `list_tasks`), không phải
một execution graph đầy đủ kiểu LangGraph — đúng như spec yêu cầu KHÔNG cần cài
LangGraph, chỉ cần tư duy "lưu trạng thái, có thể tiếp tục, không làm lại phần
đã xong". **Resume tự động giữa các lần chạy app (nếu app tắt giữa chừng) chưa
được nối vào main.py — xem Known Issues.**

## TEST RESULTS
```
python -m unittest tests.test_document_intelligence -v
Ran 29 tests in 0.53s
OK
```
Bao phủ: router (4 test, gồm 2 test chống misroute .xml/.doc) · extraction
6 định dạng bắt buộc · file rỗng/không tồn tại/sai định dạng/hỏng · đa tài liệu +
cô lập lỗi · verification (4 test) · checkpoint round-trip · retry (thành công /
hết lượt thử / timeout thật sự có tác dụng) · **1 test end-to-end đầy đủ: 3 tài
liệu → read → extract → tạo báo cáo → verify**.

`python -m compileall .` — toàn repo: **0 lỗi**.
`core.action_loader.discover_actions()` (đúng đường dẫn khởi động thật của
main.py) — nạp thành công **17/17** action, gồm `document_intelligence` mới.

## KNOWN ISSUES
1. **Chưa test với Gemini thật.** Môi trường build này không có API key —
   `summarize`, `question_answer`, `compare`, `multi_document_analysis` được
   test qua đường dẫn dispatch (đúng hàm được gọi, đúng câu trả lời khi trích
   xuất thất bại) nhưng CHƯA gọi Gemini thật. Cần chạy tay 1 lần trên máy có
   API key trước khi coi là production-ready.
2. **Resume sau khi app tắt giữa chừng chưa tự động.** `DocumentTask` đã lưu
   đủ state để resume, nhưng chưa có code nào trong `main.py` tự đọc lại task
   dở dang lúc khởi động — hiện tại phải tự gọi `load_task(task_id)` thủ công.
3. **`.doc` (Word nhị phân cũ) không đọc được**, có chủ đích — báo lỗi rõ ràng
   thay vì đoán mò. Nếu cần, có thể thêm `textract`/`antiword` sau.
4. **`file_processor.py` chưa dùng chung Extraction Layer mới** — theo đúng
   spec §13 (không tạo hệ thống song song, không đổi API đang chạy tốt), các
   handler cũ trong `file_processor.py` vẫn tự trích xuất theo cách riêng của
   chúng. Có thể hợp nhất dần sau, không cấp thiết vì cả hai đều hoạt động.

## NEXT INTEGRATION POINT FOR TASK PLANNER
`core/document_intelligence` viết tách biệt khỏi UI/tool cố ý — một Task Planner
sau này (phần `agent/` đã bàn trước đó) có thể gọi thẳng `run_operation()`,
`new_task()/save_task()/load_task()` như một bước trong kế hoạch nhiều bước, mà
không cần đi qua lớp tool-calling của Gemini. `DocumentTask` dùng chung "hình dạng"
trạng thái (task_id/status/completed/failed) mà một `agent/task_queue.py` sau này
có thể tái dùng thẳng, thay vì phát minh lại.
