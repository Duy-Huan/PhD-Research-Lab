# BỘ TIÊU CHUẨN GIAO DIỆN FRONTEND (FRONTEND INTERFACE STANDARDS)

Dưới đây là bộ tiêu chuẩn toàn diện về giao diện Frontend dành cho lập trình web, bao gồm các quy tắc về kỹ thuật, hiệu năng, trải nghiệm người dùng (UX) và khả năng tiếp cận (Accessibility).

---

## 1. Tiêu Chuẩn Cấu Trúc & Mã Nguồn (Code & Semantic Standards)
*   **HTML Ngữ Nghĩa (Semantic HTML):** Sử dụng các thẻ HTML5 đúng mục đích (`<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`) để tối ưu SEO và hỗ trợ các công cụ đọc màn hình (Screen Readers).
*   **Mô-đun Hóa (Modular Components):** Chia nhỏ giao diện thành các thành phần độc lập, có khả năng tái sử dụng cao (ví dụ: *Button, Input, Modal, Card*).
*   **Chuẩn Mã Nguồn (Clean Code):** Tuân thủ quy tắc đặt tên (BEM cho CSS, CamelCase cho JavaScript/TypeScript). Mã nguồn phải sạch, dễ đọc và được định dạng tự động bằng Prettier/ESLint.
*   **Hợp Lệ W3C (W3C Validation):** Đảm bảo mã HTML/CSS không chứa lỗi cú pháp nghiêm trọng khi kiểm tra qua các bộ validator.

## 2. Tiêu Chuẩn Hiển Thị & Tương Thích (Responsive & Cross-Browser)
*   **Thiết Kế Đáp Ứng (Responsive Design):** Áp dụng chiến lược *Mobile-First*. Giao diện phải hiển thị hoàn hảo trên mọi kích thước màn hình phổ biến (Mobile, Tablet, Laptop, Desktop) sử dụng Flexbox, CSS Grid và Media Queries.
*   **Tương Thích Trình Duyệt (Cross-Browser Compatibility):** Đảm bảo website hoạt động ổn định trên các trình duyệt hiện đại bao gồm Chrome, Safari, Firefox và Edge. Sử dụng các kỹ thuật polyfill hoặc autoprefixer nếu cần.
*   **Trạng Thái Giao Diện (UI States):** Thiết kế đầy đủ các trạng thái của thành phần tương tác: *Default, Hover, Focus, Active, Disabled, Loading, và Error*.

## 3. Tiêu Chuẩn Hiệu Năng & Tối Ưu (Performance Standards)
*   **Tối Ưu Tài Nguyên (Asset Optimization):** 
    *   Sử dụng định dạng hình ảnh hiện đại (WebP, AVIF) hoặc vector (SVG).
    *   Áp dụng kỹ thuật tải chậm (*Lazy Loading*) cho hình ảnh và tài nguyên chưa cần thiết ngay.
    *   Nén và tối thiểu hóa (*Minify*) các tệp tin CSS, JS.
*   **Chỉ Số Core Web Vitals:** 
    *   **LCP (Largest Contentful Paint):** Tốc độ tải nội dung chính dưới 2.5 giây.
    *   **INP (Interaction to Next Paint):** Thời gian phản hồi tương tác dưới 200 mili-giây.
    *   **CLS (Cumulative Layout Shift):** Độ ổn định của bố cục trang khi tải dưới 0.1.

## 4. Trải Nghiệm Người Dùng & Khả Năng Tiếp Cận (UX & Accessibility - A11y)
*   **Tính Nhất Quán (Consistency):** Tuân thủ chặt chẽ Hệ thống thiết kế (Design System). Nhất quán về bảng màu (Color Palette), hệ thống font chữ (Typography), khoảng cách (Spacing/Grid System) và hiệu ứng chuyển động (Animation).
*   **Khả Năng Tiếp Cận (WCAG 2.1 AA):**
    *   Đảm bảo độ tương phản màu sắc (Color Contrast) giữa chữ và nền tối thiểu là 4.5:1.
    *   Có thể điều hướng toàn bộ website hoàn toàn bằng bàn phím (phím `Tab`, `Enter`, `Arrow keys`).
    *   Tất cả hình ảnh mang tính nội dung phải có thuộc tính `alt` mô tả chính xác.
*   **Phản Hồi Trực Quan (Visual Feedback):** Luôn hiển thị thông báo rõ ràng khi người dùng thực hiện hành động (ví dụ: gửi biểu mẫu thành công, thông báo lỗi nhập liệu, hoặc thanh tiến trình khi tải dữ liệu).
