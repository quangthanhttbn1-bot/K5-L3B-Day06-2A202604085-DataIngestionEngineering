# Starter · PostgreSQL + pgvector

Bộ khởi động **tùy chọn** cho lab cá nhân. Docker Compose tạo PostgreSQL + pgvector local; các file trong `src/` là **khung pseudocode có TODO**, chưa đọc tài liệu, tạo embedding, lưu vector hay chạy benchmark. Bạn cần tự hiện thực. Vẫn có thể chọn Qdrant, Chroma hoặc vector store tương đương theo [GUIDE.md](../GUIDE.md).

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf và python-dotenv
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # TODO: đọc / chuẩn hóa tài liệu
│   ├── chunking.py        # TODO: chia chunk
│   ├── embeddings.py      # TODO: chọn model API hoặc local
│   ├── store.py           # TODO: lưu vector, metadata và filter
│   ├── evaluation.py      # TODO: chấm truy xuất, lưu trace
│   └── run.py             # TODO: kết nối các bước thành pipeline
├── data/                  # bạn tự chuẩn bị corpus được phép sử dụng
└── results/               # lưu kết quả của bạn
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14**, và mạng để tải image/dependencies lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Điền key tương ứng trong `.env` nếu dùng OpenRouter, OpenAI hoặc Gemini; **không commit `.env`**. Model local không cần API key. `requirements.txt` chỉ có dependencies cơ bản: tự cài SDK hoặc thư viện local phù hợp với model bạn chọn và ghi lại version/lệnh cài trong báo cáo. Ghi tên model và số chiều; dùng cùng model cho toàn bộ chiến lược và vector query tương thích vector document.

## 3. Hoàn thiện pipeline

1. Đặt corpus vào `data/` hoặc cung cấp manifest/hướng dẫn truy cập. Đọc [GUIDE.md](../GUIDE.md) về **30 trang nội dung**, quyền dữ liệu và metadata.
2. Hoàn thiện từng hàm TODO trong `src/`. Lưu ID tài liệu, nguồn, trang/vị trí và ít nhất một trường filter có ích.
3. Xây ít nhất ba cấu hình; ví dụ A fixed-size, B theo đoạn, C như B nhưng có filter. Cần cùng corpus, model và benchmark; nạp lại không nhân đôi và xử lý chunk cũ khi dữ liệu đổi.
4. Tự viết ít nhất 20 câu hỏi kèm evidence, tách dev/test trước khi thử theo [BENCHMARK.md](../BENCHMARK.md). Lưu trace top-3 và báo cáo đủ năm tiêu chí.
5. Sau khi hoàn thiện, chạy `python -m src.run` từ thư mục `starter/`. Trước khi làm TODO, lệnh này **chủ động báo `NotImplementedError`**.

Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ.

## Corpus Technology đã chuẩn bị

`data/pg7213-images.html` là snapshot Project Gutenberg eBook 7213, *My Life and Work* (Henry Ford, với Samuel Crowther). Chủ đề sử dụng là Technology: cơ khí, ô tô, sản xuất và tổ chức công nghiệp. Đây là hồi ký/luận bàn về kinh doanh, không phải giáo trình kỹ thuật hiện đại; kết quả chỉ đại diện cho nguồn này.

Nguồn gốc: <https://www.gutenberg.org/cache/epub/7213/pg7213-images.html>. Snapshot giữ nguyên HTML gốc, bao gồm thông tin giấy phép Project Gutenberg. Hãy kiểm tra điều khoản áp dụng tại nơi sử dụng trước khi phân phối lại. Manifest có checksum snapshot, ngày truy cập, số unit và số ký tự được sinh khi chạy pipeline. Loader chỉ giữ phần giữa dấu START/END của ebook, chuẩn hóa Unicode NFC, rồi chia theo đoạn thành unit có `section`, `unit_id`, số ký tự và SHA-256. Bộ nạp sẽ dừng nếu không đạt 30 unit, mỗi unit tối thiểu 1.500 ký tự.

Trường metadata lọc: `section` (tên chương/Introduction được lấy từ heading trong HTML), `category=technology`, `language=en`; `document_type=html`. Filter `section` hữu ích để giới hạn một chương. Tránh filter theo category vì corpus này chỉ có một category. Unit ID là trang/vị trí truy vết tương đương cho nguồn HTML không phân trang.

### Chạy pipeline

Cần cài lại dependencies sau khi thêm pgvector:

```powershell
python -m pip install -r requirements.txt
docker compose -p day6_student_starter up -d --wait
python -m src.run
```

Model mặc định là Sentence Transformers `BAAI/bge-m3` (1024 chiều, local), dùng `encode_document`/`encode_query`, vector chuẩn hóa L2; lần đầu cần tải model. Không có fallback giả lập. Vector store là PostgreSQL + pgvector; dùng cosine distance, tìm kiếm exact (chưa tạo ANN index), collection/bảng `corpus_chunks`, khóa strategy và chunk ID. Upsert thay toàn bộ dữ liệu của từng strategy trong transaction để xóa chunk cũ và không nhân đôi.

Chiến lược A dùng cửa sổ 500 ký tự, overlap 50; B gom đoạn theo ranh giới đoạn, tối đa 1.200 ký tự; C dùng chunk B và áp dụng metadata filter khi câu hỏi có `filter`. Cần PostgreSQL đang chạy và bộ câu hỏi đã kiểm chứng tại `data/benchmark.json`. Mỗi câu hỏi phải có `id`, `split`, `question`, `expected_answer`, `gold_source_id`, `gold_page` (unit ID) và `evidence_quote`; `filter` là tùy chọn. Pipeline kiểm tra tối thiểu 20 câu (15 dev/5 test), 3 filter (ít nhất 1 test), evidence quote tồn tại chính xác trong unit gold và filter khớp metadata trước khi embed hoặc truy xuất.

Benchmark đã được chuẩn bị tại `data/benchmark.json`: 15 dev / 5 test, 6 câu có filter, evidence được kiểm tra với snapshot sau khi chuẩn hóa khoảng trắng. Kết quả sinh trong `results/traces.json` (top-3, text, score, metadata và gold), `results/run_summary.json` (Hit@1, Evidence Hit@3, số chunk, độ dài, thời gian, model/store) và `results/experiment_report.md` (so sánh và nhãn coherence/grounding thủ công). Metadata top-3 test được đối chiếu với manifest. Test đã được xem trong lúc sửa lỗi nhập liệu nên kết quả hiện tại là exploratory, không phải test mù; xem giới hạn trong báo cáo.
