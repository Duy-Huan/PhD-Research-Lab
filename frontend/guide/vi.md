# Hướng dẫn sử dụng PhD Research Lab

PhD Research Lab là phòng thí nghiệm nghiên cứu chạy trên máy của bạn. Nó kết hợp **AI đám mây** (Claude, GPT, Gemini…) cho các việc cần suy luận sâu và viết học thuật, với **AI cục bộ** (Ollama hoặc LM Studio) cho các việc trích xuất nhanh, riêng tư và miễn phí. Hướng dẫn này đi từ cài đặt, qua từng công cụ, đến quy trình làm việc hiệu quả nhất cho một nghiên cứu sinh.

> **Nguyên tắc vàng:** AI soạn nháp, **bạn** là tác giả. Mọi trích dẫn, con số và kết luận phải được bạn kiểm chứng trước khi nộp bài.

## Bắt đầu nhanh (5 phút)

1. **Chạy app:** Windows chạy `run.bat`; Linux/macOS chạy `./run.sh`. Trình duyệt mở `http://127.0.0.1:8765`.
2. **Nhập API key:** thanh bên → *Cloud AI providers* → bấm hãng (ví dụ Anthropic Claude) → dán key → **↻ List** → chọn model → **Test connection** → **Save configuration**.
3. **(Tuỳ chọn) Bật AI cục bộ:** cài **Ollama** (khuyên dùng) hoặc mở LM Studio → *Developer* → **Start Server**. Ở thanh bên, bấm **Nạp** cạnh model muốn dùng (Ollama: gõ tên model rồi **⤓ Tải về** nếu chưa có).
   - **(Tuỳ chọn) Máy có Docker/GPU:** tab **🐳 Docker & Hệ thống** → *🔎 Quét lại máy* → *⚡ Áp dụng cấu hình khuyên dùng*.
4. **Tạo dự án:** *📂 Research project* → **＋ New** → đặt tên đề tài.
5. **Đưa tài liệu vào:** tab *Papers & Writer* → *Reference Library* → kéo-thả các PDF toàn văn (IEEE, ACM, arXiv…).
6. **Chạy Tool 1:** tab *Lit2Plan* → mô tả ý tưởng → **Generate research plan** → đặt câu hỏi tiếp trong khung chat bên dưới.

## Ngôn ngữ

- **EN / VI** ở góc trên bên phải đổi toàn bộ giao diện và cuốn hướng dẫn này. Lựa chọn được ghi nhớ trong trình duyệt.
- **🌐 Ngôn ngữ output của AI (Tool 1, 2, 4)** ở thanh bên có 3 lựa chọn: *Theo ngôn ngữ giao diện*, *Luôn tiếng Anh*, *Luôn tiếng Việt*. Thuật ngữ kỹ thuật, tên phương pháp, trích dẫn, công thức và code vẫn giữ tiếng Anh.
- **Bài báo LaTeX (Tool 3) luôn viết bằng tiếng Anh.** Chat trả lời theo ngôn ngữ bạn dùng để hỏi.

## Kiến trúc & chi phí

| Tác vụ | Engine khuyên dùng | Lý do |
|---|---|---|
| Mở rộng truy vấn, đọc metadata PDF, BibTeX (3.1), chuyển dữ liệu → bảng LaTeX | 🖥 Local | Nhanh, riêng tư, miễn phí, việc có cấu trúc rõ |
| Lit2Plan, thiết kế thí nghiệm, viết bài (3.2), phản biện (3.3), sửa bài (3.4), Masterclass | ☁ Cloud | Cần suy luận sâu và văn phong học thuật |
| Chat theo dõi (💬) | ☁ Cloud (hoặc Local cho câu hỏi ngắn) | Chất lượng phân tích quyết định giá trị |

- Mỗi agent chọn engine riêng ở *⚙ Agent engines*: **Default** (hãng cloud mặc định), **Local**, hoặc một hãng cụ thể. Ví dụ: Claude viết bài, GPT phản biện. Dùng hai model khác nhau cho viết và phản biện sẽ giúp bản phản biện khách quan hơn.
- Bật *Fall back to Claude if local fails* để công việc không bị dừng khi LM Studio tắt.
- **Tiết kiệm token:**
  - Tắt *🔗 Shared context* khi chỉ hỏi nhanh.
  - Chỉ đính kèm phần tài liệu thật sự cần.
  - Dùng Local cho các việc lặp lại.

## Dự án nghiên cứu (Projects)

Mỗi dự án có **thư mục data** riêng (workspace, output, chat, ghi chú 📌, thư viện) và **thư mục references** riêng (PDF). API key và cấu hình AI dùng chung cho mọi dự án.

- **＋ New**: tạo dự án mới (mặc định trong `projects/<tên>`).
- **📂 Open… / 📁 Browse** (cạnh *Data folder*): mở một thư mục bất kỳ thành dự án, ví dụ thư mục chép từ máy khác hoặc ổ mạng.
- **📁** cạnh *References folder*: chọn nơi chứa PDF của dự án.
- **✕**: chỉ gỡ dự án khỏi danh sách, **không xoá file**.
- **Mẹo:** để references nằm *bên trong* data folder. Khi đó cả dự án là một thư mục trọn vẹn, dễ sao lưu, nén hoặc đồng bộ qua OneDrive/Google Drive.

## Tool 1 — Lit2Plan: định hướng nghiên cứu

**Đầu vào:** ý tưởng thô và ràng buộc (dữ liệu, phần cứng, thời gian, venue mục tiêu).
**Đầu ra:**
- Mở rộng truy vấn, kèm chuỗi tìm kiếm dán thẳng vào IEEE Xplore, ACM, Scopus.
- Taxonomy SOTA, các research gap G1…Gn, giả thuyết kiểm chứng được H1…Hn.
- **Roadmap 6 tháng**, bảng rủi ro và venue phù hợp.

**Cách dùng hiệu quả:**
1. Viết ý tưởng **cụ thể**, nêu rõ bối cảnh và ràng buộc. Ví dụ: *"Khử nhiễu ảnh siêu phổ cho UAV, ngân sách 2 W, có dữ liệu Indian Pines, 6 tháng, nhắm IEEE TGRS"*.
2. **Đưa PDF vào thư viện trước**. Planner sẽ trích dẫn tài liệu của bạn bằng `[bib_key]` thay vì dựa vào kiến thức chung.
3. Dùng chuỗi truy vấn sinh ra để tìm thêm bài, tải PDF về, nạp vào thư viện, rồi **chạy lại** Lit2Plan. Mỗi vòng như vậy, kế hoạch bám tài liệu chắc hơn.
4. Đào sâu bằng 💬 chat. Ví dụ: *"Phản biện H1 như một reviewer khó tính"*, *"Gap nào dễ xuất bản nhất trong 6 tháng?"*, *"Chuyển tháng 1 thành kế hoạch từng tuần"*.
5. **Chốt 🔒 các định hướng** ngay trong chat: bấm 🔒 *Chốt* dưới câu trả lời (hoặc bôi đen một đoạn trong kế hoạch → *🔒 Chốt đoạn đã chọn*), chọn loại: định hướng / giả thuyết / gap / ràng buộc / hướng đã loại. Các quyết định đã chốt hiện ở thẻ *🔒 Quyết định đã chốt*, **ràng buộc mọi agent** (Tool 2–4, Code IDE, Writer) và hiện thành node 📌 trong tab Ngữ cảnh.
6. Sau nhiều vòng thảo luận, bấm **🔄 Tạo lại tổng quan từ thảo luận**: kế hoạch được viết lại dựa trên cuộc chat và các quyết định đã chốt. Bản cũ luôn được giữ trong **🕘 Phiên bản** (khôi phục được).

## Tool 2 — Thiết kế thí nghiệm

**Đầu ra:**
- Công thức toán, các metric kèm công thức, ma trận ablation và quy trình thống kê.
- File **`experiment_skeleton.py`** chạy được ngay với dữ liệu tổng hợp.

**Cách dùng hiệu quả:**
1. Phần *Novelty* nên mô tả: đóng góp mới, giả thuyết cần kiểm chứng, và baseline cần thắng.
2. Ghi rõ ràng buộc tính toán, ví dụ *"1× RTX 4090, 3 tuần"*. Thiết kế sẽ thực tế hơn.
3. Tải `experiment_skeleton.py`, chạy thử trên dữ liệu tổng hợp, rồi thay `Dataset` bằng dữ liệu thật.
4. Trong 💬 chat, đính kèm **log huấn luyện, file `.py` hoặc ảnh biểu đồ** để AI phân tích lỗi, đề xuất sửa code hoặc kiểm định thống kê.
5. Bấm **→ Use as paper method notes** để đưa thiết kế sang Paper Writer.

### 📥 Kết quả nghiên cứu của bạn (v3.1)
Khi bạn tự code và chạy thí nghiệm ở ngoài app, hãy đưa kết quả vào thẻ **📥 Kết quả nghiên cứu của bạn** (cuối tab Thiết kế thí nghiệm):
1. **Thả file** (hoặc bấm để chọn): ảnh PNG/JPG/SVG/EPS, PDF, `.tex`, `.md`, `.csv/.tsv`, `.xlsx`, `.docx`, `.ipynb`, `.json`, `.log`, code… Có thể ghi **mô tả chung** và **nhãn** trước khi thả. Hoặc **＋ Nhập kết quả bằng tay** (dán số liệu, bảng Markdown).
2. **Mô tả từng kết quả** ngay trên thẻ: thí nghiệm gì, bộ dữ liệu, thiết lập, baseline, kết quả cho thấy điều gì. AI dựa vào mô tả này (đặc biệt với ảnh).
3. **✨ Phân tích:** AI đọc file hoặc **ảnh** (model có thị giác) và ghi lại các con số chính, phát hiện, lưu ý và gợi ý chú thích hình. Chỉ dựa trên nội dung file, không bịa số.
4. **▦ Bảng LaTeX:** chuyển CSV/Markdown/Excel/.tex thành bảng booktabs và thêm vào Paper Writer.
5. **📌 Ghim** (mọi agent bắt buộc tính tới) hoặc **🙈 Ẩn khỏi AI** (file vẫn giữ). Kết quả cũng hiện thành node trong tab 🧠 Ngữ cảnh.
6. **✍ Dùng trong bài báo:** chọn mục (vd. Thí nghiệm và kết quả) và cách trình bày (bảng, hình, số liệu trong câu, so sánh, kết quả nổi bật) — kết quả được thêm vào 🎯 Brief của mục đó.

Mọi chat, bộ thiết kế thí nghiệm (sẽ đề xuất các thí nghiệm còn thiếu dựa trên kết quả bạn đã có) và agent viết bài đều nhận được tóm tắt các kết quả này. File lưu trong `data/results/` của dự án; xoá thì chuyển vào `data/results/_trash/`.

## Tool 3 — Thư viện, Data Chat & Paper Writer

### 1. Thư viện tài liệu (Reference Library)
- Kéo-thả PDF toàn văn. App đọc tiêu đề, tác giả, abstract, DOI và năm. Bấm **✨ AI-parse** để AI chuẩn hoá metadata.
- Bấm **👁 Đọc** (hoặc bấm vào tiêu đề bài) để **đọc PDF ngay trên web**. Trình đọc dùng sẵn bộ xem PDF của trình duyệt, nên phóng to, tìm chữ và in được. Chuyển bài trước/sau bằng ‹ › hoặc phím ← →; bấm vào khoá trích dẫn để chép.
- Bấm **Edit** để sửa metadata hoặc đặt **BibTeX key** cố định. Bỏ tick **Use** để loại một bài khỏi bài báo.
- **3.1 Generate references.bib** tạo file BibTeX sạch.
- PDF scan (chỉ có ảnh) cần OCR trước, ví dụ bằng `ocrmypdf`.

### 2. Data Chat — dữ liệu thành bảng LaTeX
- Dán hoặc đính kèm log, CSV, kết quả ablation, output SystemC-AMS/MATLAB, hoặc file Excel.
- AI trả về **bảng LaTeX chuẩn booktabs** (in đậm kết quả tốt nhất, ghi mean ± std) kèm nhận xét chỉ dựa trên số liệu.
- Bấm **➕ Add table to paper** để đưa bảng vào bài báo.

### 3. Viết bài (Paper Writer) — từng phần, chuyên sâu
**Chuẩn bị:** mở **Thông tin bài báo** và điền tiêu đề, tác giả (`Tên | Đơn vị | email | Quốc gia`), IEEE/ACM, **nơi dự định nộp** (vd. *IEEE TGRS (Q1)*), đóng góp chính, ghi chú phương pháp và ghi chú kết quả. Nơi nộp giúp phản biện chấm đúng chuẩn.

**Thanh điều khiển** (luôn ghim ở trên cùng khi cuộn) có 2 chế độ:
- **🔬 Chuyên sâu · từng phần** (khuyên dùng): app làm lần lượt từng phần theo vòng *viết → phản biện riêng phần đó → sửa*, rồi mới sang phần tiếp theo. Abstract được viết cuối cùng.
  - **Số vòng:** 1–3 vòng phản biện → sửa cho mỗi phần. Phần đạt điểm ≥ 9/10 sẽ không bị sửa thêm.
  - **Bỏ qua phần đã duyệt:** phần bạn đã bấm ✓ Duyệt sẽ được giữ nguyên.
  - **Dừng sau mỗi phần:** app hỏi bạn trước khi sang phần tiếp theo, để bạn đọc và sửa tay.
  - **Phản biện toàn bài ở cuối:** sau khi ghép main.tex, Agent 3.3 đọc lại cả bài.
- **⚡ Chạy nhanh:** viết mọi phần trong một lượt: 3.1 → 3.2 → Ghép → 3.3 → 3.4 → Ghép.
- Mỗi bước trên thanh tiến trình là một nút: bấm vào để **chỉ chạy bước đó** (vd. chỉ chạy lại 3.3).
- **■ Dừng** ngắt agent ngay lập tức, kể cả khi AI đang viết dở. Các bước đã xong được giữ; bước đang dở bị huỷ, nên nội dung cũ của phần đó vẫn còn nguyên.

**Bảng các phần (bên trái):** mỗi phần có chấm trạng thái (trống · đã viết · đã phản biện · đã sửa · đã duyệt), số từ, điểm phản biện /10 và các nút nhanh ✍ Viết · 🔍 Phản biện · ✎ Sửa · 🔬 Chu trình sâu.

**Khu làm việc (bên phải):**
- **LaTeX:** xem AI viết trực tiếp từng chữ; sửa tay rồi bấm 💾 Lưu.
- **🔍 Phản biện phần:** điểm, các lỗi Nghiêm trọng/Lớn/Nhỏ có trích nguyên văn, nội dung còn thiếu, kiểm tra trích dẫn và gợi ý viết lại.
- **🎯 Brief · định hướng & kết quả** (v3.1, thay cho *Chỉ dẫn cho AI*): mọi phần đều tuỳ chọn, được gửi tới Tác giả (3.2), Biên tập (3.4) và Phản biện mục (3.3 — sẽ báo lỗi nếu bài lệch brief), ưu tiên hơn góp ý phản biện.
  - **🧭 Định hướng & mong muốn:** mục này phải lập luận, nhấn mạnh điều gì. Bấm các gợi ý ＋ để thêm nhanh (vd. *"Kết thúc bằng danh sách 3 đóng góp"*, *"Báo cáo trung bình ± độ lệch chuẩn"*).
  - **📊 Kết quả cần trình bày:** *＋ Chọn kết quả…* từ file bạn đã tải (Thiết kế thí nghiệm), các lần chạy và hình từ Code IDE, bảng LaTeX và ghi chú kết quả của Writer. Mỗi kết quả: **trình bày dạng** (tự động / bảng / hình / số liệu trong câu chữ / phân tích so sánh / kết quả nổi bật), một **ghi chú** (vd. *"làm nổi bật mức +1.2 dB so với QRNN3D"*), và thứ tự ↑↓. Tick *Chỉ trình bày các kết quả đã chọn* để AI không đưa kết quả khác vào. Hình được chèn đúng dòng `\includegraphics{figures/…}` và tự kèm vào bản xem trước PDF, `latex.zip`.
  - **🧱 Cấu trúc:** dàn ý theo thứ tự (mỗi dòng một đoạn hoặc tiểu mục). **✅ Bắt buộc có / ⛔ Phải tránh.** **🎚 Giọng văn & độ dài** (hoặc số từ mục tiêu). **📚 Tài liệu cần nhấn mạnh.**
  - **👁 Xem trước nội dung AI nhận**, **⧉ Sao chép brief sang mục khác**, **✍ Viết theo brief này**. Mục có brief được đánh dấu 🎯 trên bảng các mục.
  - **🧭 Định hướng chung cả bài** (trong *Dự án bài báo*, hoặc nút *Định hướng chung cả bài…*): mạch chính & luận điểm then chốt, văn phong, thuật ngữ & ký hiệu, điều không được khẳng định — áp dụng cho mọi mục.
- **🔬 Viết chuyên sâu:** viết dài và chi tiết hơn khi bấm ✍ Viết hoặc ✎ Sửa riêng lẻ.
- **✓ Duyệt:** đánh dấu phần là bản cuối.

**📄 Xem trước PDF** (ngay dưới khu làm việc):
- Bấm **▶ Biên dịch PDF** để ghép main.tex và biên dịch bằng LaTeX trên máy bạn: pdfLaTeX + BibTeX, latexmk, XeLaTeX hoặc Tectonic. PDF hiện ngay bên dưới; có nút **⤢ Toàn màn hình** và **⬇ main.pdf**.
- **Tự biên dịch:** tự biên dịch lại sau mỗi lần agent viết/sửa xong và mỗi lần bạn bấm Lưu (Ctrl+S).
- **Lỗi LaTeX** được liệt kê theo từng phần. Bấm vào một lỗi để nhảy tới đúng dòng trong trình soạn thảo. App cũng báo tham chiếu/trích dẫn chưa định nghĩa và placeholder còn sót. Xem chi tiết ở **📜 Log**.
- **Bố cục nhanh:** nếu máy chưa có class IEEEtran/acmart, app tự biên dịch bằng class `article`, nên bạn vẫn đọc nhanh được bản thảo.
- **Chưa cài LaTeX?**
  - Windows: `winget install TectonicTypesetting.Tectonic`, hoặc MiKTeX;
  - Ubuntu: `sudo apt install texlive-latex-extra texlive-publishers texlive-bibtex-extra latexmk`;
  - macOS: `brew install tectonic` hoặc MacTeX.

  Nếu chưa cài được, có thể tick *Cho phép biên dịch online*; khi đó bài báo sẽ được gửi tới dịch vụ bên ngoài.

**Tô màu cú pháp LaTeX:** ô soạn thảo tô màu lệnh, môi trường (`\begin{…}`), `\section`, `\cite`/`\ref`/`\label`, công thức `$…$`, comment `%` và placeholder `[TBD]` màu đỏ, kể cả khi AI đang viết. Phím **Tab** chèn 2 dấu cách, **Ctrl+S** để lưu.

**Mẹo:** chạy chế độ Chuyên sâu một lần, đọc phản biện từng phần, viết chỉ dẫn cho các phần yếu, rồi bấm 🔬 Chu trình sâu riêng cho chúng. Dùng **💬 Paper chat** để hỏi *"Câu nào chưa được kết quả chứng minh?"*. Cuối cùng **⬇ Export latex.zip** → Overleaf (*New Project → Upload Project*).

**Bộ bảo vệ tính trung thực:**
- Mọi `\cite{}` không có trong `references.bib` đều bị xoá tự động.
- Chỗ thiếu bằng chứng được đánh dấu đỏ `[CITATION NEEDED]`.
- Chỗ thiếu số liệu được đánh dấu đỏ `[TBD]`.
- **Không nộp bài khi còn placeholder.**

### 4. Phản biện bài báo (bài đã viết sẵn)
Một quy trình riêng để **thử lửa bài báo trước khi nộp**: app đọc toàn văn bản thảo và phản biện như hội đồng của một hội nghị hoặc tạp chí thật, rồi giúp bạn sửa từ lỗi nghiêm trọng đến lỗi chính tả. Mặc định dùng **Claude** làm phản biện (*✳ Ưu tiên Claude*; nếu chưa có key Claude thì dùng hãng mặc định — đổi ở ⚙ Agent engines → 📝 Review).

**1. Bản thảo:** kéo thả **PDF**, **Word (.docx)**, **LaTeX (.tex)** hoặc Markdown. App kiểm tra tự động (không dùng AI):
- số trang, số từ, số hình, bảng và tài liệu tham khảo;
- các mục chuẩn bị thiếu (Abstract, Introduction, Related work, Method, Experiments, Conclusion, References);
- **lỗi lộ danh tính** khi phản biện kín: email, mục Acknowledgment, cụm *"our previous work"*, link GitHub, `\author{}`;
- placeholder còn sót: `??`, TODO, TBD, "Error! Reference source not found".

Nếu có **mã nguồn .tex**, bấm **📎 Đính kèm .tex**: bản sửa sẽ được viết bằng LaTeX và app có thể tự áp dụng vào một bản sao.

**2. Chuẩn nơi nộp:**

| Loại | Tiêu chí | Mức |
|---|---|---|
| 🎤 Hội nghị | Hạng **ICORE / CORE** | C → B → A → A* |
| 🎤 Hội nghị | **Chỉ số h5** (Google Scholar) | <10 · 10–24 · 25–49 · 50–99 · 100+ |
| 📰 Tạp chí | **Phân hạng Q** quốc tế (SJR / JCR) | Q4 → Q3 → Q2 → Q1 |

Mỗi mức có mô tả chuẩn chấm. Ví dụ: A* đòi hỏi đóng góp vượt trội so với SOTA, còn Q1 thường cho Major Revision ở lần nộp đầu. Có thể ghi thêm **tên nơi nộp** (vd. CVPR, IEEE TGRS) và **lĩnh vực / track**.

Chọn **1–3 phản biện:**
- **R1 — chuyên gia lĩnh vực:** tính mới, tầm quan trọng, công trình liên quan.
- **R2 — chuyên gia phương pháp & thí nghiệm:** "Reviewer 2" khó tính, soi toán, baseline, thống kê.
- **R3 — trình bày:** cấu trúc, văn phong, hình/bảng, độ phù hợp với nơi nộp.

**3. ▶ Bắt đầu phản biện:**
1. Từng phản biện viết báo cáo kèm khuyến nghị (Accept … Reject), điểm /10, độ tự tin, bảng điểm theo tiêu chí, câu hỏi cho tác giả, và nhận xét theo trang **(p. N)**.
2. **Area Chair** (hội nghị) hoặc **Biên tập** (tạp chí) cân nhắc các phản biện, ra **quyết định**, và lập **lộ trình sửa theo pha**: Pha 1 nghiêm trọng → Pha 2 lớn → Pha 3 nhỏ → Pha 4 văn phong. Mỗi bước có ước lượng công sức.
3. App gom thành **danh sách lỗi** đã khử trùng lặp, xếp từ **Nghiêm trọng → Lớn → Nhỏ → Chính tả**. Mỗi trích dẫn nguyên văn được **đối chiếu tự động** với bài: ✓ có trong bài, hoặc ⚠ không khớp — cần kiểm tra.

**4. Sửa nhanh (🛠 Lỗi & cách sửa):**
- **✨ Sửa nhanh** một lỗi, **✨ Sửa lỗi nghiêm trọng**, hoặc **✨ Sửa tất cả (nghiêm trọng → chính tả)**.
- Mỗi bản sửa hiển thị **bản gốc ↔ bản sửa** với phần thay đổi được tô màu. Lỗi cần thí nghiệm mới sẽ có thêm **kế hoạch thực hiện** và placeholder `[TBD]`; AI không bao giờ bịa số liệu.
- Với mỗi lỗi, bạn có thể:
  - **✓ Duyệt bản sửa**, **Chép bản sửa**, **Làm lại theo chỉ dẫn…**;
  - **✓ Xong** hoặc **✕ Không sửa** để quản lý tiến độ.
- Nếu đã đính kèm .tex: bấm **⚙ Áp dụng bản sửa đã duyệt vào .tex** để tải về `…_revised.tex`. File gốc không bị thay đổi.

**5. Kết quả:**
- **✉ Thư phản hồi:** soạn thư trả lời từng ý của phản biện. Lỗi chưa sửa có placeholder `[AUTHOR: …]`, nên thư không bao giờ nhận vơ một thay đổi chưa làm.
- **⬇ Báo cáo phản biện đầy đủ (.md):** meta-review, checklist lỗi kèm trạng thái, và toàn bộ báo cáo phản biện.
- **💬 Chat** với Area Chair: *"Phải sửa gì trước để được nhận?"*, *"Soạn phản hồi cho R2"*, *"Bài này hợp với hạng B hơn không?"*.
- **■ Dừng** dùng được ở mọi bước; các bước đã xong được giữ.

> Phản biện mô phỏng giúp bạn tập dượt sát thực tế, nhưng không đảm bảo kết quả thật. Tỉ lệ nhận và tỉ lệ hạng chỉ là con số tham khảo điển hình.

## Tool 4 — Masterclass

Chọn một cột mốc, ví dụ: rebuttal, major revision, viết đề xuất xin tài trợ, bảo vệ luận án, PRISMA. Thêm bối cảnh của bạn (lĩnh vực, giai đoạn, deadline, nhận xét của reviewer) để nhận hướng dẫn có template và checklist.

Trong 💬 chat, có thể nhờ mentor **đóng vai hội đồng hoặc reviewer**. Ví dụ: *"Đóng vai giám khảo và hỏi tôi 5 câu khó"*.

## Chat, đính kèm & ngữ cảnh chia sẻ

**Gửi tin nhắn:**
- **Enter** để gửi, **Shift+Enter** để xuống dòng. Không gửi nhầm khi đang gõ tiếng Việt kiểu Telex.
- Câu trả lời hiện dần từng chữ. Bấm **■** để dừng, phần đã viết vẫn được giữ.
- **↻ Retry** để tạo lại câu trả lời. **✎ Edit** để sửa câu hỏi rồi gửi lại.

**Đính kèm:**
- 📎 **Tệp:** PDF, DOCX, PPTX, XLSX, CSV, LaTeX, code, notebook, **ảnh**. Kéo-thả hoặc dán đều được.
- 🔗 **Link:** trang web, arXiv, DOI, PDF online. Dán một link, app sẽ gợi ý đính kèm luôn.
- 📚 **Paper:** gửi kèm toàn văn bài báo từ thư viện.
- Bấm vào chip đính kèm để xem **chính xác nội dung AI nhận được**.

**Trích dẫn:** `[bib_key]` hiển thị thành thẻ (ví dụ *He et al. 2016*). Bấm vào thẻ để xem chi tiết, mở PDF, mở DOI hoặc đính kèm vào chat.

**🔗 Shared context:**
- Khi bật, AI ở mỗi tool thấy thêm output mới nhất, các tin nhắn gần đây của tool khác, và các ghi chú 📌.
- Ghim **📌 Pin** một câu trả lời, hoặc chỉ đoạn bạn bôi đen, để mọi tool cùng dùng.
- Nút **📌 (số ghi chú)** ở góc trên, cạnh tên dự án, mở cửa sổ **Ngữ cảnh chung** từ bất kỳ tab nào. Trong cửa sổ này:
  - **tìm theo từ khoá**, từ khớp được tô màu;
  - lọc theo tool;
  - bấm vào từng ghim để **mở rộng / thu gọn**, hoặc dùng *Mở rộng tất cả / Thu gọn tất cả*;
  - chép hoặc xoá từng ghi chú.

**Phiên chat:**
- Mỗi tool có danh sách phiên riêng: tạo mới, đổi tên, xoá, xuất Markdown.
- *Auto-open* quyết định có tự mở lại phiên gần nhất khi khởi động hay không.

**Giới hạn mỗi lượt hỏi:** khoảng 150.000 ký tự tài liệu và tối đa 8 ảnh. Tài liệu ở tin nhắn mới nhất được ưu tiên.

## 💻 Code IDE (v3.0)

Tab **Code IDE** là một VS Code thu nhỏ gắn với sandbox Docker và các agent:

- **Thanh hoạt động** bên trái: Explorer (cây file), Tìm trong file, Quản lý mã nguồn (Git/GitHub), Runs (lịch sử chạy), và nút mở tab Docker. Nút ✳ bật/tắt khung agent bên phải. Có thể kéo giãn các khung.
- **Bắt đầu:** bấm *🧪 Bắt đầu từ blueprint* để tạo `src/`, `README.md`, `requirements.txt` từ Tool 2. Hoặc nút *→ 💻 Mở trong Code IDE* ở tab Thiết kế thí nghiệm.
- **Soạn thảo:** Monaco (giống VS Code), nhiều tab, **Ctrl+S** lưu, **Ctrl+Enter** chạy file đang mở. Nếu agent hoặc một lần chạy sửa file mà bạn cũng đang sửa, app hỏi giữ bản nào.
- **Chạy:** ▶ chạy trong sandbox; output hiện trực tiếp ở *Terminal*; dòng log dạng `epoch 3 loss=0.12 psnr=28.4` được vẽ ngay ở *Metric trực tiếp*. Ô lệnh dưới terminal chạy được `pip install …`, `nvidia-smi`, `ls`…
- **Agent lập trình cùng** (khung phải):
  - **💡 Gợi ý:** agent đề xuất thay đổi file; bấm ⇄ để xem diff, ✓ để áp dụng, hoặc *Áp dụng tất cả*.
  - **⚡ Tự động:** agent áp dụng → chạy trong sandbox → đọc stderr → tự sửa, tối đa N lần (*lần thử*). Bạn thấy từng vòng ❌/✅. ■ dừng bất cứ lúc nào.
  - Agent biết: các quyết định đã chốt, mục 📌, bộ nhớ dự án, blueprint Tool 2, cây file và lần chạy gần nhất. Nên đặt agent *Co-coding* ở Ollama/LM Studio (14B coder) hoặc Claude.
- **Runs:** mỗi lần chạy lưu ở `data/runs/<id>/` (log, `metrics.json`, hình trong `figures/`). Mở một run để xem metric, đường cong, hình; **Dùng kết quả trong bài báo** điền ghi chú kết quả và thêm bảng LaTeX bằng **số đo thật** vào Writer (hoặc *⇣ Nhập kết quả từ Code IDE* ở Writer).
- **Quản lý mã nguồn / GitHub:** *Khởi tạo repository* → xem thay đổi, diff → *Commit* → *Push/Pull*. **🚀 Đăng lên GitHub**: nhập tên repo, chọn công khai/riêng tư. Cần **Personal Access Token** (⚙ Cài đặt GitHub): token lưu trong `data/config.json`, chỉ gửi tới GitHub và không bao giờ ghi vào `.git/config`.
- Ghi `metrics.json` (dict số, hoặc list theo epoch) vào thư mục chạy hiện tại hoặc `/runs/<id>/` để app nhận metric chính xác nhất; hình `.png/.svg/.pdf` lưu vào `figures/`.

## 🐳 Docker & Hệ thống (v3.0)

Tab giám sát chi tiết, tự làm mới mỗi 2 giây:

- **5 thẻ trạng thái:** Docker (phiên bản, backend WSL2, số container) · Sandbox (engine, image, container, giới hạn) · GPU (mức dùng, VRAM, nhiệt độ/công suất, driver/CUDA) · Máy (RAM, CPU, ổ đĩa chứa `data/`) · Tài nguyên container (CPU, RAM, tiến trình, I/O) và 4 biểu đồ nhỏ.
- **Container sandbox:** ▶ Khởi động, ■ Dừng, ↻ Khởi động lại, ♻ Tạo lại (áp dụng image/giới hạn mới), ⤓ Tải image (có tiến trình), 🎮 Kiểm tra GPU.
- **Cài đặt sandbox (theo từng dự án):** engine (Tự động / Chỉ Docker / venv cục bộ), image, giới hạn RAM/CPU/bộ nhớ chia sẻ, dùng GPU, mạng (cần cho `pip install`), giới hạn thời gian, số lần tự sửa lỗi.
- **Job:** bảng các lần chạy với trạng thái, thời gian, mã thoát và nút xem log.
- **Cấu hình khuyên dùng:** app quét máy (OS, CPU, RAM, GPU, Docker, WSL2, Git, LaTeX, Ollama/LM Studio) và đề xuất: image PyTorch+CUDA khi GPU dùng được trong Docker, giới hạn RAM/CPU, **kích thước model cục bộ theo VRAM** (12 GB → 14B Q4_K_M, ngữ cảnh 8k), engine cho agent. Bấm *⚡ Áp dụng cấu hình khuyên dùng*.
- **Server MCP:** sandbox được cung cấp cho các app AI khác trên máy (Claude Desktop, VS Code…) qua `http://127.0.0.1:8765/mcp` hoặc `mcp_stdio_bridge.py`.

**Cài đặt trên Windows 11 (Docker Desktop + WSL2 + GPU):**
1. Cài driver NVIDIA mới cho **Windows** (không cài driver Linux trong WSL).
2. PowerShell (Admin): `wsl --install` (hoặc `wsl --update`), khởi động lại máy.
3. Cài Docker Desktop, chọn *Use WSL 2 based engine*; mở Docker Desktop.
4. Trong app: tab Docker → *🎮 Kiểm tra GPU*. Lần đầu sẽ tải image PyTorch+CUDA (≈ 8 GB).
5. Card 12 GB: **⏏ gỡ model Ollama/LM Studio** ở thanh bên trước khi huấn luyện GPU lâu.

## 🧠 Ngữ cảnh & bộ nhớ (v3.0)

- **Đồ thị tri thức:** mọi thứ agent biết về dự án — mục tiêu, giả thuyết, quyết định đã chốt, ràng buộc, tài liệu, giả định trong code, metric, bản tóm tắt. Lọc theo loại, tìm kiếm, *hiện mục đã loại*.
- Bấm một node để **xem / sửa**, **📌 Ghim** (mọi agent *bắt buộc* tuân theo — được chèn vào mọi chat dưới dạng MUST-FOLLOW), **🗑 Loại bỏ** (ẩn khỏi mọi agent; tài liệu bị loại không còn trong danh mục tham khảo; dữ liệu vẫn giữ, khôi phục được), hoặc xoá node tự thêm.
- **Agent quyết định ngữ cảnh:** nói bằng lời, ví dụ *"Bỏ các giả định CNN cũ, tập trung vào giảm FLOPs bằng phân rã tensor"*. Agent đề xuất các thao tác (ghim, loại, thêm ràng buộc…); bạn tick và bấm *✓ Áp dụng mục đã chọn*.
- **Bộ nhớ 3 tầng** (`data/memory/project_state.json`):
  - **Tầng 1 · Bộ nhớ làm việc:** các lượt chat gần đây của mọi tool + log sandbox.
  - **Tầng 2 · Tóm tắt theo giai đoạn:** khi Tầng 1 vượt ngưỡng (mặc định 24.000 token), **agent tóm tắt chạy nền trên model cục bộ** nén các lượt cũ thành bản tóm tắt. Có thể *🗜 Tóm tắt ngay*, giữ (không gộp) hoặc xoá từng bản.
  - **Tầng 3 · Tri thức dài hạn:** mục tiêu, giả thuyết, ràng buộc (tự lấy từ Lit2Plan, sửa tay được), metric tốt nhất từ các lần chạy, tài liệu đã xác thực, quyết định đã chốt.
  - Nhờ vậy agent nhớ cả dự án mà không vượt giới hạn ngữ cảnh của model 14B.

## Tìm kiếm trên internet (v2.6)

Các AI agent có thể **tự tìm paper và thông tin mới trên mạng** trước khi trả lời. Kết quả là dữ liệu thật từ các cơ sở dữ liệu học thuật và công cụ tìm kiếm; AI chỉ đọc và trích dẫn, không tự nghĩ ra nguồn.

**Bật / tắt cho từng chat:** dùng ô chọn **🌐** cạnh khung nhập tin nhắn, có ở mọi tool có chat:
- **🌐 Tìm kiếm: tắt** — như trước, không tìm kiếm.
- **📚 Tìm paper** — OpenAlex, arXiv, Semantic Scholar (miễn phí, không cần key).
- **🌐 Tìm trên web** — DuckDuckGo (miễn phí), hoặc Tavily / Brave nếu bạn có key.
- **🌐📚 Paper + web** — cả hai.

App nhớ lựa chọn riêng cho từng tool.

**Cách hoạt động:** với mỗi câu hỏi,
1. một agent nhỏ lập 1–3 truy vấn tiếng Anh. Nếu bạn hỏi kiểu "mới nhất" hoặc "từ 2023", app tự lọc theo năm;
2. app tìm kiếm, gộp các kết quả trùng (theo DOI) và đánh số **[S1], [S2]…**;
3. AI trả lời và trích dẫn bằng link **[S1](url)**.

Dưới mỗi câu trả lời có danh sách **🌐 nguồn**: tác giả, năm, venue, số trích dẫn. Với mỗi nguồn:
- **📥 Thư viện** tải PDF truy cập mở vào Thư viện tài liệu, kèm metadata chuẩn (tiêu đề, tác giả, DOI).
- **📎** đính kèm toàn văn trang hoặc PDF vào câu hỏi tiếp theo.

**Tool 1 Lit2Plan:** chọn *🌐 Tìm trên internet khi lập kế hoạch*. Kế hoạch sẽ dựa trên paper thật, mới, có thêm mục **9. Key Papers Found Online**, và thẻ **Tài liệu tìm được trên mạng** để lưu PDF.

**Thư viện tài liệu → 🔎 Tìm paper trên mạng:** tìm theo chủ đề (lọc "từ năm"), rồi bấm 📥 để nạp thẳng vào thư viện.

**Cài đặt (thanh bên → 🔎 Tìm kiếm internet):**
- công cụ tìm web và API key (Tavily, Brave);
- số kết quả mỗi lần tìm;
- key Semantic Scholar và e-mail OpenAlex (tuỳ chọn, giúp nhanh và ổn định hơn);
- có đọc nội dung các trang web đầu hay không.

> Chỉ các truy vấn tìm kiếm được gửi đi, không gửi file hay dữ liệu dự án. Paper chỉ có abstract, nên hãy mở bài gốc trước khi trích dẫn chi tiết. Không có mạng thì app báo lỗi và vẫn trả lời bằng thư viện cục bộ.

## Quy trình 6 tháng khuyên dùng

| Giai đoạn | Việc chính trong app | Kết quả |
|---|---|---|
| Tuần 1–2 | Tạo dự án → nạp 20–40 PDF cốt lõi → Lit2Plan → chat đào sâu → ghim quyết định | Hướng nghiên cứu, H1–H3, roadmap |
| Tuần 3–4 | Tool 2 → chạy `experiment_skeleton.py` → chat sửa code theo log | Pipeline thí nghiệm chạy được |
| Tháng 2–4 | Chạy thí nghiệm → Data Chat → thêm bảng vào bài | Bảng kết quả LaTeX |
| Tháng 5 | Viết bài: chế độ 🔬 Chuyên sâu → đọc phản biện từng phần → chỉ dẫn + sửa tay → Paper chat | Bản thảo đầy đủ |
| Tháng 6 | ④ Phản biện bài báo theo chuẩn nơi nộp → sửa nhanh từ nghiêm trọng đến nhỏ → kiểm tra trích dẫn và số liệu → Masterclass (cover letter) → latex.zip → Overleaf | Bài nộp |

## Mẹo đạt chất lượng cao

- **Cho AI dữ liệu thật:** càng nhiều PDF toàn văn, log và số liệu, câu trả lời càng ít chung chung.
- **Viết prompt có ràng buộc:** venue, độ dài, giả thuyết, giới hạn tính toán.
- **Một phiên chat cho một chủ đề:** dùng ＋ New thay vì một phiên dài lẫn lộn nhiều chủ đề.
- **Phản biện chéo:** dùng một model để viết, model khác để phản biện (3.3) hoặc review lại trong Paper chat.
- **Ghim quyết định:** các ràng buộc then chốt (venue, phạm vi, số tham số) nên ở 📌 để tool nào cũng tuân thủ.
- **Luôn kiểm chứng:** mở từng thẻ trích dẫn, so số trong bảng với log gốc, tìm `[TBD]` và `[CITATION NEEDED]`.

## Phím tắt & thao tác nhanh

| Thao tác | Cách làm |
|---|---|
| Gửi / xuống dòng | Enter / Shift+Enter |
| Dừng câu trả lời / agent đang chạy | Bấm ■ (chat) hoặc **■ Dừng** (Viết bài, Phản biện) |
| Đóng cửa sổ, menu | Esc |
| Chọn model | Gõ để lọc, ↑/↓ để di chuyển, Enter để chọn |
| Đính kèm nhanh | Kéo-thả tệp hoặc dán ảnh vào ô chat |
| Đọc toàn màn hình | Nút ⤢ |
| Giao diện sáng/tối | ☀ / 🌙 / 🖥 ở góc trên |
| Ngôn ngữ giao diện | **EN / VI** ở góc trên |

## Dữ liệu, sao lưu & nâng cấp

- **Dữ liệu của bạn nằm ở:** `data/` (cấu hình, API key, Default project), `references/` (PDF của dự án mặc định) và `projects/` (các dự án khác).
- Trong mỗi thư mục data của dự án (v3.0): `workspace/` (bài báo, chat, phiên bản Lit2Plan), `code/` (Code IDE, repo git), `runs/` (log, metric, hình), `sandbox/` (cài đặt, venv), `memory/` (bộ nhớ, đồ thị ngữ cảnh), `results/` (kết quả bạn tải lên). `data/system/` lưu kết quả quét máy. **⬇ project_export.zip** (ở Writer) đóng gói tất cả.
- **Sao lưu:** nén thư mục dự án (data folder) là đủ.
- **Nâng cấp phiên bản:**
  1. Giải nén **toàn bộ** zip mới vào **thư mục mới**.
  2. Chép `data/`, `references/` và `projects/` từ thư mục cũ sang.
  3. **Không** chép đè từng file lẻ. `start.py` sẽ phát hiện nếu thư mục bị trộn phiên bản.
- **Bảo mật:** API key được lưu dạng văn bản trong `data/config.json`, nên giữ thư mục này ở chỗ riêng tư. Mỗi key chỉ được gửi tới đúng hãng của nó. Server chỉ chạy trên `127.0.0.1`, máy khác trong mạng không truy cập được.

## Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Không vào được trang | Giữ cửa sổ đen mở; xem dòng `[ERROR]`; thử `python start.py --check` |
| "Cannot reach LM Studio" | LM Studio → Developer → Start Server; URL phải kết thúc bằng `/v1` |
| Lỗi 401/403 từ hãng AI | Sai key, key hết hạn hoặc chưa bật thanh toán |
| Lỗi 404 "model not found" | Bấm ↻ List và chọn model tài khoản bạn có |
| PDF "no extractable text" | PDF scan → chạy OCR trước |
| Link không đọc được | Trang cần đăng nhập/JS → tải PDF rồi đính kèm |
| Windows chặn DLL (Smart App Control) | App tự chuyển sang pypdf; không cần tắt bảo mật |
| Ubuntu báo "externally-managed-environment" | `start.py` tự tạo `.venv`; nếu thiếu: `sudo apt install python3-venv` |
| Nâng cấp xong nhưng không thấy tab mới | Một bản cũ vẫn đang chạy (cửa sổ đen cũ). Đóng hết cửa sổ cũ, chạy lại `run.bat`; nếu trình duyệt vẫn hiện trang cũ, nhấn **Ctrl+F5**. Từ v3.1 app tự phát hiện và chạy bản mới ở cổng khác |
| Code IDE báo "Docker chưa chạy" | Mở Docker Desktop, chờ biểu tượng cá voi đứng yên; trong lúc đó code chạy bằng venv cục bộ |
| Không dùng được GPU trong Docker | Cập nhật driver NVIDIA (Windows), bật WSL integration trong Docker Desktop, `wsl --update`. App tự chạy lại bằng CPU |
| CUDA out of memory | ⏏ Gỡ model Ollama/LM Studio ở thanh bên trước khi huấn luyện |
| `pip install` trong sandbox lỗi | Bật 🌐 Mạng trong cài đặt sandbox rồi ♻ Tạo lại container |
| Đăng lên GitHub báo 401 | Token thiếu quyền: fine-grained cần *Contents* + *Administration* (read/write), hoặc classic `repo` |
