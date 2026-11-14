# Báo cáo cá nhân — Day 6

**MSSV:** 2A202604085  
**Họ tên:** Nguyễn Quang Thành

## Dữ liệu và pipeline

- **Chủ đề:** Technology — đổi mới cơ khí, ô tô, sản xuất và tổ chức công nghiệp.
- **Nguồn:** Henry Ford và Samuel Crowther, *My Life and Work*, Project Gutenberg eBook 7213: <https://www.gutenberg.org/cache/epub/7213/pg7213-images.html>. Snapshot HTML: [`starter/data/pg7213-images.html`](../../starter/data/pg7213-images.html). Quyền: snapshot có Project Gutenberg License; cần tuân thủ điều khoản và cảnh báo pháp lý kèm theo ebook khi phân phối lại. Ngày truy cập ghi trong [manifest](../../starter/data/manifest.json).
- **Quy tắc đếm:** HTML không phân trang; tách theo thứ tự đoạn thành 120 unit có ID truy vết, 1.834–4.996 ký tự/unit, tổng 519.276 ký tự chuẩn hóa. Mỗi unit đạt ngưỡng tối thiểu 1.500 ký tự. Một số thông tin đầu sách/mục lục còn nằm trong unit đầu; chưa được loại riêng hoàn toàn.
- **Chuẩn hóa và giới hạn:** Python HTMLParser, Unicode NFC, chuẩn hóa xuống dòng/khoảng trắng, giữ ranh giới đoạn và ID unit. Nguồn HTML không cần OCR. Evidence được kiểm tra sau khi gộp khoảng trắng; các trích dẫn dài bị cắt qua ranh giới chunk có thể không được tính là hit. Đây là một hồi ký/luận bàn công nghiệp đầu thế kỷ 20, không đại diện cho tài liệu kỹ thuật hiện đại.
- **Embedding:** Sentence Transformers 5.7.0, model `BAAI/bge-m3`, 1.024 chiều, vector chuẩn hóa L2; tài liệu dùng `encode_document`, câu hỏi dùng `encode_query`. Model chạy local, chi phí dịch vụ $0. Revision cụ thể của model Hugging Face không được pin.
- **Vector store:** PostgreSQL 16 + pgvector 0.8.7 trong Docker Compose, bảng `corpus_chunks`, cosine distance `<=>`, exact search, chưa dùng ANN index. Lệnh chạy từ `starter/`: `python -m src.run` (trên Windows có thể dùng `.\.venv\Scripts\python.exe -m src.run` khi đã ở trong thư mục `starter/`; nếu gọi từ repo root: `starter\.venv\Scripts\python.exe -m src.run`).
- **Metadata:** `document_id`, `source`, `page` (số thứ tự unit) và `unit_id` (ID vị trí truy vết). Trường lọc `section` lấy từ heading chương trong HTML; `category=technology` và `language=en` được gắn theo nguồn/corpus. `section` cho phép lọc chương; `category` chỉ có một giá trị trong corpus này.

## Cấu hình và benchmark

- **A:** fixed-size 500 ký tự, overlap 50; 1.191 chunk.
- **B:** gom theo đoạn, giới hạn 1.200 ký tự; 588 chunk.
- **C:** chunk giống B, chỉ thêm filter `section` khi câu hỏi có phạm vi chương; 588 chunk. B–C chỉ thay filter.
- **Benchmark:** 20 câu trong [benchmark.json](../../starter/data/benchmark.json), chia 15 dev / 5 test; 6 câu có filter, gồm 3 test. Mỗi câu có đáp án, source/unit gold và evidence quote. Pipeline kiểm tra quote tồn tại trong unit nguồn và filter khớp metadata trước truy xuất.
- **Tiêu chí chọn chiến lược:** chưa ghi nhận tiêu chí lựa chọn được chốt trước khi xem test. Test đã được mở trong quá trình sửa lỗi nhập liệu và pipeline; do đó kết quả chỉ mang tính khám phá, không dùng để tuyên bố một cấu hình thắng tổng quát.

## Kết quả

### Retrieval accuracy

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí |
|---|---|---:|---:|---:|---|---:|
| A | dev | 8/15 | 10/15 | 1.191 | 0,038 giây (tái sử dụng vector) | $0 |
| A | test | 2/5 | 4/5 | 1.191 | — | $0 |
| B | dev | 11/15 | 13/15 | 588 | 0,033 giây (tái sử dụng ở lần báo cáo cuối) | $0 |
| B | test | 3/5 | 4/5 | 588 | — | $0 |
| C | dev | 11/15 | 13/15 | 588 | 0,037 giây (tái sử dụng vector B) | $0 |
| C | test | 4/5 | 4/5 | 588 | — | $0 |

Lần encode đầy đủ B được ghi là 681,158 giây; các thời gian rất ngắn trong bảng là lần chạy cuối sau khi vector đã lưu và không thể so sánh như thời gian ingest đầy đủ. Thời gian encode đầy đủ của A không được ghi lại thành công. C dùng lại vector B vì chunk giống hệt.

### Audit thủ công và metadata

| Strategy | Coherence trung bình /2 (n) | Metadata đúng/đủ (n/N) | Filter tuân thủ trên test (n/N) | Grounding mức 0/1/2; trung bình /2 |
|---|---:|---:|---:|---|
| A | 1,0/2 (10) | 45/45 | N/A — không lọc theo thiết kế | 1/0/4; 1,6/2 |
| B | 1,2/2 (10) | 45/45 | N/A — không lọc theo thiết kế | 1/0/4; 1,6/2 |
| C | 1,2/2 (10) | 45/45 | 3/3 câu test có filter | 1/0/4; 1,6/2 |

Coherence dùng 10 vị trí đầu đoạn trong unit 009–018. Metadata là 45 kết quả top-3 của 5 câu test × 3 cấu hình, đối chiếu source, unit ID/vị trí và section với manifest. Grounding chấm 5 câu test × top-3 theo độ đủ của bằng chứng; cùng một người thực hiện chấm nên có nguy cơ thiên lệch. Nhãn và lý do chi tiết nằm trong [experiment_report.md](../../starter/results/experiment_report.md).

**Trace và cấu hình:** [traces.json](../../starter/results/traces.json), [run_summary.json](../../starter/results/run_summary.json), [manifest.json](../../starter/data/manifest.json).

## Phân tích và kết luận

- **A–B:** B tăng Hit@1 từ 2/5 lên 3/5 trên test, Evidence Hit@3 giữ ở 4/5; coherence tăng từ 1,0 lên 1,2/2. Chunk theo đoạn giảm số chunk khoảng một nửa, nhưng các đoạn dài hơn giới hạn vẫn bị chia.
- **B–C:** C đạt Hit@1 4/5 so với 3/5 của B, còn Evidence Hit@3 vẫn 4/5. Filter giúp q18 trả evidence đúng ở top-1; q19 vẫn không có evidence gold trong top-3. Chỉ có 3 câu test có filter, nên chênh lệch này chưa đủ để khái quát.
- **Hai lỗi truy xuất:** (1) q19 hỏi so sánh năng suất 20 người với 59 người tại unit `pg7213-my-life-and-work:unit-095`; cả A/B/C đều không đưa evidence vào top-3. (2) q18 hỏi về bảo dưỡng đầu máy/toa xe tại cùng unit; A và B xếp chunk sai chương ở top-1, còn evidence gold chỉ xuất hiện thấp hơn trong top-3; C lọc `Chapter Xvi` và đưa evidence lên top-1.
- **Lựa chọn sử dụng:** không kết luận cấu hình tốt nhất từ test nhỏ đã bị xem trong lúc gỡ lỗi. B là baseline hợp lý khi không có filter; C phù hợp khi ngữ cảnh câu hỏi cung cấp trước một `section` đáng tin. Cần test holdout mới trước khi đưa ra kết luận chính thức.
- **Hạn chế:** một ebook, một ngôn ngữ và một chủ đề hẹp; benchmark test chỉ 5 câu; người chấm không độc lập; exact quote có thể bỏ sót evidence diễn đạt tương đương hoặc nằm qua nhiều chunk; revision model chưa pin; thời gian encode CPU cao và số đo lần chạy cuối chủ yếu là tái sử dụng vector.
- **Nếu làm lại:** tạo và khóa test holdout trước khi xem trace; chốt tiêu chí chọn chiến lược trước khi đánh giá; pin revision model; loại riêng mục lục/đầu sách; lưu thời gian ingest đầy đủ cho cả A/B/C; nhờ người chấm độc lập kiểm tra coherence và grounding.
