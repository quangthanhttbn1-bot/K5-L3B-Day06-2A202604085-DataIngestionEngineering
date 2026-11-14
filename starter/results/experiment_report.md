# Báo cáo truy xuất Technology

Ngày chạy: 2026-11-14. Corpus: Project Gutenberg eBook 7213, *My Life and Work* (Henry Ford, Samuel Crowther). Snapshot và đơn vị nguồn được mô tả trong `../data/manifest.json`.

## Cấu hình

- 120 unit, 519.276 ký tự; độ dài unit 1.834–4.996 ký tự.
- Embedding local Sentence Transformers `BAAI/bge-m3`, 1.024 chiều, L2-normalized; dùng `encode_document` và `encode_query`; chi phí dịch vụ: 0 USD.
- PostgreSQL + pgvector, cosine distance `<=>`, exact search; bảng `corpus_chunks`.
- A: 1.191 chunk, fixed 500 ký tự, overlap 50.
- B: 588 chunk, theo đoạn, giới hạn 1.200 ký tự.
- C: cùng chunk B, lọc theo `section` khi câu hỏi cung cấp phạm vi chương.
- Benchmark: 15 dev / 5 test; 6 câu có filter, trong đó 3 câu test.

## Retrieval accuracy

| Cấu hình | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 |
|---|---:|---:|---:|---:|
| A | 8/15 | 10/15 | 2/5 | 4/5 |
| B | 11/15 | 13/15 | 3/5 | 4/5 |
| C | 11/15 | 13/15 | 4/5 | 4/5 |

Evidence Hit@3 dùng điều kiện exact quote trong một chunk gold. Các trường hợp bằng chứng tương đương hoặc chia qua nhiều chunk chưa được tính là hit.

## Metadata usefulness

Đối chiếu 45 bản ghi trong top-3 của 5 câu test × 3 cấu hình với manifest: `source`, unit ID/vị trí và `section` đúng 45/45. Với 3 câu test có filter trong cấu hình C, cả 3 bộ top-3 đều tuân thủ `section` (3/3). `section` hỗ trợ truy vết và giới hạn phạm vi chương; `category=technology` chỉ có một giá trị trong corpus nên không phân biệt được phạm vi.

## Chunk coherence và grounding

Chấm thủ công bởi người thực hiện (tác giả pipeline), nên có nguy cơ thiên lệch. Với coherence, chọn trước 10 vị trí là đoạn nội dung đầu tiên trong các unit 009–018; chấm chunk chứa đầu đoạn theo thang 0–2 của GUIDE.md. Điểm theo vị trí:

| Unit | A | B | C | Ghi chú |
|---|---:|---:|---:|---|
| 009 | 1 | 1 | 1 | A cắt giữa câu; B/C giữ phần lớn đoạn dài nhưng dừng trước khi ý kết thúc. |
| 010 | 1 | 1 | 1 | Các chunk chứa phần đầu của đoạn dài, thiếu phần tiếp theo để khép ý. |
| 011 | 1 | 2 | 2 | B/C giữ trọn đoạn; A cắt trước khi hết đoạn. |
| 012 | 1 | 1 | 1 | Cả ba dừng giữa phần giải thích dài. |
| 013 | 1 | 1 | 1 | B/C vẫn cắt đoạn vượt giới hạn 1.200 ký tự; A ngắn hơn. |
| 014 | 1 | 1 | 1 | Đoạn rất dài; chunk được chọn chưa chứa toàn bộ giải thích. |
| 015 | 1 | 2 | 2 | B/C giữ trọn đoạn đầu; A chỉ giữ một phần. |
| 016 | 1 | 1 | 1 | Chunk được chọn dừng khi đoạn còn tiếp tục. |
| 017 | 1 | 1 | 1 | B/C giữ phần lớn nhưng vẫn thiếu kết luận của đoạn dài. |
| 018 | 1 | 2 | 2 | B/C giữ trọn đoạn; A cắt đoạn. |
| **Trung bình /2** | **1,0** | **1,2** | **1,2** | **A 10/20; B 12/20; C 12/20.** |

Grounding trên cùng 5 câu test, chấm top-3 theo mức 0–2:

| Câu test | A | B | C | Lý do |
|---|---:|---:|---:|---|
| q15 — việc làm quanh năm | 2 | 2 | 2 | Top-3 có đoạn nêu tác động đến việc làm, tổ chức sản xuất và cải tiến. |
| q17 — bỏ biểu mẫu/thống kê | 2 | 2 | 2 | Top-3 có lý do bỏ thống kê không trực tiếp tạo ô tô/giúp sản xuất. |
| q18 — bảo dưỡng đường sắt | 2 | 2 | 2 | Top-3 có đoạn về đại tu đầu máy và toa xe tại xưởng của công ty. |
| q19 — năng suất một xưởng | 0 | 0 | 0 | Không cấu hình nào đưa được bằng chứng so sánh 20 người với 59 người vào top-3. |
| q20 — xay xát gần nơi trồng ngũ cốc | 2 | 2 | 2 | Top-3 có khuyến nghị xay ngũ cốc tại nơi trồng và bối cảnh phân quyền sản xuất. |
| **Trung bình /2** | **1,6** | **1,6** | **1,6** | **Mỗi cấu hình: bốn câu mức 2, một câu mức 0.** |

Các điểm coherence/grounding là đánh giá thủ công của cùng người thực hiện, không phải kết quả độc lập; dùng để giải thích mẫu nhỏ này, không khẳng định hiệu năng tổng quát.

## Tác động và giới hạn

B tăng Hit@1 test từ 2/5 lên 3/5 so với A trong mẫu này, trong khi Evidence Hit@3 giữ ở 4/5. C giữ nguyên Evidence Hit@3 so với B và đạt Hit@1 4/5; đây là mẫu test chỉ có 5 câu, không đủ để kết luận C tốt hơn tổng quát. C dùng lại embedding của B vì chunk giống nhau; thời gian ingest ghi trong `run_summary.json` là thời gian của lần chạy tái sử dụng vector đã lưu, không phải thời gian encode lần đầu.

Test đã được xem trong lúc xử lý lỗi và sửa ký tự apostrophe bị PowerShell làm hỏng trước lần chạy kết quả cuối. Vì vậy kết quả được xem là exploratory, không phải đánh giá test mù. Không điều chỉnh chiến lược dựa trên kết quả này; nên tạo test holdout mới nếu cần kết luận so sánh chính thức.

Trace top-3 đầy đủ nằm trong `traces.json`; chỉ số và cấu hình máy nằm trong `run_summary.json`.
