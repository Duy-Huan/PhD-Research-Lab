# Hướng dẫn sử dụng PhD Research Lab

PhD Research Lab là phòng thí nghiệm nghiên cứu chạy trên máy của bạn. Nó kết hợp **AI đám mây** (Claude, GPT, Gemini…) cho các việc cần suy luận sâu và viết học thuật, với **AI cục bộ** (LM Studio) cho các việc trích xuất nhanh, riêng tư và miễn phí. Hướng dẫn này đi từ cài đặt, qua từng công cụ, đến quy trình làm việc hiệu quả nhất cho một nghiên cứu sinh.

> **Nguyên tắc vàng:** AI soạn nháp, **bạn** là tác giả. Mọi trích dẫn, con số và kết luận phải được bạn kiểm chứng trước khi nộp bài.

## Bắt đầu nhanh (5 phút)

1. **Chạy app:** Windows chạy `run.bat`; Linux/macOS chạy `./run.sh`. Trình duyệt mở `http://127.0.0.1:8765`.
2. **Nhập API key:** thanh bên → *Cloud AI providers* → bấm hãng (ví dụ Anthropic Claude) → dán key → **↻ List** → chọn model → **Test connection** → **Save configuration**.
3. **(Tuỳ chọn) Bật AI cục bộ:** mở LM Studio → tab *Developer* → tải một model 7–14B → **Start Server**. App sẽ báo "LM Studio online".
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
5. Ghim 📌 những quyết định quan trọng (venue, phạm vi, giả thuyết chính) để Tool 2–4 cùng biết.

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

## Tool 3 — Thư viện, Data Chat & Paper Writer

### 1. Thư viện tài liệu (Reference Library)
- Kéo-thả PDF toàn văn. App đọc tiêu đề, tác giả, abstract, DOI và năm. Bấm **✨ AI-parse** để AI chuẩn hoá metadata.
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
- **📝 Chỉ dẫn cho AI:** ghi yêu cầu riêng cho phần này (vd. *"nhấn mạnh giới hạn 2 W, không quá 1 trang"*). Chỉ dẫn được gửi mỗi lần viết/sửa và được ưu tiên hơn góp ý của phản biện.
- **🔬 Viết chuyên sâu:** viết dài và chi tiết hơn khi bấm ✍ Viết hoặc ✎ Sửa riêng lẻ.
- **✓ Duyệt:** đánh dấu phần là bản cuối.

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

**Phiên chat:**
- Mỗi tool có danh sách phiên riêng: tạo mới, đổi tên, xoá, xuất Markdown.
- *Auto-open* quyết định có tự mở lại phiên gần nhất khi khởi động hay không.

**Giới hạn mỗi lượt hỏi:** khoảng 150.000 ký tự tài liệu và tối đa 8 ảnh. Tài liệu ở tin nhắn mới nhất được ưu tiên.

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
